from __future__ import annotations

from contextvars import ContextVar, Token
from dataclasses import dataclass

from financial_agent.settings import settings


@dataclass(frozen=True)
class LLMConfig:
    llm_provider: str
    llm_model: str
    llm_base_url: str | None
    llm_api_key: str | None
    llm_api_key_source: str | None
    llm_temperature: float
    deepseek_thinking: str
    deepseek_reasoning_effort: str
    minimax_reasoning_split: bool

    @classmethod
    def from_settings(cls) -> "LLMConfig":
        return cls(
            llm_provider=settings.llm_provider,
            llm_model=settings.llm_model,
            llm_base_url=settings.llm_base_url,
            llm_api_key=settings.llm_api_key,
            llm_api_key_source=settings.llm_api_key_source,
            llm_temperature=settings.llm_temperature,
            deepseek_thinking=settings.deepseek_thinking,
            deepseek_reasoning_effort=settings.deepseek_reasoning_effort,
            minimax_reasoning_split=settings.minimax_reasoning_split,
        )


_runtime_llm_config: ContextVar[LLMConfig | None] = ContextVar(
    "runtime_llm_config",
    default=None,
)


def get_effective_llm_config() -> LLMConfig:
    return _runtime_llm_config.get() or LLMConfig.from_settings()


def set_runtime_llm_config(config: LLMConfig | None) -> Token:
    return _runtime_llm_config.set(config)


def reset_runtime_llm_config(token: Token) -> None:
    _runtime_llm_config.reset(token)


def _provider_kwargs(config: LLMConfig) -> dict:
    if config.llm_provider == "deepseek":
        kwargs: dict = {}
        if config.deepseek_thinking in {"enabled", "disabled"}:
            kwargs["extra_body"] = {"thinking": {"type": config.deepseek_thinking}}
        if config.deepseek_thinking == "enabled":
            kwargs["reasoning_effort"] = config.deepseek_reasoning_effort
        return kwargs

    if config.llm_provider == "minimax" and config.minimax_reasoning_split:
        return {"extra_body": {"reasoning_split": True}}

    return {}


def get_chat_model(temperature: float | None = None):
    """Return a chat model when credentials are configured, otherwise None."""
    config = get_effective_llm_config()
    if not config.llm_api_key:
        return None

    from langchain_openai import ChatOpenAI

    kwargs = {}
    if config.llm_base_url:
        kwargs["base_url"] = config.llm_base_url
    kwargs.update(_provider_kwargs(config))

    return ChatOpenAI(
        model=config.llm_model,
        api_key=config.llm_api_key,
        temperature=config.llm_temperature if temperature is None else temperature,
        **kwargs,
    )


async def generate_text(prompt: str, fallback: str, temperature: float | None = None) -> str:
    model = get_chat_model(temperature=temperature)
    if model is None:
        return fallback

    try:
        response = await model.ainvoke(prompt)
    except Exception as exc:
        return f"{fallback}\n\n> LLM 生成失败，已使用规则兜底。错误：`{exc}`"

    content = getattr(response, "content", "")
    if isinstance(content, str) and content.strip():
        return content.strip()

    return fallback
