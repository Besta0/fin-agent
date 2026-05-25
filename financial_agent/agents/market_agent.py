from __future__ import annotations

from financial_agent.graph.state import ResearchState
from financial_agent.tools.market_data import get_market_snapshot


async def market_node(state: ResearchState) -> ResearchState:
    ticker = state.get("ticker", "")
    if not ticker:
        return {
            "market_data": {"ok": False, "error": "Missing ticker."},
            "agent_notes": [
                *state.get("agent_notes", []),
                {"agent": "Market Agent", "summary": "Skipped because ticker is missing."},
            ],
        }

    market_data = get_market_snapshot(ticker)

    if market_data.get("ok"):
        summary = (
            f"Fetched {ticker} market data. Last close={market_data.get('last_close')}, "
            f"1m return={market_data.get('returns', {}).get('1m')}%."
        )
    else:
        summary = f"Failed to fetch market data for {ticker}: {market_data.get('error')}"

    return {
        "market_data": market_data,
        "agent_notes": [
            *state.get("agent_notes", []),
            {"agent": "Market Agent", "summary": summary},
        ],
    }
