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


def _rating_change(previous: str | None, current: str) -> str:
    if not previous:
        return "无历史评级可对比"
    if previous == current:
        return f"评级维持 {current}"
    return f"评级由 {previous} 调整为 {current}"


def _memory_influence(state: ResearchState, current_rating: str) -> dict:
    memory_context = state.get("memory_context", {})
    guidance = memory_context.get("memory_guidance", {})
    report_references = memory_context.get("report_references", [])
    previous_rating = guidance.get("previous_rating")
    previous_thesis = guidance.get("previous_thesis") or ""

    if not report_references and not previous_thesis:
        return {
            "used": False,
            "summary": "未找到足够相关的历史记忆，本次投委会主要基于当前数据和多空观点。",
            "rating_change": "无历史评级可对比",
            "focus_points": guidance.get("focus_points", []),
            "known_risks": guidance.get("known_risks", []),
            "reference_count": 0,
        }

    rating_change = _rating_change(previous_rating, current_rating)
    focus_points = guidance.get("focus_points", [])
    known_risks = guidance.get("known_risks", [])
    summary_parts = [rating_change]
    if previous_thesis:
        summary_parts.append(f"历史 thesis：{previous_thesis}")
    if focus_points:
        summary_parts.append(f"本次重点复核：{', '.join(focus_points[:4])}")
    if known_risks:
        summary_parts.append(f"延续关注风险：{', '.join(known_risks[:4])}")

    return {
        "used": True,
        "summary": "；".join(summary_parts),
        "rating_change": rating_change,
        "previous_rating": previous_rating,
        "previous_confidence": guidance.get("previous_confidence"),
        "previous_report_path": guidance.get("previous_report_path"),
        "previous_timestamp": guidance.get("previous_timestamp"),
        "previous_thesis": previous_thesis,
        "focus_points": focus_points,
        "known_risks": known_risks,
        "reference_count": guidance.get("reference_count", len(report_references)),
    }


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

    memory_influence = _memory_influence(state, rating)
    if memory_influence.get("used"):
        key_reasons.append(f"历史记忆对比：{memory_influence.get('rating_change')}")

    uncertainty = "需要继续观察价格是否站稳关键均线、成交量是否配合，以及新闻催化是否持续。"
    if rating in {"偏多", "中性偏多"} and bear_confidence >= 60:
        uncertainty = "虽然结论偏多，但看空侧风险不弱，需要防范短线回撤。"
    elif rating in {"偏空", "中性偏空"} and bull_confidence >= 60:
        uncertainty = "虽然结论偏空，但看多侧趋势仍有支撑，需要等待跌破关键位置确认。"
    elif memory_influence.get("known_risks"):
        risks = "、".join(memory_influence["known_risks"][:3])
        uncertainty = f"历史记忆提示仍需跟踪 {risks}，本次结论需以后续数据验证。"

    committee_view = {
        "rating": rating,
        "confidence": confidence,
        "bull_confidence": bull_confidence,
        "bear_confidence": bear_confidence,
        "balance": balance,
        "key_reasons": key_reasons,
        "uncertainty": uncertainty,
        "memory_influence": memory_influence,
    }

    return {
        "committee_view": committee_view,
        "agent_notes": [
            *state.get("agent_notes", []),
            {
                "agent": "Committee Agent",
                "summary": (
                    f"Committee rating={rating}, confidence={confidence}, balance={balance}; "
                    f"memory={memory_influence.get('rating_change')}."
                ),
            },
        ],
    }
