from __future__ import annotations

from financial_agent.graph.state import ResearchState
from financial_agent.tools.history import append_history


async def history_node(state: ResearchState) -> ResearchState:
    ticker = state.get("ticker") or "unknown"
    committee_view = state.get("committee_view", {})
    market_data = state.get("market_data", {})
    portfolio = state.get("portfolio", {})
    verification = state.get("verification", {})

    record = {
        "ticker": ticker,
        "company_name": state.get("company_name") or ticker,
        "horizon": state.get("horizon"),
        "price": market_data.get("last_close"),
        "rating": committee_view.get("rating"),
        "confidence": committee_view.get("confidence"),
        "portfolio_priority": portfolio.get("priority_label"),
        "portfolio_score": portfolio.get("priority_score"),
        "portfolio_role": portfolio.get("portfolio_role"),
        "verification_status": verification.get("status"),
        "report_path": verification.get("report_path"),
    }
    history_path = append_history(record)

    return {
        "history_record": {**record, "history_path": history_path},
        "agent_notes": [
            *state.get("agent_notes", []),
            {
                "agent": "History Agent",
                "summary": f"Saved history record for {ticker} to {history_path}.",
            },
        ],
    }
