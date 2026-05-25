from __future__ import annotations

from financial_agent.settings import settings


def _provider_kwargs() -> dict:
    if settings.llm_provider == "deepseek":
        kwargs: dict = {}
        if settings.deepseek_thinking in {"enabled", "disabled"}:
            kwargs["extra_body"] = {"thinking": {"type": settings.deepseek_thinking}}
        if settings.deepseek_thinking == "enabled":
            kwargs["reasoning_effort"] = settings.deepseek_reasoning_effort
        return kwargs

    if settings.llm_provider == "minimax" and settings.minimax_reasoning_split:
        return {"extra_body": {"reasoning_split": True}}

    return {}


def get_chat_model(temperature: float | None = None):
    """Return a chat model when credentials are configured, otherwise None."""
    if not settings.llm_api_key:
        return None

    from langchain_openai import ChatOpenAI

    kwargs = {}
    if settings.llm_base_url:
        kwargs["base_url"] = settings.llm_base_url
    kwargs.update(_provider_kwargs())

    return ChatOpenAI(
        model=settings.llm_model,
        api_key=settings.llm_api_key,
        temperature=settings.llm_temperature if temperature is None else temperature,
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
