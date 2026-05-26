from __future__ import annotations

from financial_agent.graph.state import ResearchState
from financial_agent.tools.history import load_latest_history


def _is_number(value) -> bool:
    return isinstance(value, (int, float))


def _performance_label(previous_rating: str, return_percent: float | None) -> str:
    if return_percent is None:
        return "无法评估"

    bullish = previous_rating in {"偏多", "中性偏多"}
    bearish = previous_rating in {"偏空", "中性偏空"}

    if bullish and return_percent > 2:
        return "基本兑现"
    if bullish and return_percent < -2:
        return "暂未兑现"
    if bearish and return_percent < -2:
        return "基本兑现"
    if bearish and return_percent > 2:
        return "暂未兑现"
    if previous_rating == "中性" and abs(return_percent) <= 3:
        return "基本兑现"
    return "部分兑现"


async def review_node(state: ResearchState) -> ResearchState:
    ticker = state.get("ticker", "")
    current_price = state.get("market_data", {}).get("last_close")
    previous = load_latest_history(ticker) if ticker else None

    if not previous:
        review = {
            "has_history": False,
            "summary": "暂无历史报告，本次为该标的的首条复盘记录。",
            "reminder": "本次报告会作为后续复盘基准。",
        }
    else:
        previous_price = previous.get("price")
        return_percent = None
        if _is_number(previous_price) and _is_number(current_price) and previous_price != 0:
            return_percent = round((current_price / previous_price - 1) * 100, 2)

        previous_rating = previous.get("rating", "N/A")
        label = _performance_label(previous_rating, return_percent)
        review = {
            "has_history": True,
            "previous_timestamp": previous.get("timestamp"),
            "previous_rating": previous_rating,
            "previous_confidence": previous.get("confidence"),
            "previous_price": previous_price,
            "current_price": current_price,
            "return_percent": return_percent,
            "performance_label": label,
            "previous_report_path": previous.get("report_path"),
            "summary": (
                f"上次评级为 {previous_rating}，上次价格为 {previous_price}，"
                f"当前价格为 {current_price}，期间涨跌幅为 {return_percent}%：{label}。"
            ),
            "reminder": "若上次判断未兑现，本次投委会应更关注反方证据和风险项。",
        }

    return {
        "review": review,
        "agent_notes": [
            *state.get("agent_notes", []),
            {
                "agent": "Review Agent",
                "summary": review.get("summary", "No review summary."),
            },
        ],
    }
