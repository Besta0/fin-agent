from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from financial_agent.graph.state import ResearchState
from financial_agent.tools.memory import user_reports_dir


PROHIBITED_ADVICE = [
    "建议买入",
    "强烈买入",
    "立即买入",
    "应该买入",
    "建议加仓",
    "应该加仓",
    "满仓",
    "梭哈",
]


RATING_ORDER = ["偏多", "中性偏多", "中性", "中性偏空", "偏空"]
RATING_MATCH_ORDER = sorted(RATING_ORDER, key=len, reverse=True)


def _issue(severity: str, category: str, message: str) -> dict[str, str]:
    return {"severity": severity, "category": category, "message": message}


def _status_from_issues(issues: list[dict[str, str]]) -> str:
    severities = {issue["severity"] for issue in issues}
    if "high" in severities:
        return "fail"
    if severities:
        return "warning"
    return "pass"


def _format_verification(verification: dict[str, Any]) -> str:
    status_label = {
        "pass": "通过",
        "warning": "需注意",
        "fail": "未通过",
    }.get(verification.get("status"), "未知")

    issues = verification.get("issues", [])
    suggestions = verification.get("suggestions", [])
    issue_text = "\n".join(
        f"{idx}. [{issue.get('severity')}] {issue.get('message')}"
        for idx, issue in enumerate(issues, start=1)
    )
    suggestion_text = "\n".join(
        f"{idx}. {suggestion}" for idx, suggestion in enumerate(suggestions, start=1)
    )

    return f"""## 质量检查

- 状态：**{status_label}**
- 检查项：评级一致性、关键数字、财报日期语义、投资建议措辞、资料线索、记忆引用

发现问题：
{issue_text or "未发现明显问题。"}

建议：
{suggestion_text or "暂无。"}"""


def _check_rating(report: str, state: ResearchState, issues: list[dict[str, str]]) -> None:
    expected = state.get("committee_view", {}).get("rating")
    if not expected:
        return

    if expected not in report:
        issues.append(
            _issue(
                "high",
                "rating_consistency",
                f"投委会评级为 {expected}，但报告正文没有出现该评级。",
            )
        )
        return

    conclusion_lines = [
        line
        for line in report.splitlines()
        if any(keyword in line for keyword in ("最终评级", "投委会评级", "结论", "评级："))
        and "分析师" not in line
    ]
    contradictory = []
    for line in conclusion_lines:
        remaining = line
        for rating in RATING_MATCH_ORDER:
            if rating in remaining:
                if rating != expected:
                    contradictory.append(rating)
                remaining = remaining.replace(rating, "")
    if contradictory:
        issues.append(
            _issue(
                "medium",
                "rating_consistency",
                f"最终结论相关行中出现了其他评级词：{', '.join(sorted(set(contradictory)))}。请确认是否为多空讨论而非最终结论。",
            )
        )


def _check_numbers(report: str, state: ResearchState, issues: list[dict[str, str]]) -> None:
    market_data = state.get("market_data", {})
    technicals = state.get("technicals", {})
    fundamentals = state.get("fundamentals", {})

    expected_numbers = [
        ("最新收盘价", market_data.get("last_close")),
        ("RSI", technicals.get("rsi_14")),
        ("Forward PE", fundamentals.get("forward_pe")),
        ("营收增长", fundamentals.get("revenue_growth_percent")),
        ("净利率", fundamentals.get("profit_margins_percent")),
    ]
    for label, value in expected_numbers:
        if isinstance(value, (int, float)):
            value_text = str(value)
            if value_text not in report:
                issues.append(
                    _issue(
                        "low",
                        "number_reference",
                        f"结构化数据中 {label}={value_text}，报告未直接引用该数值。",
                    )
                )


def _check_missing_fields(report: str, state: ResearchState, issues: list[dict[str, str]]) -> None:
    fundamentals = state.get("fundamentals", {})
    missing_fields = [
        ("trailing_pe", "Trailing PE"),
        ("forward_pe", "Forward PE"),
        ("price_to_sales", "PS"),
        ("revenue_growth_percent", "营收增长"),
        ("profit_margins_percent", "净利率"),
    ]
    for key, label in missing_fields:
        if fundamentals.get(key) is None:
            pattern = rf"{re.escape(label)}[^。\n]*\d"
            if re.search(pattern, report, flags=re.IGNORECASE):
                issues.append(
                    _issue(
                        "high",
                        "missing_data",
                        f"{label} 在结构化数据中缺失，但报告似乎引用了具体数值。",
                    )
                )


def _check_earnings_date(report: str, state: ResearchState, issues: list[dict[str, str]]) -> None:
    fundamentals = state.get("fundamentals", {})
    if fundamentals.get("earnings_date_context") != "past":
        return

    suspicious_patterns = ["下一次财报", "即将公布的财报", "即将发布的财报", "未来财报日期"]
    sentences = re.split(r"[。！？\n]", report)
    found: list[str] = []
    for sentence in sentences:
        if any(negation in sentence for negation in ("不涉及", "不是", "不要", "不会", "不能", "不应")):
            continue
        for pattern in suspicious_patterns:
            if pattern in sentence:
                found.append(pattern)
    if found:
        issues.append(
            _issue(
                "high",
                "date_consistency",
                f"财报日期上下文为 past，但报告出现未来财报表述：{', '.join(sorted(set(found)))}。",
            )
        )


