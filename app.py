from __future__ import annotations

import chainlit as cl
from chainlit.input_widget import Select, Slider, TextInput

from financial_agent.entry_router import classify_entry_query
from financial_agent.graph.workflow import build_research_graph
from financial_agent.help import HELP_MESSAGE, is_help_intent
from financial_agent.llm import (
    LLMConfig,
    reset_runtime_llm_config,
    set_runtime_llm_config,
)
from financial_agent.tools.charting import build_price_chart
from financial_agent.tools.dashboard import format_dashboard_response, is_dashboard_intent
from financial_agent.tools.memory import (
    format_preferences_response,
    format_semantic_memory_response,
    is_preference_intent,
    is_semantic_memory_intent,
    load_semantic_memories,
    safe_user_id,
    update_preferences_from_query,
)
from financial_agent.tools.report_browser import (
    format_report_export_response,
    format_report_browser_response,
    format_report_list_response,
    is_report_export_intent,
    is_report_browser_intent,
    is_report_list_intent,
    list_reports,
    resolve_report_ticker,
)
from financial_agent.tools.run_dashboard import (
    append_run_event,
    complete_run_record,
    create_run_record,
    fail_run_record,
    format_debate_dashboard_response,
    format_live_run_board,
    format_run_dashboard_response,
    is_debate_dashboard_intent,
    is_run_dashboard_intent,
)
from financial_agent.tools.settings_panel import (
    format_settings_response,
    is_connection_test_intent,
    is_settings_intent,
)
from financial_agent.settings import PROVIDER_DEFAULTS
from financial_agent.tools.vector_memory import count_vector_memories
from financial_agent.tools.watchlist import (
    format_watchlist_detail_response,
    format_watchlist_response,
    is_watchlist_detail_intent,
    is_watchlist_intent,
    load_watchlist,
    watchlist_limit_from_query,
)


AGENT_TITLES = {
    "coordinator": "Coordinator Agent",
    "memory": "Memory Agent",
    "market": "Market Agent",
    "review": "Review Agent",
    "technical": "Technical Agent",
    "fundamental": "Fundamental Agent",
    "news_risk": "News & Risk Agent",
    "bull": "Bull Agent",
    "bear": "Bear Agent",
    "committee": "Committee Agent",
    "portfolio": "Portfolio Agent",
    "report": "Report Agent",
    "verifier": "Verifier Agent",
    "history": "History Agent",
}

PROVIDER_LABELS = {
    "openai": "OpenAI",
    "deepseek": "DeepSeek",
    "minimax": "MiniMax",
    "xiaomi": "Xiaomi MiMo",
    "mimo": "Xiaomi MiMo",
}

PROVIDER_ITEMS = {
    "OpenAI": "openai",
    "DeepSeek": "deepseek",
    "MiniMax": "minimax",
    "Xiaomi MiMo": "xiaomi",
}

PROVIDER_MODEL_ITEMS = {
    "openai": {
        "GPT-5.1": "gpt-5.1",
        "GPT-5": "gpt-5",
        "GPT-5 mini": "gpt-5-mini",
        "GPT-5 nano": "gpt-5-nano",
        "GPT-4.1": "gpt-4.1",
        "GPT-4.1 mini": "gpt-4.1-mini",
        "GPT-4o mini": "gpt-4o-mini",
    },
    "deepseek": {
        "DeepSeek V4 Flash": "deepseek-v4-flash",
        "DeepSeek V4 Pro": "deepseek-v4-pro",
    },
    "minimax": {
        "MiniMax M2.7": "MiniMax-M2.7",
        "MiniMax M2.7 highspeed": "MiniMax-M2.7-highspeed",
        "MiniMax M2.5": "MiniMax-M2.5",
        "MiniMax M2.5 highspeed": "MiniMax-M2.5-highspeed",
        "MiniMax M2-her": "M2-her",
    },
    "xiaomi": {
        "MiMo V2.5 Pro": "mimo-v2.5-pro",
        "MiMo V2.5": "mimo-v2.5",
        "MiMo V2 Flash": "mimo-v2-flash",
    },
}

SESSION_LLM_CONFIGS: dict[str, LLMConfig] = {}

HOME_KEYWORDS = [
    "首页",
    "主页",
    "home",
    "产品首页",
    "产品主页",
    "产品介绍",
    "产品功能",
    "介绍产品",
    "功能介绍",
    "landing",
    "官网",
    "回到首页",
    "开始",
    "start",
]

WORKSPACE_HOME_KEYWORDS = [
    "进入工作台",
    "工作台首页",
    "任务中心",
    "研究工作台",
]

QUICK_ACTION_DEFS = [
    (
        "analyze_nvda",
        "分析 NVDA",
        "启动一次完整多 Agent 投研流程",
        "search",
    ),
    (
        "settings",
        "模型设置",
        "配置 provider、model、base_url 和 API key",
        "settings",
    ),
    (
        "connection_test",
        "测试连接",
        "发起一次最小 LLM 请求，验证当前模型配置",
        "plug",
    ),
    (
        "reports",
        "报告库",
        "打开本地报告库",
        "file-text",
    ),
    (
        "watchlist",
        "观察池",
        "查看研究队列和优先级",
        "star",
    ),
    (
        "dashboard",
        "投研工作台",
        "打开观察池、记忆库和最近报告总览",
        "layout-dashboard",
    ),
    (
        "help",
        "能力指南",
        "查看完整功能说明和示例问题",
        "circle-help",
    ),
]


def _mask_api_key(value: str | None) -> str:
    if not value:
        return "未配置"
    if len(value) <= 8:
        return "已配置 ****"
    return f"已配置 {value[:3]}****{value[-4:]}"


def _provider_label(provider: str) -> str:
    return PROVIDER_LABELS.get(provider, f"{provider} (OpenAI-compatible)")


def _quick_actions() -> list[cl.Action]:
    return [
        cl.Action(
            name="quick_action",
            payload={"intent": intent},
            label=label,
            tooltip=tooltip,
            icon=icon,
        )
        for intent, label, tooltip, icon in QUICK_ACTION_DEFS
    ]


def _product_landing_actions(user_id: str) -> list[cl.Action]:
    config = _effective_llm_config_for_ui()
    ticker = _top_watchlist_ticker(user_id)
    model_label = "模型设置" if config.llm_api_key else "配置模型"
    return [
        cl.Action(
            name="quick_action",
            payload={"intent": "workspace_home"},
            label="进入工作台",
            tooltip="打开状态栏、任务中心和研究流水线",
            icon="layout-dashboard",
        ),
        cl.Action(
            name="quick_action",
            payload={"intent": "analyze_top", "ticker": ticker},
            label=f"分析 {ticker}",
            tooltip=f"启动 {ticker} 的完整多 Agent 投研流程",
            icon="search",
        ),
        cl.Action(
            name="quick_action",
            payload={"intent": "settings"},
            label=model_label,
            tooltip="配置 provider、model、base_url 和 API key",
            icon="settings",
        ),
        cl.Action(
            name="quick_action",
            payload={"intent": "help"},
            label="能力指南",
            tooltip="查看完整功能说明和示例问题",
            icon="circle-help",
        ),
    ]


