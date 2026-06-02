from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from financial_agent.tools.memory import USERS_DIR, safe_user_id, user_dir


AGENT_FLOW = [
    ("coordinator", "Coordinator", "任务分派", "识别 ticker、公司、市场和分析周期"),
    ("memory", "Memory", "记忆检索", "读取用户偏好、历史 thesis 和语义记忆"),
    ("market", "Market", "行情数据", "获取价格、成交量和阶段涨跌幅"),
    ("review", "Review", "历史复盘", "对比上次评级、价格和观点兑现情况"),
    ("technical", "Technical", "技术面", "计算均线、RSI、MACD 和趋势状态"),
    ("fundamental", "Fundamental", "基本面", "整理估值、盈利能力、增长和分析师预期"),
    ("news_risk", "News Risk", "新闻风险", "整理新闻线索和风险清单"),
    ("bull", "Bull", "看多分析师", "提炼看多论据、置信度和薄弱点"),
    ("bear", "Bear", "看空分析师", "提炼看空论据、置信度和反驳点"),
    ("committee", "Committee", "投委会", "裁决多空分歧并给出最终评级"),
    ("portfolio", "Portfolio", "观察池", "更新优先级、组合角色和跟踪理由"),
    ("report", "Report", "报告撰写", "生成中文投研报告"),
    ("verifier", "Verifier", "质量检查", "检查报告和结构化数据一致性"),
    ("history", "History", "沉淀归档", "保存历史记录、语义记忆和向量记忆"),
]

AGENT_BY_NODE = {node: {"name": name, "role": role, "mission": mission} for node, name, role, mission in AGENT_FLOW}
AGENT_INDEX = {node: idx for idx, (node, *_rest) in enumerate(AGENT_FLOW)}

RUN_DASHBOARD_KEYWORDS = [
    "agent看板",
    "agent 看板",
    "协作看板",
    "运行看板",
    "多agent看板",
    "多 agent 看板",
    "查看agent",
    "查看 agent",
    "agent dashboard",
    "run dashboard",
]

DEBATE_KEYWORDS = [
    "多空辩论",
    "辩论区",
    "bull bear",
    "bull/bear",
    "投委会辩论",
    "看多看空",
]


def is_run_dashboard_intent(text: str) -> bool:
    normalized = text.strip().lower()
    if not normalized:
        return False
    compact = "".join(normalized.split())
    return any("".join(keyword.lower().split()) in compact for keyword in RUN_DASHBOARD_KEYWORDS)


def is_debate_dashboard_intent(text: str) -> bool:
    normalized = text.strip().lower()
    if not normalized:
        return False
    compact = "".join(normalized.split())
    return any("".join(keyword.lower().split()) in compact for keyword in DEBATE_KEYWORDS)


def user_runs_dir(user_id: str | None = None) -> Path:
    return user_dir(user_id) / "runs"


def _run_path(user_id: str | None, run_id: str) -> Path:
    safe_run_id = "".join(ch for ch in str(run_id) if ch.isalnum() or ch in {"-", "_"})[:64]
    return user_runs_dir(user_id) / f"{safe_run_id or 'unknown'}.json"


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _json_default(value: Any) -> str:
    return str(value)


def _write_run(record: dict[str, Any]) -> None:
    path = _run_path(record.get("user_id"), record.get("run_id", "unknown"))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2, default=_json_default), encoding="utf-8")


def load_run(user_id: str | None = None, run_id: str | None = None) -> dict[str, Any] | None:
    if run_id:
        path = _run_path(user_id, run_id)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
        return data if isinstance(data, dict) else None

    return load_latest_run(user_id)


def load_latest_run(user_id: str | None = None) -> dict[str, Any] | None:
    directory = user_runs_dir(user_id)
    if not directory.exists():
        return None
    candidates = sorted(directory.glob("*.json"), key=lambda path: path.stat().st_mtime, reverse=True)
    for path in candidates:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if isinstance(data, dict):
            return data
    return None


def list_run_users() -> list[dict[str, Any]]:
    if not USERS_DIR.exists():
        return []

    users: list[dict[str, Any]] = []
    for directory in sorted(USERS_DIR.iterdir(), key=lambda path: path.name):
        runs_dir = directory / "runs"
        if not directory.is_dir() or not runs_dir.exists():
            continue
        run_count = len(list(runs_dir.glob("*.json")))
        if run_count <= 0:
            continue
        latest = load_latest_run(directory.name)
        users.append(
            {
                "user_id": directory.name,
                "run_count": run_count,
                "latest_run_id": latest.get("run_id") if latest else None,
                "latest_updated_at": latest.get("updated_at") if latest else None,
            }
        )
    return users


