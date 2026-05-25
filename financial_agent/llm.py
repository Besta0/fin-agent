from __future__ import annotations

from financial_agent.settings import settings


PROVIDER_BASE_URLS = {
    "openai": None,
    "deepseek": "https://api.deepseek.com",
    "minimax": "https://api.minimax.io/v1",
}


def get_chat_model(temperature: float | None = None):
    """Return a chat model when credentials are configured, otherwise None."""
    if not settings.llm_api_key:
        return None

    from langchain_openai import ChatOpenAI

    base_url = settings.llm_base_url or PROVIDER_BASE_URLS.get(settings.llm_provider)
    kwargs = {}
    if base_url:
        kwargs["base_url"] = base_url

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