def _home_actions(user_id: str) -> list[cl.Action]:
    config = _effective_llm_config_for_ui()
    ticker = _top_watchlist_ticker(user_id)
    if not config.llm_api_key:
        return [
            cl.Action(
                name="quick_action",
                payload={"intent": "settings"},
                label="配置模型",
                tooltip="先配置 provider、model、base_url 和 API key",
                icon="settings",
            ),
            cl.Action(
                name="quick_action",
                payload={"intent": "connection_test"},
                label="测试连接",
                tooltip="验证当前模型配置是否可用",
                icon="plug",
            ),
            cl.Action(
                name="quick_action",
                payload={"intent": "reports"},
                label="报告库",
                tooltip="查看已保存的研究报告",
                icon="file-text",
            ),
            cl.Action(
                name="quick_action",
                payload={"intent": "watchlist"},
                label="观察池",
                tooltip="查看研究队列和优先级",
                icon="star",
            ),
            cl.Action(
                name="quick_action",
                payload={"intent": "product_home"},
                label="产品主页",
                tooltip="回到产品功能介绍页",
                icon="home",
            ),
        ]

    return [
        cl.Action(
            name="quick_action",
            payload={"intent": "analyze_top", "ticker": ticker},
            label=f"分析 {ticker}",
            tooltip=f"启动 {ticker} 的完整多 Agent 投研流程",
            icon="search",
        ),
        cl.Action(
            name="quick_action",
            payload={"intent": "reports"},
            label="报告库",
            tooltip="查看最近报告和结论摘要",
            icon="file-text",
        ),
        cl.Action(
            name="quick_action",
            payload={"intent": "watchlist"},
            label="观察池",
            tooltip="查看研究队列和优先级",
            icon="star",
        ),
        cl.Action(
            name="quick_action",
            payload={"intent": "settings"},
            label="模型设置",
            tooltip="管理 provider、model、base_url 和 API key",
            icon="settings",
        ),
        cl.Action(
            name="quick_action",
            payload={"intent": "product_home"},
            label="产品主页",
            tooltip="回到产品功能介绍页",
            icon="home",
        ),
    ]


def _report_actions(ticker: str) -> list[cl.Action]:
    safe_ticker = ticker or "NVDA"
    return [
        cl.Action(
            name="report_action",
            payload={"intent": "open_report", "ticker": safe_ticker},
            label="打开报告",
            tooltip=f"进入 {safe_ticker} 的报告阅读页",
            icon="book-open",
        ),
        cl.Action(
            name="report_action",
            payload={"intent": "reanalyze", "ticker": safe_ticker},
            label="重新分析",
            tooltip=f"重新运行 {safe_ticker} 的完整多 Agent 投研流程",
            icon="refresh-cw",
        ),
        cl.Action(
            name="report_action",
            payload={"intent": "export_report", "ticker": safe_ticker},
            label="导出报告",
            tooltip=f"导出 {safe_ticker} 的独立 HTML 报告",
            icon="download",
        ),
        cl.Action(
            name="quick_action",
            payload={"intent": "reports"},
            label="报告库",
            tooltip="查看最近保存的本地报告",
            icon="list",
        ),
        cl.Action(
            name="quick_action",
            payload={"intent": "dashboard"},
            label="投研工作台",
            tooltip="返回观察池、记忆库和最近报告总览",
            icon="layout-dashboard",
        ),
        cl.Action(
            name="report_action",
            payload={"intent": "watchlist", "ticker": safe_ticker},
            label="观察池",
            tooltip="查看当前观察池优先级",
            icon="star",
        ),
        cl.Action(
            name="quick_action",
            payload={"intent": "settings"},
            label="模型设置",
            tooltip="配置 provider、model、base_url 和 API key",
            icon="settings",
        ),
    ]


def _run_dashboard_actions(run_id: str, ticker: str = "NVDA") -> list[cl.Action]:
    safe_ticker = ticker or "NVDA"
    return [
        cl.Action(
            name="run_action",
            payload={"intent": "run_dashboard", "run_id": run_id},
            label="Agent 看板",
            tooltip="查看本次多 Agent 协作过程和每个 Agent 输出",
            icon="network",
        ),
        cl.Action(
            name="run_action",
            payload={"intent": "debate", "run_id": run_id},
            label="多空辩论",
            tooltip="查看 Bull / Bear / Committee 的观点对比",
            icon="scale",
        ),
        cl.Action(
            name="report_action",
            payload={"intent": "open_report", "ticker": safe_ticker},
            label="打开报告",
            tooltip=f"进入 {safe_ticker} 的报告阅读页",
            icon="book-open",
        ),
        cl.Action(
            name="report_action",
            payload={"intent": "export_report", "ticker": safe_ticker},
            label="导出报告",
            tooltip=f"导出 {safe_ticker} 的独立 HTML 报告",
            icon="download",
        ),
        cl.Action(
            name="report_action",
            payload={"intent": "reanalyze", "ticker": safe_ticker},
            label="重新分析",
            tooltip=f"重新运行 {safe_ticker} 的完整多 Agent 投研流程",
            icon="refresh-cw",
        ),
    ]


def _report_library_actions() -> list[cl.Action]:
    return [
        cl.Action(
            name="report_action",
            payload={"intent": "open_latest"},
            label="打开最近",
            tooltip="进入最近一份报告阅读页",
            icon="book-open",
        ),
        cl.Action(
            name="report_action",
            payload={"intent": "export_latest"},
            label="导出最近",
            tooltip="导出最近一份报告为独立 HTML",
            icon="download",
        ),
        cl.Action(
            name="quick_action",
            payload={"intent": "watchlist"},
            label="观察池",
            tooltip="查看研究队列和优先级",
            icon="star",
        ),
        cl.Action(
            name="quick_action",
            payload={"intent": "settings"},
            label="模型设置",
            tooltip="配置 provider、model、base_url 和 API key",
            icon="settings",
        ),
        cl.Action(
            name="quick_action",
            payload={"intent": "analyze_nvda"},
            label="分析 NVDA",
            tooltip="启动一次完整多 Agent 投研流程",
            icon="search",
        ),
    ]