def list_runs(user_id: str | None = None, limit: int = 30) -> list[dict[str, Any]]:
    directory = user_runs_dir(user_id)
    if not directory.exists():
        return []

    rows: list[dict[str, Any]] = []
    candidates = sorted(directory.glob("*.json"), key=lambda path: path.stat().st_mtime, reverse=True)
    for path in candidates[:limit]:
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if not isinstance(record, dict):
            continue
        rows.append(
            {
                "run_id": record.get("run_id"),
                "status": record.get("status"),
                "ticker": record.get("ticker"),
                "company_name": record.get("company_name"),
                "horizon": record.get("horizon"),
                "rating": record.get("rating"),
                "confidence": record.get("confidence"),
                "user_query": record.get("user_query"),
                "created_at": record.get("created_at"),
                "updated_at": record.get("updated_at"),
                "event_count": len(record.get("events") or []),
            }
        )
    return rows


def run_dashboard_payload(user_id: str | None = None, run_id: str | None = None) -> dict[str, Any]:
    safe_id = safe_user_id(user_id)
    run = load_run(safe_id, run_id)
    return {
        "user_id": safe_id,
        "users": list_run_users(),
        "runs": list_runs(safe_id),
        "run": run,
        "agent_flow": [
            {"node": node, "name": name, "role": role, "mission": mission}
            for node, name, role, mission in AGENT_FLOW
        ],
    }


def create_run_record(user_id: str | None, user_query: str) -> dict[str, Any]:
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:8]
    safe_id = safe_user_id(user_id)
    record = {
        "run_id": run_id,
        "user_id": safe_id,
        "user_query": user_query,
        "status": "running",
        "created_at": _now(),
        "updated_at": _now(),
        "finished_at": None,
        "current_node": AGENT_FLOW[0][0],
        "ticker": None,
        "company_name": None,
        "horizon": None,
        "rating": None,
        "confidence": None,
        "report_path": None,
        "events": [],
        "errors": [],
    }
    _write_run(record)
    return record


def _sanitize_value(value: Any, depth: int = 0) -> Any:
    if depth > 5:
        return _truncate_text(str(value), 240)
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return _truncate_text(value, 1600)
    if isinstance(value, list):
        items = [_sanitize_value(item, depth + 1) for item in value[:8]]
        if len(value) > 8:
            items.append({"truncated_items": len(value) - 8})
        return items
    if isinstance(value, dict):
        output: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            if key_text in {"agent_notes"}:
                continue
            if key_text in {"prices", "price_history", "price_series", "historical_prices"} and isinstance(item, list):
                output[key_text] = {"items": len(item), "sample": _sanitize_value(item[-3:], depth + 1)}
                continue
            output[key_text] = _sanitize_value(item, depth + 1)
        return output
    return _truncate_text(str(value), 600)


def _truncate_text(text: str, limit: int = 600) -> str:
    value = str(text or "").replace("\x00", "").strip()
    if len(value) <= limit:
        return value
    return value[: limit - 3] + "..."


