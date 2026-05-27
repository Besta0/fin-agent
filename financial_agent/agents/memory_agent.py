from __future__ import annotations

from financial_agent.graph.state import ResearchState
from financial_agent.tools.memory import (
    load_user_preferences,
    search_semantic_memory,
    update_preferences_from_query,
)


async def memory_node(state: ResearchState) -> ResearchState:
    user_id = state.get("user_id")
    query = state.get("user_query", "")
    ticker = state.get("ticker") or ""

    update_result = update_preferences_from_query(user_id, query)
    preferences = update_result.get("preferences") or load_user_preferences(user_id)
    memory_query = f"{query} {ticker}".strip()
    relevant_memories = search_semantic_memory(user_id, memory_query, limit=3)

    memory_context = {
        "user_id": user_id,
        "preferences": preferences,
        "preference_updates": update_result.get("changes", []),
        "relevant_memories": relevant_memories,
    }

    summary_parts = []
    if update_result.get("changes"):
        summary_parts.append(f"updated preferences: {', '.join(update_result['changes'])}")
    summary_parts.append(f"loaded {len(relevant_memories)} relevant semantic memories")

    return {
        "memory_context": memory_context,
        "agent_notes": [
            *state.get("agent_notes", []),
            {
                "agent": "Memory Agent",
                "summary": "; ".join(summary_parts),
            },
        ],
    }
