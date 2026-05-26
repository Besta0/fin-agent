from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from financial_agent.agents.bear_agent import bear_node
from financial_agent.agents.bull_agent import bull_node
from financial_agent.agents.committee_agent import committee_node
from financial_agent.agents.coordinator import coordinator_node
from financial_agent.agents.fundamental_agent import fundamental_node
from financial_agent.agents.history_agent import history_node
from financial_agent.agents.market_agent import market_node
from financial_agent.agents.news_risk_agent import news_risk_node
from financial_agent.agents.portfolio_agent import portfolio_node
from financial_agent.agents.report_agent import report_node
from financial_agent.agents.review_agent import review_node
from financial_agent.agents.technical_agent import technical_node
from financial_agent.agents.verifier_agent import verifier_node
from financial_agent.graph.state import ResearchState


def build_research_graph():
    workflow = StateGraph(ResearchState)

    workflow.add_node("coordinator", coordinator_node)
    workflow.add_node("market", market_node)
    workflow.add_node("review", review_node)
    workflow.add_node("technical", technical_node)
    workflow.add_node("fundamental", fundamental_node)
    workflow.add_node("news_risk", news_risk_node)
    workflow.add_node("bull", bull_node)
    workflow.add_node("bear", bear_node)
    workflow.add_node("committee", committee_node)
    workflow.add_node("portfolio", portfolio_node)
    workflow.add_node("report", report_node)
    workflow.add_node("verifier", verifier_node)
    workflow.add_node("history", history_node)

    workflow.add_edge(START, "coordinator")
    workflow.add_edge("coordinator", "market")
    workflow.add_edge("market", "review")
    workflow.add_edge("review", "technical")
    workflow.add_edge("technical", "fundamental")
    workflow.add_edge("fundamental", "news_risk")
    workflow.add_edge("news_risk", "bull")
    workflow.add_edge("bull", "bear")
    workflow.add_edge("bear", "committee")
    workflow.add_edge("committee", "portfolio")
    workflow.add_edge("portfolio", "report")
    workflow.add_edge("report", "verifier")
    workflow.add_edge("verifier", "history")
    workflow.add_edge("history", END)

    return workflow.compile()
