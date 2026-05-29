from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


load_dotenv()

PROVIDER_DEFAULTS = {
    "openai": {
        "model": "gpt-4o-mini",
        "base_url": None,
        "api_key_envs": ["OPENAI_API_KEY"],
        "model_envs": ["OPENAI_MODEL"],
        "base_url_envs": ["OPENAI_BASE_URL"],
    },
    "deepseek": {
        "model": "deepseek-v4-flash",
        "base_url": "https://api.deepseek.com",
        "api_key_envs": ["DEEPSEEK_API_KEY"],
        "model_envs": ["DEEPSEEK_MODEL"],
        "base_url_envs": ["DEEPSEEK_BASE_URL"],
    },
    "minimax": {
        "model": "MiniMax-M2.7",
        "base_url": "https://api.minimax.io/v1",
        "api_key_envs": ["MINIMAX_API_KEY"],
        "model_envs": ["MINIMAX_MODEL"],
        "base_url_envs": ["MINIMAX_BASE_URL"],
    },
    "xiaomi": {
        "model": "mimo-v2.5-pro",
        "base_url": "https://api.xiaomimimo.com/v1",
        "api_key_envs": ["MIMO_API_KEY", "XIAOMI_API_KEY"],
        "model_envs": ["MIMO_MODEL", "XIAOMI_MODEL"],
        "base_url_envs": ["MIMO_BASE_URL", "XIAOMI_BASE_URL"],
    },
    "mimo": {
        "model": "mimo-v2.5-pro",
        "base_url": "https://api.xiaomimimo.com/v1",
        "api_key_envs": ["MIMO_API_KEY", "XIAOMI_API_KEY"],
        "model_envs": ["MIMO_MODEL", "XIAOMI_MODEL"],
        "base_url_envs": ["MIMO_BASE_URL", "XIAOMI_BASE_URL"],
    },
}


def _truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _provider() -> str:
    value = os.getenv("LLM_PROVIDER", "openai").strip().lower()
    return value or "openai"


def _provider_default(provider: str, key: str):
    return PROVIDER_DEFAULTS.get(provider, PROVIDER_DEFAULTS["openai"])[key]


def _provider_envs(provider: str, key: str) -> list[str]:
    defaults = PROVIDER_DEFAULTS.get(provider, PROVIDER_DEFAULTS["openai"])
    envs = defaults.get(key) or []
    return [str(env) for env in envs if env]


def _provider_api_key_envs(provider: str) -> list[str]:
    return _provider_envs(provider, "api_key_envs") or ["OPENAI_API_KEY"]


def _api_key_candidates(provider: str) -> list[str]:
    candidates = ["LLM_API_KEY", *_provider_api_key_envs(provider), "OPENAI_API_KEY"]
    deduped: list[str] = []
    for candidate in candidates:
        if candidate not in deduped:
            deduped.append(candidate)
    return deduped


def _provider_api_key(provider: str) -> str | None:
    for env_name in _api_key_candidates(provider):
        value = os.getenv(env_name)
        if value:
            return value
    return None


def _provider_api_key_source(provider: str) -> str | None:
    for env_name in _api_key_candidates(provider):
        if os.getenv(env_name):
            return env_name
    return None


def _first_env(names: list[str]) -> str | None:
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    return None


def _model(provider: str) -> str:
    legacy_envs = ["OPENAI_MODEL"] if provider == "openai" or provider not in PROVIDER_DEFAULTS else []
    return (
        os.getenv("LLM_MODEL")
        or _first_env(_provider_envs(provider, "model_envs"))
        or _first_env(legacy_envs)
        or _provider_default(provider, "model")
    )


def _base_url(provider: str) -> str | None:
    legacy_envs = ["OPENAI_BASE_URL"] if provider == "openai" or provider not in PROVIDER_DEFAULTS else []
    return (
        os.getenv("LLM_BASE_URL")
        or _first_env(_provider_envs(provider, "base_url_envs"))
        or _first_env(legacy_envs)
        or _provider_default(provider, "base_url")
    )


@dataclass(frozen=True)
class Settings:
    llm_provider: str = _provider()
    llm_api_key: str | None = _provider_api_key(llm_provider)
    llm_api_key_source: str | None = _provider_api_key_source(llm_provider)
    llm_base_url: str | None = _base_url(llm_provider)
    llm_model: str = _model(llm_provider)
    llm_temperature: float = float(os.getenv("LLM_TEMPERATURE", "0.2"))
    deepseek_thinking: str = os.getenv("DEEPSEEK_THINKING", "disabled").strip().lower()
    deepseek_reasoning_effort: str = os.getenv("DEEPSEEK_REASONING_EFFORT", "high").strip().lower()
    minimax_reasoning_split: bool = _truthy(os.getenv("MINIMAX_REASONING_SPLIT"))


settings = Settings()
