"""
同步 LLM Provider — 支持 anthropic / openai-chat 两种接口格式
复用 backend app/services/ai/provider.py 的协议设计，改为同步 httpx 调用
"""
from dataclasses import dataclass
import httpx
import json
from loguru import logger


@dataclass
class LLMConfig:
    provider_type: str   # "anthropic" | "openai-chat"
    base_url: str
    api_key: str
    model: str


class AnthropicProvider:
    """Anthropic /v1/messages (Claude) — 同步调用."""

    def chat_once(self, config: LLMConfig, system: str, prompt: str, max_tokens: int = 4000) -> str:
        url = f"{config.base_url.rstrip('/')}/messages"
        headers = {
            "x-api-key": config.api_key,
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01",
        }
        body = {
            "model": config.model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "stream": False,
        }
        if system:
            body["system"] = system

        with httpx.Client(timeout=httpx.Timeout(120.0)) as client:
            resp = client.post(url, headers=headers, json=body)
            if resp.status_code != 200:
                raise httpx.HTTPStatusError(
                    f"Anthropic API error: {resp.status_code} {resp.text}",
                    request=resp.request,
                    response=resp,
                )
            data = resp.json()
            content_blocks = data.get("content", [])
            for block in content_blocks:
                if block.get("type") == "text":
                    return block.get("text", "")
            return ""


class OpenAIChatProvider:
    """OpenAI-compatible /v1/chat/completions — 同步调用."""

    def chat_once(self, config: LLMConfig, system: str, prompt: str, max_tokens: int = 4000) -> str:
        url = f"{config.base_url.rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {config.api_key}",
            "Content-Type": "application/json",
        }
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        body = {
            "model": config.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "stream": False,
        }

        with httpx.Client(timeout=httpx.Timeout(120.0)) as client:
            resp = client.post(url, headers=headers, json=body)
            if resp.status_code != 200:
                raise httpx.HTTPStatusError(
                    f"OpenAI API error: {resp.status_code} {resp.text}",
                    request=resp.request,
                    response=resp,
                )
            data = resp.json()
            return data["choices"][0]["message"]["content"]


class LLMService:
    """统一 LLM 调用入口 — 根据 provider_type 自动分发."""

    _providers = {
        "anthropic": AnthropicProvider(),
        "openai-chat": OpenAIChatProvider(),
    }

    def __init__(self, config: LLMConfig):
        self.config = config
        self._provider = self._providers.get(config.provider_type)
        if not self._provider:
            raise ValueError(
                f"Unknown AI provider type: {config.provider_type}. "
                f"Supported: {list(self._providers.keys())}"
            )

    def chat_once(self, system: str, prompt: str, max_tokens: int = 4000) -> str:
        return self._provider.chat_once(self.config, system, prompt, max_tokens)
