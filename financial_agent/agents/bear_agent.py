from __future__ import annotations

from financial_agent.graph.state import ResearchState


def _is_number(value) -> bool:
    return isinstance(value, (int, float))


async def bear_node(state: ResearchState) -> ResearchState:
    market_data = state.get("market_data", {})
    technicals = state.get("technicals", {})
    risks = state.get("risks", [])
    returns = market_data.get("returns", {})

    arguments: list[str] = []
    rebuttals: list[str] = []
    confidence = 45

    one_day = returns.get("1d")
    five_day = returns.get("5d")
    one_month = returns.get("1m")
    if _is_number(one_day) and one_day < -3:
        arguments.append(f"近 1 日下跌 {abs(one_day)}%，短线抛压正在上升。")
        confidence += 6
    if _is_number(five_day) and five_day < -5:
        arguments.append(f"近 5 日下跌 {abs(five_day)}%，短期趋势有转弱迹象。")
        confidence += 6
    if _is_number(one_month) and one_month > 20:
        arguments.append(f"近 1 月涨幅达 {one_month}%，获利盘和估值消化压力较高。")
        confidence += 8

    rsi = technicals.get("rsi_14")
    if _is_number(rsi) and rsi >= 70:
        arguments.append(f"RSI 为 {rsi}，进入偏热区间，回撤风险上升。")
        confidence += 6

    macd_label = technicals.get("macd_signal_label", "")
    if "偏空" in macd_label:
        arguments.append("MACD 动能偏空，说明短线买盘力度不足。")
        confidence += 7

    trend = technicals.get("trend_label", "")
    if "偏弱" in trend:
        arguments.append("价格位于中期均线之下，趋势结构偏弱。")
        confidence += 8

    for risk in risks[:2]:
        arguments.append(risk)
        confidence += 2

    if not arguments:
        arguments.append("当前缺少强烈看空信号，Bear Agent 主要提醒潜在回撤和预期风险。")

    if "偏强" in trend:
        rebuttals.append("中期趋势仍偏强，单纯看空需要等待跌破关键均线确认。")
    if _is_number(rsi) and 40 <= rsi <= 65:
        rebuttals.append("RSI 尚未过热，短线调整未必意味着趋势反转。")

    confidence = max(35, min(confidence, 78))
    bear_case = {
        "stance": "看空",
        "confidence": confidence,
        "summary": arguments[0],
        "arguments": arguments[:5],
        "rebuttals": rebuttals[:3],
    }

    return {
        "bear_case": bear_case,
        "agent_notes": [
            *state.get("agent_notes", []),
            {
                "agent": "Bear Agent",
                "summary": f"Built bearish case with confidence={confidence}.",
            },
        ],
    }
