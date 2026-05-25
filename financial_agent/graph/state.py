from __future__ import annotations

from typing import Any, TypedDict


class ResearchState(TypedDict, total=False):
    user_query: str
    ticker: str
    company_name: str
    market: str
    horizon: str
    ticker_resolution: dict[str, Any]
    analysis_modules: list[str]
    market_data: dict[str, Any]
    technicals: dict[str, Any]
    news: list[dict[str, Any]]
    risks: list[str]
    bull_case: dict[str, Any]
    bear_case: dict[str, Any]
    committee_view: dict[str, Any]
    agent_notes: list[dict[str, str]]
    final_report: str
    errors: list[str]
