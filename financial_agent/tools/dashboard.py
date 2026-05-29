from __future__ import annotations

from datetime import datetime
from typing import Any

from financial_agent.tools.memory import (
    load_semantic_memories,
    safe_user_id,
    user_reports_dir,
    user_semantic_memory_path,
)
from financial_agent.tools.vector_memory import (
    count_vector_memories,
    recent_vector_memories,
    vector_memory_path,
)
from financial_agent.tools.watchlist import load_watchlist


DASHBOARD_KEYWORDS = [
    "/dashboard",
    "dashboard",
    "投研工作台",
    "工作台",
    "仪表盘",
    "看板",
    "总览",
    "项目首页",
    "打开工作台",
    "打开dashboard",
]


def is_dashboard_intent(text: str) -> bool:
    normalized = text.strip().lower()
    if not normalized:
        return False
    compact = "".join(normalized.split())
    return any(keyword.lower() in compact for keyword in DASHBOARD_KEYWORDS)


def _display(value: Any, fallback: str = "N/A") -> str:
    if value is None or value == "":
        return fallback
    return str(value)


def _format_percent(value: Any) -> str:
    if isinstance(value, (int, float)):
        return f"{value}%"
    return "N/A"


def _truncate(text: Any, limit: int = 42) -> str:
    value = str(text or "").replace("\n", " ").strip()
    if len(value) <= limit:
        return value or "暂无"
    return f"{value[:limit - 1]}..."


def _recent_reports(user_id: str | None = None, limit: int = 5) -> list[dict[str, str]]:
    reports_dir = user_reports_dir(user_id)
    if not reports_dir.exists():
        return []

    files = sorted(
        reports_dir.glob("*.md"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    reports: list[dict[str, str]] = []
    for path in files[:limit]:
        stem = path.stem
        ticker = stem.split("_", 1)[0] if stem else "N/A"
        kind = "质检版" if "_verified_" in stem else "初稿"
        reports.append(
            {
                "ticker": ticker,
                "kind": kind,
                "updated_at": datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds"),
                "path": str(path),
            }
        )
    return reports


def _watchlist_section(user_id: str | None = None, limit: int = 8) -> str:
    watchlist = load_watchlist(user_id)
    items = watchlist.get("items", [])[:limit]
    if not items:
        return """## 观察池

当前观察池还是空的。先分析一只股票，Portfolio Agent 会自动把它加入观察池。

可复制：
`帮我分析一下 NVDA 未来一个月走势`"""

    lines = [
        "## 观察池",
        "",
        f"- 更新时间：**{watchlist.get('updated_at') or 'N/A'}**",
        f"- 标的数量：**{len(watchlist.get('items', []))}**",
        "",
        "| 排名 | Ticker | 公司 | 优先级 | 分数 | 评级 | 置信度 | 组合角色 | 近1月 |",
        "|---:|---|---|---|---:|---|---:|---|---:|",
    ]
    for idx, item in enumerate(items, start=1):
        returns = item.get("returns") or {}
        lines.append(
            "| "
            f"{idx} | "
            f"{_display(item.get('ticker'))} | "
            f"{_truncate(item.get('company_name'), 18)} | "
            f"{_display(item.get('priority_label'))} | "
            f"{_display(item.get('priority_score'))} | "
            f"{_display(item.get('rating'))} | "
            f"{_display(item.get('confidence'))}% | "
            f"{_display(item.get('portfolio_role'))} | "
            f"{_format_percent(returns.get('1m'))} |"
        )
    return "\n".join(lines)


def _memory_section(user_id: str | None = None, limit: int = 5) -> str:
    vector_count = count_vector_memories(user_id)
    semantic_count = len(load_semantic_memories(user_id))
    recent = recent_vector_memories(user_id, limit=limit)

    lines = [
        "## 记忆库",
        "",
        f"- SQLite 向量记忆：**{vector_count}** 条",
        f"- JSONL 语义备份：**{semantic_count}** 条",
        f"- SQLite 文件：`{vector_memory_path(user_id)}`",
        f"- JSONL 文件：`{user_semantic_memory_path(user_id)}`",
        "",
    ]
    if not recent:
        lines.append("暂无 SQLite 向量记忆。完成一次股票分析后，History Agent 会自动写入。")
        return "\n".join(lines)

    lines.extend(
        [
            "| 时间 | Ticker | 评级 | 置信度 | 摘要 | 报告 |",
            "|---|---|---|---:|---|---|",
        ]
    )
    for memory in recent:
        report_path = memory.get("report_path") or "N/A"
        lines.append(
            "| "
            f"{_display(memory.get('timestamp'))} | "
            f"{_display(memory.get('ticker'))} | "
            f"{_display(memory.get('rating'))} | "
            f"{_display(memory.get('confidence'))}% | "
            f"{_truncate(memory.get('summary'), 48)} | "
            f"`{report_path}` |"
        )
    return "\n".join(lines)


def _reports_section(user_id: str | None = None, limit: int = 5) -> str:
    reports = _recent_reports(user_id, limit=limit)
    lines = [
        "## 最近报告",
        "",
        f"- 报告目录：`{user_reports_dir(user_id)}`",
        "",
    ]
    if not reports:
        lines.append("暂无本地报告。完成一次投研流程后会自动生成 Markdown 报告。")
        return "\n".join(lines)

    lines.extend(
        [
            "| 时间 | Ticker | 类型 | 路径 |",
            "|---|---|---|---|",
        ]
    )
    for report in reports:
        lines.append(
            "| "
            f"{report['updated_at']} | "
            f"{report['ticker']} | "
            f"{report['kind']} | "
            f"`{report['path']}` |"
        )
    return "\n".join(lines)


def _next_actions_section(user_id: str | None = None) -> str:
    items = load_watchlist(user_id).get("items", [])
    ticker = str(items[0].get("ticker")) if items else "NVDA"
    return f"""## 下一步动作

可复制到输入框：

- `帮我重新分析 {ticker}，重点看估值压力和观点变化`
- `为什么 {ticker} 是核心跟踪`
- `以前分析过 {ticker} 吗`
- `查看观察池`

工作台刷新：

- `投研工作台`
- `/dashboard`"""


def format_dashboard_response(user_id: str | None = None) -> str:
    safe_id = safe_user_id(user_id)
    generated_at = datetime.now().isoformat(timespec="seconds")
    return "\n\n".join(
        [
            "# Fin Agent 投研工作台",
            f"- 用户：`{safe_id}`\n- 生成时间：**{generated_at}**",
            _watchlist_section(safe_id),
            _memory_section(safe_id),
            _reports_section(safe_id),
            _next_actions_section(safe_id),
        ]
    )
