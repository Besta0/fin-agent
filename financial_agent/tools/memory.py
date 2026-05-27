from __future__ import annotations

import json
import math
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any


DEFAULT_USER_ID = "default"
OUTPUTS_DIR = Path("outputs")
USERS_DIR = OUTPUTS_DIR / "users"
LEGACY_HISTORY_DIR = OUTPUTS_DIR / "history"
LEGACY_REPORT_DIR = OUTPUTS_DIR / "reports"
LEGACY_WATCHLIST_PATH = OUTPUTS_DIR / "watchlist" / "watchlist.json"

PREFERENCE_KEYWORDS = [
    "记住",
    "以后",
    "我的偏好",
    "我偏好",
    "偏好",
    "只看",
    "主要关注",
    "关注",
    "我喜欢",
    "我不想看",
]

SEMANTIC_MEMORY_KEYWORDS = [
    "记忆",
    "历史里",
    "历史报告",
    "以前分析",
    "过去分析",
    "之前分析",
    "查一下历史",
    "查记忆",
    "检索记忆",
    "有没有分析过",
]

SECTOR_KEYWORDS = {
    "科技": "科技",
    "半导体": "半导体",
    "ai": "AI",
    "人工智能": "AI",
    "芯片": "半导体",
    "软件": "软件",
    "云": "云计算",
    "航天": "航天",
    "军工": "军工",
    "新能源": "新能源",
    "消费": "消费",
    "医药": "医药",
    "金融": "金融",
}

MARKET_KEYWORDS = {
    "美股": "US",
    "港股": "HK",
    "a股": "CN",
    "A股": "CN",
}


def safe_user_id(user_id: str | None) -> str:
    raw = str(user_id or DEFAULT_USER_ID).strip()
    safe = "".join(ch for ch in raw if ch.isalnum() or ch in {"_", "-", "."})
    return safe[:64] or DEFAULT_USER_ID


def user_dir(user_id: str | None = None) -> Path:
    return USERS_DIR / safe_user_id(user_id)


def user_history_dir(user_id: str | None = None) -> Path:
    return user_dir(user_id) / "history"


def user_reports_dir(user_id: str | None = None) -> Path:
    return user_dir(user_id) / "reports"


def user_watchlist_path(user_id: str | None = None) -> Path:
    return user_dir(user_id) / "watchlist" / "watchlist.json"


def user_memory_dir(user_id: str | None = None) -> Path:
    return user_dir(user_id) / "memory"


def user_preferences_path(user_id: str | None = None) -> Path:
    return user_memory_dir(user_id) / "preferences.json"


def user_semantic_memory_path(user_id: str | None = None) -> Path:
    return user_memory_dir(user_id) / "semantic_memory.jsonl"


def load_user_preferences(user_id: str | None = None) -> dict[str, Any]:
    path = user_preferences_path(user_id)
    if not path.exists():
        return {
            "user_id": safe_user_id(user_id),
            "updated_at": None,
            "markets": [],
            "sectors": [],
            "horizon": None,
            "risk_profile": None,
            "output_style": None,
            "notes": [],
        }

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {
            "user_id": safe_user_id(user_id),
            "updated_at": None,
            "markets": [],
            "sectors": [],
            "horizon": None,
            "risk_profile": None,
            "output_style": None,
            "notes": [],
        }

    if not isinstance(data, dict):
        return {"user_id": safe_user_id(user_id), "updated_at": None}
    data.setdefault("user_id", safe_user_id(user_id))
    data.setdefault("markets", [])
    data.setdefault("sectors", [])
    data.setdefault("notes", [])
    return data


def _append_unique(values: list[str], value: str) -> bool:
    if value in values:
        return False
    values.append(value)
    return True


def update_preferences_from_query(user_id: str | None, query: str) -> dict[str, Any]:
    normalized = query.strip()
    lowered = normalized.lower()
    prefs = load_user_preferences(user_id)
    changes: list[str] = []

    if not any(keyword.lower() in lowered or keyword in normalized for keyword in PREFERENCE_KEYWORDS):
        return {"updated": False, "preferences": prefs, "changes": []}

    markets = list(prefs.get("markets") or [])
    for key, market in MARKET_KEYWORDS.items():
        if key.lower() in lowered or key in normalized:
            if _append_unique(markets, market):
                changes.append(f"市场偏好：{market}")
    prefs["markets"] = markets

    sectors = list(prefs.get("sectors") or [])
    for key, sector in SECTOR_KEYWORDS.items():
        if key.lower() in lowered:
            if _append_unique(sectors, sector):
                changes.append(f"行业偏好：{sector}")
    prefs["sectors"] = sectors

    if any(key in normalized for key in ("短线", "日内", "盘中", "一周")):
        prefs["horizon"] = "短线"
        changes.append("周期偏好：短线")
    elif any(key in normalized for key in ("中线", "一个月", "三个月")):
        prefs["horizon"] = "中线"
        changes.append("周期偏好：中线")
    elif any(key in normalized for key in ("长期", "长线", "半年", "一年")):
        prefs["horizon"] = "长线"
        changes.append("周期偏好：长线")

    if any(key in normalized for key in ("保守", "低风险", "稳健")):
        prefs["risk_profile"] = "稳健"
        changes.append("风险偏好：稳健")
    elif any(key in normalized for key in ("激进", "高风险", "进攻")):
        prefs["risk_profile"] = "进取"
        changes.append("风险偏好：进取")

    if any(key in normalized for key in ("简洁", "短一点", "简单")):
        prefs["output_style"] = "简洁"
        changes.append("输出偏好：简洁")
    elif any(key in normalized for key in ("详细", "深入", "完整")):
        prefs["output_style"] = "详细"
        changes.append("输出偏好：详细")

    notes = list(prefs.get("notes") or [])
    if changes:
        notes.append({"timestamp": datetime.now().isoformat(timespec="seconds"), "query": normalized})
        prefs["notes"] = notes[-20:]
        prefs["updated_at"] = datetime.now().isoformat(timespec="seconds")
        path = user_preferences_path(user_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(prefs, ensure_ascii=False, indent=2), encoding="utf-8")

    return {"updated": bool(changes), "preferences": prefs, "changes": changes}


