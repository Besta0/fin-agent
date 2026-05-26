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
WATCHLIST_DETAIL_KEYWORDS = [
    "为什么",
    "原因",
    "理由",
    "详情",
    "详细",
    "跟踪理由",
    "为什么在观察池",
    "观察池详情",
    "核心跟踪",
    "高优先级",
    "常规观察",
    "低优先级",
    "风险警戒",
    "组合角色",
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


def _format_reasons(reasons: list[Any]) -> str:
    if not reasons:
        return "暂无明确跟踪理由。"
    return "\n".join(f"{idx}. {reason}" for idx, reason in enumerate(reasons[:8], start=1))


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


def find_watchlist_item_from_query(text: str) -> dict[str, Any] | None:
    normalized = text.strip().lower()
    if not normalized:
        return None

    safe_query = _safe_ticker(text)
    for item in load_watchlist().get("items", []):
        ticker = str(item.get("ticker") or "")
        company_name = str(item.get("company_name") or "")
        safe_ticker = _safe_ticker(ticker)
        if safe_ticker and safe_ticker in safe_query:
            return item
        if company_name and company_name.lower() in normalized:
            return item

    match = re.search(r"(?<![A-Za-z0-9.])([A-Za-z]{1,5}(?:\.[A-Za-z])?)(?![A-Za-z0-9.])", text)
    if match:
        return get_watchlist_item(match.group(1))
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


def is_watchlist_detail_intent(text: str) -> bool:
    normalized = text.strip().lower()
    if not normalized:
        return False
    compact = "".join(normalized.split())
    if not any(keyword.lower() in compact for keyword in WATCHLIST_DETAIL_KEYWORDS):
        return False
    return find_watchlist_item_from_query(text) is not None


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


def format_watchlist_detail_response(text_or_ticker: str) -> str:
    item = find_watchlist_item_from_query(text_or_ticker) or get_watchlist_item(text_or_ticker)
    if not item:
        return f"""我没有在观察池里找到 `{text_or_ticker}`。

你可以先输入 `查看观察池` 看当前有哪些标的，或者先分析一只股票让 Portfolio Agent 自动加入观察池。"""

    returns = item.get("returns") or {}
    reasons = item.get("watch_reasons") or []
    ticker = item.get("ticker") or "N/A"

    return f"""## {ticker} 观察池详情

- 公司：**{_display(item.get("company_name"))}**
- 优先级：**{_display(item.get("priority_label"))}**
- 分数：**{_display(item.get("priority_score"))}/100**
- 组合角色：**{_display(item.get("portfolio_role"))}**
- 投委会评级：**{_display(item.get("rating"))}**
- 置信度：**{_display(item.get("confidence"))}%**
- 当前价格：**{_display(item.get("price"))}**
- 近 1 日 / 近 5 日 / 近 1 月涨跌幅：**{_format_percent(returns.get("1d"))} / {_format_percent(returns.get("5d"))} / {_format_percent(returns.get("1m"))}**
- 近 3 月 / 近 6 月涨跌幅：**{_format_percent(returns.get("3m"))} / {_format_percent(returns.get("6m"))}**
- 风险数量 / 新闻数量：**{_display(item.get("risk_count"))} / {_display(item.get("news_count"))}**
- 所属行业：**{_display(item.get("sector"))} / {_display(item.get("industry"))}**
- 更新时间：**{_display(item.get("updated_at"))}**

跟踪理由：
{_format_reasons(reasons)}

你可以继续输入：`帮我分析一下 {ticker} 未来一个月走势`，我会重新跑完整投研流程并更新观察池。"""
