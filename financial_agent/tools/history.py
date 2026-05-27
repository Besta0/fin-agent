from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from financial_agent.tools.memory import DEFAULT_USER_ID, LEGACY_HISTORY_DIR, user_history_dir


def _history_path(ticker: str, user_id: str | None = None) -> Path:
    safe_ticker = "".join(ch for ch in ticker.upper() if ch.isalnum() or ch in {".", "-"})
    return user_history_dir(user_id) / f"{safe_ticker or 'unknown'}.jsonl"


def _legacy_history_path(ticker: str) -> Path:
    safe_ticker = "".join(ch for ch in ticker.upper() if ch.isalnum() or ch in {".", "-"})
    return LEGACY_HISTORY_DIR / f"{safe_ticker or 'unknown'}.jsonl"


def load_latest_history(ticker: str, user_id: str | None = None) -> dict[str, Any] | None:
    path = _history_path(ticker, user_id)
    if not path.exists() and (user_id is None or user_id == DEFAULT_USER_ID):
        path = _legacy_history_path(ticker)
    if not path.exists():
        return None

    last_line = ""
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            last_line = line.strip()

    if not last_line:
        return None

    try:
        return json.loads(last_line)
    except json.JSONDecodeError:
        return None


def append_history(record: dict[str, Any], user_id: str | None = None) -> str:
    ticker = str(record.get("ticker") or "unknown")
    path = _history_path(ticker, user_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "user_id": user_id or DEFAULT_USER_ID,
        **record,
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    return str(path)
