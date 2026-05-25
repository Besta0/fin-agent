from __future__ import annotations

import re

from financial_agent.graph.state import ResearchState


COMPANY_ALIASES = {
    "英伟达": ("NVDA", "NVIDIA"),
    "nvidia": ("NVDA", "NVIDIA"),
    "苹果": ("AAPL", "Apple"),
    "apple": ("AAPL", "Apple"),
    "特斯拉": ("TSLA", "Tesla"),
    "tesla": ("TSLA", "Tesla"),
    "微软": ("MSFT", "Microsoft"),
    "microsoft": ("MSFT", "Microsoft"),
    "谷歌": ("GOOGL", "Alphabet"),
    "google": ("GOOGL", "Alphabet"),
    "alphabet": ("GOOGL", "Alphabet"),
    "亚马逊": ("AMZN", "Amazon"),
    "amazon": ("AMZN", "Amazon"),
    "meta": ("META", "Meta Platforms"),
    "脸书": ("META", "Meta Platforms"),
    "amd": ("AMD", "Advanced Micro Devices"),
    "台积电": ("TSM", "Taiwan Semiconductor"),
}


def _extract_ticker(query: str) -> tuple[str, str]:
    lowered = query.lower()
    for alias, (ticker, company_name) in COMPANY_ALIASES.items():
        if alias in lowered or alias in query:
            return ticker, company_name

    matches = re.findall(r"\b[A-Z]{1,5}(?:\.[A-Z])?\b", query.upper())
    if matches:
        ticker = matches[0]
        return ticker, ticker

    return "", ""


def _extract_horizon(query: str) -> str:
    if any(key in query for key in ("今天", "盘中", "日内")):
        return "1 day"
    if any(key in query for key in ("一周", "本周", "7天", "7 天")):
        return "1 week"
    if any(key in query for key in ("一个月", "1个月", "1 个月", "30天", "30 天", "未来一个月")):
        return "1 month"
    if any(key in query for key in ("三个月", "3个月", "季度")):
        return "3 months"
    if any(key in query for key in ("半年", "6个月")):
        return "6 months"
    return "1 month"


async def coordinator_node(state: ResearchState) -> ResearchState:
    query = state.get("user_query", "")
    ticker, company_name = _extract_ticker(query)
    horizon = _extract_horizon(query)

    errors = list(state.get("errors", []))
    if not ticker:
        errors.append("Coordinator Agent 未能识别股票代码，请在问题中加入美股 ticker，例如 NVDA、AAPL。")

    return {
        "ticker": ticker,
        "company_name": company_name,
        "market": "US",
        "horizon": horizon,
        "analysis_modules": ["market", "technical", "news_risk", "report"],
        "errors": errors,
        "agent_notes": [
            *state.get("agent_notes", []),
            {
                "agent": "Coordinator Agent",
                "summary": f"Parsed ticker={ticker or 'N/A'}, horizon={horizon}.",
            },
        ],
    }
