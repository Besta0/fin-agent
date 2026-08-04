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

from financial_agent.tools.dashboard_settings import (
    payload_to_llm_config,
    save_user_model_settings,
    settings_page_payload,
    user_settings_to_llm_config,
)
from financial_agent.tools.memory import safe_user_id, user_reports_dir
from financial_agent.tools.report_browser import (
    _extract_confidence,
    _extract_links,
    _extract_period,
    _extract_quality_status,
    _extract_rating,
    _report_title,
    export_report_html,
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
from financial_agent.tools.run_preflight import run_preflight_payload, run_preflight_rejection_payload
from financial_agent.tools.watchlist import load_watchlist


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
        if parsed.path not in {"/api/run/start", "/api/run/preflight", "/api/settings/save", "/api/settings/test"}:
            self._send_json({"error": "Unknown API route."}, HTTPStatus.NOT_FOUND)
            return

        body = self._read_json_body()
        if body is None:
            self._send_json({"error": "Invalid JSON body."}, HTTPStatus.BAD_REQUEST)
            return

        if parsed.path == "/api/settings/save":
            user_id = safe_user_id(str(body.get("user_id") or "chainlit"))
            settings = save_user_model_settings(user_id, body)
            self._send_json({"ok": True, "settings": settings})
            return

        if parsed.path == "/api/settings/test":
            user_id = safe_user_id(str(body.get("user_id") or "chainlit"))
            config = payload_to_llm_config(user_id, body)
            result = _run_llm_connection_test(config)
            self._send_json({"ok": bool(result.get("ok")), "result": result})
            return

        query = str(body.get("query") or "").strip()
        user_id = safe_user_id(str(body.get("user_id") or "chainlit"))
        if not query:
            self._send_json({"error": "query is required."}, HTTPStatus.BAD_REQUEST)
            return

        if parsed.path == "/api/run/preflight":
            self._send_json(run_preflight_payload(query, user_id=user_id))
            return

        preflight = run_preflight_payload(query, user_id=user_id)
        if not preflight.get("can_start"):
            self._send_json(run_preflight_rejection_payload(preflight), HTTPStatus.UNPROCESSABLE_ENTITY)
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

        if path == "/api/report/export":
            self._handle_report_export(user_id, run_id or None)
            return

        if path == "/api/compare":
            self._send_json(_compare_payload(user_id, run_id or None))
            return

        if path == "/api/watchlist":
            self._send_json(_watchlist_payload(user_id))
            return

        if path == "/api/settings":
            self._send_json(settings_page_payload(user_id))
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

    def _send_html(self, body: str, status: HTTPStatus = HTTPStatus.OK) -> None:
        encoded = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(encoded)

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

    def _handle_report_export(self, user_id: str, run_id: str | None) -> None:
        run = load_run(user_id, run_id)
        if not run:
            self._send_json({"ok": False, "message": "没有找到对应 run。"}, HTTPStatus.NOT_FOUND)
            return

        query = f"导出 {run.get('ticker') or '最近'} 报告"
        result = export_report_html(query=query, user_id=user_id, report_path=run.get("report_path"))
        if not result.get("ok"):
            self._send_json(result, HTTPStatus.NOT_FOUND)
            return

        path = Path(str(result.get("path") or "")).expanduser()
        try:
            html_text = path.read_text(encoding="utf-8")
        except OSError as exc:
            self._send_json({"ok": False, "message": str(exc), "path": str(path)}, HTTPStatus.INTERNAL_SERVER_ERROR)
            return

        self._send_html(html_text)


def _first(query: dict[str, list[str]], key: str, fallback: str) -> str:
    values = query.get(key)
    if not values:
        return fallback
    return values[0] or fallback


def _run_llm_connection_test(config) -> dict:
    from financial_agent.llm import reset_runtime_llm_config, set_runtime_llm_config
    from financial_agent.tools.settings_panel import test_llm_connection

    async def runner() -> dict:
        token = set_runtime_llm_config(config)
        try:
            return await test_llm_connection(timeout_seconds=20)
        finally:
            reset_runtime_llm_config(token)

    return asyncio.run(runner())


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


def _compare_payload(user_id: str, run_id: str | None) -> dict:
    current = load_run(user_id, run_id)
    if not current:
        return {"ok": False, "status": "missing_run", "message": "没有找到对应 run。"}

    ticker = str(current.get("ticker") or "").upper()
    if not ticker:
        return {"ok": False, "status": "missing_ticker", "message": "当前 run 尚未识别 ticker。"}

    rows = []
    for summary in list_runs(user_id, limit=80):
        if str(summary.get("ticker") or "").upper() != ticker:
            continue
        full_run = load_run(user_id, str(summary.get("run_id") or ""))
        if full_run:
            rows.append(_compare_row(full_run, current_run_id=str(current.get("run_id") or "")))

    rows.sort(key=lambda item: item.get("updated_at") or "", reverse=True)
    current_row = next((row for row in rows if row.get("is_current")), _compare_row(current, current_run_id=str(current.get("run_id") or "")))
    current_index = next((idx for idx, row in enumerate(rows) if row.get("is_current")), -1)
    previous_row = rows[current_index + 1] if current_index >= 0 and current_index + 1 < len(rows) else None
    changes = _compare_changes(current_row, previous_row)

    return {
        "ok": True,
        "user_id": user_id,
        "ticker": ticker,
        "current_run_id": current.get("run_id"),
        "current": current_row,
        "previous": previous_row,
        "changes": changes,
        "runs": rows[:12],
        "message": "找到可对比历史。" if previous_row else "当前标的还没有更早的历史 run。",
    }


def _compare_row(run: dict, current_run_id: str) -> dict:
    events = {event.get("node"): event for event in run.get("events") or []}
    market = (events.get("market") or {}).get("output") or {}
    technical = events.get("technical") or {}
    fundamental = (events.get("fundamental") or {}).get("output") or {}
    bull = events.get("bull") or {}
    bear = events.get("bear") or {}
    committee = (events.get("committee") or {}).get("output") or {}
    returns = market.get("returns") or {}
    return {
        "run_id": run.get("run_id"),
        "is_current": run.get("run_id") == current_run_id,
        "status": run.get("status"),
        "ticker": run.get("ticker"),
        "company_name": run.get("company_name"),
        "horizon": run.get("horizon"),
        "rating": run.get("rating"),
        "confidence": _number_or_none(run.get("confidence")),
        "last_close": _number_or_none(market.get("last_close")),
        "return_1d": _number_or_none(returns.get("1d")),
        "return_1m": _number_or_none(returns.get("1m")),
        "technical_summary": technical.get("summary") or "",
        "bull_summary": bull.get("summary") or "",
        "bear_summary": bear.get("summary") or "",
        "committee_summary": committee.get("rating") or run.get("rating") or "",
        "fundamental_pe": _number_or_none(fundamental.get("trailing_pe")),
        "report_path": run.get("report_path"),
        "user_query": run.get("user_query"),
        "updated_at": run.get("updated_at"),
        "event_count": len(run.get("events") or []),
    }


def _compare_changes(current: dict | None, previous: dict | None) -> dict:
    if not current or not previous:
        return {
            "has_previous": False,
            "summary": "暂无可对比的更早 run。",
            "items": [],
        }

    items = []
    if current.get("rating") != previous.get("rating"):
        items.append(f"结论从 {previous.get('rating') or 'N/A'} 变为 {current.get('rating') or 'N/A'}。")
    else:
        items.append(f"结论维持 {current.get('rating') or 'N/A'}。")

    confidence_delta = _delta(current.get("confidence"), previous.get("confidence"))
    if confidence_delta is not None:
        items.append(f"置信度变化 {confidence_delta:+.0f} 个百分点。")

    close_delta = _delta(current.get("last_close"), previous.get("last_close"))
    close_delta_pct = _pct_delta(current.get("last_close"), previous.get("last_close"))
    if close_delta is not None and close_delta_pct is not None:
        items.append(f"最新收盘价变化 {close_delta:+.2f}（{close_delta_pct:+.2f}%）。")

    return_1m_delta = _delta(current.get("return_1m"), previous.get("return_1m"))
    if return_1m_delta is not None:
        items.append(f"近 1 月涨跌幅变化 {return_1m_delta:+.2f} 个百分点。")

    return {
        "has_previous": True,
        "summary": " ".join(items),
        "items": items,
        "confidence_delta": confidence_delta,
        "last_close_delta": close_delta,
        "last_close_delta_pct": close_delta_pct,
        "return_1m_delta": return_1m_delta,
        "rating_changed": current.get("rating") != previous.get("rating"),
    }


def _number_or_none(value) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _delta(current, previous) -> float | None:
    current_value = _number_or_none(current)
    previous_value = _number_or_none(previous)
    if current_value is None or previous_value is None:
        return None
    return current_value - previous_value


def _pct_delta(current, previous) -> float | None:
    current_value = _number_or_none(current)
    previous_value = _number_or_none(previous)
    if current_value is None or previous_value in {None, 0}:
        return None
    return (current_value - previous_value) / previous_value * 100


def _watchlist_payload(user_id: str) -> dict:
    watchlist = load_watchlist(user_id)
    items = watchlist.get("items") or []
    core_count = sum(1 for item in items if item.get("priority_label") == "核心跟踪")
    high_count = sum(1 for item in items if item.get("priority_label") in {"核心跟踪", "高优先级"})
    risk_count = sum(1 for item in items if item.get("priority_label") == "风险警戒")
    return {
        "ok": True,
        "user_id": user_id,
        "updated_at": watchlist.get("updated_at"),
        "total": len(items),
        "core_count": core_count,
        "high_count": high_count,
        "risk_count": risk_count,
        "items": [_watchlist_item_payload(item) for item in items[:12]],
    }


def _watchlist_item_payload(item: dict) -> dict:
    returns = item.get("returns") or {}
    return {
        "ticker": item.get("ticker"),
        "company_name": item.get("company_name"),
        "market": item.get("market"),
        "sector": item.get("sector"),
        "industry": item.get("industry"),
        "price": _number_or_none(item.get("price")),
        "rating": item.get("rating"),
        "confidence": _number_or_none(item.get("confidence")),
        "priority_score": _number_or_none(item.get("priority_score")),
        "priority_label": item.get("priority_label"),
        "portfolio_role": item.get("portfolio_role"),
        "risk_count": item.get("risk_count"),
        "news_count": item.get("news_count"),
        "return_1d": _number_or_none(returns.get("1d")),
        "return_5d": _number_or_none(returns.get("5d")),
        "return_1m": _number_or_none(returns.get("1m")),
        "watch_reasons": item.get("watch_reasons") or [],
        "updated_at": item.get("updated_at"),
    }


def _run_research_in_background(user_id: str, run_id: str, query: str) -> None:
    async def runner() -> None:
        latest_state: dict = {}
        token = None
        try:
            from financial_agent.graph.workflow import build_research_graph
            from financial_agent.llm import reset_runtime_llm_config, set_runtime_llm_config

            token = set_runtime_llm_config(user_settings_to_llm_config(user_id))
            graph = build_research_graph()
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
        finally:
            if token is not None:
                reset_runtime_llm_config(token)

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
