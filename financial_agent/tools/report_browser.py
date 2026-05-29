from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any

from financial_agent.tools.memory import safe_user_id, user_reports_dir


REPORT_BROWSER_KEYWORDS = [
    "打开最近报告",
    "查看最近报告",
    "最近报告",
    "最新报告",
    "报告详情",
    "阅读报告",
    "打开报告",
    "查看报告",
    "report browser",
]

REPORT_LIST_KEYWORDS = ["报告列表", "所有报告", "查看报告列表", "列出报告", "reports"]

REPORT_ACTION_KEYWORDS = ["打开", "查看", "最近", "最新", "详情", "阅读"]

RATING_WORDS = ["中性偏多", "中性偏空", "偏多", "偏空", "中性"]


def is_report_browser_intent(text: str) -> bool:
    normalized = text.strip().lower()
    if not normalized:
        return False
    compact = "".join(normalized.split())
    if any(keyword.lower().replace(" ", "") in compact for keyword in REPORT_BROWSER_KEYWORDS):
        return True
    return "报告" in compact and any(keyword in compact for keyword in REPORT_ACTION_KEYWORDS)


def is_report_list_intent(text: str) -> bool:
    normalized = text.strip().lower()
    if not normalized:
        return False
    compact = "".join(normalized.split())
    return any(keyword.lower().replace(" ", "") in compact for keyword in REPORT_LIST_KEYWORDS)


def _safe_ticker(ticker: str) -> str:
    return "".join(ch for ch in ticker.upper() if ch.isalnum() or ch in {".", "-"})


def _extract_ticker(text: str) -> str:
    match = re.search(r"(?<![A-Za-z0-9.])([A-Za-z]{1,5}(?:\.[A-Za-z])?)(?![A-Za-z0-9.])", text)
    if match:
        candidate = match.group(1).upper()
        if candidate not in {"OPEN", "VIEW", "REPORT"}:
            return candidate
    return ""


