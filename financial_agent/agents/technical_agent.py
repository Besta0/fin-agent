from __future__ import annotations

from financial_agent.graph.state import ResearchState
from financial_agent.tools.indicators import calculate_technicals


async def technical_node(state: ResearchState) -> ResearchState:
    market_data = state.get("market_data", {})
    technicals = calculate_technicals(market_data.get("prices", []))

    return {
        "technicals": technicals,
        "agent_notes": [
            *state.get("agent_notes", []),
            {
                "agent": "Technical Agent",
                "summary": (
                    f"Trend={technicals.get('trend_label')}, "
                    f"RSI={technicals.get('rsi_14')}, "
                    f"MACD={technicals.get('macd_signal_label')}."
                ),
            },
        ],
    }
