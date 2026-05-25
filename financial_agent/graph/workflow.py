from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from financial_agent.agents.coordinator import coordinator_node
from financial_agent.agents.market_agent import market_node
from financial_agent.agents.news_risk_agent import news_risk_node
from financial_agent.agents.report_agent import report_node
from financial_agent.agents.technical_agent import technical_node
from financial_agent.graph.state import ResearchState


def build_research_graph():
    workflow = StateGraph(ResearchState)

    workflow.add_node("coordinator", coordinator_node)
    workflow.add_node("market", market_node)
    workflow.add_node("technical", technical_node)
    workflow.add_node("news_risk", news_risk_node)
    workflow.add_node("report", report_node)

    workflow.add_edge(START, "coordinator")
    workflow.add_edge("coordinator", "market")
    workflow.add_edge("market", "technical")
    workflow.add_edge("technical", "news_risk")
    workflow.add_edge("news_risk", "report")
    workflow.add_edge("report", END)

    return workflow.compile()
