from __future__ import annotations

from typing import Any

from financial_agent.graph.state import ResearchState
from financial_agent.tools.watchlist import load_watchlist, top_watchlist_items, upsert_watchlist_item


BULLISH_RATINGS = {"偏多", "中性偏多"}
BEARISH_RATINGS = {"偏空", "中性偏空"}


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float))


def _rating_signal(rating: str) -> int:
    if rating == "偏多":
        return 22
    if rating == "中性偏多":
        return 14
    if rating == "中性":
        return 6
    if rating == "中性偏空":
        return 14
    if rating == "偏空":
        return 22
    return 5


def _priority_label(score: int, rating: str) -> str:
    if rating in BEARISH_RATINGS and score >= 60:
        return "风险警戒"
    if score >= 72:
        return "核心跟踪"
    if score >= 56:
        return "高优先级"
    if score >= 40:
        return "常规观察"
    return "低优先级"


def _portfolio_role(rating: str, confidence: int, risk_count: int) -> str:
    if rating in BULLISH_RATINGS and confidence >= 65:
        return "进攻观察"
    if rating in BEARISH_RATINGS and (confidence >= 65 or risk_count >= 4):
        return "风险警戒"
    if rating == "中性":
        return "中性跟踪"
    if rating in BULLISH_RATINGS:
        return "趋势跟踪"
    if rating in BEARISH_RATINGS:
        return "防守观察"
    return "待确认"


def _same_sector_items(items: list[dict[str, Any]], ticker: str, sector: str | None) -> list[dict[str, Any]]:
    if not sector:
        return []
    return [
        item
        for item in items
        if item.get("sector") == sector and str(item.get("ticker") or "").upper() != ticker.upper()
    ]


def _build_watch_reasons(
    rating: str,
    confidence: int,
    market_data: dict[str, Any],
    review: dict[str, Any],
    risk_count: int,
    same_sector_count: int,
) -> list[str]:
    returns = market_data.get("returns", {})
    reasons: list[str] = []

    if rating in BULLISH_RATINGS:
        reasons.append(f"投委会评级为 {rating}，适合继续跟踪多头证据是否延续。")
    elif rating in BEARISH_RATINGS:
        reasons.append(f"投委会评级为 {rating}，需要观察风险是否继续扩散。")
    else:
        reasons.append("投委会结论偏中性，适合等待新的催化或趋势确认。")

    if confidence >= 68:
        reasons.append(f"本次结论置信度达到 {confidence}%，值得提高复盘优先级。")

    one_month = returns.get("1m")
    if _is_number(one_month) and abs(one_month) >= 8:
        reasons.append(f"近 1 月涨跌幅为 {one_month}%，波动已经足够影响组合排序。")

    if review.get("has_history") and _is_number(review.get("return_percent")):
        reasons.append(f"相对上次复盘涨跌幅为 {review.get('return_percent')}%，需要纳入跟踪。")
    elif not review.get("has_history"):
        reasons.append("这是该标的首条记录，后续可用作复盘基准。")

    if risk_count >= 4:
        reasons.append(f"风险清单包含 {risk_count} 项，需要持续观察。")

    if same_sector_count:
        reasons.append(f"观察池已有 {same_sector_count} 个同板块标的，注意赛道集中度。")

    return reasons[:5]


def _priority_score(
    rating: str,
    confidence: int,
    market_data: dict[str, Any],
    review: dict[str, Any],
    risk_count: int,
    news_count: int,
    same_sector_count: int,
) -> int:
    returns = market_data.get("returns", {})
    score = 18 + _rating_signal(rating) + max(0, confidence - 50) // 2

    one_day = returns.get("1d")
    one_month = returns.get("1m")
    if _is_number(one_day):
        score += min(8, int(abs(one_day)))
    if _is_number(one_month):
        score += min(16, int(abs(one_month)))

    if review.get("has_history") and _is_number(review.get("return_percent")):
        score += min(10, int(abs(review.get("return_percent"))))
    elif not review.get("has_history"):
        score += 4

    score += min(10, risk_count * 2)
    score += min(6, news_count)
    score += min(6, same_sector_count * 2)
    return max(0, min(100, score))


async def portfolio_node(state: ResearchState) -> ResearchState:
    user_id = state.get("user_id")
    ticker = state.get("ticker") or ""
    if not ticker:
        portfolio = {
            "ok": False,
            "error": "Missing ticker.",
            "summary": "缺少 ticker，无法更新观察池。",
        }
        return {
            "portfolio": portfolio,
            "agent_notes": [
                *state.get("agent_notes", []),
                {"agent": "Portfolio Agent", "summary": portfolio["summary"]},
            ],
        }

    watchlist = load_watchlist(user_id)
    existing_items = watchlist.get("items", [])
    fundamentals = state.get("fundamentals", {})
    market_data = state.get("market_data", {})
    committee_view = state.get("committee_view", {})
    review = state.get("review", {})
    risks = state.get("risks", [])
    news = state.get("news", [])

    sector = fundamentals.get("sector")
    same_sector = _same_sector_items(existing_items, ticker, sector)
    rating = committee_view.get("rating") or "中性"
    confidence = int(committee_view.get("confidence") or 50)
    risk_count = len(risks)
    news_count = len(news)
    score = _priority_score(
        rating,
        confidence,
        market_data,
        review,
        risk_count,
        news_count,
        len(same_sector),
    )
    priority_label = _priority_label(score, rating)
    role = _portfolio_role(rating, confidence, risk_count)
    watch_reasons = _build_watch_reasons(
        rating,
        confidence,
        market_data,
        review,
        risk_count,
        len(same_sector),
    )

    record = {
        "ticker": ticker,
        "company_name": state.get("company_name") or ticker,
        "market": state.get("market"),
        "horizon": state.get("horizon"),
        "sector": sector,
        "industry": fundamentals.get("industry"),
        "price": market_data.get("last_close"),
        "returns": market_data.get("returns", {}),
        "rating": rating,
        "confidence": confidence,
        "priority_score": score,
        "priority_label": priority_label,
        "portfolio_role": role,
        "risk_count": risk_count,
        "news_count": news_count,
        "watch_reasons": watch_reasons,
    }
    item, watchlist_path = upsert_watchlist_item(record, user_id=user_id)
    top_items = top_watchlist_items(limit=5, user_id=user_id)

    portfolio = {
        "ok": True,
        "user_id": user_id,
        "watchlist_path": watchlist_path,
        "watchlist_size": len(load_watchlist(user_id).get("items", [])),
        "status": "updated",
        "current_item": item,
        "priority_score": score,
        "priority_label": priority_label,
        "portfolio_role": role,
        "same_sector_count": len(same_sector),
        "same_sector_tickers": [item.get("ticker") for item in same_sector[:5]],
        "top_items": top_items,
        "summary": f"{ticker} 已加入/更新观察池，优先级为 {priority_label}（{score}/100），组合角色为 {role}。",
    }

    return {
        "portfolio": portfolio,
        "agent_notes": [
            *state.get("agent_notes", []),
            {
                "agent": "Portfolio Agent",
                "summary": portfolio["summary"],
            },
        ],
    }
