from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


load_dotenv()

PROVIDER_DEFAULTS = {
    "openai": {
        "model": "gpt-4o-mini",
        "base_url": None,
        "api_key_env": "OPENAI_API_KEY",
    },
    "deepseek": {
        "model": "deepseek-v4-flash",
        "base_url": "https://api.deepseek.com",
        "api_key_env": "DEEPSEEK_API_KEY",
    },
    "minimax": {
        "model": "MiniMax-M2.7",
        "base_url": "https://api.minimax.io/v1",
        "api_key_env": "MINIMAX_API_KEY",
    },
}


def _truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _provider() -> str:
    value = os.getenv("LLM_PROVIDER", "openai").strip().lower()
    return value or "openai"


def _provider_default(provider: str, key: str):
    return PROVIDER_DEFAULTS.get(provider, PROVIDER_DEFAULTS["openai"])[key]


def _provider_api_key(provider: str) -> str | None:
    env_name = _provider_default(provider, "api_key_env")
    return (
        os.getenv("LLM_API_KEY")
        or os.getenv(env_name)
        or os.getenv("OPENAI_API_KEY")
        or None
    )


@dataclass(frozen=True)
class Settings:
    llm_provider: str = _provider()
    llm_api_key: str | None = _provider_api_key(llm_provider)
    llm_base_url: str | None = (
        os.getenv("LLM_BASE_URL")
        or os.getenv("OPENAI_BASE_URL")
        or _provider_default(llm_provider, "base_url")
    )
    llm_model: str = os.getenv("LLM_MODEL") or os.getenv("OPENAI_MODEL") or _provider_default(
        llm_provider, "model"
    )
    llm_temperature: float = float(os.getenv("LLM_TEMPERATURE", "0.2"))
    deepseek_thinking: str = os.getenv("DEEPSEEK_THINKING", "disabled").strip().lower()
    deepseek_reasoning_effort: str = os.getenv("DEEPSEEK_REASONING_EFFORT", "high").strip().lower()
    minimax_reasoning_split: bool = _truthy(os.getenv("MINIMAX_REASONING_SPLIT"))


settings = Settings()
