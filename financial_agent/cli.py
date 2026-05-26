from __future__ import annotations

import asyncio
import sys

from financial_agent.graph.workflow import build_research_graph
from financial_agent.help import HELP_MESSAGE, is_help_intent


async def main() -> int:
    query = " ".join(sys.argv[1:]).strip()
    if not query:
        print('Usage: python -m financial_agent.cli "帮我分析一下 NVDA 未来一个月走势"')
        return 1

    if is_help_intent(query):
        print(HELP_MESSAGE)
        return 0

    graph = build_research_graph()
    state = await graph.ainvoke(
        {
            "user_query": query,
            "agent_notes": [],
            "errors": [],
        }
    )
    print(state.get("direct_response") or state.get("final_report", "No report generated."))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
