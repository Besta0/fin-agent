from __future__ import annotations

import json
import re

from financial_agent.graph.state import ResearchState
from financial_agent.llm import get_chat_model


COMPANY_ALIASES = {
    "英伟达": ("NVDA", "NVIDIA"),
    "nvidia": ("NVDA", "NVIDIA"),
    "苹果": ("AAPL", "Apple"),
    "apple": ("AAPL", "Apple"),
    "特斯拉": ("TSLA", "Tesla"),
    "tesla": ("TSLA", "Tesla"),
    "微软": ("MSFT", "Microsoft"),
    "microsoft": ("MSFT", "Microsoft"),
    "谷歌": ("GOOGL", "Alphabet"),
    "google": ("GOOGL", "Alphabet"),
    "alphabet": ("GOOGL", "Alphabet"),
    "亚马逊": ("AMZN", "Amazon"),
    "amazon": ("AMZN", "Amazon"),
    "meta": ("META", "Meta Platforms"),
    "脸书": ("META", "Meta Platforms"),
    "amd": ("AMD", "Advanced Micro Devices"),
    "台积电": ("TSM", "Taiwan Semiconductor"),
    "闪迪": ("SNDK", "Sandisk"),
    "sandisk": ("SNDK", "Sandisk"),
    "san disk": ("SNDK", "Sandisk"),
    "西部数据": ("WDC", "Western Digital"),
    "western digital": ("WDC", "Western Digital"),
    "wdc": ("WDC", "Western Digital"),
}


def _extract_ticker(query: str) -> tuple[str, str]:
    lowered = query.lower()
    for alias, (ticker, company_name) in COMPANY_ALIASES.items():
        if alias in lowered or alias in query:
            return ticker, company_name

    matches = re.findall(r"\b[A-Z]{1,5}(?:\.[A-Z])?\b", query.upper())
    if matches:
        ticker = matches[0]
        return ticker, ticker

    return "", ""


def _clean_json(content: str) -> str:
    cleaned = content.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?", "", cleaned, flags=re.IGNORECASE).strip()
        cleaned = re.sub(r"```$", "", cleaned).strip()
    return cleaned


def _valid_ticker(ticker: str) -> bool:
    return bool(re.fullmatch(r"[A-Z]{1,5}(?:\.[A-Z])?", ticker.upper().strip()))


async def _extract_ticker_with_llm(query: str) -> tuple[str, str, float, str]:
    model = get_chat_model(temperature=0)
    if model is None:
        return "", "", 0.0, "llm_not_configured"

    prompt = f"""你是一个股票代码识别助手。

请从用户问题中识别最可能的上市公司股票代码。优先识别美股 ticker；如果用户明确提到 A 股、港股或其他市场，也可以给出对应市场代码。

只输出 JSON，不要添加解释。格式：
{{
  "ticker": "NVDA",
  "company_name": "NVIDIA",
  "market": "US",
  "confidence": 0.95
}}

规则：
1. 如果不能确定，ticker 为空字符串，confidence 小于 0.5。
2. 不要编造不存在或不确定的 ticker。
3. ticker 使用大写。

用户问题：{query}
"""

    try:
        response = await model.ainvoke(prompt)
    except Exception as exc:
        return "", "", 0.0, f"llm_error: {exc}"

    content = getattr(response, "content", "")
    if not isinstance(content, str) or not content.strip():
        return "", "", 0.0, "llm_empty_response"

    try:
        payload = json.loads(_clean_json(content))
    except json.JSONDecodeError:
        return "", "", 0.0, "llm_invalid_json"

    ticker = str(payload.get("ticker", "")).upper().strip()
    company_name = str(payload.get("company_name", "")).strip()
    confidence = float(payload.get("confidence") or 0)

    if confidence < 0.7 or not _valid_ticker(ticker):
        return "", "", confidence, "llm_low_confidence"

    return ticker, company_name or ticker, confidence, "llm_resolved"


def _extract_horizon(query: str) -> str:
    if any(key in query for key in ("今天", "盘中", "日内")):
        return "1 day"
    if any(key in query for key in ("一周", "本周", "7天", "7 天")):
        return "1 week"
    if any(key in query for key in ("一个月", "1个月", "1 个月", "30天", "30 天", "未来一个月")):
        return "1 month"
    if any(key in query for key in ("三个月", "3个月", "季度")):
        return "3 months"
    if any(key in query for key in ("半年", "6个月")):
        return "6 months"
    return "1 month"


async def coordinator_node(state: ResearchState) -> ResearchState:
    query = state.get("user_query", "")
    ticker, company_name = _extract_ticker(query)
    horizon = _extract_horizon(query)
    resolution_method = "rules"
    resolution_confidence = 1.0 if ticker else 0.0

    if not ticker:
        ticker, company_name, resolution_confidence, resolution_method = await _extract_ticker_with_llm(query)

    errors = list(state.get("errors", []))
    if not ticker:
        errors.append(
            "Coordinator Agent 未能可靠识别股票代码，请在问题中加入 ticker，例如 NVDA、AAPL、SNDK。"
        )

    return {
        "ticker": ticker,
        "company_name": company_name,
        "market": "US",
        "horizon": horizon,
        "ticker_resolution": {
            "method": resolution_method,
            "confidence": resolution_confidence,
        },
        "analysis_modules": ["market", "technical", "news_risk", "report"],
        "errors": errors,
        "agent_notes": [
            *state.get("agent_notes", []),
            {
                "agent": "Coordinator Agent",
                "summary": (
                    f"Parsed ticker={ticker or 'N/A'}, horizon={horizon}, "
                    f"method={resolution_method}, confidence={resolution_confidence}."
                ),
            },
        ],
    }
