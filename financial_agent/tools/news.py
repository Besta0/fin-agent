from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def _timestamp_to_date(value: Any) -> str | None:
    if not value:
        return None
    try:
        return datetime.fromtimestamp(int(value), tz=timezone.utc).strftime("%Y-%m-%d")
    except Exception:
        return None


def _get_nested_url(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return value.get("url", "")
    return ""


def get_recent_news(ticker: str, limit: int = 6) -> list[dict[str, Any]]:
    if not ticker:
        return []

    try:
        import yfinance as yf
    except ImportError:
        return []

    try:
        raw_items = yf.Ticker(ticker).news or []
    except Exception:
        return []

    items: list[dict[str, Any]] = []
    for raw in raw_items[:limit]:
        content = raw.get("content", raw) if isinstance(raw, dict) else {}
        title = content.get("title") or raw.get("title") if isinstance(raw, dict) else None
        publisher = (
            content.get("provider", {}).get("displayName")
            if isinstance(content.get("provider"), dict)
            else content.get("publisher") or raw.get("publisher", "")
        )
        link = _get_nested_url(content.get("canonicalUrl")) or raw.get("link", "")
        published = content.get("pubDate") or _timestamp_to_date(raw.get("providerPublishTime"))

        if title:
            items.append(
                {
                    "title": title,
                    "publisher": publisher or "Unknown",
                    "published": published,
                    "link": link,
                }
            )

    return items
