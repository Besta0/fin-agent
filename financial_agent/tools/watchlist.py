from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any


WATCHLIST_DIR = Path("outputs/watchlist")
WATCHLIST_PATH = WATCHLIST_DIR / "watchlist.json"
MAX_WATCHLIST_ITEMS = 50


def _safe_ticker(ticker: str) -> str:
    return "".join(ch for ch in ticker.upper() if ch.isalnum() or ch in {".", "-"}) or "UNKNOWN"


def _empty_watchlist() -> dict[str, Any]:
    return {"updated_at": None, "items": []}


def load_watchlist() -> dict[str, Any]:
    if not WATCHLIST_PATH.exists():
        return _empty_watchlist()

    try:
        data = json.loads(WATCHLIST_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return _empty_watchlist()

    if not isinstance(data, dict):
        return _empty_watchlist()

    items = data.get("items")
    if not isinstance(items, list):
        data["items"] = []
    return data


def get_watchlist_item(ticker: str) -> dict[str, Any] | None:
    safe_ticker = _safe_ticker(ticker)
    for item in load_watchlist().get("items", []):
        if _safe_ticker(str(item.get("ticker") or "")) == safe_ticker:
            return item
    return None


def upsert_watchlist_item(record: dict[str, Any]) -> tuple[dict[str, Any], str]:
    WATCHLIST_DIR.mkdir(parents=True, exist_ok=True)

    watchlist = load_watchlist()
    safe_ticker = _safe_ticker(str(record.get("ticker") or "UNKNOWN"))
    existing_items = [
        item
        for item in watchlist.get("items", [])
        if _safe_ticker(str(item.get("ticker") or "")) != safe_ticker
    ]

    item = {
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        **record,
        "ticker": safe_ticker,
    }
    existing_items.append(item)
    existing_items.sort(
        key=lambda value: (
            float(value.get("priority_score") or 0),
            str(value.get("updated_at") or ""),
        ),
        reverse=True,
    )

    watchlist = {
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "items": existing_items[:MAX_WATCHLIST_ITEMS],
    }
    WATCHLIST_PATH.write_text(
        json.dumps(watchlist, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return item, str(WATCHLIST_PATH)


def top_watchlist_items(limit: int = 5) -> list[dict[str, Any]]:
    return load_watchlist().get("items", [])[:limit]
