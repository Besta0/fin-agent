from __future__ import annotations

import chainlit as cl
from chainlit.input_widget import Select, TextInput

from financial_agent.graph.workflow import build_research_graph
from financial_agent.help import HELP_MESSAGE, is_help_intent
from financial_agent.tools.charting import build_price_chart
from financial_agent.tools.dashboard import format_dashboard_response, is_dashboard_intent
from financial_agent.tools.memory import (
    format_preferences_response,
    format_semantic_memory_response,
    is_preference_intent,
    is_semantic_memory_intent,
    safe_user_id,
    update_preferences_from_query,
)
from financial_agent.tools.report_browser import (
    format_report_browser_response,
    format_report_list_response,
    is_report_browser_intent,
    is_report_list_intent,
)
from financial_agent.tools.settings_panel import (
    format_settings_response,
    is_connection_test_intent,
    is_settings_intent,
)
from financial_agent.settings import PROVIDER_DEFAULTS, settings
from financial_agent.tools.watchlist import (
    format_watchlist_detail_response,
    format_watchlist_response,
    is_watchlist_detail_intent,
    is_watchlist_intent,
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

QUICK_ACTION_DEFS = [
    (
        "settings",
        "模型设置",
        "查看当前 provider、model、base_url 和 API key 状态",
        "settings",
    ),
    (
        "connection_test",
        "测试连接",
        "发起一次最小 LLM 请求，验证当前模型配置",
        "plug",
    ),
    (
        "xiaomi",
        "小米配置",
        "查看 Xiaomi MiMo 的配置模板",
        "cpu",
    ),
    (
        "dashboard",
        "投研工作台",
        "打开观察池、记忆库和最近报告总览",
        "layout-dashboard",
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


async def _send_settings_widgets() -> None:
    provider_values = list(PROVIDER_DEFAULTS.keys())
    provider = settings.llm_provider if settings.llm_provider in provider_values else "openai"
    initial_index = provider_values.index(provider)

    await cl.ChatSettings(
        [
            Select(
                id="llm_provider_view",
                label="当前 Provider（来自 .env，只读）",
                values=provider_values,
                initial_index=initial_index,
                disabled=True,
            ),
            TextInput(
                id="llm_provider_label_view",
                label="Provider 名称",
                initial=_provider_label(settings.llm_provider),
                disabled=True,
            ),
            TextInput(
                id="llm_model_view",
                label="当前模型",
                initial=settings.llm_model,
                disabled=True,
            ),
            TextInput(
                id="llm_base_url_view",
                label="Base URL",
                initial=settings.llm_base_url or "N/A",
                disabled=True,
            ),
            TextInput(
                id="llm_key_status_view",
                label="API Key 状态",
                initial=f"{_mask_api_key(settings.llm_api_key)}；来源：{settings.llm_api_key_source or 'N/A'}",
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


@cl.set_starters
async def set_starters():
    return [
        cl.Starter(
            label="模型设置",
            message="模型设置",
            icon="settings",
        ),
        cl.Starter(
            label="测试模型连接",
            message="测试模型连接",
            icon="plug",
        ),
        cl.Starter(
            label="小米 MiMo 配置",
            message="小米配置",
            icon="cpu",
        ),
        cl.Starter(
            label="投研工作台",
            message="投研工作台",
            icon="layout-dashboard",
        ),
        cl.Starter(
            label="分析英伟达",
            message="分析一下英伟达最近走势",
            icon="search",
        ),
    ]


@cl.on_chat_start
async def on_chat_start() -> None:
    await _send_settings_widgets()
    await cl.Message(
        content=(
            "欢迎使用 Fin Agent。你可以直接点下面的快捷按钮，"
            "也可以在左侧/顶部的设置面板查看当前模型配置。\n\n"
            f"{HELP_MESSAGE}"
        ),
        actions=_quick_actions(),
    ).send()


@cl.action_callback("quick_action")
async def on_quick_action(action: cl.Action) -> None:
    intent = action.payload.get("intent")
    user_id = _current_user_id()

    if intent == "settings":
        await cl.Message(content=await format_settings_response()).send()
        return

    if intent == "connection_test":
        await cl.Message(content=await format_settings_response(test_connection=True)).send()
        return

    if intent == "xiaomi":
        await cl.Message(content=await format_settings_response()).send()
        return

    if intent == "dashboard":
        await cl.Message(content=format_dashboard_response(user_id)).send()
        return


@cl.on_message
async def on_message(message: cl.Message) -> None:
    user_query = message.content.strip()
    user_id = _current_user_id()
    if not user_query:
        await cl.Message(content="请输入一个股票分析问题，比如：`分析一下 AAPL 最近走势`。").send()
        return

    if is_help_intent(user_query):
        await cl.Message(content=HELP_MESSAGE).send()
        return

    if is_dashboard_intent(user_query):
        await cl.Message(content=format_dashboard_response(user_id)).send()
        return

    if is_report_list_intent(user_query):
        await cl.Message(content=format_report_list_response(user_id)).send()
        return

    if is_report_browser_intent(user_query):
        await cl.Message(content=format_report_browser_response(user_query, user_id=user_id)).send()
        return

    if is_connection_test_intent(user_query):
        await cl.Message(content=await format_settings_response(test_connection=True)).send()
        return

    if is_settings_intent(user_query):
        await cl.Message(content=await format_settings_response()).send()
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
        await cl.Message(content=format_watchlist_detail_response(user_query, user_id=user_id)).send()
        return

    if is_watchlist_intent(user_query):
        limit = watchlist_limit_from_query(user_query)
        await cl.Message(content=format_watchlist_response(limit=limit, user_id=user_id)).send()
        return

    graph = build_research_graph()
    latest_state: dict = {}

    await cl.Message(content="收到，我先判断问题类型和标的。").send()

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
                await cl.Message(
                    author=AGENT_TITLES.get(node_name, node_name),
                    content=_brief_update(node_name, update),
                ).send()
    except Exception as exc:
        await cl.Message(content=f"运行 Agent 流程时出错：`{exc}`").send()
        return

    if latest_state.get("direct_response"):
        return

    final_report = latest_state.get("final_report")
    if not final_report:
        await cl.Message(content="报告生成失败，请检查 ticker 或数据源连接。").send()
        return

    chart = build_price_chart(
        latest_state.get("market_data", {}),
        latest_state.get("technicals", {}),
    )
    elements = []
    if chart is not None:
        elements.append(cl.Plotly(name="price_chart", figure=chart, display="inline"))

    await cl.Message(content=final_report, elements=elements).send()
