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
REPORT_TICKER_ALIASES = {
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
VIEWER_SECTIONS = {
    "conclusion": ["投资结论", "核心观点", "投委会综合判断"],
    "market": ["行情摘要", "市场行情", "价格行为"],
    "technical": ["技术面判断", "技术分析"],
    "fundamental": ["基本面与估值"],
    "debate": ["多空观点对比"],
    "news": ["新闻与催化", "资料线索"],
    "risk": ["主要风险", "风险因素"],
    "memory": ["历史记忆参考", "历史复盘"],
    "portfolio": ["组合观察池"],
    "quality": ["质量检查"],
}


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
    lowered = text.lower()
    for alias, ticker in REPORT_TICKER_ALIASES.items():
        if alias in lowered or alias in text:
            return ticker

    match = re.search(r"(?<![A-Za-z0-9.])([A-Za-z]{1,5}(?:\.[A-Za-z])?)(?![A-Za-z0-9.])", text)
    if match:
        candidate = match.group(1).upper()
        if candidate not in {"OPEN", "VIEW", "REPORT"}:
            return candidate
    return ""


def list_reports(
    user_id: str | None = None,
    ticker: str | None = None,
    limit: int = 20,
    include_metadata: bool = False,
) -> list[dict[str, Any]]:
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
        ticker_value = path.stem.split("_", 1)[0] if path.stem else "N/A"
        kind = "质检版" if "_verified_" in path.stem else "初稿"
        updated_at = datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds")
        report = {
            "ticker": ticker_value,
            "kind": kind,
            "updated_at": updated_at,
            "path": str(path),
        }
        if include_metadata:
            report.update(_report_metadata(path, ticker=ticker_value))
        reports.append(report)
    return reports


def _latest_report_path(user_id: str | None = None, ticker: str | None = None) -> Path | None:
    reports = list_reports(user_id, ticker=ticker, limit=1)
    if not reports:
        return None
    return Path(reports[0]["path"])


def _heading_level(line: str) -> int | None:
    match = re.match(r"^(#{2,4})\s+", line)
    if not match:
        return None
    return len(match.group(1))


def _strip_markdown(value: str) -> str:
    cleaned = re.sub(r"<br\s*/?>", "；", value, flags=re.IGNORECASE)
    cleaned = re.sub(r"`([^`]+)`", r"\1", cleaned)
    cleaned = re.sub(r"\*\*([^*]+)\*\*", r"\1", cleaned)
    cleaned = cleaned.replace("&nbsp;", " ")
    return cleaned.strip(" \t\n\r|")


def _normalize_heading(line: str) -> str:
    heading = re.sub(r"^#{1,6}\s*", "", line).strip()
    heading = _strip_markdown(heading).strip("* ")
    return re.sub(r"^\d+\.\s*", "", heading).strip()


def _section(markdown: str, title: str, max_chars: int = 1200) -> str:
    lines = markdown.splitlines()
    start = None
    for idx, line in enumerate(lines):
        if _heading_level(line) is not None and title in _normalize_heading(line):
            start = idx
            break
    if start is None:
        return f"## {title}\n\n暂无。"

    end = len(lines)
    start_level = _heading_level(lines[start]) or 2
    for idx in range(start + 1, len(lines)):
        level = _heading_level(lines[idx])
        if level is not None and level <= start_level:
            end = idx
            break

    content_lines = list(lines[start:end])
    content_lines[0] = f"## {_normalize_heading(content_lines[0])}"
    content = "\n".join(content_lines).strip()
    return _clip(content, max_chars=max_chars)


def _section_body(markdown: str, title: str, max_chars: int = 1200) -> str:
    section = _section(markdown, title, max_chars=max_chars)
    lines = section.splitlines()
    if lines and lines[0].startswith("## "):
        lines = lines[1:]
    return _clip("\n".join(lines).strip(), max_chars=max_chars)


def _first_matching_section(markdown: str, titles: list[str], max_chars: int = 1200) -> str:
    for title in titles:
        section = _section_body(markdown, title, max_chars=max_chars)
        if section != "暂无。":
            return section
    return "暂无。"


def _headings(markdown: str, limit: int = 14) -> list[str]:
    headings: list[str] = []
    for line in markdown.splitlines():
        if _heading_level(line) is not None:
            headings.append(_normalize_heading(line))
    return headings[:limit]


def _clip(text: str, max_chars: int = 900) -> str:
    value = text.strip()
    if len(value) <= max_chars:
        return value or "暂无。"
    return f"{value[: max_chars - 20].rstrip()}\n\n...（已截断）"


def _extract_rating(markdown: str) -> str:
    for label in ("结论", "投委会结论", "评级"):
        value = _extract_pair(markdown, label)
        if value != "N/A":
            for rating in RATING_WORDS:
                if rating in value:
                    return rating
            return value
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
    value = _extract_pair(markdown, "置信度")
    if value != "N/A":
        match = re.search(r"(\d+(?:\.\d+)?)\s*%?", value)
        if match:
            return f"{match.group(1)}%"
        return value
    match = re.search(r"置信度[:：]\s*\*\*?(\d+(?:\.\d+)?)%?\*\*?", markdown)
    if match:
        return f"{match.group(1)}%"
    return "N/A"


def _extract_pair(markdown: str, label: str) -> str:
    compact_label = label.replace(" ", "")
    for line in markdown.splitlines():
        if "|" not in line or label not in line:
            continue
        cells = [_strip_markdown(cell) for cell in line.strip().strip("|").split("|")]
        if not cells or all(re.fullmatch(r":?-{2,}:?", cell.strip()) for cell in cells if cell.strip()):
            continue
        for idx, cell in enumerate(cells[:-1]):
            compact_cell = cell.replace(" ", "")
            if compact_cell == compact_label or compact_label in compact_cell:
                value = cells[idx + 1].strip()
                if value and not re.fullmatch(r":?-{2,}:?", value):
                    return value

    patterns = (
        rf"\|\s*\*\*?{re.escape(label)}\*\*?\s*\|\s*(.*?)\s*\|",
        rf"-\s*{re.escape(label)}[:：]\s*\*\*?([^*\n]+)\*\*?",
        rf"\*\*{re.escape(label)}[:：]\*\*\s*([^\n]+)",
        rf"{re.escape(label)}[:：]\s*\*\*?([^\n*]+)\*\*?",
    )
    for pattern in patterns:
        match = re.search(pattern, markdown)
        if match:
            return _strip_markdown(match.group(1))
    return "N/A"


def _extract_market(markdown: str) -> str:
    return _extract_pair(markdown, "市场")


def _extract_industry(markdown: str) -> str:
    return _extract_pair(markdown, "行业")


def _extract_close(markdown: str) -> str:
    for label in ("最新收盘价", "当前价格"):
        value = _extract_pair(markdown, label)
        if value != "N/A":
            return value
    return "N/A"


def _extract_bull_bear(markdown: str) -> tuple[str, str]:
    match = re.search(
        r"多空强度[:：]\s*Bull\s*\*\*?(\d+(?:\.\d+)?)%?\*\*?\s*/\s*Bear\s*\*\*?(\d+(?:\.\d+)?)%?\*\*?",
        markdown,
        flags=re.IGNORECASE,
    )
    if match:
        return f"{match.group(1)}%", f"{match.group(2)}%"
    return "N/A", "N/A"


def _extract_links(markdown: str, limit: int = 6) -> list[dict[str, str]]:
    links_by_url: dict[str, dict[str, str]] = {}
    lines = markdown.splitlines()
    for idx, line in enumerate(lines):
        for match in re.finditer(r"\[([^\]]+)\]\((https?://[^)]+)\)", line):
            publisher = "N/A"
            published = "N/A"
            for meta in lines[idx + 1 : idx + 3]:
                publisher_match = re.search(r"来源[:：]\s*([^；;\n]+)", meta)
                date_match = re.search(r"日期[:：]\s*([^；;\n]+)", meta)
                if publisher_match:
                    publisher = _strip_markdown(publisher_match.group(1))
                if date_match:
                    published = _strip_markdown(date_match.group(1))
            url = match.group(2).strip()
            current = links_by_url.get(url)
            if current is None:
                links_by_url[url] = {
                    "title": _strip_markdown(match.group(1)),
                    "url": url,
                    "publisher": publisher,
                    "date": published,
                }
                continue
            if current["publisher"] == "N/A" and publisher != "N/A":
                current["publisher"] = publisher
            if current["date"] == "N/A" and published != "N/A":
                current["date"] = published
    return list(links_by_url.values())[:limit]


def _table_cell(value: str) -> str:
    return str(value).replace("|", "/").replace("\n", "<br>")


def _links_table(markdown: str) -> str:
    links = _extract_links(markdown)
    if not links:
        return "暂无可展示链接。"
    rows = [
        "| 标题 | 来源 | 日期 |",
        "|---|---|---|",
    ]
    for link in links:
        rows.append(
            f"| [{_table_cell(link['title'])}]({link['url']}) | "
            f"{_table_cell(link['publisher'])} | {_table_cell(link['date'])} |"
        )
    return "\n".join(rows)


def _metric_table(markdown: str, ticker: str, kind: str, updated_at: str, title: str) -> str:
    bull, bear = _extract_bull_bear(markdown)
    return "\n".join(
        [
            "| 指标 | 值 | 指标 | 值 |",
            "|---|---:|---|---:|",
            f"| Ticker | **{ticker}** | 评级 | **{_extract_rating(markdown)}** |",
            f"| 置信度 | **{_extract_confidence(markdown)}** | 分析周期 | **{_extract_period(markdown)}** |",
            f"| Bull / Bear | **{bull} / {bear}** | 质检状态 | **{_extract_quality_status(markdown)}** |",
            f"| 市场 / 行业 | **{_extract_market(markdown)} / {_extract_industry(markdown)}** | 最新价格 | **{_extract_close(markdown)}** |",
            f"| 类型 | **{kind}** | 更新时间 | **{updated_at}** |",
            f"| 标题 | **{_table_cell(title)}** | 文件 | `{ticker}` report |",
        ]
    )


def _extract_period(markdown: str) -> str:
    value = _extract_pair(markdown, "分析周期")
    if value != "N/A":
        return value
    match = re.search(r"分析周期[:：]\s*\*\*([^*]+)\*\*", markdown)
    if match:
        return _strip_markdown(match.group(1))
    return "N/A"


def _extract_quality_status(markdown: str) -> str:
    section = _section(markdown, "质量检查", max_chars=600)
    value = _extract_pair(section, "状态")
    if value != "N/A":
        return value
    match = re.search(r"状态[:：]\s*\*\*([^*]+)\*\*", section)
    if match:
        return _strip_markdown(match.group(1))
    return "N/A"


def _report_title(markdown: str, fallback: str) -> str:
    for line in markdown.splitlines():
        if re.match(r"^#{1,4}\s+", line):
            title = _normalize_heading(line)
            if title and not title.startswith("质量检查"):
                return title
    return fallback


def _report_metadata(path: Path, ticker: str) -> dict[str, str]:
    try:
        markdown = path.read_text(encoding="utf-8")
    except OSError as exc:
        return {
            "title": f"{ticker} 报告",
            "rating": "N/A",
            "confidence": "N/A",
            "period": "N/A",
            "quality_status": f"读取失败：{exc}",
            "close": "N/A",
            "link_count": "0",
        }

    return {
        "title": _report_title(markdown, fallback=f"{ticker} 报告"),
        "rating": _extract_rating(markdown),
        "confidence": _extract_confidence(markdown),
        "period": _extract_period(markdown),
        "quality_status": _extract_quality_status(markdown),
        "close": _extract_close(markdown),
        "link_count": str(len(_extract_links(markdown, limit=20))),
    }


def _key_value_block(markdown: str, labels: list[str], max_chars: int = 900) -> str:
    rows: list[str] = []
    for label in labels:
        value = _extract_pair(markdown, label)
        if value != "N/A":
            rows.append(f"- **{label}**：{value}")
    return _clip("\n".join(rows), max_chars=max_chars)


def _next_actions(ticker: str) -> str:
    safe_ticker = ticker if ticker and ticker != "N/A" else "NVDA"
    return f"""## 下一步动作

- `帮我重新分析 {safe_ticker}，重点看估值压力和观点变化`
- `以前分析过 {safe_ticker} 吗`
- `为什么 {safe_ticker} 在观察池`
- `打开 {safe_ticker} 报告`
- `报告列表`
- `投研工作台`
- `查看观察池`"""


def _viewer_block(title: str, body: str) -> str:
    return f"## {title}\n\n{body or '暂无。'}"


def format_report_browser_response(query: str, user_id: str | None = None) -> str:
    safe_id = safe_user_id(user_id)
    ticker = _extract_ticker(query)
    path = _latest_report_path(safe_id, ticker=ticker or None)
    if path is None:
        target = f" `{ticker}`" if ticker else ""
        return f"""没有找到{target} 的本地报告。

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
    conclusion = _first_matching_section(markdown, VIEWER_SECTIONS["conclusion"], max_chars=1400)
    market = _first_matching_section(markdown, VIEWER_SECTIONS["market"], max_chars=900)
    technical = _first_matching_section(markdown, VIEWER_SECTIONS["technical"], max_chars=900)
    fundamental = _first_matching_section(markdown, VIEWER_SECTIONS["fundamental"], max_chars=1000)
    debate = _first_matching_section(markdown, VIEWER_SECTIONS["debate"], max_chars=1100)
    risk = _first_matching_section(markdown, VIEWER_SECTIONS["risk"], max_chars=900)
    if risk == "暂无。":
        risk = _key_value_block(markdown, ["风险因素", "主要风险", "后续观察指标"], max_chars=900)
    memory = _first_matching_section(markdown, VIEWER_SECTIONS["memory"], max_chars=1000)
    portfolio = _first_matching_section(markdown, VIEWER_SECTIONS["portfolio"], max_chars=800)
    quality = _first_matching_section(markdown, VIEWER_SECTIONS["quality"], max_chars=900)

    return "\n\n".join(
        [
            f"# {ticker} 报告阅读页",
            f"> {title}",
            f"用户：`{safe_id}`  |  文件：`{path}`",
            "## 结论面板\n\n" + _metric_table(markdown, ticker=ticker, kind=kind, updated_at=updated_at, title=title),
            _viewer_block("投资结论", conclusion),
            _viewer_block("市场与技术", f"### 行情\n\n{market}\n\n### 技术\n\n{technical}"),
            _viewer_block("基本面与估值", fundamental),
            _viewer_block("多空与投委会", debate),
            _viewer_block("风险与观察指标", risk),
            _viewer_block("新闻线索", _links_table(markdown)),
            _viewer_block("历史记忆与观察池", f"### 历史记忆\n\n{memory}\n\n### 观察池\n\n{portfolio}"),
            _viewer_block("质量检查", quality),
            f"## 正文目录\n\n{headings_text or '暂无目录。'}",
            _next_actions(ticker),
        ]
    )


def resolve_report_ticker(query: str, user_id: str | None = None) -> str:
    safe_id = safe_user_id(user_id)
    ticker = _extract_ticker(query)
    path = _latest_report_path(safe_id, ticker=ticker or None)
    if path is not None and path.stem:
        return path.stem.split("_", 1)[0]
    return ticker or "NVDA"


def format_report_list_response(user_id: str | None = None, limit: int = 10) -> str:
    safe_id = safe_user_id(user_id)
    reports = list_reports(safe_id, limit=limit, include_metadata=True)
    if not reports:
        return f"""# 报告库

`{safe_id}` 还没有本地报告。

## 开始生成

- `帮我分析一下 NVDA 未来一个月走势`
- `帮我分析一下闪迪今天走势`
- `投研工作台`
- `模型设置`"""

    latest = reports[0]

    lines = [
        "# 报告库",
        "",
        f"> 已保存 **{len(reports)}** 份最近报告，优先展示质检版；复制“打开方式”即可进入报告阅读页。",
        "",
        "| 指标 | 值 | 指标 | 值 |",
        "|---|---:|---|---:|",
        f"| 用户 | `{safe_id}` | 报告目录 | `{user_reports_dir(safe_id)}` |",
        f"| 最新标的 | **{latest['ticker']}** | 最新结论 | **{latest.get('rating', 'N/A')} / {latest.get('confidence', 'N/A')}** |",
        f"| 质检状态 | **{latest.get('quality_status', 'N/A')}** | 打开最新 | `打开最近报告` |",
        "",
        "## 最近报告",
        "",
        "| 报告 | 结论 | 质量与线索 | 打开 |",
        "|---|---|---|---|",
    ]
    for report in reports:
        ticker = report["ticker"]
        title = _clip(str(report.get("title") or f"{ticker} 报告"), max_chars=90).replace("\n", " ")
        lines.append(
            "| "
            f"**{ticker}**<br>{_table_cell(title)}<br>`{report['updated_at']}` | "
            f"评级 **{_table_cell(report.get('rating', 'N/A'))}**<br>"
            f"置信度 **{_table_cell(report.get('confidence', 'N/A'))}**<br>"
            f"周期 `{_table_cell(report.get('period', 'N/A'))}`<br>"
            f"价格 `{_table_cell(report.get('close', 'N/A'))}` | "
            f"{_table_cell(report['kind'])}<br>"
            f"质检 **{_table_cell(report.get('quality_status', 'N/A'))}**<br>"
            f"链接 `{_table_cell(report.get('link_count', '0'))}` 条 | "
            f"`打开 {ticker} 报告` |"
        )
    lines.extend(
        [
            "",
            "## 下一步动作",
            "",
            "- `打开最近报告`",
            f"- `帮我重新分析 {latest['ticker']}，重点看估值压力和观点变化`",
            f"- `以前分析过 {latest['ticker']} 吗`",
            "- `投研工作台`",
            "- `查看观察池`",
        ]
    )
    return "\n".join(lines)