def _workspace_actions() -> list[cl.Action]:
    return [
        cl.Action(
            name="quick_action",
            payload={"intent": "product_home"},
            label="产品主页",
            tooltip="回到产品首页",
            icon="home",
        ),
        cl.Action(
            name="quick_action",
            payload={"intent": "reports"},
            label="报告库",
            tooltip="查看最近报告和结论摘要",
            icon="file-text",
        ),
        cl.Action(
            name="quick_action",
            payload={"intent": "watchlist"},
            label="观察池",
            tooltip="查看研究队列和优先级",
            icon="star",
        ),
        cl.Action(
            name="quick_action",
            payload={"intent": "settings"},
            label="模型设置",
            tooltip="配置 provider、model、base_url 和 API key",
            icon="settings",
        ),
        cl.Action(
            name="quick_action",
            payload={"intent": "analyze_nvda"},
            label="分析 NVDA",
            tooltip="启动一次完整多 Agent 投研流程",
            icon="search",
        ),
    ]


def _watchlist_actions(ticker: str = "NVDA") -> list[cl.Action]:
    safe_ticker = ticker or "NVDA"
    return [
        cl.Action(
            name="report_action",
            payload={"intent": "reanalyze", "ticker": safe_ticker},
            label="重新分析",
            tooltip=f"重新运行 {safe_ticker} 的完整多 Agent 投研流程",
            icon="refresh-cw",
        ),
        cl.Action(
            name="quick_action",
            payload={"intent": "reports"},
            label="报告库",
            tooltip="查看最近报告和结论摘要",
            icon="file-text",
        ),
        cl.Action(
            name="quick_action",
            payload={"intent": "dashboard"},
            label="投研工作台",
            tooltip="返回观察池、记忆库和最近报告总览",
            icon="layout-dashboard",
        ),
        cl.Action(
            name="quick_action",
            payload={"intent": "settings"},
            label="模型设置",
            tooltip="配置 provider、model、base_url 和 API key",
            icon="settings",
        ),
    ]


def _settings_actions(user_id: str) -> list[cl.Action]:
    ticker = _top_watchlist_ticker(user_id)
    return [
        cl.Action(
            name="quick_action",
            payload={"intent": "connection_test"},
            label="测试连接",
            tooltip="验证当前模型配置是否可用",
            icon="plug",
        ),
        cl.Action(
            name="quick_action",
            payload={"intent": "analyze_top", "ticker": ticker},
            label=f"分析 {ticker}",
            tooltip=f"启动 {ticker} 的完整多 Agent 投研流程",
            icon="search",
        ),
        cl.Action(
            name="quick_action",
            payload={"intent": "product_home"},
            label="产品主页",
            tooltip="回到产品首页",
            icon="home",
        ),
    ]


def _is_home_intent(text: str) -> bool:
    normalized = text.strip().lower()
    if not normalized:
        return False
    compact = "".join(normalized.split())
    return any(keyword.lower().replace(" ", "") == compact for keyword in HOME_KEYWORDS)


def _is_workspace_home_intent(text: str) -> bool:
    normalized = text.strip().lower()
    if not normalized:
        return False
    compact = "".join(normalized.split())
    return any(keyword.lower().replace(" ", "") == compact for keyword in WORKSPACE_HOME_KEYWORDS)


def _current_session_key() -> str:
    try:
        session_id = cl.user_session.get("id")
    except Exception:
        session_id = None
    return str(session_id or "chainlit")


def _session_llm_config() -> LLMConfig | None:
    return SESSION_LLM_CONFIGS.get(_current_session_key())


def _effective_llm_config_for_ui() -> LLMConfig:
    return _session_llm_config() or LLMConfig.from_settings()


def _top_watchlist_ticker(user_id: str) -> str:
    items = load_watchlist(user_id).get("items", [])
    if items:
        return str(items[0].get("ticker") or "NVDA")
    return "NVDA"


def _provider_defaults(provider: str) -> dict:
    return PROVIDER_DEFAULTS.get(provider, PROVIDER_DEFAULTS["openai"])


def _provider_model_items(provider: str, current_model: str | None = None) -> dict[str, str]:
    items = dict(PROVIDER_MODEL_ITEMS.get(provider, PROVIDER_MODEL_ITEMS["openai"]))
    if current_model and current_model not in items.values():
        items[f"当前自定义：{current_model}"] = current_model
    return items


def _provider_model_values(provider: str) -> set[str]:
    return set(PROVIDER_MODEL_ITEMS.get(provider, {}).values())


def _build_session_llm_config(updated: dict) -> LLMConfig:
    previous = _session_llm_config()
    fallback = LLMConfig.from_settings()
    provider = str(updated.get("llm_provider") or fallback.llm_provider).strip().lower()
    provider = provider or "openai"
    defaults = _provider_defaults(provider)

    previous_effective = previous or fallback
    selected_model = str(updated.get("llm_model") or "").strip()
    custom_model = str(updated.get("llm_custom_model") or "").strip()
    raw_model = custom_model or selected_model
    provider_model_values = _provider_model_values(provider)
    previous_model_values = _provider_model_values(previous_effective.llm_provider)
    if custom_model:
        model = custom_model
    elif not raw_model:
        model = str(defaults["model"])
    elif previous_effective.llm_provider != provider and raw_model not in provider_model_values:
        model = str(defaults["model"])
    elif previous_effective.llm_provider != provider and raw_model in previous_model_values:
        model = str(defaults["model"])
    else:
        model = raw_model

    base_url_input = str(updated.get("llm_base_url") or "").strip()
    if not base_url_input:
        base_url = defaults.get("base_url")
    elif previous_effective.llm_provider != provider and base_url_input == (previous_effective.llm_base_url or ""):
        base_url = defaults.get("base_url")
    else:
        base_url = base_url_input

    api_key_input = str(updated.get("llm_api_key") or "").strip()
    if api_key_input:
        api_key = api_key_input
        api_key_source = "UI Session"
    elif previous and previous.llm_provider == provider and previous.llm_api_key_source == "UI Session":
        api_key = previous.llm_api_key
        api_key_source = previous.llm_api_key_source
    elif provider == fallback.llm_provider:
        api_key = fallback.llm_api_key
        api_key_source = fallback.llm_api_key_source
    else:
        api_key = None
        api_key_source = None

    try:
        temperature = float(updated.get("llm_temperature", fallback.llm_temperature))
    except (TypeError, ValueError):
        temperature = fallback.llm_temperature

    return LLMConfig(
        llm_provider=provider,
        llm_model=model,
        llm_base_url=base_url,
        llm_api_key=api_key,
        llm_api_key_source=api_key_source,
        llm_temperature=temperature,
        deepseek_thinking=fallback.deepseek_thinking,
        deepseek_reasoning_effort=fallback.deepseek_reasoning_effort,
        minimax_reasoning_split=fallback.minimax_reasoning_split,
    )


def _activate_session_llm_config():
    return set_runtime_llm_config(_session_llm_config())