def list_reports(user_id: str | None = None, ticker: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
    reports_dir = user_reports_dir(user_id)
    if not reports_dir.exists():
        return []

    safe_ticker = _safe_ticker(ticker or "")
    files = [path for path in reports_dir.glob("*.md") if path.is_file()]
    if safe_ticker:
        files = [path for path in files if _safe_ticker(path.stem.split("_", 1)[0]) == safe_ticker]

    files.sort(
        key=lambda path: (
            path.stat().st_mtime,
            1 if "_verified_" in path.stem else 0,
        ),
        reverse=True,
    )

    reports: list[dict[str, Any]] = []
    for path in files[: max(0, limit)]:
        reports.append(
            {
                "ticker": path.stem.split("_", 1)[0] if path.stem else "N/A",
                "kind": "质检版" if "_verified_" in path.stem else "初稿",
                "updated_at": datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds"),
                "path": str(path),
            }
        )
    return reports


def _latest_report_path(user_id: str | None = None, ticker: str | None = None) -> Path | None:
    reports = list_reports(user_id, ticker=ticker, limit=1)
    if not reports:
        return None
    return Path(reports[0]["path"])


def _section(markdown: str, title: str, max_chars: int = 1200) -> str:
    lines = markdown.splitlines()
    start = None
    for idx, line in enumerate(lines):
        if line.startswith("## ") and title in line:
            start = idx
            break
    if start is None:
        return f"## {title}\n\n暂无。"

    end = len(lines)
    for idx in range(start + 1, len(lines)):
        if lines[idx].startswith("## "):
            end = idx
            break

    content = "\n".join(lines[start:end]).strip()
    return _clip(content, max_chars=max_chars)


def _headings(markdown: str, limit: int = 14) -> list[str]:
    headings: list[str] = []
    for line in markdown.splitlines():
        if line.startswith("## "):
            heading = line.replace("#", "").strip()
            heading = re.sub(r"^\d+\.\s*", "", heading)
            headings.append(heading)
    return headings[:limit]


def _clip(text: str, max_chars: int = 900) -> str:
    value = text.strip()
    if len(value) <= max_chars:
        return value or "暂无。"
    return f"{value[: max_chars - 20].rstrip()}\n\n...（已截断）"


def _extract_rating(markdown: str) -> str:
    for pattern in (
        r"结论[:：]\s*\*\*([^*]+)\*\*",
        r"投委会结论[:：]\s*\*\*([^*]+)\*\*",
        r"评级[:：]\s*\*\*([^*]+)\*\*",
    ):
        match = re.search(pattern, markdown)
        if match:
            value = match.group(1).strip()
            for rating in RATING_WORDS:
                if rating in value:
                    return rating
            return value
    for rating in RATING_WORDS:
        if rating in markdown[:1500]:
            return rating
    return "N/A"


def _extract_confidence(markdown: str) -> str:
    match = re.search(r"置信度[:：]\s*\*\*?(\d+(?:\.\d+)?)%?\*\*?", markdown)
    if match:
        return f"{match.group(1)}%"
    return "N/A"


def _extract_period(markdown: str) -> str:
    match = re.search(r"分析周期[:：]\s*\*\*([^*]+)\*\*", markdown)
    if match:
        return match.group(1).strip()
    return "N/A"


def _extract_quality_status(markdown: str) -> str:
    section = _section(markdown, "质量检查", max_chars=600)
    match = re.search(r"状态[:：]\s*\*\*([^*]+)\*\*", section)
    if match:
        return match.group(1).strip()
    return "N/A"


def _report_title(markdown: str, fallback: str) -> str:
    for line in markdown.splitlines():
        if line.startswith("# "):
            return line.replace("#", "", 1).strip()
    return fallback


def _next_actions(ticker: str) -> str:
    safe_ticker = ticker if ticker and ticker != "N/A" else "NVDA"
    return f"""## 下一步动作

- `帮我重新分析 {safe_ticker}，重点看估值压力和观点变化`
- `以前分析过 {safe_ticker} 吗`
- `为什么 {safe_ticker} 是核心跟踪`
- `投研工作台`
- `查看观察池`"""


def format_report_browser_response(query: str, user_id: str | None = None) -> str:
    safe_id = safe_user_id(user_id)
    ticker = _extract_ticker(query)
    path = _latest_report_path(safe_id, ticker=ticker or None)
    if path is None:
        target = f" `{ticker}`" if ticker else ""
        return f"""没有找到{target}的本地报告。

你可以先运行一次完整分析，系统会在 Report Agent 和 Verifier Agent 阶段保存 Markdown 报告。

可复制：
`帮我分析一下 {ticker or "NVDA"} 未来一个月走势`"""

    markdown = path.read_text(encoding="utf-8")
    ticker = path.stem.split("_", 1)[0] if path.stem else ticker or "N/A"
    kind = "质检版" if "_verified_" in path.stem else "初稿"
    updated_at = datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds")
    title = _report_title(markdown, fallback=f"{ticker} 报告详情")
    headings = _headings(markdown)
    headings_text = "\n".join(f"{idx}. {heading}" for idx, heading in enumerate(headings, start=1))

    return "\n\n".join(
        [
            f"# {ticker} 报告详情",
            f"- 用户：`{safe_id}`\n- 标题：**{title}**\n- 类型：**{kind}**\n- 更新时间：**{updated_at}**\n- 文件：`{path}`",
            "## 顶部摘要\n\n"
            f"- 评级：**{_extract_rating(markdown)}**\n"
            f"- 置信度：**{_extract_confidence(markdown)}**\n"
            f"- 分析周期：**{_extract_period(markdown)}**\n"
            f"- 质检状态：**{_extract_quality_status(markdown)}**",
            f"## 正文目录\n\n{headings_text or '暂无目录。'}",
            _section(markdown, "投资结论", max_chars=1100),
            _section(markdown, "历史记忆参考", max_chars=1100),
            _section(markdown, "质量检查", max_chars=900),
            _section(markdown, "资料线索", max_chars=900),
            _next_actions(ticker),
        ]
    )


def format_report_list_response(user_id: str | None = None, limit: int = 10) -> str:
    safe_id = safe_user_id(user_id)
    reports = list_reports(safe_id, limit=limit)
    if not reports:
        return f"`{safe_id}` 还没有本地报告。"

    lines = [
        "# 最近报告",
        "",
        f"- 用户：`{safe_id}`",
        f"- 报告目录：`{user_reports_dir(safe_id)}`",
        "",
        "| 时间 | Ticker | 类型 | 打开方式 | 路径 |",
        "|---|---|---|---|---|",
    ]
    for report in reports:
        ticker = report["ticker"]
        lines.append(
            "| "
            f"{report['updated_at']} | "
            f"{ticker} | "
            f"{report['kind']} | "
            f"`打开 {ticker} 报告` | "
            f"`{report['path']}` |"
        )
    return "\n".join(lines)