def _event_output(node_name: str, update: dict[str, Any]) -> dict[str, Any]:
    if node_name == "coordinator":
        return {
            "intent": update.get("intent"),
            "ticker": update.get("ticker"),
            "company_name": update.get("company_name"),
            "market": update.get("market"),
            "horizon": update.get("horizon"),
            "should_continue": update.get("should_continue"),
            "direct_response": update.get("direct_response"),
            "ticker_resolution": update.get("ticker_resolution"),
        }

    if node_name == "memory":
        memory = update.get("memory_context") or {}
        guidance = memory.get("memory_guidance") or {}
        return {
            "preference_updates": memory.get("preference_updates"),
            "ticker_history_count": len(memory.get("ticker_history") or []),
            "semantic_memory_count": len(memory.get("semantic_memories") or []),
            "focus_points": guidance.get("focus_points"),
            "known_risks": guidance.get("known_risks"),
            "previous_thesis": guidance.get("previous_thesis"),
        }

    if node_name == "market":
        market = update.get("market_data") or {}
        return {
            "ok": market.get("ok"),
            "error": market.get("error"),
            "last_close": market.get("last_close"),
            "last_volume": market.get("last_volume"),
            "returns": market.get("returns"),
            "fifty_two_week_low": market.get("fifty_two_week_low"),
            "fifty_two_week_high": market.get("fifty_two_week_high"),
        }

    if node_name == "review":
        return update.get("review") or {}

    if node_name == "technical":
        tech = update.get("technicals") or {}
        return {
            "trend_label": tech.get("trend_label"),
            "rsi_14": tech.get("rsi_14"),
            "macd": tech.get("macd"),
            "macd_signal": tech.get("macd_signal"),
            "macd_signal_label": tech.get("macd_signal_label"),
            "ma_20": tech.get("ma_20"),
            "ma_60": tech.get("ma_60"),
        }

    if node_name == "fundamental":
        fundamentals = update.get("fundamentals") or {}
        return {
            "ok": fundamentals.get("ok"),
            "error": fundamentals.get("error"),
            "company_name": fundamentals.get("company_name"),
            "sector": fundamentals.get("sector"),
            "industry": fundamentals.get("industry"),
            "market_cap_display": fundamentals.get("market_cap_display"),
            "trailing_pe": fundamentals.get("trailing_pe"),
            "forward_pe": fundamentals.get("forward_pe"),
            "revenue_growth_percent": fundamentals.get("revenue_growth_percent"),
            "profit_margins_percent": fundamentals.get("profit_margins_percent"),
            "recommendation_key": fundamentals.get("recommendation_key"),
            "highlights": fundamentals.get("highlights"),
            "risks": fundamentals.get("risks"),
        }

    if node_name == "news_risk":
        return {
            "news_count": len(update.get("news") or []),
            "news": [
                {
                    "title": item.get("title"),
                    "publisher": item.get("publisher"),
                    "published": item.get("published"),
                    "link": item.get("link"),
                }
                for item in (update.get("news") or [])[:6]
            ],
            "risks": update.get("risks") or [],
        }

    if node_name == "bull":
        return update.get("bull_case") or {}

    if node_name == "bear":
        return update.get("bear_case") or {}

    if node_name == "committee":
        return update.get("committee_view") or {}

    if node_name == "portfolio":
        portfolio = update.get("portfolio") or {}
        current = portfolio.get("current_item") or {}
        return {
            "priority_label": portfolio.get("priority_label"),
            "priority_score": portfolio.get("priority_score"),
            "portfolio_role": portfolio.get("portfolio_role"),
            "watchlist_size": portfolio.get("watchlist_size"),
            "watch_reasons": current.get("watch_reasons"),
            "top_items": portfolio.get("top_items"),
        }

    if node_name == "report":
        return {
            "final_report_preview": _truncate_text(update.get("final_report") or "", 1200),
        }

    if node_name == "verifier":
        return update.get("verification") or {}

    if node_name == "history":
        return update.get("history_record") or {}

    return _sanitize_value(update)


def _next_node(node_name: str) -> str | None:
    index = AGENT_INDEX.get(node_name)
    if index is None:
        return None
    if index + 1 >= len(AGENT_FLOW):
        return None
    return AGENT_FLOW[index + 1][0]


def append_run_event(
    user_id: str | None,
    run_id: str,
    node_name: str,
    summary: str,
    update: dict[str, Any],
) -> dict[str, Any]:
    record = load_run(user_id, run_id)
    if not record:
        record = create_run_record(user_id, update.get("user_query") or "")
        record["run_id"] = run_id

    event = {
        "index": len(record.get("events") or []) + 1,
        "node": node_name,
        "agent_name": AGENT_BY_NODE.get(node_name, {}).get("name", node_name),
        "role": AGENT_BY_NODE.get(node_name, {}).get("role", "Agent"),
        "status": "completed",
        "summary": summary,
        "finished_at": _now(),
        "output": _sanitize_value(_event_output(node_name, update)),
    }
    record.setdefault("events", []).append(event)
    record["updated_at"] = _now()
    record["current_node"] = _next_node(node_name)
    record["ticker"] = update.get("ticker") or record.get("ticker")
    record["company_name"] = update.get("company_name") or record.get("company_name")
    record["horizon"] = update.get("horizon") or record.get("horizon")
    committee = update.get("committee_view") or {}
    if committee:
        record["rating"] = committee.get("rating") or record.get("rating")
        record["confidence"] = committee.get("confidence") or record.get("confidence")
    verification = update.get("verification") or {}
    history = update.get("history_record") or {}
    record["report_path"] = (
        verification.get("report_path")
        or history.get("report_path")
        or record.get("report_path")
    )
    errors = update.get("errors")
    if errors:
        record.setdefault("errors", []).extend(errors)
    _write_run(record)
    return record