def _format_product_landing(user_id: str) -> str:
    config = _effective_llm_config_for_ui()
    watchlist_items = load_watchlist(user_id).get("items", [])
    reports = list_reports(user_id, limit=5)
    vector_count = count_vector_memories(user_id)
    semantic_count = len(load_semantic_memories(user_id))
    top_ticker = str(watchlist_items[0].get("ticker")) if watchlist_items else "NVDA"
    key_status = "已配置，可以生成完整 AI 报告" if config.llm_api_key else "未配置，建议先进入模型设置"
    base_url = config.llm_base_url or "OpenAI 默认"

    return f"""# Fin Agent

> 面向中文用户的 AI 投研工作台。它把一句股票问题，拆成数据采集、技术面、基本面、新闻风险、多空辩论、投委会结论、报告质检和观察池跟踪。

## 产品价值

| 用户痛点 | Fin Agent 的解决方式 | 结果 |
|---|---|---|
| 不知道先看什么 | 自动识别标的、周期和问题类型 | 从自然语言直接进入研究任务 |
| 信息分散 | 聚合行情、技术指标、基本面、新闻线索和历史记忆 | 一份报告里看到完整证据链 |
| AI 结论不透明 | 多 Agent 分工输出中间过程 | 能看到每一步为什么这么判断 |
| 报告用完就丢 | 保存报告、写入记忆、更新观察池 | 形成可复盘的连续研究循环 |

## 核心功能

| 功能模块 | 能做什么 | 适合场景 |
|---|---|---|
| 新建研究 | 输入股票名或 ticker，自动生成中文投研报告 | 快速分析 NVDA、闪迪、小米概念股等标的 |
| 多 Agent 流水线 | Coordinator、Market、Technical、Fundamental、Bull、Bear、Committee 等分工协作 | 展示 Agent 工程能力和投研流程 |
| Agent 协作看板 | 实时展示每个 Agent 的状态、角色、摘要和关键输出 | 像看不同分析师协作一样理解系统运行 |
| 多空辩论区 | 对比 Bull、Bear、Committee 的观点、置信度和裁决依据 | 观察多空分歧如何形成最终结论 |
| 报告库 | 查看历史报告、评级、置信度、质检状态和资料链接 | 复盘历史观点，比较前后判断变化 |
| 观察池 | 自动沉淀分析过的标的，按优先级排序 | 做每日研究队列和持续跟踪 |
| 记忆系统 | SQLite + 本地 TF-IDF/Hash Embedding 记录偏好和历史 thesis | 让历史报告主动影响后续分析 |
| 模型设置 | 支持 OpenAI、DeepSeek、MiniMax、小米 MiMo 和兼容接口 | 用户可自行配置 API key 和模型 |

## 研究流程

| 步骤 | 系统动作 | 用户获得 |
|---:|---|---|
| 1 | 识别 ticker、公司名、市场和周期 | 不需要严格输入股票代码 |
| 2 | 拉取行情、指标、基本面和新闻线索 | 结构化证据，不只是聊天回答 |
| 3 | 生成看多、看空和投委会观点 | 有分歧、有权衡、有最终评级 |
| 4 | 写入报告库、记忆库和观察池 | 下次分析能延续历史上下文 |
| 5 | 质量检查报告一致性 | 减少数据和结论互相矛盾 |

## 当前环境

| 项目 | 状态 |
|---|---|
| Provider | **{_provider_label(config.llm_provider)}** |
| Model | **{config.llm_model}** |
| Base URL | `{base_url}` |
| API Key | **{key_status}** |
| 观察池 | **{len(watchlist_items)}** 个标的 |
| 报告库 | **{len(reports)}** 份报告 |
| 记忆库 | **{vector_count + semantic_count}** 条记录 |

## 现在可以开始

| 你想做什么 | 建议入口 |
|---|---|
| 先了解系统状态和下一步任务 | 点击 **进入工作台** |
| 直接体验完整投研流程 | 点击 **分析 {top_ticker}** |
| 先配置自己的模型和 API key | 点击 **模型设置** |
| 查看完整能力和示例问题 | 点击 **能力指南** |
"""


def _format_product_home(user_id: str) -> str:
    config = _effective_llm_config_for_ui()
    watchlist = load_watchlist(user_id)
    watchlist_items = watchlist.get("items", [])
    reports = list_reports(user_id, limit=5)
    vector_count = count_vector_memories(user_id)
    semantic_count = len(load_semantic_memories(user_id))
    key_status = "已配置" if config.llm_api_key else "未配置"
    key_source = config.llm_api_key_source or "N/A"
    base_url = config.llm_base_url or "OpenAI 默认"
    top_ticker = str(watchlist_items[0].get("ticker")) if watchlist_items else "NVDA"
    latest_report = reports[0]["ticker"] if reports else "暂无"
    if not config.llm_api_key:
        primary_task = "配置模型并完成连接测试"
        primary_reason = "没有可用 API Key 时，报告生成会退回到规则模板。"
        primary_command = "模型设置"
    elif not reports:
        primary_task = f"创建第一份 {top_ticker} 投研报告"
        primary_reason = "报告库为空，先生成一份报告才能进入复盘和观察池循环。"
        primary_command = f"帮我分析一下 {top_ticker} 未来一个月走势"
    else:
        primary_task = f"复盘 {top_ticker} 的最新观点"
        primary_reason = "已有报告和记忆，适合继续跟踪观点变化、估值压力和风险兑现。"
        primary_command = f"帮我重新分析 {top_ticker}，重点看估值压力和观点变化"

    readiness = "可开始研究" if config.llm_api_key else "需要配置模型"
    mode = "复盘模式" if reports else "初始化模式"

    return f"""# Fin Agent 投研工作台

> 一个面向中文用户的多 Agent 股票研究工作区：从新建研究、观察池跟踪到报告复盘，形成可追溯的投研循环。

## 状态栏

| 模型状态 | 当前值 | 研究资产 | 当前值 |
|---|---|---|---:|
| 运行状态 | **{readiness}** | 观察池 | **{len(watchlist_items)}** |
| Provider | **{_provider_label(config.llm_provider)}** | 报告库 | **{len(reports)}** |
| Model | **{config.llm_model}** | SQLite 记忆 | **{vector_count}** |
| Base URL | `{base_url}` | 语义备份 | **{semantic_count}** |
| API Key | **{key_status}**（{key_source}） | 最新报告 | **{latest_report}** |

## 任务中心

| 优先级 | 建议任务 | 为什么 | 操作 |
|---:|---|---|---|
| 1 | **{primary_task}** | {primary_reason} | `{primary_command}` |
| 2 | 查看报告库质量状态 | 先看结论、置信度、质检问题，再决定是否重跑。 | `报告列表` |
| 3 | 检查观察池队列 | 用优先级和近期走势决定今天先复盘谁。 | `查看观察池` |

## 工作区

| 入口 | 当前状态 | 适合做什么 | 快捷命令 |
|---|---|---|---|
| 新建研究 | **{mode}** | 跑完整 Agent 流程，生成新报告并更新观察池 | `帮我分析一下 {top_ticker} 未来一个月走势` |
| 报告库 | **{len(reports)} 份** | 查看评级、置信度、质检状态和资料链接 | `报告列表` |
| 观察池 | **{len(watchlist_items)} 个标的** | 查看研究队列、跟踪理由和下一步动作 | `查看观察池` |
| 记忆库 | **{vector_count + semantic_count} 条记录** | 检索历史 thesis 和观点变化 | `以前分析过 {top_ticker} 吗` |
| 模型设置 | **{_provider_label(config.llm_provider)}** | 切换 provider、model、base_url 和 API key | `模型设置` |

## 研究流水线

| 阶段 | 用户能看到什么 |
|---|---|
| 识别 | ticker、公司名、分析周期、是否需要早停 |
| 数据 | 行情、技术指标、基本面、新闻链接和风险线索 |
| 辩论 | Bull / Bear / Committee 的多空观点与最终评级 |
| 沉淀 | 报告、质检、历史记忆、观察池优先级 |
"""


