from __future__ import annotations

from financial_agent.graph.state import ResearchState


def _is_number(value) -> bool:
    return isinstance(value, (int, float))


async def bull_node(state: ResearchState) -> ResearchState:
    market_data = state.get("market_data", {})
    technicals = state.get("technicals", {})
    fundamentals = state.get("fundamentals", {})
    news = state.get("news", [])
    returns = market_data.get("returns", {})

    arguments: list[str] = []
    weak_points: list[str] = []
    confidence = 45

    one_month = returns.get("1m")
    five_day = returns.get("5d")
    if _is_number(one_month) and one_month > 5:
        arguments.append(f"近 1 月涨幅为 {one_month}%，说明资金仍在确认上行趋势。")
        confidence += 8
    if _is_number(five_day) and five_day > 2:
        arguments.append(f"近 5 日涨幅为 {five_day}%，短期仍有一定动量。")
        confidence += 5

    trend = technicals.get("trend_label", "")
    if "偏强" in trend:
        arguments.append("价格位于中期均线之上，趋势结构仍偏强。")
        confidence += 8

    rsi = technicals.get("rsi_14")
    if _is_number(rsi) and 45 <= rsi <= 68:
        arguments.append(f"RSI 为 {rsi}，处于中性偏强区间，尚未明显过热。")
        confidence += 4

    macd_label = technicals.get("macd_signal_label", "")
    if "偏多" in macd_label:
        arguments.append("MACD 动能偏多，短线趋势仍有延续基础。")
        confidence += 5

    revenue_growth = fundamentals.get("revenue_growth_percent")
    profit_margin = fundamentals.get("profit_margins_percent")
    target_mean = fundamentals.get("target_mean_price")
    last_close = market_data.get("last_close")
    recommendation = (fundamentals.get("recommendation_key") or "").lower()
    if _is_number(revenue_growth) and revenue_growth >= 15:
        arguments.append(f"营收增长为 {revenue_growth}%，基本面增长动能较强。")
        confidence += 6
    if _is_number(profit_margin) and profit_margin >= 15:
        arguments.append(f"净利率为 {profit_margin}%，盈利质量提供估值支撑。")
        confidence += 4
    if _is_number(target_mean) and _is_number(last_close) and target_mean > last_close * 1.1:
        upside = round((target_mean / last_close - 1) * 100, 2)
        arguments.append(f"分析师平均目标价较现价有约 {upside}% 上行空间。")
        confidence += 5
    if recommendation in {"buy", "strong_buy"}:
        arguments.append(f"分析师一致预期为 {recommendation}，市场预期偏正面。")
        confidence += 3

    if news:
        arguments.append("近期仍有新闻和市场讨论度，可能为短线关注度提供支撑。")
        confidence += 3

    if not arguments:
        arguments.append("当前缺少明确看多信号，Bull Agent 仅保留轻度乐观假设。")

    if _is_number(one_month) and one_month > 20:
        weak_points.append("近 1 月涨幅较大，短线继续上行需要新增催化。")
    if "偏空" in macd_label:
        weak_points.append("MACD 动能偏空，可能限制短线反弹持续性。")
    if _is_number(rsi) and rsi >= 70:
        weak_points.append("RSI 进入高位区间，追高性价比下降。")
    forward_pe = fundamentals.get("forward_pe")
    price_to_sales = fundamentals.get("price_to_sales")
    if _is_number(forward_pe) and forward_pe >= 45:
        weak_points.append(f"Forward PE 为 {forward_pe}，估值对增长兑现较敏感。")
    if _is_number(price_to_sales) and price_to_sales >= 15:
        weak_points.append(f"PS 为 {price_to_sales}，收入预期已经较高。")

    confidence = max(35, min(confidence, 78))
    bull_case = {
        "stance": "看多",
        "confidence": confidence,
        "summary": arguments[0],
        "arguments": arguments[:5],
        "weak_points": weak_points[:3],
    }

    return {
        "bull_case": bull_case,
        "agent_notes": [
            *state.get("agent_notes", []),
            {
                "agent": "Bull Agent",
                "summary": f"Built bullish case with confidence={confidence}.",
            },
        ],
    }
