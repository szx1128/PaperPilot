"""
PaperPilot LLM 统一调用模块。

封装 OpenAI 兼容 API 调用，提供：
- is_llm_available()：判断 LLM 是否可用
- get_llm_config()：按会话输入 / Secrets / 环境变量解析配置
- call_llm()：发送请求并返回文本响应

当 API Key 不存在或调用失败时，默认为不可用状态，
调用方应自动降级到 Fallback 模式，系统不会因 LLM 不可用而崩溃。

依赖：
- python-dotenv（加载 .env）
- openai 包不强制依赖，直接使用 requests 调 HTTP API
"""

import os
from pathlib import Path

import requests
from dotenv import load_dotenv

# ── 环境变量加载 ──────────────────────────────────────────

# 从项目根目录加载 .env；部署或演示时只需要改环境变量，不需要改业务代码。
ENV_PATH = Path(__file__).parent.parent / ".env"
load_dotenv(ENV_PATH)

PLACEHOLDER_VALUES = {
    "your_openai_api_key_here",
    "your_openai_compatible_api_key_here",
    "your_api_key_here",
}


DEFAULT_BASE_URL = "https://api.openai.com/v1"
DEFAULT_MODEL = "gpt-4o-mini"


def _read_streamlit_session_value(name: str) -> str:
    """尝试读取当前 Streamlit 会话配置。命令行环境下会静默降级。"""
    try:
        import streamlit as st
        value = st.session_state.get(name, "")
        return str(value).strip() if value else ""
    except Exception:
        return ""


def _read_streamlit_secret(name: str) -> str:
    """尝试读取 Streamlit Cloud Secrets。失败时静默降级。"""
    try:
        import streamlit as st
        value = st.secrets.get(name, "")
        return str(value).strip() if value else ""
    except Exception:
        return ""


def _is_placeholder(value: str) -> bool:
    """判断配置值是否仍是模板占位符。"""
    return (value or "").strip().lower() in PLACEHOLDER_VALUES


def _read_config_value(name: str, default: str = "") -> str:
    """读取部署级配置：Streamlit Secrets 优先，其次环境变量，最后 default。"""
    value = _read_streamlit_secret(name)
    if value:
        return value
    value = os.getenv(name, "").strip()
    if value:
        return value
    return default


def _valid_api_key(value: str) -> str:
    """返回可用 key；空值或模板占位符视为未配置。"""
    value = (value or "").strip()
    if not value or _is_placeholder(value):
        return ""
    return value


def mask_api_key(key: str) -> str:
    """脱敏展示 API Key，避免在页面或日志中暴露完整密钥。"""
    if not key:
        return ""
    if len(key) <= 8:
        return "********"
    return key[:4] + "..." + key[-4:]


def get_llm_config() -> dict:
    """
    解析当前 LLM 配置。

    优先级：
    1. st.session_state 中的用户临时输入；
    2. Streamlit Cloud Secrets；
    3. 本地 .env / 环境变量；
    4. 未配置，进入基础模式。
    """
    # 1. 页面会话输入：只保存在当前浏览器会话，不落盘。
    session_key = _valid_api_key(_read_streamlit_session_value("LLM_API_KEY"))
    if session_key:
        base_url = (
            _read_streamlit_session_value("LLM_BASE_URL")
            or DEFAULT_BASE_URL
        )
        model = (
            _read_streamlit_session_value("LLM_MODEL")
            or DEFAULT_MODEL
        )
        return {
            "api_key": session_key,
            "base_url": base_url,
            "model": model,
            "source": _read_streamlit_session_value("LLM_CONFIG_SOURCE") or "session_input",
            "available": True,
            "masked_api_key": mask_api_key(session_key),
        }

    # 2. Streamlit Secrets：部署方配置。
    secret_key = _valid_api_key(_read_streamlit_secret("LLM_API_KEY"))
    if not secret_key:
        secret_key = _valid_api_key(_read_streamlit_secret("OPENAI_API_KEY"))
    if secret_key:
        base_url = (
            _read_streamlit_secret("LLM_BASE_URL")
            or os.getenv("LLM_BASE_URL", "").strip()
            or DEFAULT_BASE_URL
        )
        model = (
            _read_streamlit_secret("LLM_MODEL")
            or os.getenv("LLM_MODEL", "").strip()
            or DEFAULT_MODEL
        )
        return {
            "api_key": secret_key,
            "base_url": base_url,
            "model": model,
            "source": "streamlit_secrets",
            "available": True,
            "masked_api_key": mask_api_key(secret_key),
        }

    # 3. 本地 .env / 环境变量：开发和本地运行场景。
    env_key = _valid_api_key(os.getenv("LLM_API_KEY", "").strip())
    if not env_key:
        env_key = _valid_api_key(os.getenv("OPENAI_API_KEY", "").strip())
    if env_key:
        return {
            "api_key": env_key,
            "base_url": os.getenv("LLM_BASE_URL", "").strip() or DEFAULT_BASE_URL,
            "model": os.getenv("LLM_MODEL", "").strip() or DEFAULT_MODEL,
            "source": "env",
            "available": True,
            "masked_api_key": mask_api_key(env_key),
        }

    return {
        "api_key": "",
        "base_url": _read_config_value("LLM_BASE_URL", DEFAULT_BASE_URL),
        "model": _read_config_value("LLM_MODEL", DEFAULT_MODEL),
        "source": "missing",
        "available": False,
        "masked_api_key": "",
    }

