from __future__ import annotations

import chainlit as cl

from financial_agent.graph.workflow import build_research_graph
from financial_agent.tools.charting import build_price_chart


AGENT_TITLES = {
    "coordinator": "Coordinator Agent",
    "market": "Market Agent",
    "technical": "Technical Agent",
    "news_risk": "News & Risk Agent",
    "bull": "Bull Agent",
    "bear": "Bear Agent",
    "committee": "Committee Agent",
    "report": "Report Agent",
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

    if node_name == "technical":
        technicals = update.get("technicals", {})
        return (
            f"技术面判断：**{technicals.get('trend_label', '暂无判断')}**；"
            f"RSI：**{technicals.get('rsi_14', 'N/A')}**；"
            f"MACD 信号：**{technicals.get('macd_signal_label', 'N/A')}**。"
        )

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

    if node_name == "report":
        return "中文投研报告已生成。"

    return "节点已完成。"


@cl.on_chat_start
async def on_chat_start() -> None:
    await cl.Message(
        content=(
            "你好，我是一个多 Agent 投研助手 MVP。\n\n"
            "你可以这样问：`帮我分析一下 NVDA 未来一个月走势`。"
        )
    ).send()


@cl.on_message
async def on_message(message: cl.Message) -> None:
    user_query = message.content.strip()
    if not user_query:
        await cl.Message(content="请输入一个股票分析问题，比如：`分析一下 AAPL 最近走势`。").send()
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
