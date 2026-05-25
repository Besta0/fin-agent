from __future__ import annotations

from financial_agent.graph.state import ResearchState


def _rating_from_balance(balance: int) -> str:
    if balance >= 14:
        return "偏多"
    if balance >= 5:
        return "中性偏多"
    if balance <= -14:
        return "偏空"
    if balance <= -5:
        return "中性偏空"
    return "中性"


async def committee_node(state: ResearchState) -> ResearchState:
    bull_case = state.get("bull_case", {})
    bear_case = state.get("bear_case", {})
    bull_confidence = int(bull_case.get("confidence") or 45)
    bear_confidence = int(bear_case.get("confidence") or 45)
    balance = bull_confidence - bear_confidence
    rating = _rating_from_balance(balance)
    confidence = max(52, min(78, 56 + abs(balance)))

    bull_arguments = bull_case.get("arguments", [])
    bear_arguments = bear_case.get("arguments", [])
    key_reasons: list[str] = []
    if bull_arguments:
        key_reasons.append(f"看多侧：{bull_arguments[0]}")
    if bear_arguments:
        key_reasons.append(f"看空侧：{bear_arguments[0]}")
    if not key_reasons:
        key_reasons.append("多空证据都不充分，维持中性判断。")

    uncertainty = "需要继续观察价格是否站稳关键均线、成交量是否配合，以及新闻催化是否持续。"
    if rating in {"偏多", "中性偏多"} and bear_confidence >= 60:
        uncertainty = "虽然结论偏多，但看空侧风险不弱，需要防范短线回撤。"
    elif rating in {"偏空", "中性偏空"} and bull_confidence >= 60:
        uncertainty = "虽然结论偏空，但看多侧趋势仍有支撑，需要等待跌破关键位置确认。"

    committee_view = {
        "rating": rating,
        "confidence": confidence,
        "bull_confidence": bull_confidence,
        "bear_confidence": bear_confidence,
        "balance": balance,
        "key_reasons": key_reasons,
        "uncertainty": uncertainty,
    }

    return {
        "committee_view": committee_view,
        "agent_notes": [
            *state.get("agent_notes", []),
            {
                "agent": "Committee Agent",
                "summary": (
                    f"Committee rating={rating}, confidence={confidence}, balance={balance}."
                ),
            },
        ],
    }