def _check_advice_language(report: str, issues: list[dict[str, str]]) -> None:
    found: list[str] = []
    sentences = re.split(r"[。！？\n]", report)
    for sentence in sentences:
        if any(context in sentence for context in ("分析师", "一致预期", "共识", "评级为", "评级")):
            continue
        for phrase in PROHIBITED_ADVICE:
            if phrase in sentence:
                found.append(phrase)
    if found:
        issues.append(
            _issue(
                "high",
                "investment_advice",
                f"报告出现可能构成直接投资建议的措辞：{', '.join(sorted(set(found)))}。",
            )
        )


def _check_sources(report: str, state: ResearchState, issues: list[dict[str, str]]) -> None:
    news = state.get("news", [])
    has_links = any(item.get("link") for item in news)
    if has_links and "## 资料线索" not in report:
        issues.append(
            _issue(
                "medium",
                "source_links",
                "新闻数据包含链接，但报告没有资料线索章节。",
            )
        )


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _check_memory_references(report: str, state: ResearchState, issues: list[dict[str, str]]) -> None:
    memory_context = state.get("memory_context", {})
    references = memory_context.get("report_references") or []
    if not references:
        return

    if "历史记忆参考" not in report:
        issues.append(
            _issue(
                "medium",
                "memory_reference",
                "Memory Agent 提供了可引用历史记忆，但报告缺少“历史记忆参考”部分。",
            )
        )

    report_paths = [
        str(memory.get("report_path"))
        for memory in references
        if memory.get("report_path") and str(memory.get("report_path")) != "N/A"
    ]
    if report_paths and not any(path in report for path in report_paths):
        issues.append(
            _issue(
                "medium",
                "memory_reference",
                "报告引用历史记忆时没有保留旧报告路径，用户难以追溯来源。",
            )
        )

    threshold = _as_float(memory_context.get("memory_guidance", {}).get("report_reference_threshold"), 0.35)
    low_score_refs = [
        memory
        for memory in references
        if memory.get("score") is not None and _as_float(memory.get("score")) < threshold
    ]
    ticker = str(state.get("ticker") or "").upper()
    unsupported = [
        memory
        for memory in low_score_refs
        if str(memory.get("ticker") or "").upper() != ticker
    ]
    if unsupported:
        issues.append(
            _issue(
                "medium",
                "memory_reference",
                "报告引用列表包含低相似度且非同 ticker 的记忆，请确认是否应降级为内部参考。",
            )
        )


def _build_suggestions(issues: list[dict[str, str]]) -> list[str]:
    if not issues:
        return []

    suggestions: list[str] = []
    categories = {issue["category"] for issue in issues}
    if "rating_consistency" in categories:
        suggestions.append("确认最终结论以 Committee Agent 的 rating 为准，并把多空讨论与最终评级区分开。")
    if "missing_data" in categories:
        suggestions.append("缺失字段只能写“暂无数据”或“未提供”，不要补写具体数值。")
    if "date_consistency" in categories:
        suggestions.append("财报日期若已过去，应写成“最近一次财报”或“已发布财报”。")
    if "investment_advice" in categories:
        suggestions.append("将直接买卖措辞改成研究性表达，例如“评级偏多/中性/偏空”。")
    if "source_links" in categories:
        suggestions.append("保留资料线索章节，方便用户追溯新闻来源。")
    if "memory_reference" in categories:
        suggestions.append("历史记忆进入报告正文时，应写明摘要、相似度、检索后端和旧报告路径。")
    if "number_reference" in categories:
        suggestions.append("低优先级：可补充关键结构化数值，让报告更可核验。")
    return suggestions


def _save_verified_report(ticker: str, report: str, user_id: str | None = None) -> str:
    report_dir = user_reports_dir(user_id)
    report_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = report_dir / f"{ticker}_verified_{timestamp}.md"
    report_path.write_text(report, encoding="utf-8")
    return str(report_path)


async def verifier_node(state: ResearchState) -> ResearchState:
    report = state.get("final_report", "")
    issues: list[dict[str, str]] = []

    if not report:
        issues.append(_issue("high", "report_missing", "未生成最终报告，无法进行质量检查。"))
    else:
        _check_rating(report, state, issues)
        _check_numbers(report, state, issues)
        _check_missing_fields(report, state, issues)
        _check_earnings_date(report, state, issues)
        _check_advice_language(report, issues)
        _check_sources(report, state, issues)
        _check_memory_references(report, state, issues)

    verification = {
        "status": _status_from_issues(issues),
        "issues": issues,
        "suggestions": _build_suggestions(issues),
    }

    verification_section = _format_verification(verification)
    final_report = f"{report.rstrip()}\n\n{verification_section}" if report else verification_section
    ticker = state.get("ticker") or "unknown"
    verified_path = _save_verified_report(ticker, final_report, user_id=state.get("user_id"))
    verification["report_path"] = verified_path

    return {
        "verification": verification,
        "final_report": f"{final_report}\n\n---\n质检后报告已保存到 `{verified_path}`。",
        "agent_notes": [
            *state.get("agent_notes", []),
            {
                "agent": "Verifier Agent",
                "summary": f"Verification status={verification['status']}, issues={len(issues)}.",
            },
        ],
    }
