from __future__ import annotations

import chainlit as cl

from financial_agent.graph.workflow import build_research_graph
from financial_agent.tools.charting import build_price_chart


AGENT_TITLES = {
    "coordinator": "Coordinator Agent",
    "market": "Market Agent",
    "technical": "Technical Agent",
    "news_risk": "News & Risk Agent",
    "report": "Report Agent",
}


def _brief_update(node_name: str, update: dict) -> str:
    if node_name == "coordinator":
        ticker = update.get("ticker") or "未识别"
        horizon = update.get("horizon") or "默认周期"
        return f"已识别标的：**{ticker}**；分析周期：**{horizon}**。"

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
        return f"已整理 **{len(news)}** 条新闻线索和 **{len(risks)}** 条主要风险。"

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
