from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from financial_agent.graph.state import ResearchState
from financial_agent.llm import generate_text


REPORT_DIR = Path("outputs/reports")


def _rating_from_state(state: ResearchState) -> tuple[str, int]:
    committee_view = state.get("committee_view", {})
    committee_rating = committee_view.get("rating")
    committee_confidence = committee_view.get("confidence")
    if isinstance(committee_rating, str) and isinstance(committee_confidence, (int, float)):
        return committee_rating, int(committee_confidence)

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


def _format_value(value, suffix: str = "") -> str:
    if value is None or value == "":
        return "N/A"
    return f"{value}{suffix}"


def _format_fundamentals(fundamentals: dict) -> str:
    if not fundamentals:
        return "暂无基本面数据。"
    if not fundamentals.get("ok"):
        return f"基本面数据获取失败：{fundamentals.get('error', '未知错误')}"

    highlights = fundamentals.get("highlights", [])
    risks = fundamentals.get("risks", [])
    highlight_text = "\n".join(f"{idx}. {item}" for idx, item in enumerate(highlights[:4], start=1))
    risk_text = "\n".join(f"{idx}. {item}" for idx, item in enumerate(risks[:4], start=1))

    return f"""- 公司：**{fundamentals.get("company_name") or fundamentals.get("ticker", "N/A")}**
- 行业：**{fundamentals.get("sector") or "N/A"} / {fundamentals.get("industry") or "N/A"}**
- 市值：**{fundamentals.get("market_cap_display") or "N/A"} {fundamentals.get("currency") or ""}**
- Trailing PE / Forward PE：**{_format_value(fundamentals.get("trailing_pe"))} / {_format_value(fundamentals.get("forward_pe"))}**
- PS / PB：**{_format_value(fundamentals.get("price_to_sales"))} / {_format_value(fundamentals.get("price_to_book"))}**
- EPS Trailing / Forward：**{_format_value(fundamentals.get("eps_trailing"))} / {_format_value(fundamentals.get("eps_forward"))}**
- 营收增长：**{_format_value(fundamentals.get("revenue_growth_percent"), "%")}**
- 净利率 / 毛利率：**{_format_value(fundamentals.get("profit_margins_percent"), "%")} / {_format_value(fundamentals.get("gross_margins_percent"), "%")}**
- 分析师目标均价：**{_format_value(fundamentals.get("target_mean_price"))}**
- 一致预期：**{fundamentals.get("recommendation_key") or "N/A"}**
- 财报日期：**{fundamentals.get("earnings_date") or "N/A"} ({fundamentals.get("earnings_date_context") or "unknown"})**

基本面亮点：
{highlight_text or "暂无明确亮点。"}

基本面风险：
{risk_text or "暂无明确风险。"}"""


def _format_review(review: dict) -> str:
    if not review:
        return "暂无历史复盘信息。"
    if not review.get("has_history"):
        return f"{review.get('summary', '暂无历史报告。')}\n\n{review.get('reminder', '')}".strip()
    return f"""- 上次时间：**{review.get("previous_timestamp") or "N/A"}**
- 上次评级：**{review.get("previous_rating") or "N/A"}**
- 上次置信度：**{review.get("previous_confidence") or "N/A"}%**
- 上次价格 / 当前价格：**{review.get("previous_price") or "N/A"} / {review.get("current_price") or "N/A"}**
- 期间涨跌幅：**{review.get("return_percent") if review.get("return_percent") is not None else "N/A"}%**
- 兑现情况：**{review.get("performance_label") or "N/A"}**
- 复盘提醒：{review.get("reminder") or "暂无"}"""