async def _format_settings_for_session(test_connection: bool = False) -> str:
    token = _activate_session_llm_config()
    try:
        return await format_settings_response(test_connection=test_connection)
    finally:
        reset_runtime_llm_config(token)


async def _send_settings_widgets() -> None:
    config = _effective_llm_config_for_ui()
    provider_values = list(PROVIDER_ITEMS.values())
    provider = config.llm_provider if config.llm_provider in provider_values else "openai"
    provider_default = _provider_defaults(provider)

    await cl.ChatSettings(
        [
            Select(
                id="llm_provider",
                label="Provider",
                items=PROVIDER_ITEMS,
                initial_value=provider,
                description="选择本会话使用的 OpenAI-compatible provider。",
            ),
            Select(
                id="llm_model",
                label="模型",
                items=_provider_model_items(provider, config.llm_model),
                initial_value=config.llm_model,
                description="模型选项会随 Provider 改变；切换 Provider 后保存一次会自动刷新。",
            ),
            TextInput(
                id="llm_custom_model",
                label="自定义模型名（可选）",
                initial="",
                placeholder="填写后覆盖上方模型选择",
                description="如果 provider 新增模型但下拉中还没有，可以临时手动填写。",
            ),
            TextInput(
                id="llm_base_url",
                label="Base URL（随 Provider 自动刷新）",
                initial=config.llm_base_url or "",
                placeholder=str(provider_default.get("base_url") or "OpenAI 官方接口可留空"),
                description="切换 Provider 后保存一次会刷新为对应默认 Base URL；也可以手动覆盖。",
            ),
            TextInput(
                id="llm_api_key",
                label="API Key（本会话）",
                initial="",
                placeholder=f"留空则保留当前 key；当前：{_mask_api_key(config.llm_api_key)}",
                description="保存后只在当前服务进程的会话内使用，不写入 .env、报告或记忆库。",
            ),
            Slider(
                id="llm_temperature",
                label="Temperature",
                initial=float(config.llm_temperature),
                min=0,
                max=1,
                step=0.1,
            ),
            TextInput(
                id="llm_key_status_view",
                label="API Key 状态",
                initial=f"{_mask_api_key(config.llm_api_key)}；来源：{config.llm_api_key_source or 'N/A'}",
                disabled=True,
            ),
        ]
    ).send()


def _current_user_id() -> str:
    user = cl.user_session.get("user")
    identifier = getattr(user, "identifier", None) or getattr(user, "id", None)
    if identifier:
        return safe_user_id(str(identifier))
    session_id = cl.user_session.get("id")
    if session_id:
        return safe_user_id(str(session_id))
    return "chainlit"


def _format_news_clues(news: list[dict], limit: int = 6) -> str:
    if not news:
        return "暂无可用新闻线索。"

    lines = []
    for idx, item in enumerate(news[:limit], start=1):
        title = item.get("title") or "Untitled"
        publisher = item.get("publisher") or "Unknown"
        published = item.get("published") or "日期未知"
        link = item.get("link") or ""
        title_text = f"[{title}]({link})" if link else title
        lines.append(f"{idx}. {title_text}\n   来源：{publisher}；日期：{published}")
    return "\n".join(lines)


def _format_risk_clues(risks: list[str], limit: int = 5) -> str:
    if not risks:
        return "暂无明确风险线索。"
    return "\n".join(f"{idx}. {risk}" for idx, risk in enumerate(risks[:limit], start=1))


def _format_case(case: dict, argument_key: str = "arguments") -> str:
    if not case:
        return "暂无观点。"
    confidence = case.get("confidence", "N/A")
    summary = case.get("summary", "暂无摘要")
    arguments = case.get(argument_key, [])
    lines = [f"置信度：**{confidence}%**", f"摘要：{summary}"]
    if arguments:
        lines.append("核心论据：")
        lines.extend(f"{idx}. {arg}" for idx, arg in enumerate(arguments[:4], start=1))
    return "\n".join(lines)


def _format_fundamentals(fundamentals: dict) -> str:
    if not fundamentals:
        return "暂无基本面数据。"
    if not fundamentals.get("ok"):
        return f"基本面数据获取失败：{fundamentals.get('error', '未知错误')}"

    rows = [
        f"- 公司：**{fundamentals.get('company_name') or fundamentals.get('ticker', 'N/A')}**",
        f"- 行业：**{fundamentals.get('sector') or 'N/A'} / {fundamentals.get('industry') or 'N/A'}**",
        f"- 市值：**{fundamentals.get('market_cap_display') or 'N/A'} {fundamentals.get('currency') or ''}**",
        f"- Trailing PE / Forward PE：**{fundamentals.get('trailing_pe') or 'N/A'} / {fundamentals.get('forward_pe') or 'N/A'}**",
        f"- PS / PB：**{fundamentals.get('price_to_sales') or 'N/A'} / {fundamentals.get('price_to_book') or 'N/A'}**",
        f"- 营收增长 / 净利率：**{fundamentals.get('revenue_growth_percent') or 'N/A'}% / {fundamentals.get('profit_margins_percent') or 'N/A'}%**",
        f"- 分析师目标均价：**{fundamentals.get('target_mean_price') or 'N/A'}**",
        f"- 一致预期：**{fundamentals.get('recommendation_key') or 'N/A'}**",
        f"- 财报日期：**{fundamentals.get('earnings_date') or 'N/A'} ({fundamentals.get('earnings_date_context') or 'unknown'})**",
    ]
    highlights = fundamentals.get("highlights", [])
    risks = fundamentals.get("risks", [])
    if highlights:
        rows.append("\n亮点：")
        rows.extend(f"{idx}. {item}" for idx, item in enumerate(highlights[:3], start=1))
    if risks:
        rows.append("\n风险：")
        rows.extend(f"{idx}. {item}" for idx, item in enumerate(risks[:3], start=1))
    return "\n".join(rows)


