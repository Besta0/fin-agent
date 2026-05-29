from __future__ import annotations

import asyncio
from typing import Any

from financial_agent.llm import LLMConfig, get_chat_model, get_effective_llm_config
from financial_agent.settings import PROVIDER_DEFAULTS


SETTINGS_KEYWORDS = [
    "模型设置",
    "查看模型配置",
    "api配置",
    "api 设置",
    "llm配置",
    "llm 设置",
    "provider配置",
    "小米配置",
    "mimo配置",
    "xiaomi配置",
]

EXACT_SETTINGS_KEYWORDS = [
    "设置",
    "settings",
    "config",
]

CONNECTION_TEST_KEYWORDS = [
    "测试模型连接",
    "测试连接",
    "连接测试",
    "测试 llm",
    "测试api",
    "测试 api",
]


def is_settings_intent(text: str) -> bool:
    normalized = text.strip().lower()
    if not normalized:
        return False
    compact = "".join(normalized.split())
    if compact in EXACT_SETTINGS_KEYWORDS:
        return True
    return any(keyword.lower().replace(" ", "") in compact for keyword in SETTINGS_KEYWORDS)


def is_connection_test_intent(text: str) -> bool:
    normalized = text.strip().lower()
    if not normalized:
        return False
    compact = "".join(normalized.split())
    return any(keyword.lower().replace(" ", "") in compact for keyword in CONNECTION_TEST_KEYWORDS)


def _mask_api_key(value: str | None) -> str:
    if not value:
        return "未配置"
    if len(value) <= 8:
        return "已配置 ****"
    return f"已配置 {value[:3]}****{value[-4:]}"


def _display(value: Any) -> str:
    if value is None or value == "":
        return "N/A"
    return str(value)


def _provider_label(provider: str) -> str:
    labels = {
        "openai": "OpenAI",
        "deepseek": "DeepSeek",
        "minimax": "MiniMax",
        "xiaomi": "Xiaomi MiMo",
        "mimo": "Xiaomi MiMo",
    }
    return labels.get(provider, f"{provider} (OpenAI-compatible)")


async def test_llm_connection(timeout_seconds: int = 20) -> dict[str, Any]:
    config = get_effective_llm_config()
    if not config.llm_api_key:
        return {
            "ok": False,
            "status": "not_configured",
            "message": "未配置 API Key。请先在 UI 设置面板或 .env 中配置当前 provider 的 key。",
        }

    model = get_chat_model(temperature=0)
    if model is None:
        return {
            "ok": False,
            "status": "model_unavailable",
            "message": "无法创建 ChatOpenAI 实例，请检查 provider/model/base_url 配置。",
        }

    try:
        response = await asyncio.wait_for(
            model.ainvoke("请只回复 OK，不要添加其他内容。"),
            timeout=timeout_seconds,
        )
    except Exception as exc:
        return {
            "ok": False,
            "status": "failed",
            "message": str(exc),
        }

    content = getattr(response, "content", "")
    return {
        "ok": True,
        "status": "success",
        "message": str(content).strip()[:120] or "模型已响应。",
    }


def _provider_template(provider: str) -> str:
    defaults = PROVIDER_DEFAULTS[provider]
    model = defaults["model"]
    base_url = defaults["base_url"] or ""
    api_key_envs = defaults.get("api_key_envs") or ["LLM_API_KEY"]
    primary_key = api_key_envs[0]

    extra_lines = []
    if provider == "deepseek":
        extra_lines.extend(
            [
                "DEEPSEEK_THINKING=disabled",
                "DEEPSEEK_REASONING_EFFORT=high",
            ]
        )
    elif provider == "minimax":
        extra_lines.append("MINIMAX_REASONING_SPLIT=false")

    lines = [
        f"LLM_PROVIDER={provider}",
        f"{primary_key}=your_{provider}_api_key",
        f"LLM_MODEL={model}",
        f"LLM_BASE_URL={base_url}",
        *extra_lines,
    ]
    return "\n".join(lines)


def _templates_section() -> str:
    providers = ["openai", "deepseek", "minimax", "xiaomi"]
    blocks = []
    for provider in providers:
        blocks.append(
            f"### {_provider_label(provider)}\n\n"
            "```bash\n"
            f"{_provider_template(provider)}\n"
            "```"
        )
    return "\n\n".join(blocks)


def _current_settings_section(config: LLMConfig) -> str:
    provider = config.llm_provider
    defaults = PROVIDER_DEFAULTS.get(provider)
    known_label = "内置 provider" if defaults else "自定义 OpenAI-compatible provider"
    key_source = config.llm_api_key_source or "N/A"
    default_model = defaults.get("model") if defaults else "N/A"
    default_base_url = defaults.get("base_url") if defaults else "N/A"
    key_envs = ", ".join(defaults.get("api_key_envs", [])) if defaults else "LLM_API_KEY"
    model_envs = ", ".join(["LLM_MODEL", *(defaults.get("model_envs", []) if defaults else [])])
    base_url_envs = ", ".join(["LLM_BASE_URL", *(defaults.get("base_url_envs", []) if defaults else [])])
    notes: list[str] = []
    if defaults and config.llm_model != default_model:
        notes.append(f"当前 model 与 {_provider_label(provider)} 默认值 `{default_model}` 不同。")
    if defaults and (config.llm_base_url or "") != (default_base_url or ""):
        notes.append(f"当前 base_url 与默认值 `{default_base_url or 'N/A'}` 不同。")
    if key_source == "UI Session":
        notes.append("当前正在使用 UI 会话级配置；不会写入 `.env`。")
    notes_text = "\n".join(f"- {note}" for note in notes) if notes else "- 暂无异常提示。"
    return f"""## 当前模型配置

- Provider：**{_provider_label(provider)}**
- Provider 类型：**{known_label}**
- Model：**{_display(config.llm_model)}**
- Base URL：`{_display(config.llm_base_url)}`
- API Key：**{_mask_api_key(config.llm_api_key)}**
- Key 来源：`{key_source}`
- 推荐 Key 环境变量：`{key_envs}`
- 推荐 Model 环境变量：`{model_envs}`
- 推荐 Base URL 环境变量：`{base_url_envs}`
- Provider 默认模型：`{_display(default_model)}`
- Provider 默认 Base URL：`{_display(default_base_url)}`
- Temperature：**{config.llm_temperature}**
- DeepSeek Thinking：**{config.deepseek_thinking}**
- MiniMax Reasoning Split：**{config.minimax_reasoning_split}**

配置诊断：
{notes_text}"""


def _connection_result_section(result: dict[str, Any] | None) -> str:
    if result is None:
        return """## 连接测试

未执行。输入 `测试模型连接` 可以发起一次最小 LLM 请求。"""

    label = "成功" if result.get("ok") else "失败"
    return f"""## 连接测试

- 状态：**{label}**
- 代码：`{result.get("status", "unknown")}`
- 响应 / 错误：{result.get("message") or "N/A"}"""


async def format_settings_response(test_connection: bool = False) -> str:
    config = get_effective_llm_config()
    result = await test_llm_connection() if test_connection else None
    return "\n\n".join(
        [
            "# 模型设置",
            _current_settings_section(config),
            _connection_result_section(result),
            "## 安全说明\n\n- 页面不会展示完整 API Key。\n- UI 中填写的 API Key 只保存在当前 Python 进程的会话内存中，不写入 `.env`、报告或记忆库。\n- 刷新或重启服务后，如果没有重新填写，会回退到 `.env` 配置。",
            "## 配置模板",
            _templates_section(),
        ]
    )
