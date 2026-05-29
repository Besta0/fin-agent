from __future__ import annotations

from financial_agent.graph.state import ResearchState
from financial_agent.tools.history import load_latest_history
from financial_agent.tools.memory import (
    load_user_preferences,
    search_semantic_memory,
    update_preferences_from_query,
)


REPORT_REFERENCE_THRESHOLD = 0.35

HORIZON_KEYWORDS = (
    "今天",
    "盘中",
    "日内",
    "一周",
    "本周",
    "7天",
    "7 天",
    "一个月",
    "1个月",
    "1 个月",
    "30天",
    "30 天",
    "未来一个月",
    "三个月",
    "3个月",
    "季度",
    "半年",
    "6个月",
    "长期",
    "长线",
)

PREFERENCE_HORIZON_MAP = {
    "短线": "1 week",
    "中线": "3 months",
    "长线": "6 months",
}

FOCUS_KEYWORDS = {
    "估值": "估值压力",
    "pe": "PE/估值",
    "ps": "PS/估值",
    "ai": "AI 需求",
    "人工智能": "AI 需求",
    "芯片": "芯片需求",
    "半导体": "半导体景气度",
    "毛利": "毛利率",
    "利润率": "利润率",
    "营收": "营收增长",
    "财报": "财报与指引",
    "出口": "出口限制",
    "监管": "监管风险",
    "竞争": "竞争格局",
    "均线": "关键均线",
    "rsi": "RSI 动能",
    "回撤": "回撤风险",
}

RISK_KEYWORDS = {
    "估值": "估值压力",
    "回撤": "短线回撤",
    "出口": "出口限制",
    "监管": "监管风险",
    "竞争": "竞争加剧",
    "需求": "需求放缓",
    "毛利": "毛利率压力",
    "客户集中": "客户集中",
    "财报": "财报不确定性",
}


def _query_mentions_horizon(query: str) -> bool:
    normalized = query.lower()
    return any(keyword.lower() in normalized or keyword in query for keyword in HORIZON_KEYWORDS)


def _same_ticker(memory: dict, ticker: str) -> bool:
    return bool(ticker and str(memory.get("ticker") or "").upper() == ticker.upper())


