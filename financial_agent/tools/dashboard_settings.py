from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from financial_agent.llm import LLMConfig
from financial_agent.settings import PROVIDER_DEFAULTS
from financial_agent.tools.memory import safe_user_id, user_dir


PROVIDER_LABELS = {
    "openai": "OpenAI",
    "deepseek": "DeepSeek",
    "minimax": "MiniMax",
    "xiaomi": "Xiaomi MiMo",
    "mimo": "Xiaomi MiMo",
}

PROVIDER_MODEL_ITEMS = {
    "openai": {
        "GPT-5.1": "gpt-5.1",
        "GPT-5": "gpt-5",
        "GPT-5 mini": "gpt-5-mini",
        "GPT-5 nano": "gpt-5-nano",
        "GPT-4.1": "gpt-4.1",
        "GPT-4.1 mini": "gpt-4.1-mini",
        "GPT-4o mini": "gpt-4o-mini",
    },
    "deepseek": {
        "DeepSeek V4 Flash": "deepseek-v4-flash",
        "DeepSeek V4 Pro": "deepseek-v4-pro",
    },
    "minimax": {
        "MiniMax M2.7": "MiniMax-M2.7",
        "MiniMax M2.7 highspeed": "MiniMax-M2.7-highspeed",
        "MiniMax M2.5": "MiniMax-M2.5",
        "MiniMax M2.5 highspeed": "MiniMax-M2.5-highspeed",
        "MiniMax M2-her": "M2-her",
    },
    "xiaomi": {
        "MiMo V2.5 Pro": "mimo-v2.5-pro",
        "MiMo V2.5": "mimo-v2.5",
        "MiMo V2 Flash": "mimo-v2-flash",
    },
}

PUBLIC_PROVIDER_ORDER = ["openai", "deepseek", "minimax", "xiaomi"]


def user_model_settings_path(user_id: str | None = None) -> Path:
    return user_dir(user_id) / "settings.json"


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _mask_api_key(value: str | None) -> str:
    if not value:
        return "未配置"
    if len(value) <= 8:
        return "已配置 ****"
    return f"已配置 {value[:3]}****{value[-4:]}"


def _provider_label(provider: str) -> str:
    return PROVIDER_LABELS.get(provider, f"{provider} (OpenAI-compatible)")


def _provider_defaults(provider: str) -> dict[str, Any]:
    return PROVIDER_DEFAULTS.get(provider, PROVIDER_DEFAULTS["openai"])


def _env_candidates(provider: str, key: str) -> list[str]:
    defaults = _provider_defaults(provider)
    envs = list(defaults.get(key) or [])
    if key == "api_key_envs":
        envs = ["LLM_API_KEY", *envs, "OPENAI_API_KEY"]
    if key == "model_envs":
        envs = ["LLM_MODEL", *envs]
    if key == "base_url_envs":
        envs = ["LLM_BASE_URL", *envs]
    deduped: list[str] = []
    for env in envs:
        if env and env not in deduped:
            deduped.append(env)
    return deduped


def _first_env(names: list[str]) -> tuple[str | None, str | None]:
    for name in names:
        value = os.getenv(name)
        if value:
            return value, name
    return None, None


def _load_raw_user_settings(user_id: str | None = None) -> dict[str, Any]:
    path = user_model_settings_path(user_id)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def _sanitize_provider(provider: Any) -> str:
    value = str(provider or "").strip().lower()
    if value == "mimo":
        return "xiaomi"
    if value in PROVIDER_DEFAULTS:
        return value
    return "openai"


def _sanitize_temperature(value: Any, fallback: float = 0.2) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return fallback
    return max(0.0, min(1.0, number))


def provider_options_payload() -> list[dict[str, Any]]:
    providers = []
    for provider in PUBLIC_PROVIDER_ORDER:
        defaults = _provider_defaults(provider)
        models = [
            {"label": label, "value": value}
            for label, value in PROVIDER_MODEL_ITEMS.get(provider, {}).items()
        ]
        providers.append(
            {
                "value": provider,
                "label": _provider_label(provider),
                "default_model": defaults.get("model"),
                "default_base_url": defaults.get("base_url") or "",
                "models": models,
            }
        )
    return providers