def _format_review(review: dict) -> str:
    if not review:
        return "暂无复盘信息。"
    if not review.get("has_history"):
        return f"{review.get('summary', '暂无历史报告。')}\n\n{review.get('reminder', '')}".strip()

    return (
        f"{review.get('summary', '')}\n\n"
        f"- 上次时间：**{review.get('previous_timestamp') or 'N/A'}**\n"
        f"- 上次评级：**{review.get('previous_rating') or 'N/A'}** "
        f"({review.get('previous_confidence') or 'N/A'}%)\n"
        f"- 上次价格 / 当前价格：**{review.get('previous_price') or 'N/A'} / "
        f"{review.get('current_price') or 'N/A'}**\n"
        f"- 期间涨跌幅：**{review.get('return_percent') if review.get('return_percent') is not None else 'N/A'}%**\n"
        f"- 兑现情况：**{review.get('performance_label') or 'N/A'}**\n"
        f"- 提醒：{review.get('reminder') or '暂无'}"
    )


def _format_portfolio(portfolio: dict) -> str:
    if not portfolio:
        return "暂无观察池信息。"
    if not portfolio.get("ok"):
        return f"观察池更新失败：{portfolio.get('error', '未知错误')}"

    current = portfolio.get("current_item", {})
    reasons = current.get("watch_reasons", [])
    top_items = portfolio.get("top_items", [])
    same_sector = portfolio.get("same_sector_tickers", [])

    reason_text = "\n".join(f"{idx}. {reason}" for idx, reason in enumerate(reasons[:5], start=1))
    top_text = "\n".join(
        f"{idx}. **{item.get('ticker', 'N/A')}** "
        f"{item.get('priority_label', 'N/A')} "
        f"({item.get('priority_score', 'N/A')}/100) - "
        f"{item.get('rating', 'N/A')}"
        for idx, item in enumerate(top_items[:5], start=1)
    )
    sector_text = ", ".join(str(item) for item in same_sector) if same_sector else "暂无"

    return (
        f"- 观察池规模：**{portfolio.get('watchlist_size', 'N/A')}**\n"
        f"- 当前优先级：**{portfolio.get('priority_label', 'N/A')}** "
        f"({portfolio.get('priority_score', 'N/A')}/100)\n"
        f"- 组合角色：**{portfolio.get('portfolio_role', 'N/A')}**\n"
        f"- 同板块已有标的：{sector_text}\n"
        f"- 本地文件：`{portfolio.get('watchlist_path', 'N/A')}`\n\n"
        f"跟踪理由：\n{reason_text or '暂无'}\n\n"
        f"观察池 Top 5：\n{top_text or '暂无'}"
    )


def _brief_update(node_name: str, update: dict) -> str:
    if node_name == "coordinator":
        direct_response = update.get("direct_response")
        if direct_response:
            return direct_response

        ticker = update.get("ticker") or "未识别"
        horizon = update.get("horizon") or "默认周期"
        resolution = update.get("ticker_resolution", {})
        method = resolution.get("method", "rules")
        confidence = resolution.get("confidence")
        confidence_text = f"；置信度：**{confidence:.0%}**" if isinstance(confidence, (int, float)) else ""
        return f"已识别标的：**{ticker}**；分析周期：**{horizon}**；识别方式：**{method}**{confidence_text}。"

    if node_name == "market":
        market_data = update.get("market_data", {})
        if not market_data.get("ok"):
            return f"行情数据获取失败：{market_data.get('error', '未知错误')}"
        price = market_data.get("last_close")
        change = market_data.get("returns", {}).get("1d")
        return f"已获取行情数据。最新收盘价：**{price}**；近 1 日涨跌幅：**{change}%**。"

    if node_name == "memory":
        memory_context = update.get("memory_context", {})
        updates = memory_context.get("preference_updates", [])
        ticker_memories = memory_context.get("ticker_history", [])
        semantic_memories = memory_context.get("semantic_memories", [])
        guidance = memory_context.get("memory_guidance", {})
        update_text = "；".join(updates) if updates else "无新增偏好"
        return (
            f"已加载用户记忆。偏好更新：**{update_text}**；"
            f"同标的历史：**{len(ticker_memories)}** 条；"
            f"语义相似记忆：**{len(semantic_memories)}** 条；"
            f"关注点：**{', '.join(guidance.get('focus_points', [])[:3]) or '暂无'}**。"
        )

    if node_name == "review":
        return "### 历史复盘\n" + _format_review(update.get("review", {}))

    if node_name == "technical":
        technicals = update.get("technicals", {})
        return (
            f"技术面判断：**{technicals.get('trend_label', '暂无判断')}**；"
            f"RSI：**{technicals.get('rsi_14', 'N/A')}**；"
            f"MACD 信号：**{technicals.get('macd_signal_label', 'N/A')}**。"
        )

    if node_name == "fundamental":
        return "### 基本面与估值\n" + _format_fundamentals(update.get("fundamentals", {}))

    if node_name == "news_risk":
        risks = update.get("risks", [])
        news = update.get("news", [])
        return (
            f"已整理 **{len(news)}** 条新闻线索和 **{len(risks)}** 条主要风险。\n\n"
            "### 新闻线索\n"
            f"{_format_news_clues(news)}\n\n"
            "### 风险线索\n"
            f"{_format_risk_clues(risks)}"
        )

    if node_name == "bull":
        return "### 看多观点\n" + _format_case(update.get("bull_case", {}))

    if node_name == "bear":
        return "### 看空观点\n" + _format_case(update.get("bear_case", {}))

    if node_name == "committee":
        view = update.get("committee_view", {})
        reasons = view.get("key_reasons", [])
        memory_influence = view.get("memory_influence", {})
        reason_text = "\n".join(f"{idx}. {reason}" for idx, reason in enumerate(reasons, start=1))
        return (
            f"投委会结论：**{view.get('rating', 'N/A')}**；"
            f"置信度：**{view.get('confidence', 'N/A')}%**。\n\n"
            f"多空强度：Bull **{view.get('bull_confidence', 'N/A')}%** / "
            f"Bear **{view.get('bear_confidence', 'N/A')}%**\n\n"
            f"关键依据：\n{reason_text or '暂无'}\n\n"
            f"记忆影响：{memory_influence.get('summary', '暂无历史记忆影响。')}\n\n"
            f"不确定性：{view.get('uncertainty', '暂无')}"
        )

    if node_name == "portfolio":
        return "### 组合观察池\n" + _format_portfolio(update.get("portfolio", {}))

    if node_name == "report":
        return "中文投研报告已生成。"

    if node_name == "verifier":
        verification = update.get("verification", {})
        issues = verification.get("issues", [])
        suggestions = verification.get("suggestions", [])
        issue_text = "\n".join(
            f"{idx}. [{issue.get('severity')}] {issue.get('message')}"
            for idx, issue in enumerate(issues[:5], start=1)
        )
        suggestion_text = "\n".join(
            f"{idx}. {suggestion}" for idx, suggestion in enumerate(suggestions[:5], start=1)
        )
        return (
            f"质量检查状态：**{verification.get('status', 'unknown')}**；"
            f"发现问题：**{len(issues)}** 个。\n\n"
            f"### 问题\n{issue_text or '未发现明显问题。'}\n\n"
            f"### 建议\n{suggestion_text or '暂无。'}"
        )

    if node_name == "history":
        record = update.get("history_record", {})
        return (
            f"已保存历史记录：`{record.get('history_path', 'N/A')}`\n\n"
            f"- 标的：**{record.get('ticker', 'N/A')}**\n"
            f"- 评级：**{record.get('rating', 'N/A')}**\n"
            f"- 价格：**{record.get('price', 'N/A')}**"
        )

    return "节点已完成。"


