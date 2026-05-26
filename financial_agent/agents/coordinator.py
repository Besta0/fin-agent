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

RESEARCH_KEYWORDS = (
    "股票",
    "股价",
    "代码",
    "走势",
    "分析",
    "研究",
    "投研",
    "投资",
    "市场",
    "美股",
    "港股",
    "a股",
    "财报",
    "估值",
    "基本面",
    "技术面",
    "新闻",
    "风险",
    "评级",
    "目标价",
    "看多",
    "看空",
    "偏多",
    "偏空",
    "买入",
    "卖出",
    "持仓",
    "观察池",
    "盘中",
    "涨",
    "跌",
    "回撤",
    "ticker",
    "stock",
    "share",
    "price",
    "earnings",
    "valuation",
    "revenue",
    "risk",
    "watchlist",
)
MARKET_TOKEN_BLOCKLIST = {"US", "USA", "HK", "HKG"}


def _extract_alias(query: str) -> tuple[str, str]:
    lowered = query.lower()
    for alias, (ticker, company_name) in COMPANY_ALIASES.items():
        if alias in lowered or alias in query:
            return ticker, company_name
    return "", ""


def _extract_ticker_token(query: str) -> tuple[str, str]:
    pattern = re.compile(
        r"(?<![A-Za-z0-9.])([A-Za-z]{1,5}(?:\.[A-Za-z])?)(?![A-Za-z0-9.])"
    )
    for match in pattern.finditer(query):
        ticker = match.group(1).upper()
        next_char = query[match.end() : match.end() + 1]
        if ticker == "A" and next_char == "股":
            continue
        if ticker in MARKET_TOKEN_BLOCKLIST:
            continue
        return ticker, ticker

    return "", ""


def _is_symbol_only_query(query: str) -> bool:
    return bool(re.fullmatch(r"\s*[A-Za-z]{1,5}(?:\.[A-Za-z])?\s*", query))


def _looks_like_research_query(query: str) -> bool:
    lowered = query.lower()
    return any(keyword in lowered or keyword in query for keyword in RESEARCH_KEYWORDS)


def _missing_ticker_response() -> str:
    return """我理解你想做股票投研分析，但还没有识别出明确的公司或 ticker。

为了避免后面的行情、技术面、基本面 Agent 跑偏，请你补充一个股票代码或公司名。

你可以这样问：

- 帮我分析一下 NVDA 未来一个月走势
- 看看闪迪最近怎么样
- 帮我分析一下特斯拉是偏多还是偏空
- 帮我看一下微软最近的风险点"""


def _non_research_response() -> str:
    return """这个问题看起来不是股票、公司或市场投研请求，所以我不会启动后面的投研 Agent。

我是 Fin Agent，当前主要负责股票投研分析。你可以给我一个公司名或 ticker，我会帮你拉取行情、分析技术面和基本面、整理新闻风险、生成多空观点、更新观察池并输出中文报告。

你可以这样问：

- 帮我分析一下 NVDA 未来一个月走势
- 看看闪迪最近怎么样
- 英伟达现在还值得继续跟踪吗

如果你想了解我的能力，可以输入：你能做什么。"""


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
    alias_ticker, alias_company = _extract_alias(query)
    research_like = _looks_like_research_query(query)

    if alias_ticker:
        ticker, company_name = alias_ticker, alias_company
        research_like = True
    elif research_like or _is_symbol_only_query(query):
        ticker, company_name = _extract_ticker_token(query)
    else:
        ticker, company_name = "", ""

    horizon = _extract_horizon(query)
    resolution_method = "rules"
    resolution_confidence = 1.0 if ticker else 0.0

    if not ticker and research_like:
        ticker, company_name, resolution_confidence, resolution_method = await _extract_ticker_with_llm(query)

    errors = list(state.get("errors", []))
    if not ticker:
        intent = "missing_ticker" if research_like else "non_research"
        direct_response = _missing_ticker_response() if research_like else _non_research_response()
        if research_like:
            errors.append(
                "Coordinator Agent 未能可靠识别股票代码，请在问题中加入 ticker，例如 NVDA、AAPL、SNDK。"
            )
        return {
            "ticker": "",
            "company_name": "",
            "market": "US",
            "horizon": horizon,
            "intent": intent,
            "should_continue": False,
            "direct_response": direct_response,
            "final_report": direct_response,
            "ticker_resolution": {
                "method": resolution_method,
                "confidence": resolution_confidence,
            },
            "analysis_modules": [],
            "errors": errors,
            "agent_notes": [
                *state.get("agent_notes", []),
                {
                    "agent": "Coordinator Agent",
                    "summary": f"Stopped early with intent={intent}, ticker=N/A.",
                },
            ],
        }

    return {
        "ticker": ticker,
        "company_name": company_name,
        "market": "US",
        "horizon": horizon,
        "intent": "research",
        "should_continue": True,
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