def load_user_model_settings(user_id: str | None = None) -> dict[str, Any]:
    raw = _load_raw_user_settings(user_id)
    provider = _sanitize_provider(raw.get("provider") or os.getenv("LLM_PROVIDER") or "openai")
    defaults = _provider_defaults(provider)
    env_model, model_source = _first_env(_env_candidates(provider, "model_envs"))
    env_base_url, base_url_source = _first_env(_env_candidates(provider, "base_url_envs"))
    env_key, key_source = _first_env(_env_candidates(provider, "api_key_envs"))

    model = str(raw.get("model") or env_model or defaults.get("model") or "").strip()
    base_url = str(raw.get("base_url") if raw.get("base_url") is not None else (env_base_url or defaults.get("base_url") or "")).strip()
    api_key = str(raw.get("api_key") or env_key or "").strip()
    api_key_source = "Dashboard" if raw.get("api_key") else (key_source or None)
    temperature = _sanitize_temperature(raw.get("temperature"), fallback=0.2)

    return {
        "user_id": safe_user_id(user_id),
        "provider": provider,
        "provider_label": _provider_label(provider),
        "model": model,
        "model_source": "Dashboard" if raw.get("model") else (model_source or "default"),
        "base_url": base_url,
        "base_url_source": "Dashboard" if raw.get("base_url") is not None else (base_url_source or "default"),
        "temperature": temperature,
        "api_key": api_key,
        "api_key_source": api_key_source,
        "api_key_configured": bool(api_key),
        "api_key_masked": _mask_api_key(api_key),
        "updated_at": raw.get("updated_at"),
        "path": str(user_model_settings_path(user_id)),
    }


def public_user_model_settings(user_id: str | None = None) -> dict[str, Any]:
    settings = load_user_model_settings(user_id)
    return {
        key: value
        for key, value in settings.items()
        if key != "api_key"
    }


def save_user_model_settings(user_id: str | None, payload: dict[str, Any]) -> dict[str, Any]:
    previous = _load_raw_user_settings(user_id)
    provider = _sanitize_provider(payload.get("provider") or previous.get("provider") or "openai")
    defaults = _provider_defaults(provider)
    model = str(payload.get("model") or defaults.get("model") or "").strip()
    base_url = str(payload.get("base_url") if payload.get("base_url") is not None else (defaults.get("base_url") or "")).strip()
    api_key_input = str(payload.get("api_key") or "").strip()
    temperature = _sanitize_temperature(payload.get("temperature"), fallback=0.2)

    record = {
        "provider": provider,
        "model": model,
        "base_url": base_url,
        "temperature": temperature,
        "updated_at": _now(),
    }
    previous_provider = _sanitize_provider(previous.get("provider") or provider)
    if api_key_input:
        record["api_key"] = api_key_input
    elif previous.get("api_key") and previous_provider == provider:
        record["api_key"] = previous["api_key"]

    path = user_model_settings_path(user_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    return public_user_model_settings(user_id)


def payload_to_llm_config(user_id: str | None, payload: dict[str, Any]) -> LLMConfig:
    saved = load_user_model_settings(user_id)
    provider = _sanitize_provider(payload.get("provider") or saved.get("provider") or "openai")
    defaults = _provider_defaults(provider)
    model = str(payload.get("model") or saved.get("model") or defaults.get("model") or "").strip()
    base_url = str(
        payload.get("base_url")
        if payload.get("base_url") is not None
        else (saved.get("base_url") or defaults.get("base_url") or "")
    ).strip()
    saved_provider = _sanitize_provider(saved.get("provider") or provider)
    saved_key = saved.get("api_key") if saved_provider == provider else ""
    env_key, env_key_source = _first_env(_env_candidates(provider, "api_key_envs"))
    api_key_input = str(payload.get("api_key") or "").strip()
    api_key = str(api_key_input or saved_key or env_key or "").strip()
    api_key_source = "Dashboard" if api_key_input else (saved.get("api_key_source") if saved_key else env_key_source)
    temperature = _sanitize_temperature(payload.get("temperature"), fallback=float(saved.get("temperature") or 0.2))
    fallback = LLMConfig.from_settings()
    return LLMConfig(
        llm_provider=provider,
        llm_model=model or str(defaults.get("model") or fallback.llm_model),
        llm_base_url=base_url or None,
        llm_api_key=api_key or None,
        llm_api_key_source=api_key_source,
        llm_temperature=temperature,
        deepseek_thinking=fallback.deepseek_thinking,
        deepseek_reasoning_effort=fallback.deepseek_reasoning_effort,
        minimax_reasoning_split=fallback.minimax_reasoning_split,
    )


def user_settings_to_llm_config(user_id: str | None = None) -> LLMConfig:
    settings = load_user_model_settings(user_id)
    fallback = LLMConfig.from_settings()
    provider = settings["provider"]
    return LLMConfig(
        llm_provider=provider,
        llm_model=settings["model"] or _provider_defaults(provider).get("model") or fallback.llm_model,
        llm_base_url=settings["base_url"] or None,
        llm_api_key=settings["api_key"] or None,
        llm_api_key_source=settings["api_key_source"],
        llm_temperature=settings["temperature"],
        deepseek_thinking=fallback.deepseek_thinking,
        deepseek_reasoning_effort=fallback.deepseek_reasoning_effort,
        minimax_reasoning_split=fallback.minimax_reasoning_split,
    )


def settings_page_payload(user_id: str | None = None) -> dict[str, Any]:
    return {
        "ok": True,
        "providers": provider_options_payload(),
        "settings": public_user_model_settings(user_id),
    }
