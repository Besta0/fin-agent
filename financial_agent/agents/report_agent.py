from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from financial_agent.graph.state import ResearchState
from financial_agent.llm import generate_text


REPORT_DIR = Path("outputs/reports")


def _rating_from_state(state: ResearchState) -> tuple[str, int]:
    market_data = state.get("market_data", {})
    technicals = state.get("technicals", {})
    returns = market_data.get("returns", {})
    score = 0

    one_month = returns.get("1m")
    if isinstance(one_month, (int, float)):
        if one_month > 5:
            score += 1
        elif one_month < -5:
            score -= 1

    trend = technicals.get("trend_label", "")
    if "偏强" in trend:
        score += 1
    if "偏弱" in trend:
        score -= 1

    rsi = technicals.get("rsi_14")
    if isinstance(rsi, (int, float)):
        if rsi >= 75:
            score -= 1
        elif 45 <= rsi <= 65:
            score += 1

    if score >= 2:
        return "偏多", 68
    if score <= -2:
        return "偏空", 66
    if score == 1:
        return "中性偏多", 62
    if score == -1:
        return "中性偏空", 60
    return "中性", 55


def _format_news(news: list[dict]) -> str:
    if not news:
        return "暂无可用新闻数据。"

    lines = []
    for item in news[:5]:
        title = item.get("title", "Untitled")
        publisher = item.get("publisher", "Unknown")
        published = item.get("published") or "日期未知"
        link = item.get("link", "")
        title_text = f"[{title}]({link})" if link else title
        lines.append(f"- {title_text} ({publisher}, {published})")
    return "\n".join(lines)


def _source_links_section(news: list[dict]) -> str:
    if not news:
        return ""

    lines = ["## 资料线索"]
    for idx, item in enumerate(news[:6], start=1):
        title = item.get("title") or "Untitled"
        publisher = item.get("publisher") or "Unknown"
        published = item.get("published") or "日期未知"
        link = item.get("link") or ""
        title_text = f"[{title}]({link})" if link else title
        lines.append(f"{idx}. {title_text}\n   来源：{publisher}；日期：{published}")
    return "\n".join(lines)


def _append_source_links(report: str, news: list[dict]) -> str:
    section = _source_links_section(news)
    if not section or "## 资料线索" in report:
        return report
    return f"{report.rstrip()}\n\n{section}"


def _fallback_report(state: ResearchState) -> str:
    ticker = state.get("ticker") or "N/A"
    company_name = state.get("company_name") or ticker
    horizon = state.get("horizon", "1 month")
    market_data = state.get("market_data", {})
    technicals = state.get("technicals", {})
    risks = state.get("risks", [])
    news = state.get("news", [])
    rating, confidence = _rating_from_state(state)

    returns = market_data.get("returns", {})
    price = market_data.get("last_close", "N/A")
    volume = market_data.get("last_volume", "N/A")

    risk_text = "\n".join(f"{idx}. {risk}" for idx, risk in enumerate(risks[:5], start=1))

    return f"""# {company_name} ({ticker}) 多 Agent 投研报告

> 本报告由多 Agent MVP 自动生成，仅用于研究和学习，不构成投资建议。

## 1. 投资结论

- 结论：**{rating}**
- 置信度：**{confidence}%**
- 分析周期：**{horizon}**

## 2. 行情摘要

- 最新收盘价：**{price}**
- 最新成交量：**{volume}**
- 近 1 日涨跌幅：**{returns.get("1d", "N/A")}%**
- 近 5 日涨跌幅：**{returns.get("5d", "N/A")}%**
- 近 1 月涨跌幅：**{returns.get("1m", "N/A")}%**
- 近 3 月涨跌幅：**{returns.get("3m", "N/A")}%**

## 3. 技术面判断

- 趋势：**{technicals.get("trend_label", "暂无判断")}**
- MA20：**{technicals.get("ma_20", "N/A")}**
- MA60：**{technicals.get("ma_60", "N/A")}**
- RSI(14)：**{technicals.get("rsi_14", "N/A")}**
- MACD：**{technicals.get("macd_signal_label", "N/A")}**

## 4. 新闻与催化

{_format_news(news)}

## 5. 主要风险

{risk_text}

## 6. 后续观察指标

1. 下一次财报中的收入增速、利润率和管理层指引。
2. 股价能否站稳关键均线，以及成交量是否配合。
3. 分析师评级、监管政策和行业需求是否出现方向性变化。
4. 若短期涨幅较大，需要观察获利盘压力和估值消化情况。
"""


def _build_llm_prompt(state: ResearchState, fallback_rating: str, confidence: int) -> str:
    payload = {
        "ticker": state.get("ticker"),
        "company_name": state.get("company_name"),
        "market": state.get("market"),
        "horizon": state.get("horizon"),
        "market_data": state.get("market_data"),
        "technicals": state.get("technicals"),
        "news": state.get("news"),
        "risks": state.get("risks"),
        "fallback_rating": fallback_rating,
        "confidence": confidence,
    }

    return f"""你是一个严谨的中文投研报告写作 Agent。

请基于下面的结构化数据，生成一份中文短线投研报告。要求：
1. 不要编造数据；没有数据就明确说明。
2. 结论必须是 偏多 / 中性偏多 / 中性 / 中性偏空 / 偏空 之一。
3. 必须包含置信度、核心理由、风险因素和后续观察指标。
4. 语气专业克制，不要给出直接买卖指令。
5. 明确写出“仅用于研究，不构成投资建议”。
6. 新闻与催化部分如果有 link 字段，必须保留为 Markdown 链接。

结构化数据：
```json
{json.dumps(payload, ensure_ascii=False, indent=2)}
```
"""


async def report_node(state: ResearchState) -> ResearchState:
    fallback = _fallback_report(state)
    rating, confidence = _rating_from_state(state)
    prompt = _build_llm_prompt(state, rating, confidence)
    final_report = await generate_text(prompt, fallback=fallback)
    final_report = _append_source_links(final_report, state.get("news", []))

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    ticker = state.get("ticker") or "unknown"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = REPORT_DIR / f"{ticker}_{timestamp}.md"
    report_path.write_text(final_report, encoding="utf-8")

    return {
        "final_report": f"{final_report}\n\n---\n报告已保存到 `{report_path}`。",
        "agent_notes": [
            *state.get("agent_notes", []),
            {
                "agent": "Report Agent",
                "summary": f"Generated final report for {ticker}.",
            },
        ],
    }
