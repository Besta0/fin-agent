from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any


HISTORY_DIR = Path("outputs/history")


def _history_path(ticker: str) -> Path:
    safe_ticker = "".join(ch for ch in ticker.upper() if ch.isalnum() or ch in {".", "-"})
    return HISTORY_DIR / f"{safe_ticker or 'unknown'}.jsonl"


def load_latest_history(ticker: str) -> dict[str, Any] | None:
    path = _history_path(ticker)
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


def append_history(record: dict[str, Any]) -> str:
    ticker = str(record.get("ticker") or "unknown")
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    path = _history_path(ticker)
    record = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        **record,
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    return str(path)