async def _run_research_flow(user_query: str, user_id: str) -> None:
    graph = build_research_graph()
    latest_state: dict = {}
    run_record = create_run_record(user_id, user_query)
    run_id = str(run_record["run_id"])
    cl.user_session.set("last_run_id", run_id)

    await cl.Message(
        content=(
            "# 研究任务已启动\n\n"
            f"Run ID：`{run_id}`\n\n"
            "我会依次完成标的识别、行情与基本面、新闻风险、多空观点、投委会结论、报告生成和质量检查。"
        )
    ).send()
    board_message = cl.Message(
        author="Multi-Agent Run Dashboard",
        content=format_live_run_board(run_record),
    )
    await board_message.send()

    token = _activate_session_llm_config()
    try:
        async for event in graph.astream(
            {
                "user_id": user_id,
                "user_query": user_query,
                "agent_notes": [],
                "errors": [],
            },
            stream_mode="updates",
        ):
            for node_name, update in event.items():
                if not isinstance(update, dict):
                    continue
                latest_state.update(update)
                summary = _brief_update(node_name, update)
                run_record = append_run_event(
                    user_id=user_id,
                    run_id=run_id,
                    node_name=node_name,
                    summary=summary,
                    update=update,
                )
                board_message.content = format_live_run_board(run_record)
                await board_message.update()
                await cl.Message(
                    author=AGENT_TITLES.get(node_name, node_name),
                    content=summary,
                ).send()
    except Exception as exc:
        failed_record = fail_run_record(user_id, run_id, str(exc))
        if failed_record:
            board_message.content = format_live_run_board(failed_record)
            await board_message.update()
        await cl.Message(content=f"运行 Agent 流程时出错：`{exc}`").send()
        return
    finally:
        reset_runtime_llm_config(token)

    if latest_state.get("direct_response"):
        stopped_record = complete_run_record(user_id, run_id, latest_state, status="stopped")
        if stopped_record:
            board_message.content = format_live_run_board(stopped_record)
            await board_message.update()
        return

    final_report = latest_state.get("final_report")
    if not final_report:
        failed_record = fail_run_record(user_id, run_id, "Final report is missing.")
        if failed_record:
            board_message.content = format_live_run_board(failed_record)
            await board_message.update()
        await cl.Message(content="报告生成失败，请检查 ticker 或数据源连接。").send()
        return

    chart = build_price_chart(
        latest_state.get("market_data", {}),
        latest_state.get("technicals", {}),
    )
    elements = []
    if chart is not None:
        elements.append(cl.Plotly(name="price_chart", figure=chart, display="inline"))

    ticker = str(latest_state.get("ticker") or "NVDA")
    completed_record = complete_run_record(user_id, run_id, latest_state, status="completed")
    if completed_record:
        board_message.content = format_live_run_board(completed_record)
        await board_message.update()
    await cl.Message(
        content=final_report,
        elements=elements,
        actions=_run_dashboard_actions(run_id, ticker),
    ).send()


@cl.set_starters
async def set_starters():
    return [
        cl.Starter(
            label="产品主页",
            message="产品主页",
            icon="home",
        ),
        cl.Starter(
            label="进入工作台",
            message="进入工作台",
            icon="layout-dashboard",
        ),
        cl.Starter(
            label="新建研究",
            message="帮我分析一下 NVDA 未来一个月走势",
            icon="search",
        ),
        cl.Starter(
            label="报告库",
            message="报告列表",
            icon="file-text",
        ),
        cl.Starter(
            label="观察池",
            message="查看观察池",
            icon="star",
        ),
        cl.Starter(
            label="模型设置",
            message="模型设置",
            icon="settings",
        ),
        cl.Starter(
            label="测试连接",
            message="测试模型连接",
            icon="plug",
        ),
    ]


@cl.on_chat_start
async def on_chat_start() -> None:
    user_id = _current_user_id()
    await _send_settings_widgets()
    await cl.Message(
        content=_format_product_landing(user_id),
        actions=_product_landing_actions(user_id),
    ).send()


@cl.on_settings_update
async def on_settings_update(updated: dict) -> None:
    user_id = _current_user_id()
    config = _build_session_llm_config(updated)
    SESSION_LLM_CONFIGS[_current_session_key()] = config
    await _send_settings_widgets()
    await cl.Message(
        content=(
            "模型配置已应用到当前会话。\n\n"
            f"- Provider：**{_provider_label(config.llm_provider)}**\n"
            f"- Model：**{config.llm_model}**\n"
            f"- Base URL：`{config.llm_base_url or 'N/A'}`\n"
            f"- API Key：**{_mask_api_key(config.llm_api_key)}**\n\n"
            "现在可以点击 **测试连接**，或直接开始投研分析。"
        ),
        actions=_settings_actions(user_id),
    ).send()


@cl.action_callback("quick_action")
async def on_quick_action(action: cl.Action) -> None:
    intent = action.payload.get("intent")
    user_id = _current_user_id()

    if intent in {"home", "product_home"}:
        await cl.Message(
            content=_format_product_landing(user_id),
            actions=_product_landing_actions(user_id),
        ).send()
        return

    if intent == "workspace_home":
        await cl.Message(content=_format_product_home(user_id), actions=_home_actions(user_id)).send()
        return

    if intent in {"analyze_nvda", "analyze_top"}:
        ticker = str(action.payload.get("ticker") or "NVDA").upper()
        await _run_research_flow(f"帮我分析一下 {ticker} 未来一个月走势", user_id)
        return

    if intent == "settings":
        await cl.Message(content=await _format_settings_for_session(), actions=_settings_actions(user_id)).send()
        return

    if intent == "connection_test":
        await cl.Message(
            content=await _format_settings_for_session(test_connection=True),
            actions=_settings_actions(user_id),
        ).send()
        return

    if intent == "reports":
        await cl.Message(content=format_report_list_response(user_id), actions=_report_library_actions()).send()
        return

    if intent == "watchlist":
        await cl.Message(
            content=format_watchlist_response(user_id=user_id),
            actions=_watchlist_actions(_top_watchlist_ticker(user_id)),
        ).send()
        return

    if intent == "dashboard":
        await cl.Message(content=format_dashboard_response(user_id), actions=_workspace_actions()).send()
        return

    if intent == "help":
        await cl.Message(content=HELP_MESSAGE).send()
        return


