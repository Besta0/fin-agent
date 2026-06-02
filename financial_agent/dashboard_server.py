from __future__ import annotations

import argparse
import asyncio
import json
import mimetypes
import threading
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from financial_agent.graph.workflow import build_research_graph
from financial_agent.tools.memory import safe_user_id, user_reports_dir
from financial_agent.tools.report_browser import (
    _extract_confidence,
    _extract_links,
    _extract_period,
    _extract_quality_status,
    _extract_rating,
    _report_title,
)
from financial_agent.tools.run_dashboard import (
    append_run_event,
    complete_run_record,
    create_run_record,
    fail_run_record,
    list_run_users,
    list_runs,
    load_run,
    run_dashboard_payload,
    summarize_run_update,
)


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DASHBOARD_DIR = PROJECT_ROOT / "dashboard"


class DashboardRequestHandler(BaseHTTPRequestHandler):
    server_version = "FinAgentDashboard/1.0"

    def log_message(self, format: str, *args) -> None:  # noqa: A002
        return

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/"):
            self._handle_api(parsed.path, parse_qs(parsed.query))
            return

        path = parsed.path
        if path in {"", "/"}:
            self._serve_file(DASHBOARD_DIR / "index.html")
            return

        static_path = (DASHBOARD_DIR / path.lstrip("/")).resolve()
        if DASHBOARD_DIR.resolve() not in static_path.parents and static_path != DASHBOARD_DIR.resolve():
            self._send_json({"error": "Invalid path."}, HTTPStatus.BAD_REQUEST)
            return
        self._serve_file(static_path)

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path != "/api/run/start":
            self._send_json({"error": "Unknown API route."}, HTTPStatus.NOT_FOUND)
            return

        body = self._read_json_body()
        if body is None:
            self._send_json({"error": "Invalid JSON body."}, HTTPStatus.BAD_REQUEST)
            return

        query = str(body.get("query") or "").strip()
        user_id = safe_user_id(str(body.get("user_id") or "chainlit"))
        if not query:
            self._send_json({"error": "query is required."}, HTTPStatus.BAD_REQUEST)
            return

        record = create_run_record(user_id, query)
        thread = threading.Thread(
            target=_run_research_in_background,
            args=(user_id, str(record["run_id"]), query),
            daemon=True,
        )
        thread.start()
        self._send_json({"ok": True, "user_id": user_id, "run_id": record["run_id"], "run": record})

    def _handle_api(self, path: str, query: dict[str, list[str]]) -> None:
        user_id = safe_user_id(_first(query, "user_id", "chainlit"))
        run_id = _first(query, "run_id", "")

        if path == "/api/health":
            self._send_json({"ok": True})
            return

        if path == "/api/users":
            self._send_json({"users": list_run_users()})
            return

        if path == "/api/runs":
            self._send_json({"user_id": user_id, "runs": list_runs(user_id)})
            return

        if path == "/api/run":
            self._send_json(run_dashboard_payload(user_id, run_id or None))
            return

        if path == "/api/run/latest":
            self._send_json(run_dashboard_payload(user_id, None))
            return

        if path == "/api/report":
            self._send_json(_report_payload(user_id, run_id or None))
            return

        if path.startswith("/api/run/"):
            requested_run_id = path.removeprefix("/api/run/").strip("/")
            run = load_run(user_id, requested_run_id)
            if not run:
                self._send_json({"error": "Run not found."}, HTTPStatus.NOT_FOUND)
                return
            self._send_json(run_dashboard_payload(user_id, requested_run_id))
            return

        self._send_json({"error": "Unknown API route."}, HTTPStatus.NOT_FOUND)

    def _serve_file(self, path: Path) -> None:
        if not path.exists() or not path.is_file():
            self._send_json({"error": "Not found."}, HTTPStatus.NOT_FOUND)
            return

        content_type = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
        body = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, payload: dict, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _read_json_body(self) -> dict | None:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            return None
        if length <= 0 or length > 64_000:
            return None
        try:
            raw = self.rfile.read(length)
            data = json.loads(raw.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return None
        return data if isinstance(data, dict) else None


def _first(query: dict[str, list[str]], key: str, fallback: str) -> str:
    values = query.get(key)
    if not values:
        return fallback
    return values[0] or fallback


def _report_payload(user_id: str, run_id: str | None) -> dict:
    run = load_run(user_id, run_id)
    if not run:
        return {"ok": False, "status": "missing_run", "message": "没有找到对应 run。"}

    report_path = str(run.get("report_path") or "").strip()
    if not report_path:
        return {"ok": False, "status": "pending", "message": "报告尚未生成。", "run": _report_run_summary(run)}

    path = Path(report_path)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    path = path.resolve()

    reports_root = (PROJECT_ROOT / user_reports_dir(user_id)).resolve()
    if reports_root not in path.parents and path != reports_root:
        return {"ok": False, "status": "forbidden", "message": "报告路径不属于当前用户目录。"}

    if not path.exists() or not path.is_file():
        return {
            "ok": False,
            "status": "missing_report",
            "message": "报告文件不存在。",
            "path": str(path),
            "run": _report_run_summary(run),
        }

    try:
        markdown = path.read_text(encoding="utf-8")
    except OSError as exc:
        return {"ok": False, "status": "read_error", "message": str(exc), "path": str(path), "run": _report_run_summary(run)}

    ticker = run.get("ticker") or (path.stem.split("_", 1)[0] if path.stem else "N/A")
    updated_at = datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds")
    return {
        "ok": True,
        "run": _report_run_summary(run),
        "report": {
            "title": _report_title(markdown, fallback=f"{ticker} 报告"),
            "ticker": ticker,
            "path": str(path),
            "updated_at": updated_at,
            "kind": "质检版" if "_verified_" in path.stem else "初稿",
            "rating": _extract_rating(markdown),
            "confidence": _extract_confidence(markdown),
            "period": _extract_period(markdown),
            "quality_status": _extract_quality_status(markdown),
            "links": _extract_links(markdown, limit=12),
            "markdown": markdown,
        },
    }


def _report_run_summary(run: dict) -> dict:
    return {
        "run_id": run.get("run_id"),
        "status": run.get("status"),
        "ticker": run.get("ticker"),
        "rating": run.get("rating"),
        "confidence": run.get("confidence"),
        "report_path": run.get("report_path"),
    }


def _run_research_in_background(user_id: str, run_id: str, query: str) -> None:
    async def runner() -> None:
        graph = build_research_graph()
        latest_state: dict = {}
        try:
            async for event in graph.astream(
                {
                    "user_id": user_id,
                    "user_query": query,
                    "agent_notes": [],
                    "errors": [],
                },
                stream_mode="updates",
            ):
                for node_name, update in event.items():
                    if not isinstance(update, dict):
                        continue
                    latest_state.update(update)
                    append_run_event(
                        user_id=user_id,
                        run_id=run_id,
                        node_name=node_name,
                        summary=summarize_run_update(node_name, update),
                        update=update,
                    )

            if latest_state.get("direct_response"):
                complete_run_record(user_id, run_id, latest_state, status="stopped")
                return

            if not latest_state.get("final_report"):
                fail_run_record(user_id, run_id, "Final report is missing.")
                return

            complete_run_record(user_id, run_id, latest_state, status="completed")
        except Exception as exc:  # noqa: BLE001
            fail_run_record(user_id, run_id, str(exc))

    asyncio.run(runner())


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the standalone Fin Agent dashboard.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8001)
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), DashboardRequestHandler)
    print(f"Fin Agent dashboard is available at http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping dashboard server.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
