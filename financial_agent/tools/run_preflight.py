from __future__ import annotations

from typing import Any

from financial_agent.entry_router import PRODUCT_ACTIONS, classify_entry_query, resolve_research_target
from financial_agent.tools.dashboard_settings import load_user_model_settings
from financial_agent.tools.run_dashboard import AGENT_FLOW


def run_preflight_payload(query: str, user_id: str | None = None) -> dict[str, Any]:
    text = str(query or "").strip()
    route = classify_entry_query(text)
    settings = load_user_model_settings(user_id)
    target = resolve_research_target(text)
    warnings: list[str] = []
    actions = list(route.actions)

    model_ready = bool(settings.get("api_key_configured"))
    if route.should_start_research and not model_ready:
        warnings.append("当前用户未配置 API Key，建议先完成模型设置和连接测试。")
        actions = [
            {"label": "打开模型设置", "kind": "settings", "value": "模型设置"},
            {"label": "测试连接", "kind": "settings", "value": "测试连接"},
            *actions,
        ]

    can_start = bool(route.should_start_research and model_ready)
    if route.should_start_research and model_ready:
        actions = [
            {"label": "启动研究", "kind": "start", "value": text},
            {"label": "打开模型设置", "kind": "settings", "value": "模型设置"},
        ]

    if not text:
        warnings.append("请输入股票研究问题。")

    summary = _summary_for_preflight(route.route, target, settings, can_start, model_ready)
    return {
        "ok": True,
        "query": text,
        "route": route.route,
        "reason": route.reason,
        "can_start": can_start,
        "summary": summary,
        "message": route.response,
        "target": target,
        "model": {
            "provider": settings.get("provider"),
            "provider_label": settings.get("provider_label"),
            "model": settings.get("model"),
            "base_url": settings.get("base_url"),
            "api_key_configured": model_ready,
            "api_key_masked": settings.get("api_key_masked"),
            "api_key_source": settings.get("api_key_source"),
            "temperature": settings.get("temperature"),
        },
        "estimated_agents": _agent_payload() if route.should_start_research else [],
        "estimated_agent_count": len(AGENT_FLOW) if route.should_start_research else 0,
        "warnings": warnings,
        "actions": _dedupe_actions(actions or list(PRODUCT_ACTIONS)),
    }


def _summary_for_preflight(
    route: str,
    target: dict[str, str],
    settings: dict[str, Any],
    can_start: bool,
    model_ready: bool,
) -> str:
    if route == "research" and can_start:
        return (
            f"预检通过：将分析 {target.get('ticker') or '目标标的'}，"
            f"使用 {settings.get('provider_label') or settings.get('provider')} / {settings.get('model')}，"
            f"预计启动 {len(AGENT_FLOW)} 个 Agent。"
        )
    if route == "research" and not model_ready:
        return (
            f"已识别 {target.get('ticker') or '目标标的'}，但当前用户未配置 API Key。"
            "建议先打开模型设置并测试连接。"
        )
    if route == "missing_ticker":
        return "还没有识别出公司或 ticker，因此不会启动 Agent。请补充股票代码或公司名。"
    if route == "product":
        return "这是产品内操作，不需要启动投研 Agent。你可以打开对应面板或选择研究示例。"
    return "这个问题不属于当前投研范围，因此不会启动 Agent。请选择一个投研示例或打开模型设置。"


def _agent_payload() -> list[dict[str, str]]:
    return [
        {
            "node": node,
            "name": name,
            "role": role,
            "mission": mission,
        }
        for node, name, role, mission in AGENT_FLOW
    ]


def _dedupe_actions(actions: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[tuple[str, str, str]] = set()
    deduped: list[dict[str, str]] = []
    for action in actions:
        key = (str(action.get("label") or ""), str(action.get("kind") or ""), str(action.get("value") or ""))
        if not key[0] or key in seen:
            continue
        seen.add(key)
        deduped.append(action)
    return deduped[:5]