@cl.action_callback("run_action")
async def on_run_action(action: cl.Action) -> None:
    intent = action.payload.get("intent")
    run_id = action.payload.get("run_id") or cl.user_session.get("last_run_id")
    user_id = _current_user_id()

    if intent == "run_dashboard":
        await cl.Message(
            content=format_run_dashboard_response(user_id=user_id, run_id=run_id),
            actions=[
                cl.Action(
                    name="run_action",
                    payload={"intent": "debate", "run_id": run_id},
                    label="多空辩论",
                    tooltip="查看 Bull / Bear / Committee 的观点对比",
                    icon="scale",
                )
            ],
        ).send()
        return

    if intent == "debate":
        await cl.Message(
            content=format_debate_dashboard_response(user_id=user_id, run_id=run_id),
            actions=[
                cl.Action(
                    name="run_action",
                    payload={"intent": "run_dashboard", "run_id": run_id},
                    label="Agent 看板",
                    tooltip="返回本次多 Agent 协作看板",
                    icon="network",
                )
            ],
        ).send()
        return


@cl.action_callback("report_action")
async def on_report_action(action: cl.Action) -> None:
    intent = action.payload.get("intent")
    ticker = str(action.payload.get("ticker") or "NVDA").upper()
    user_id = _current_user_id()

    if intent == "reanalyze":
        await _run_research_flow(f"帮我重新分析 {ticker}，重点看估值压力和观点变化", user_id)
        return

    if intent == "open_latest":
        report_ticker = resolve_report_ticker("打开最近报告", user_id=user_id)
        await cl.Message(
            content=format_report_browser_response("打开最近报告", user_id=user_id),
            actions=_report_actions(report_ticker),
        ).send()
        return

    if intent == "open_report":
        await cl.Message(
            content=format_report_browser_response(f"打开 {ticker} 报告", user_id=user_id),
            actions=_report_actions(ticker),
        ).send()
        return

    if intent == "export_latest":
        report_ticker = resolve_report_ticker("导出最近报告", user_id=user_id)
        await cl.Message(
            content=format_report_export_response("导出最近报告", user_id=user_id),
            actions=_report_actions(report_ticker),
        ).send()
        return

    if intent == "export_report":
        await cl.Message(
            content=format_report_export_response(f"导出 {ticker} 报告", user_id=user_id),
            actions=_report_actions(ticker),
        ).send()
        return

    if intent == "watchlist":
        await cl.Message(
            content=format_watchlist_response(user_id=user_id),
            actions=_watchlist_actions(_top_watchlist_ticker(user_id)),
        ).send()
        return


@cl.on_message
async def on_message(message: cl.Message) -> None:
    user_query = message.content.strip()
    user_id = _current_user_id()
    if not user_query:
        await cl.Message(content="请输入一个股票分析问题，比如：`分析一下 AAPL 最近走势`。").send()
        return

    if _is_home_intent(user_query):
        await cl.Message(
            content=_format_product_landing(user_id),
            actions=_product_landing_actions(user_id),
        ).send()
        return

    if _is_workspace_home_intent(user_query):
        await cl.Message(content=_format_product_home(user_id), actions=_home_actions(user_id)).send()
        return

    if is_help_intent(user_query):
        await cl.Message(content=HELP_MESSAGE).send()
        return

    if is_run_dashboard_intent(user_query):
        run_id = cl.user_session.get("last_run_id")
        await cl.Message(
            content=format_run_dashboard_response(user_id=user_id, run_id=run_id),
        ).send()
        return

    if is_debate_dashboard_intent(user_query):
        run_id = cl.user_session.get("last_run_id")
        await cl.Message(
            content=format_debate_dashboard_response(user_id=user_id, run_id=run_id),
        ).send()
        return

    if is_dashboard_intent(user_query):
        await cl.Message(content=format_dashboard_response(user_id), actions=_workspace_actions()).send()
        return

    if is_report_list_intent(user_query):
        await cl.Message(content=format_report_list_response(user_id), actions=_report_library_actions()).send()
        return

    if is_report_export_intent(user_query):
        report_ticker = resolve_report_ticker(user_query, user_id=user_id)
        await cl.Message(
            content=format_report_export_response(user_query, user_id=user_id),
            actions=_report_actions(report_ticker),
        ).send()
        return

    if is_report_browser_intent(user_query):
        report_ticker = resolve_report_ticker(user_query, user_id=user_id)
        await cl.Message(
            content=format_report_browser_response(user_query, user_id=user_id),
            actions=_report_actions(report_ticker),
        ).send()
        return

    if is_connection_test_intent(user_query):
        await cl.Message(
            content=await _format_settings_for_session(test_connection=True),
            actions=_settings_actions(user_id),
        ).send()
        return

    if is_settings_intent(user_query):
        await cl.Message(content=await _format_settings_for_session(), actions=_settings_actions(user_id)).send()
        return

    if is_preference_intent(user_query) and not any(
        keyword in user_query for keyword in ("分析", "走势", "看看", "研究", "评级")
    ):
        update_preferences_from_query(user_id, user_query)
        await cl.Message(content=format_preferences_response(user_id)).send()
        return

    if is_semantic_memory_intent(user_query):
        await cl.Message(content=format_semantic_memory_response(user_id, user_query)).send()
        return

    if is_watchlist_detail_intent(user_query, user_id=user_id):
        await cl.Message(
            content=format_watchlist_detail_response(user_query, user_id=user_id),
            actions=_watchlist_actions(_top_watchlist_ticker(user_id)),
        ).send()
        return

    if is_watchlist_intent(user_query):
        limit = watchlist_limit_from_query(user_query)
        await cl.Message(
            content=format_watchlist_response(limit=limit, user_id=user_id),
            actions=_watchlist_actions(_top_watchlist_ticker(user_id)),
        ).send()
        return

    entry_route = classify_entry_query(user_query)
    if not entry_route.should_start_research:
        await cl.Message(
            content=entry_route.response,
            actions=_product_landing_actions(user_id),
        ).send()
        return

    await _run_research_flow(user_query, user_id)
