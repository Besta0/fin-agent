from __future__ import annotations

from financial_agent.graph.state import ResearchState


def _is_number(value) -> bool:
    return isinstance(value, (int, float))


async def bear_node(state: ResearchState) -> ResearchState:
    market_data = state.get("market_data", {})
    technicals = state.get("technicals", {})
    fundamentals = state.get("fundamentals", {})
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

    trailing_pe = fundamentals.get("trailing_pe")
    forward_pe = fundamentals.get("forward_pe")
    price_to_sales = fundamentals.get("price_to_sales")
    revenue_growth = fundamentals.get("revenue_growth_percent")
    profit_margin = fundamentals.get("profit_margins_percent")
    target_mean = fundamentals.get("target_mean_price")
    last_close = market_data.get("last_close")
    recommendation = (fundamentals.get("recommendation_key") or "").lower()
    if _is_number(trailing_pe) and trailing_pe >= 60:
        arguments.append(f"Trailing PE 为 {trailing_pe}，估值对盈利预期较敏感。")
        confidence += 6
    if _is_number(forward_pe) and forward_pe >= 45:
        arguments.append(f"Forward PE 为 {forward_pe}，未来增长若放缓可能引发估值压缩。")
        confidence += 6
    if _is_number(price_to_sales) and price_to_sales >= 15:
        arguments.append(f"PS 为 {price_to_sales}，收入端预期已经较高。")
        confidence += 5
    if _is_number(revenue_growth) and revenue_growth < 0:
        arguments.append(f"营收增长为 {revenue_growth}%，基本面增长承压。")
        confidence += 6
    if _is_number(profit_margin) and profit_margin < 0:
        arguments.append(f"净利率为 {profit_margin}%，盈利质量偏弱。")
        confidence += 5
    if _is_number(target_mean) and _is_number(last_close) and target_mean < last_close:
        downside = round((1 - target_mean / last_close) * 100, 2)
        arguments.append(f"分析师平均目标价低于现价约 {downside}%，上行空间受限。")
        confidence += 5
    if recommendation in {"sell", "strong_sell", "underperform"}:
        arguments.append(f"分析师一致预期为 {recommendation}，市场预期偏谨慎。")
        confidence += 4

    for risk in risks[:2]:
        arguments.append(risk)
        confidence += 2

    if not arguments:
        arguments.append("当前缺少强烈看空信号，Bear Agent 主要提醒潜在回撤和预期风险。")

    if "偏强" in trend:
        rebuttals.append("中期趋势仍偏强，单纯看空需要等待跌破关键均线确认。")
    if _is_number(rsi) and 40 <= rsi <= 65:
        rebuttals.append("RSI 尚未过热，短线调整未必意味着趋势反转。")
    if _is_number(revenue_growth) and revenue_growth >= 15:
        rebuttals.append("营收增长仍然较强，估值压力需要结合增长质量判断。")
    if _is_number(profit_margin) and profit_margin >= 15:
        rebuttals.append("净利率水平较好，盈利质量可能缓冲估值回调压力。")

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
