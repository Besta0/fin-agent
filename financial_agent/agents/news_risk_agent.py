from __future__ import annotations

from financial_agent.graph.state import ResearchState
from financial_agent.tools.news import get_recent_news


def _build_risks(state: ResearchState) -> list[str]:
    risks: list[str] = []
    market_data = state.get("market_data", {})
    technicals = state.get("technicals", {})
    returns = market_data.get("returns", {})

    rsi = technicals.get("rsi_14")
    one_month_return = returns.get("1m")

    if isinstance(rsi, (int, float)) and rsi >= 70:
        risks.append("RSI 处于偏高区间，短线可能存在过热和回撤压力。")
    if isinstance(rsi, (int, float)) and rsi <= 30:
        risks.append("RSI 处于偏低区间，虽然可能有反弹，但也反映当前趋势较弱。")
    if isinstance(one_month_return, (int, float)) and one_month_return >= 20:
        risks.append("近一个月涨幅较大，若缺少新增催化，短期获利盘压力可能上升。")
    if isinstance(one_month_return, (int, float)) and one_month_return <= -15:
        risks.append("近一个月跌幅较大，市场可能正在重新定价基本面或宏观风险。")

    risks.extend(
        [
            "财报指引或盈利增速若不及预期，可能压低估值倍数。",
            "宏观利率、美元流动性和风险偏好变化可能影响成长股估值。",
            "行业竞争、监管限制或供应链扰动可能改变市场预期。",
        ]
    )
    return risks


async def news_risk_node(state: ResearchState) -> ResearchState:
    ticker = state.get("ticker", "")
    news = get_recent_news(ticker) if ticker else []
    risks = _build_risks(state)

    return {
        "news": news,
        "risks": risks,
        "agent_notes": [
            *state.get("agent_notes", []),
            {
                "agent": "News & Risk Agent",
                "summary": f"Collected {len(news)} news items and {len(risks)} risk factors.",
            },
        ],
    }