def _format_research_case(title: str, case: dict, secondary_key: str) -> str:
    if not case:
        return f"### {title}\n\n暂无观点。"

    arguments = case.get("arguments", [])
    secondary = case.get(secondary_key, [])
    lines = [
        f"### {title}",
        "",
        f"- 置信度：**{case.get('confidence', 'N/A')}%**",
        f"- 摘要：{case.get('summary', '暂无摘要')}",
    ]
    if arguments:
        lines.append("- 核心论据：")
        lines.extend(f"  {idx}. {arg}" for idx, arg in enumerate(arguments[:4], start=1))
    if secondary:
        label = "薄弱点" if secondary_key == "weak_points" else "反驳点"
        lines.append(f"- {label}：")
        lines.extend(f"  {idx}. {item}" for idx, item in enumerate(secondary[:3], start=1))
    return "\n".join(lines)


def _format_committee_view(committee_view: dict) -> str:
    if not committee_view:
        return "暂无投委会观点。"

    reasons = committee_view.get("key_reasons", [])
    reason_text = "\n".join(f"{idx}. {reason}" for idx, reason in enumerate(reasons[:4], start=1))
    return f"""- 投委会结论：**{committee_view.get("rating", "N/A")}**
- 置信度：**{committee_view.get("confidence", "N/A")}%**
- 多空强度：Bull **{committee_view.get("bull_confidence", "N/A")}%** / Bear **{committee_view.get("bear_confidence", "N/A")}%**
- 关键依据：
{reason_text or "暂无"}
- 最大不确定性：{committee_view.get("uncertainty", "暂无")}"""


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
    review = state.get("review", {})
    technicals = state.get("technicals", {})
    fundamentals = state.get("fundamentals", {})
    risks = state.get("risks", [])
    news = state.get("news", [])
    bull_case = state.get("bull_case", {})
    bear_case = state.get("bear_case", {})
    committee_view = state.get("committee_view", {})
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

### 投委会综合判断

{_format_committee_view(committee_view)}

## 2. 历史复盘

{_format_review(review)}

## 3. 行情摘要

- 最新收盘价：**{price}**
- 最新成交量：**{volume}**
- 近 1 日涨跌幅：**{returns.get("1d", "N/A")}%**
- 近 5 日涨跌幅：**{returns.get("5d", "N/A")}%**
- 近 1 月涨跌幅：**{returns.get("1m", "N/A")}%**
- 近 3 月涨跌幅：**{returns.get("3m", "N/A")}%**

## 4. 技术面判断

- 趋势：**{technicals.get("trend_label", "暂无判断")}**
- MA20：**{technicals.get("ma_20", "N/A")}**
- MA60：**{technicals.get("ma_60", "N/A")}**
- RSI(14)：**{technicals.get("rsi_14", "N/A")}**
- MACD：**{technicals.get("macd_signal_label", "N/A")}**

## 5. 基本面与估值

{_format_fundamentals(fundamentals)}

## 6. 多空观点对比

{_format_research_case("Bull Agent 看多观点", bull_case, "weak_points")}

{_format_research_case("Bear Agent 看空观点", bear_case, "rebuttals")}

## 7. 新闻与催化

{_format_news(news)}

## 8. 主要风险

{risk_text}

## 9. 后续观察指标

1. 后续财报或已发布财报中的收入增速、利润率和管理层指引。
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
        "review": state.get("review"),
        "market_data": state.get("market_data"),
        "technicals": state.get("technicals"),
        "fundamentals": state.get("fundamentals"),
        "news": state.get("news"),
        "risks": state.get("risks"),
        "bull_case": state.get("bull_case"),
        "bear_case": state.get("bear_case"),
        "committee_view": state.get("committee_view"),
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
7. 必须包含“多空观点对比”部分，分别总结 Bull Agent 和 Bear Agent 的论据。
8. 必须包含“投委会综合判断”部分，使用 committee_view 的 rating 和 confidence 作为最终结论。
9. 必须包含“基本面与估值”部分，并说明哪些指标缺失。
10. 如果 earnings_date_context 是 past，不要把 earnings_date 写成“下一次财报”。
11. 如果 review.has_history 为 true，必须包含“历史复盘”部分；如果为 false，说明本次是首条记录。

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
