from __future__ import annotations

from financial_agent.graph.state import ResearchState
from financial_agent.tools.history import append_history
from financial_agent.tools.memory import append_semantic_memory
from financial_agent.tools.vector_memory import append_vector_memory


async def history_node(state: ResearchState) -> ResearchState:
    user_id = state.get("user_id")
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
    history_path = append_history(record, user_id=user_id)
    semantic_record = {
        "ticker": ticker,
        "company_name": record.get("company_name"),
        "title": f"{record.get('company_name') or ticker} 投研报告",
        "rating": record.get("rating"),
        "confidence": record.get("confidence"),
        "report_path": record.get("report_path"),
        "summary": (
            f"{ticker} 本次评级为 {record.get('rating')}，"
            f"置信度 {record.get('confidence')}%，"
            f"观察池角色 {record.get('portfolio_role') or 'N/A'}，"
            f"优先级 {record.get('portfolio_priority') or 'N/A'}。"
        ),
        "text": state.get("final_report", "")[:4000],
        "metadata": {
            "history_path": history_path,
            "portfolio_score": record.get("portfolio_score"),
            "verification_status": record.get("verification_status"),
        },
    }
    semantic_path = append_semantic_memory(user_id, semantic_record)
    vector_path = append_vector_memory(user_id, semantic_record)

    return {
        "history_record": {
            **record,
            "history_path": history_path,
            "semantic_memory_path": semantic_path,
            "vector_memory_path": vector_path,
        },
        "agent_notes": [
            *state.get("agent_notes", []),
            {
                "agent": "History Agent",
                "summary": f"Saved history, JSONL semantic memory, and SQLite vector memory for {ticker}.",
            },
        ],
    }
