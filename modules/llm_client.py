"""
PaperPilot LLM 统一调用模块。

封装 OpenAI 兼容 API 调用，提供：
- is_llm_available()：判断 LLM 是否可用
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
    """读取配置：环境变量优先，其次 Streamlit Secrets，最后 default。"""
    value = os.getenv(name, "").strip()
    if value:
        return value
    value = _read_streamlit_secret(name)
    if value:
        return value
    return default


_primary_api_key = _read_config_value("LLM_API_KEY", "")
if _is_placeholder(_primary_api_key):
    _primary_api_key = ""

LLM_API_KEY = _primary_api_key or _read_config_value("OPENAI_API_KEY", "")
LLM_BASE_URL = _read_config_value("LLM_BASE_URL", "https://api.openai.com/v1")
LLM_MODEL = _read_config_value("LLM_MODEL", "gpt-4o-mini")

# ── 常量 ──────────────────────────────────────────────────

REQUEST_TIMEOUT = 30  # 请求超时秒数
MAX_RETRIES = 2       # 最大重试次数


# ── 公共函数 ──────────────────────────────────────────────

def is_llm_available() -> bool:
    """
    判断 LLM 是否可用。

    检查 LLM_API_KEY 是否已配置且非空。

    返回:
        True 表示 LLM 可用，False 表示不可用
    """
    key = (LLM_API_KEY or "").strip()
    if not key:
        return False
    if _is_placeholder(key):
        return False
    return True


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
    if not is_llm_available():
        # 没有 API Key 时直接返回 None，由调用方进入 Fallback 分支。
        return None

    url = f"{LLM_BASE_URL.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {LLM_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": LLM_MODEL,
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
                print(f"[llm_client] LLM API 客户端错误 ({status_code}): {e}")
                return None
            last_error = f"HTTP {status_code}"
            continue
        except requests.exceptions.ConnectionError as e:
            last_error = "网络连接失败"
            continue
        except (KeyError, IndexError, TypeError) as e:
            # 响应格式异常通常表示服务端返回不符合 chat/completions 结构。
            print(f"[llm_client] LLM 响应格式异常: {e}")
            return None
        except Exception as e:
            print(f"[llm_client] LLM 调用未知错误: {e}")
            return None

    # 所有重试都失败
    print(f"[llm_client] LLM 调用失败（已重试 {MAX_RETRIES} 次），最后错误: {last_error}")
    return None


def get_llm_info() -> dict:
    """
    返回当前 LLM 配置信息（不含 API Key）。

    用于 UI 显示，帮助用户了解当前使用的模型。
    """
    return {
        "available": is_llm_available(),
        "base_url": LLM_BASE_URL,
        "model": LLM_MODEL,
    }