# ── 常量 ──────────────────────────────────────────────────

REQUEST_TIMEOUT = 30  # 请求超时秒数
MAX_RETRIES = 2       # 最大重试次数


# ── 公共函数 ──────────────────────────────────────────────

def is_llm_available() -> bool:
    """
    判断 LLM 是否可用。

    检查当前解析出的 LLM 配置是否可用。

    返回:
        True 表示 LLM 可用，False 表示不可用
    """
    return bool(get_llm_config()["available"])


def call_llm(
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.3,
) -> str | None:
    """
    调用 OpenAI 兼容的 LLM API。

    参数:
        system_prompt: 系统提示词
        user_prompt:   用户提示词
        temperature:   生成温度，默认 0.3（偏向确定性输出）

    返回:
        LLM 返回的文本内容；如果调用失败或不可用则返回 None
        不会抛出未捕获异常
    """
    config = get_llm_config()
    if not config["available"]:
        # 没有 API Key 时直接返回 None，由调用方进入 Fallback 分支。
        return None

    url = f"{config['base_url'].rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {config['api_key']}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": config["model"],
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": temperature,
    }

    last_error = None
    for attempt in range(1 + MAX_RETRIES):
        try:
            # 使用 OpenAI 兼容 chat/completions 协议，便于替换不同模型服务。
            response = requests.post(
                url,
                headers=headers,
                json=payload,
                timeout=REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            return content.strip() if content else None

        except requests.exceptions.Timeout:
            last_error = "请求超时"
            continue
        except requests.exceptions.HTTPError as e:
            # 4xx 错误不重试（如 401 认证失败、429 限流）
            status_code = e.response.status_code if e.response is not None else 0
            if 400 <= status_code < 500:
                print(f"[llm_client] LLM API 客户端错误 ({status_code})，请检查 API Key、Base URL 或模型名称。")
                return None
            last_error = f"HTTP {status_code}"
            continue
        except requests.exceptions.ConnectionError:
            last_error = "网络连接失败"
            continue
        except (KeyError, IndexError, TypeError) as e:
            # 响应格式异常通常表示服务端返回不符合 chat/completions 结构。
            print(f"[llm_client] LLM 响应格式异常: {type(e).__name__}")
            return None
        except Exception as e:
            print(f"[llm_client] LLM 调用未知错误: {type(e).__name__}")
            return None

    # 所有重试都失败
    print(f"[llm_client] LLM 调用失败（已重试 {MAX_RETRIES} 次），最后错误: {last_error}")
    return None


def get_llm_info() -> dict:
    """
    返回当前 LLM 配置信息（不含 API Key）。

    用于 UI 显示，帮助用户了解当前使用的模型。
    """
    config = get_llm_config()
    return {
        "available": config["available"],
        "base_url": config["base_url"],
        "model": config["model"],
        "source": config["source"],
        "masked_api_key": config["masked_api_key"],
    }
