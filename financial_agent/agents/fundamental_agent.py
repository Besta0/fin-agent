from __future__ import annotations

from financial_agent.graph.state import ResearchState
from financial_agent.tools.fundamentals import get_fundamentals


async def fundamental_node(state: ResearchState) -> ResearchState:
    ticker = state.get("ticker", "")
    last_close = state.get("market_data", {}).get("last_close")

    if not ticker:
        return {
            "fundamentals": {"ok": False, "error": "Missing ticker."},
            "agent_notes": [
                *state.get("agent_notes", []),
                {"agent": "Fundamental Agent", "summary": "Skipped because ticker is missing."},
            ],
        }

    fundamentals = get_fundamentals(ticker, last_close=last_close)
    if fundamentals.get("ok"):
        summary = (
            f"Fetched fundamentals for {ticker}. "
            f"PE={fundamentals.get('trailing_pe')}, "
            f"Forward PE={fundamentals.get('forward_pe')}, "
            f"Revenue growth={fundamentals.get('revenue_growth_percent')}%."
        )
    else:
        summary = f"Failed to fetch fundamentals for {ticker}: {fundamentals.get('error')}"

    return {
        "fundamentals": fundamentals,
        "agent_notes": [
            *state.get("agent_notes", []),
            {"agent": "Fundamental Agent", "summary": summary},
        ],
    }