def _dedupe_memories(memories: list[dict]) -> list[dict]:
    seen: set[tuple[str, str, str]] = set()
    deduped: list[dict] = []
    for memory in memories:
        key = (
            str(memory.get("ticker") or ""),
            str(memory.get("timestamp") or ""),
            str(memory.get("report_path") or ""),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(memory)
    return deduped


def _memory_text(memory: dict) -> str:
    return " ".join(
        str(memory.get(key) or "")
        for key in ("ticker", "company_name", "title", "summary", "rating", "text")
    )


def _collect_focus_points(query: str, preferences: dict, memories: list[dict]) -> list[str]:
    text = " ".join([query, *(_memory_text(memory) for memory in memories)]).lower()
    points: list[str] = []

    for sector in preferences.get("sectors") or []:
        if sector not in points:
            points.append(str(sector))

    for keyword, label in FOCUS_KEYWORDS.items():
        if keyword.lower() in text and label not in points:
            points.append(label)

    return points[:6]


def _collect_known_risks(query: str, memories: list[dict]) -> list[str]:
    text = " ".join([query, *(_memory_text(memory) for memory in memories)]).lower()
    risks: list[str] = []
    for keyword, label in RISK_KEYWORDS.items():
        if keyword.lower() in text and label not in risks:
            risks.append(label)
    return risks[:5]


def _memory_guidance(
    ticker: str,
    query: str,
    preferences: dict,
    ticker_memories: list[dict],
    semantic_memories: list[dict],
) -> dict:
    all_memories = _dedupe_memories([*ticker_memories, *semantic_memories])
    primary = ticker_memories[0] if ticker_memories else None
    report_references = [
        memory
        for memory in all_memories
        if float(memory.get("score") or 0) >= REPORT_REFERENCE_THRESHOLD or _same_ticker(memory, ticker)
    ][:3]

    guidance = {
        "focus_points": _collect_focus_points(query, preferences, all_memories),
        "known_risks": _collect_known_risks(query, all_memories),
        "should_compare_with_previous": bool(primary),
        "previous_thesis": primary.get("summary") if primary else "",
        "previous_rating": primary.get("rating") if primary else None,
        "previous_confidence": primary.get("confidence") if primary else None,
        "previous_report_path": primary.get("report_path") if primary else None,
        "previous_timestamp": primary.get("timestamp") if primary else None,
        "reference_count": len(report_references),
        "report_reference_threshold": REPORT_REFERENCE_THRESHOLD,
    }
    return guidance


async def memory_node(state: ResearchState) -> ResearchState:
    user_id = state.get("user_id")
    query = state.get("user_query", "")
    ticker = state.get("ticker") or ""
    company_name = state.get("company_name") or ticker

    update_result = update_preferences_from_query(user_id, query)
    preferences = update_result.get("preferences") or load_user_preferences(user_id)
    memory_query = f"{query} {ticker} {company_name}".strip()
    relevant_memories = _dedupe_memories(search_semantic_memory(user_id, memory_query, limit=6))
    ticker_memories = [memory for memory in relevant_memories if _same_ticker(memory, ticker)]
    semantic_memories = [memory for memory in relevant_memories if not _same_ticker(memory, ticker)]

    latest_history = load_latest_history(ticker, user_id=user_id) if ticker else None
    if latest_history and not ticker_memories:
        ticker_memories.append(
            {
                "ticker": latest_history.get("ticker") or ticker,
                "company_name": company_name,
                "title": f"{company_name} 历史复盘记录",
                "rating": latest_history.get("rating"),
                "confidence": latest_history.get("confidence"),
                "summary": (
                    f"上次评级为 {latest_history.get('rating')}，"
                    f"置信度 {latest_history.get('confidence')}%，"
                    f"观察池优先级 {latest_history.get('portfolio_priority') or 'N/A'}。"
                ),
                "timestamp": latest_history.get("timestamp"),
                "report_path": latest_history.get("report_path"),
                "score": 1.0,
                "source": "jsonl_ticker_history",
            }
        )

    guidance = _memory_guidance(ticker, query, preferences, ticker_memories, semantic_memories)
    report_references = [
        memory
        for memory in _dedupe_memories([*ticker_memories, *semantic_memories])
        if float(memory.get("score") or 0) >= REPORT_REFERENCE_THRESHOLD or _same_ticker(memory, ticker)
    ][:3]

    horizon_override = None
    if not _query_mentions_horizon(query):
        horizon_override = PREFERENCE_HORIZON_MAP.get(str(preferences.get("horizon") or ""))

    memory_context = {
        "user_id": user_id,
        "preferences": preferences,
        "preference_updates": update_result.get("changes", []),
        "relevant_memories": relevant_memories,
        "ticker_history": ticker_memories[:3],
        "semantic_memories": semantic_memories[:3],
        "report_references": report_references,
        "memory_guidance": guidance,
    }

    summary_parts = []
    if update_result.get("changes"):
        summary_parts.append(f"updated preferences: {', '.join(update_result['changes'])}")
    if horizon_override and horizon_override != state.get("horizon"):
        summary_parts.append(f"applied preferred horizon: {horizon_override}")
    summary_parts.append(
        f"loaded {len(ticker_memories)} ticker memories and {len(semantic_memories)} semantic memories"
    )

    result: ResearchState = {
        "memory_context": memory_context,
        "agent_notes": [
            *state.get("agent_notes", []),
            {
                "agent": "Memory Agent",
                "summary": "; ".join(summary_parts),
            },
        ],
    }

    if horizon_override and horizon_override != state.get("horizon"):
        result["horizon"] = horizon_override

    return result