def complete_run_record(
    user_id: str | None,
    run_id: str,
    latest_state: dict[str, Any],
    status: str = "completed",
) -> dict[str, Any] | None:
    record = load_run(user_id, run_id)
    if not record:
        return None
    record["status"] = status
    record["updated_at"] = _now()
    record["finished_at"] = _now()
    record["current_node"] = None
    record["ticker"] = latest_state.get("ticker") or record.get("ticker")
    record["company_name"] = latest_state.get("company_name") or record.get("company_name")
    record["horizon"] = latest_state.get("horizon") or record.get("horizon")
    committee = latest_state.get("committee_view") or {}
    if committee:
        record["rating"] = committee.get("rating") or record.get("rating")
        record["confidence"] = committee.get("confidence") or record.get("confidence")
    verification = latest_state.get("verification") or {}
    history = latest_state.get("history_record") or {}
    record["report_path"] = (
        verification.get("report_path")
        or history.get("report_path")
        or record.get("report_path")
    )
    _write_run(record)
    return record


def fail_run_record(user_id: str | None, run_id: str, error: str) -> dict[str, Any] | None:
    record = load_run(user_id, run_id)
    if not record:
        return None
    record["status"] = "failed"
    record["updated_at"] = _now()
    record["finished_at"] = _now()
    record["current_node"] = None
    record.setdefault("errors", []).append(error)
    _write_run(record)
    return record


