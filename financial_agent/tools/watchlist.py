from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


WATCHLIST_DIR = Path("outputs/watchlist")
WATCHLIST_PATH = WATCHLIST_DIR / "watchlist.json"
MAX_WATCHLIST_ITEMS = 50
WATCHLIST_KEYWORDS = [
    "查看观察池",
    "我的观察池",
    "观察池",
    "watchlist",
    "跟踪列表",
    "研究池",
    "股票池",
    "优先级最高",
    "哪些股票值得跟踪",
    "有哪些股票值得跟踪",
    "当前跟踪",
    "跟踪池",
]


def _safe_ticker(ticker: str) -> str:
    return "".join(ch for ch in ticker.upper() if ch.isalnum() or ch in {".", "-"}) or "UNKNOWN"


def _empty_watchlist() -> dict[str, Any]:
    return {"updated_at": None, "items": []}


def _display(value: Any, suffix: str = "") -> str:
    if value is None or value == "":
        return "N/A"
    return f"{value}{suffix}"


def _format_percent(value: Any) -> str:
    if isinstance(value, (int, float)):
        return f"{value}%"
    return "N/A"


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


def is_watchlist_intent(text: str) -> bool:
    normalized = text.strip().lower()
    if not normalized:
        return False
    compact = "".join(normalized.split())
    return any(keyword.lower() in compact for keyword in WATCHLIST_KEYWORDS)


def watchlist_limit_from_query(text: str, default: int = 10) -> int:
    match = re.search(r"(?:top|前|最高|前面)\s*(\d{1,2})", text, flags=re.IGNORECASE)
    if not match:
        return default
    return max(1, min(50, int(match.group(1))))


def format_watchlist_response(limit: int = 10) -> str:
    watchlist = load_watchlist()
    items = watchlist.get("items", [])[:limit]
    if not items:
        return """当前观察池还是空的。

你可以先分析一只股票，我会在 Portfolio Agent 阶段自动把它加入观察池。

示例：

- 帮我分析一下 NVDA 未来一个月走势
- 看看闪迪最近怎么样
- 帮我分析一下特斯拉是偏多还是偏空"""

    lines = [
        f"## 当前观察池 Top {len(items)}",
        "",
        f"- 更新时间：**{watchlist.get('updated_at') or 'N/A'}**",
        f"- 本地文件：`{WATCHLIST_PATH}`",
        "",
        "| 排名 | Ticker | 公司 | 优先级 | 分数 | 组合角色 | 评级 | 近1月涨跌幅 | 更新时间 |",
        "|---:|---|---|---|---:|---|---|---:|---|",
    ]

    for idx, item in enumerate(items, start=1):
        returns = item.get("returns") or {}
        lines.append(
            "| "
            f"{idx} | "
            f"{_display(item.get('ticker'))} | "
            f"{_display(item.get('company_name'))} | "
            f"{_display(item.get('priority_label'))} | "
            f"{_display(item.get('priority_score'))} | "
            f"{_display(item.get('portfolio_role'))} | "
            f"{_display(item.get('rating'))} | "
            f"{_format_percent(returns.get('1m'))} | "
            f"{_display(item.get('updated_at'))} |"
        )

    lines.extend(
        [
            "",
            "你可以继续输入某个 ticker 做复盘，例如：`帮我分析一下 NVDA 未来一个月走势`。",
        ]
    )
    return "\n".join(lines)