def is_preference_intent(text: str) -> bool:
    normalized = text.strip().lower()
    if not normalized:
        return False
    return any(keyword.lower() in normalized or keyword in text for keyword in PREFERENCE_KEYWORDS)


def format_preferences_response(user_id: str | None = None) -> str:
    prefs = load_user_preferences(user_id)
    notes = prefs.get("notes") or []
    last_note = notes[-1].get("query") if notes and isinstance(notes[-1], dict) else "N/A"
    return f"""## 用户偏好记忆

- 用户：`{safe_user_id(user_id)}`
- 更新时间：**{prefs.get("updated_at") or "N/A"}**
- 市场偏好：**{", ".join(prefs.get("markets") or []) or "暂无"}**
- 行业偏好：**{", ".join(prefs.get("sectors") or []) or "暂无"}**
- 周期偏好：**{prefs.get("horizon") or "暂无"}**
- 风险偏好：**{prefs.get("risk_profile") or "暂无"}**
- 输出偏好：**{prefs.get("output_style") or "暂无"}**
- 最近偏好输入：{last_note}
"""


def is_semantic_memory_intent(text: str) -> bool:
    normalized = text.strip().lower()
    if not normalized:
        return False
    return any(keyword.lower() in normalized or keyword in text for keyword in SEMANTIC_MEMORY_KEYWORDS)


def _tokens(text: str) -> list[str]:
    lowered = text.lower()
    tokens = re.findall(r"[a-z0-9.]{2,}", lowered)
    chinese = re.findall(r"[\u4e00-\u9fff]+", text)
    for chunk in chinese:
        tokens.extend(chunk[i : i + 2] for i in range(max(1, len(chunk) - 1)))
    return tokens


def _score(query_tokens: Counter[str], text: str) -> float:
    memory_tokens = Counter(_tokens(text))
    if not query_tokens or not memory_tokens:
        return 0.0
    overlap = set(query_tokens) & set(memory_tokens)
    numerator = sum(query_tokens[token] * memory_tokens[token] for token in overlap)
    query_norm = math.sqrt(sum(value * value for value in query_tokens.values()))
    memory_norm = math.sqrt(sum(value * value for value in memory_tokens.values()))
    if query_norm == 0 or memory_norm == 0:
        return 0.0
    return numerator / (query_norm * memory_norm)


def append_semantic_memory(user_id: str | None, record: dict[str, Any]) -> str:
    path = user_semantic_memory_path(user_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "user_id": safe_user_id(user_id),
        **record,
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
    return str(path)


def load_semantic_memories(user_id: str | None = None) -> list[dict[str, Any]]:
    path = user_semantic_memory_path(user_id)
    if not path.exists():
        return []

    memories: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            memories.append(payload)
    return memories


def search_semantic_memory(
    user_id: str | None,
    query: str,
    limit: int = 5,
) -> list[dict[str, Any]]:
    query_tokens = Counter(_tokens(query))
    scored: list[tuple[float, dict[str, Any]]] = []
    for memory in load_semantic_memories(user_id):
        searchable = " ".join(
            str(memory.get(key) or "")
            for key in ("ticker", "company_name", "title", "summary", "rating", "text")
        )
        score = _score(query_tokens, searchable)
        if score > 0:
            scored.append((score, {**memory, "score": round(score, 3)}))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [memory for _, memory in scored[:limit]]


def format_semantic_memory_response(user_id: str | None, query: str, limit: int = 5) -> str:
    memories = search_semantic_memory(user_id, query, limit=limit)
    if not memories:
        return f"""我没有在 `{safe_user_id(user_id)}` 的语义记忆里找到相关历史记录。

你可以先分析几只股票，系统会在 History Agent 阶段把报告摘要写入语义记忆。"""

    lines = [
        "## 语义记忆检索结果",
        "",
        f"- 用户：`{safe_user_id(user_id)}`",
        f"- 查询：{query}",
        "",
    ]
    for idx, memory in enumerate(memories, start=1):
        lines.extend(
            [
                f"### {idx}. {memory.get('ticker', 'N/A')} - {memory.get('title', '历史投研记录')}",
                f"- 相似度：**{memory.get('score', 'N/A')}**",
                f"- 时间：**{memory.get('timestamp', 'N/A')}**",
                f"- 评级 / 置信度：**{memory.get('rating', 'N/A')} / {memory.get('confidence', 'N/A')}%**",
                f"- 报告：`{memory.get('report_path', 'N/A')}`",
                f"- 摘要：{memory.get('summary', '暂无摘要')}",
                "",
            ]
        )
    return "\n".join(lines).strip()