def _events_by_node(record: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {event.get("node"): event for event in record.get("events") or []}


def _status_for_node(record: dict[str, Any], node: str) -> str:
    events = _events_by_node(record)
    if node in events:
        return "已完成"
    if record.get("status") == "failed" and node == record.get("current_node"):
        return "出错"
    if record.get("status") == "running" and node == record.get("current_node"):
        return "工作中"
    if record.get("status") in {"completed", "stopped", "failed"}:
        return "未运行"
    return "等待中"


def _table_cell(value: Any) -> str:
    text = str(value if value is not None and value != "" else "N/A")
    return text.replace("|", "/").replace("\n", "<br>")


def _run_status_label(status: Any) -> str:
    return {
        "running": "运行中",
        "completed": "已完成",
        "stopped": "已早停",
        "failed": "出错",
    }.get(str(status or ""), str(status or "N/A"))


def _top_panel(record: dict[str, Any]) -> str:
    return f"""| 项目 | 当前值 | 项目 | 当前值 |
|---|---|---|---|
| Run ID | `{record.get("run_id", "N/A")}` | 状态 | **{_run_status_label(record.get("status"))}** |
| 标的 | **{record.get("ticker") or "识别中"}** | 公司 | **{record.get("company_name") or "N/A"}** |
| 周期 | **{record.get("horizon") or "N/A"}** | 结论 | **{record.get("rating") or "待投委会"}** |
| 置信度 | **{record.get("confidence") or "N/A"}** | 报告 | `{record.get("report_path") or "尚未生成"}` |
| 创建时间 | **{record.get("created_at") or "N/A"}** | 更新时间 | **{record.get("updated_at") or "N/A"}** |"""


def format_live_run_board(record: dict[str, Any]) -> str:
    events = _events_by_node(record)
    rows = [
        "| 顺序 | Agent | 角色 | 状态 | 最新输出 |",
        "|---:|---|---|---|---|",
    ]
    for idx, (node, name, role, _mission) in enumerate(AGENT_FLOW, start=1):
        event = events.get(node, {})
        rows.append(
            "| "
            f"{idx} | "
            f"**{name}** | "
            f"{role} | "
            f"**{_status_for_node(record, node)}** | "
            f"{_table_cell(_truncate_text(event.get('summary') or AGENT_BY_NODE[node]['mission'], 96))} |"
        )

    recent = record.get("events", [])[-4:]
    recent_lines = "\n".join(
        f"{event.get('index')}. **{event.get('agent_name')}**：{event.get('summary')}"
        for event in recent
    )
    if not recent_lines:
        recent_lines = "等待第一个 Agent 输出。"

    return "\n\n".join(
        [
            "# Multi-Agent 协作看板",
            f"> 用户问题：{record.get('user_query') or 'N/A'}",
            _top_panel(record),
            "## Agent 工作状态",
            "\n".join(rows),
            "## 最新协作动态",
            recent_lines,
        ]
    )


def _format_output_block(output: Any) -> str:
    if output is None:
        return "暂无结构化输出。"
    if isinstance(output, dict):
        lines = []
        for key, value in output.items():
            if isinstance(value, list):
                if not value:
                    lines.append(f"- {key}: 暂无")
                else:
                    lines.append(f"- {key}:")
                    for idx, item in enumerate(value[:6], start=1):
                        lines.append(f"  {idx}. {_truncate_text(json.dumps(item, ensure_ascii=False), 220)}")
            elif isinstance(value, dict):
                lines.append(f"- {key}: `{_truncate_text(json.dumps(value, ensure_ascii=False), 360)}`")
            else:
                lines.append(f"- {key}: **{_table_cell(value)}**")
        return "\n".join(lines) or "暂无结构化输出。"
    return _truncate_text(str(output), 1200)


def format_run_dashboard_response(user_id: str | None = None, run_id: str | None = None) -> str:
    record = load_run(user_id, run_id)
    if not record:
        return """# Agent 协作看板

还没有可展示的运行记录。先完成一次分析，例如：

`帮我分析一下 NVDA 未来一个月走势`"""

    sections = [format_live_run_board(record), "## Agent 详情"]
    events = _events_by_node(record)
    for node, name, role, mission in AGENT_FLOW:
        event = events.get(node)
        if not event:
            sections.append(f"### {name} - {role}\n\n状态：**{_status_for_node(record, node)}**\n\n任务：{mission}")
            continue
        sections.append(
            f"### {name} - {role}\n\n"
            f"- 状态：**已完成**\n"
            f"- 完成时间：**{event.get('finished_at', 'N/A')}**\n"
            f"- 摘要：{event.get('summary') or '暂无'}\n\n"
            f"关键输出：\n{_format_output_block(event.get('output'))}"
        )
    return "\n\n".join(sections)


def _find_event(record: dict[str, Any], node: str) -> dict[str, Any]:
    return _events_by_node(record).get(node, {})


def _case_lines(case: dict[str, Any], secondary_key: str) -> str:
    if not case:
        return "暂无。"
    lines = [
        f"- 置信度：**{case.get('confidence', 'N/A')}%**",
        f"- 摘要：{case.get('summary') or '暂无'}",
    ]
    arguments = case.get("arguments") or []
    if arguments:
        lines.append("- 核心论据：")
        lines.extend(f"  {idx}. {item}" for idx, item in enumerate(arguments[:5], start=1))
    secondary = case.get(secondary_key) or []
    if secondary:
        label = "薄弱点" if secondary_key == "weak_points" else "反驳点"
        lines.append(f"- {label}：")
        lines.extend(f"  {idx}. {item}" for idx, item in enumerate(secondary[:4], start=1))
    return "\n".join(lines)


def format_debate_dashboard_response(user_id: str | None = None, run_id: str | None = None) -> str:
    record = load_run(user_id, run_id)
    if not record:
        return """# 多空辩论区

还没有可展示的运行记录。先完成一次分析，例如：

`帮我分析一下 NVDA 未来一个月走势`"""

    bull = _find_event(record, "bull").get("output") or {}
    bear = _find_event(record, "bear").get("output") or {}
    committee = _find_event(record, "committee").get("output") or {}
    reasons = committee.get("key_reasons") or []
    reason_text = "\n".join(f"{idx}. {item}" for idx, item in enumerate(reasons[:6], start=1)) or "暂无。"
    memory = committee.get("memory_influence") or {}

    return f"""# 多空辩论区

> Run `{record.get("run_id")}` / 标的：**{record.get("ticker") or "N/A"}**

| 角色 | 核心结论 | 置信度 |
|---|---|---:|
| Bull Agent | {_table_cell(bull.get("summary") or "暂无")} | {_table_cell(bull.get("confidence"))}% |
| Bear Agent | {_table_cell(bear.get("summary") or "暂无")} | {_table_cell(bear.get("confidence"))}% |
| Committee Agent | **{_table_cell(committee.get("rating") or record.get("rating"))}** | {_table_cell(committee.get("confidence") or record.get("confidence"))}% |

## Bull Agent 看多观点

{_case_lines(bull, "weak_points")}

## Bear Agent 看空观点

{_case_lines(bear, "rebuttals")}

## Committee Agent 裁决

- 最终评级：**{committee.get("rating") or record.get("rating") or "N/A"}**
- 最终置信度：**{committee.get("confidence") or record.get("confidence") or "N/A"}%**
- 多空强度：Bull **{committee.get("bull_confidence", "N/A")}%** / Bear **{committee.get("bear_confidence", "N/A")}%**
- 记忆影响：{memory.get("summary") or "暂无历史记忆影响。"}
- 最大不确定性：{committee.get("uncertainty") or "暂无"}

关键依据：
{reason_text}
"""
