from __future__ import annotations

import chainlit as cl

from financial_agent.graph.workflow import build_research_graph
from financial_agent.help import HELP_MESSAGE, is_help_intent
from financial_agent.tools.charting import build_price_chart


AGENT_TITLES = {
    "coordinator": "Coordinator Agent",
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
        reason_text = "\n".join(f"{idx}. {reason}" for idx, reason in enumerate(reasons, start=1))
        return (
            f"投委会结论：**{view.get('rating', 'N/A')}**；"
            f"置信度：**{view.get('confidence', 'N/A')}%**。\n\n"
            f"多空强度：Bull **{view.get('bull_confidence', 'N/A')}%** / "
            f"Bear **{view.get('bear_confidence', 'N/A')}%**\n\n"
            f"关键依据：\n{reason_text or '暂无'}\n\n"
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


@cl.on_chat_start
async def on_chat_start() -> None:
    await cl.Message(content=HELP_MESSAGE).send()


@cl.on_message
async def on_message(message: cl.Message) -> None:
    user_query = message.content.strip()
    if not user_query:
        await cl.Message(content="请输入一个股票分析问题，比如：`分析一下 AAPL 最近走势`。").send()
        return

    if is_help_intent(user_query):
        await cl.Message(content=HELP_MESSAGE).send()
        return

    graph = build_research_graph()
    latest_state: dict = {}

    await cl.Message(content="收到，我会让几个 Agent 依次完成投研流程。").send()

    try:
        async for event in graph.astream(
            {
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
