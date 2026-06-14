from __future__ import annotations

import re
from dataclasses import dataclass


ENTRY_ROUTER_PROMPT = """你是 Fin Agent 的入口意图分类器。你的目标是在创建 run 和启动多 Agent 之前，判断用户问题是否属于本项目范围，从源头节省 token 和工具调用。

项目范围：
1. 股票、上市公司、ticker、市场、财报、估值、技术面、新闻风险、多空观点、观察池和中文投研报告。
2. 产品内操作：帮助、投研工作台、Agent 看板、报告列表、打开/导出报告、模型设置、测试连接、观察池、历史记忆和用户偏好。

只输出 JSON：
{
  "route": "research | missing_ticker | product | out_of_scope",
  "should_start_research": true,
  "reason": "一句话说明",
  "response": "如果不启动研究，给用户看的中文回复"
}

分类规则：
- 明确包含公司名或 ticker 且询问走势、估值、财报、风险、评级、看多看空、是否值得跟踪等，route=research。
- 像投研请求但没有明确标的，route=missing_ticker，并要求用户补充公司名或 ticker。
- 帮助、设置、报告、看板、观察池、记忆等产品内问题，route=product，不启动研究。
- 写代码、翻译、天气、旅游、闲聊、学习计划、非金融问答等和项目无关的问题，route=out_of_scope，不启动研究。
- 不要为了回答无关问题而启动任何后续 Agent。
"""


COMPANY_ALIASES = {
    "英伟达": "NVDA",
    "nvidia": "NVDA",
    "苹果": "AAPL",
    "apple": "AAPL",
    "特斯拉": "TSLA",
    "tesla": "TSLA",
    "微软": "MSFT",
    "microsoft": "MSFT",
    "谷歌": "GOOGL",
    "google": "GOOGL",
    "alphabet": "GOOGL",
    "亚马逊": "AMZN",
    "amazon": "AMZN",
    "meta": "META",
    "脸书": "META",
    "amd": "AMD",
    "台积电": "TSM",
    "闪迪": "SNDK",
    "sandisk": "SNDK",
    "san disk": "SNDK",
    "西部数据": "WDC",
    "western digital": "WDC",
    "wdc": "WDC",
}

RESEARCH_KEYWORDS = (
    "股票",
    "股价",
    "看看",
    "怎么样",
    "值得",
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
    "盘中",
    "回撤",
    "ticker",
    "stock",
    "share",
    "price",
    "earnings",
    "valuation",
    "revenue",
    "risk",
)

PRODUCT_KEYWORDS = (
    "帮助",
    "怎么用",
    "你能做什么",
    "能做什么",
    "功能",
    "投研工作台",
    "工作台",
    "dashboard",
    "仪表盘",
    "agent 看板",
    "协作看板",
    "报告列表",
    "打开报告",
    "导出报告",
    "最近报告",
    "模型设置",
    "测试连接",
    "观察池",
    "watchlist",
    "记忆",
    "偏好",
)

MARKET_TOKEN_BLOCKLIST = {"US", "USA", "HK", "HKG"}


@dataclass(frozen=True)
class EntryRoute:
    route: str
    should_start_research: bool
    reason: str
    response: str = ""


def format_missing_ticker_response() -> str:
    return """我理解你想做股票投研分析，但还没有识别出明确的公司或 ticker。

为了避免后面的行情、技术面、基本面、新闻和多空 Agent 跑偏，我不会启动完整投研流程。请补充一个股票代码或公司名。

你可以这样问：

- 帮我分析一下 NVDA 未来一个月走势
- 看看闪迪最近怎么样
- 帮我分析一下特斯拉是偏多还是偏空
- 帮我看一下微软最近的风险点"""


def format_out_of_scope_response() -> str:
    return """这个问题暂时不属于 Fin Agent 的项目范围，所以我不会启动多 Agent 投研流程。

我当前主要处理两类请求：

1. 股票投研：公司名或 ticker 的行情、技术面、基本面、新闻风险、多空观点、观察池和中文报告。
2. 产品操作：投研工作台、Agent 看板、报告列表、报告导出、模型设置、测试连接、观察池和历史记忆。

你可以这样问：

- 帮我分析一下 NVDA 未来一个月走势
- 看看闪迪最近怎么样
- 打开最近报告
- 投研工作台
- 模型设置

如果你想了解完整能力，可以输入：你能做什么。"""


def format_product_scope_response() -> str:
    return """这个问题属于 Fin Agent 的产品内操作，不需要启动完整投研 Agent。

你可以在聊天窗口直接输入对应指令，例如：

- 你能做什么
- 投研工作台
- 报告列表
- 模型设置
- 查看观察池"""


def classify_entry_query(query: str) -> EntryRoute:
    text = query.strip()
    if not text:
        return EntryRoute(
            route="out_of_scope",
            should_start_research=False,
            reason="empty_query",
            response="请输入一个股票投研问题，例如：帮我分析一下 NVDA 未来一个月走势。",
        )

    has_target = has_research_target(text)
    research_like = looks_like_research_query(text) or _is_symbol_only_query(text) or _is_alias_only_query(text)
    if _is_product_scope_query(text) and not (has_target and looks_like_research_query(text)):
        return EntryRoute(
            route="product",
            should_start_research=False,
            reason="product_scope_query",
            response=format_product_scope_response(),
        )

    if research_like and has_target:
        return EntryRoute(
            route="research",
            should_start_research=True,
            reason="research_query_with_target",
        )

    if research_like:
        return EntryRoute(
            route="missing_ticker",
            should_start_research=False,
            reason="research_query_without_target",
            response=format_missing_ticker_response(),
        )

    return EntryRoute(
        route="out_of_scope",
        should_start_research=False,
        reason="outside_fin_agent_scope",
        response=format_out_of_scope_response(),
    )


def looks_like_research_query(query: str) -> bool:
    lowered = query.lower()
    return any(keyword in lowered or keyword in query for keyword in RESEARCH_KEYWORDS)


def has_research_target(query: str) -> bool:
    if _extract_alias(query):
        return True
    return bool(_extract_ticker_token(query))


def _is_product_scope_query(query: str) -> bool:
    lowered = query.lower()
    compact = "".join(lowered.split())
    if "报告" in compact and any(action in compact for action in ("打开", "导出", "查看", "最近", "最新", "列表")):
        return True
    return any(keyword.lower().replace(" ", "") in compact for keyword in PRODUCT_KEYWORDS)


def _extract_alias(query: str) -> str:
    lowered = query.lower()
    for alias, ticker in COMPANY_ALIASES.items():
        if alias in lowered or alias in query:
            return ticker
    return ""


def _extract_ticker_token(query: str) -> str:
    pattern = re.compile(r"(?<![A-Za-z0-9.])([A-Za-z]{1,5}(?:\.[A-Za-z])?)(?![A-Za-z0-9.])")
    for match in pattern.finditer(query):
        ticker = match.group(1).upper()
        next_char = query[match.end() : match.end() + 1]
        if ticker == "A" and next_char == "股":
            continue
        if ticker in MARKET_TOKEN_BLOCKLIST:
            continue
        return ticker
    return ""


def _is_symbol_only_query(query: str) -> bool:
    return bool(re.fullmatch(r"\s*[A-Za-z]{1,5}(?:\.[A-Za-z])?\s*", query))


def _is_alias_only_query(query: str) -> bool:
    lowered = query.strip().lower()
    return any(lowered == alias.lower() for alias in COMPANY_ALIASES)
