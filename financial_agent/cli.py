from __future__ import annotations

import asyncio
import os
import sys

from financial_agent.help import HELP_MESSAGE, is_help_intent
from financial_agent.tools.dashboard import format_dashboard_response, is_dashboard_intent
from financial_agent.tools.memory import (
    DEFAULT_USER_ID,
    format_preferences_response,
    format_semantic_memory_response,
    is_preference_intent,
    is_semantic_memory_intent,
    update_preferences_from_query,
)
from financial_agent.tools.report_browser import (
    format_report_browser_response,
    format_report_list_response,
    is_report_browser_intent,
    is_report_list_intent,
)
from financial_agent.tools.watchlist import (
    format_watchlist_detail_response,
    format_watchlist_response,
    is_watchlist_detail_intent,
    is_watchlist_intent,
    watchlist_limit_from_query,
)


def _cli_user_id() -> str:
    return os.getenv("FIN_AGENT_USER_ID") or DEFAULT_USER_ID


async def main() -> int:
    query = " ".join(sys.argv[1:]).strip()
    user_id = _cli_user_id()
    if not query:
        print('Usage: python -m financial_agent.cli "帮我分析一下 NVDA 未来一个月走势"')
        return 1

    if is_help_intent(query):
        print(HELP_MESSAGE)
        return 0

    if is_dashboard_intent(query):
        print(format_dashboard_response(user_id))
        return 0

    if is_report_list_intent(query):
        print(format_report_list_response(user_id))
        return 0

    if is_report_browser_intent(query):
        print(format_report_browser_response(query, user_id=user_id))
        return 0

    if is_preference_intent(query) and not any(
        keyword in query for keyword in ("分析", "走势", "看看", "研究", "评级")
    ):
        update_preferences_from_query(user_id, query)
        print(format_preferences_response(user_id))
        return 0

    if is_semantic_memory_intent(query):
        print(format_semantic_memory_response(user_id, query))
        return 0

    if is_watchlist_detail_intent(query, user_id=user_id):
        print(format_watchlist_detail_response(query, user_id=user_id))
        return 0

    if is_watchlist_intent(query):
        print(format_watchlist_response(limit=watchlist_limit_from_query(query), user_id=user_id))
        return 0

    from financial_agent.graph.workflow import build_research_graph

    graph = build_research_graph()
    state = await graph.ainvoke(
        {
            "user_id": user_id,
            "user_query": query,
            "agent_notes": [],
            "errors": [],
        }
    )
    print(state.get("direct_response") or state.get("final_report", "No report generated."))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
