"""
AI Service - 支持 OpenAI Chat / Anthropic 两种接口格式
兼容 DeepSeek、Kimi、Minimax、Claude 等模型
"""
import httpx
import json
import asyncio
from typing import Optional, Literal, AsyncIterator
from dataclasses import dataclass


@dataclass
class AIConfig:
    provider_type: str          # "openai-chat" | "anthropic"
    base_url: str              # API endpoint base URL
    api_key: str               # decrypted API key
    model: str                 # model name


@dataclass
class ChatMessage:
    role: Literal["system", "user", "assistant"]
    content: str


# ----- Provider implementations -----

class OpenAIChatProvider:
    """OpenAI-compatible /v1/chat/completions provider."""

    async def chat(
        self,
        config: AIConfig,
        messages: list[ChatMessage],
        stream: bool = True,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> AsyncIterator[str]:
        url = f"{config.base_url.rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {config.api_key}",
            "Content-Type": "application/json",
        }
        body = {
            "model": config.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": stream,
        }

        async with httpx.AsyncClient(timeout=httpx.Timeout(120.0)) as client:
            async with client.stream("POST", url, headers=headers, json=body) as resp:
                if resp.status_code != 200:
                    text = await resp.text()
                    raise RuntimeError(f"AI request failed: {resp.status_code} {text}")
                async for line in resp.aiter_lines():
                    line = line.strip()
                    if not line or line == "data: [DONE]":
                        continue
                    if line.startswith("data: "):
                        line = line[6:]
                    try:
                        data = json.loads(line)
                        delta = data.get("choices", [{}])[0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            yield content
                    except json.JSONDecodeError:
                        continue

    async def chat_once(
        self,
        config: AIConfig,
        messages: list[ChatMessage],
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> str:
        url = f"{config.base_url.rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {config.api_key}",
            "Content-Type": "application/json",
        }
        body = {
            "model": config.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }

        async with httpx.AsyncClient(timeout=httpx.Timeout(120.0)) as client:
            resp = await client.post(url, headers=headers, json=body)
            if resp.status_code != 200:
                raise RuntimeError(f"AI request failed: {resp.status_code} {resp.text}")
            data = resp.json()
            return data["choices"][0]["message"]["content"]


class OpenAIResponsesProvider:
    """OpenAI /v1/responses provider (GPT-4o etc.)."""

    async def chat(
        self,
        config: AIConfig,
        messages: list[ChatMessage],
        stream: bool = True,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> AsyncIterator[str]:
        url = f"{config.base_url.rstrip('/')}/responses"
        headers = {
            "Authorization": f"Bearer {config.api_key}",
            "Content-Type": "application/json",
        }
        # Convert ChatMessage list to OpenAI Responses input format
        input_messages = [{"role": m.role, "content": m.content} for m in messages]
        body: dict = {
            "model": config.model,
            "input": input_messages,
            "stream": stream,
        }

        async with httpx.AsyncClient(timeout=httpx.Timeout(120.0)) as client:
            if not stream:
                resp = await client.post(url, headers=headers, json=body)
                if resp.status_code != 200:
                    raise RuntimeError(f"AI request failed: {resp.status_code} {resp.text}")
                data = resp.json()
                for item in data.get("output", []):
                    if item.get("type") == "message":
                        for content in item.get("content", []):
                            if content.get("type") == "output_text":
                                yield content.get("text", "")
                return

            async with client.stream("POST", url, headers=headers, json=body) as resp:
                if resp.status_code != 200:
                    text = await resp.text()
                    raise RuntimeError(f"AI request failed: {resp.status_code} {text}")
                async for line in resp.aiter_lines():
                    line = line.strip()
                    if not line:
                        continue
                    if line.startswith("data: "):
                        line = line[6:]
                    try:
                        data = json.loads(line)
                        event_type = data.get("type", "")
                        if event_type == "response.output_text.delta":
                            delta = data.get("delta", "")
                            if delta:
                                yield delta
                    except json.JSONDecodeError:
                        continue

    async def chat_once(
        self,
        config: AIConfig,
        messages: list[ChatMessage],
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> str:
        parts = []
        async for chunk in self.chat(config, messages, stream=False, temperature=temperature, max_tokens=max_tokens):
            parts.append(chunk)
        return "".join(parts)


class AnthropicProvider:
    """Anthropic /v1/messages provider (Claude)."""

    async def chat(
        self,
        config: AIConfig,
        messages: list[ChatMessage],
        stream: bool = True,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> AsyncIterator[str]:
        url = f"{config.base_url.rstrip('/')}/messages"
        headers = {
            "x-api-key": config.api_key,
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01",
            "anthropic-dangerous-direct-browser-access": "true",
        }

        # Build system prompt from first system message
        system_prompt = ""
        filtered_messages = []
        for m in messages:
            if m.role == "system":
                system_prompt = m.content
            else:
                filtered_messages.append({"role": m.role, "content": m.content})

        body: dict = {
            "model": config.model,
            "messages": filtered_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": stream,
        }
        if system_prompt:
            body["system"] = system_prompt

        async with httpx.AsyncClient(timeout=httpx.Timeout(120.0)) as client:
            async with client.stream("POST", url, headers=headers, json=body) as resp:
                if resp.status_code != 200:
                    text = await resp.text()
                    raise RuntimeError(f"AI request failed: {resp.status_code} {text}")
                async for line in resp.aiter_lines():
                    line = line.strip()
                    if not line or line == "data: [DONE]":
                        continue
                    if line.startswith("data: "):
                        line = line[6:]
                    try:
                        data = json.loads(line)
                        if data.get("type") == "content_block_delta":
                            content = data.get("delta", {}).get("text", "")
                            if content:
                                yield content
                    except json.JSONDecodeError:
                        continue

    async def chat_once(
        self,
        config: AIConfig,
        messages: list[ChatMessage],
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> str:
        url = f"{config.base_url.rstrip('/')}/messages"
        headers = {
            "x-api-key": config.api_key,
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01",
            "anthropic-dangerous-direct-browser-access": "true",
        }

        system_prompt = ""
        filtered_messages = []
        for m in messages:
            if m.role == "system":
                system_prompt = m.content
            else:
                filtered_messages.append({"role": m.role, "content": m.content})

        body: dict = {
            "model": config.model,
            "messages": filtered_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }
        if system_prompt:
            body["system"] = system_prompt

        async with httpx.AsyncClient(timeout=httpx.Timeout(120.0)) as client:
            resp = await client.post(url, headers=headers, json=body)
            if resp.status_code != 200:
                raise RuntimeError(f"AI request failed: {resp.status_code} {resp.text}")
            data = resp.json()
            return data["content"][0]["text"]


# ----- Unified AIService -----

class AIService:
    _providers = {
        "openai-chat": OpenAIChatProvider(),
        "openai-responses": OpenAIResponsesProvider(),
        "anthropic": AnthropicProvider(),
    }

    def __init__(self, config: AIConfig):
        self.config = config
        provider = self._providers.get(config.provider_type)
        if not provider:
            raise ValueError(f"Unknown AI provider type: {config.provider_type}")
        self._provider = provider

    async def chat_stream(
        self,
        messages: list[ChatMessage],
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> AsyncIterator[str]:
        async for chunk in self._provider.chat(
            config=self.config,
            messages=messages,
            stream=True,
            temperature=temperature,
            max_tokens=max_tokens,
        ):
            yield chunk

    async def chat_once(
        self,
        messages: list[ChatMessage],
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> str:
        return await self._provider.chat_once(
            config=self.config,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    # ----- Translation helpers -----

    @staticmethod
    def build_translation_system_prompt(target_lang: str = "Chinese", custom_prompt: Optional[str] = None) -> str:
        if custom_prompt:
            return custom_prompt
        return (
            f"You are a professional translator. Translate the following text to {target_lang}. "
            "Keep the original meaning, tone, and formatting. "
            "Only output the translation, no explanations or commentary."
        )

    @staticmethod
    def build_translation_messages(text: str, target_lang: str = "Chinese", custom_prompt: Optional[str] = None) -> list[ChatMessage]:
        return [
            ChatMessage(role="system", content=AIService.build_translation_system_prompt(target_lang, custom_prompt)),
            ChatMessage(role="user", content=text),
        ]

    @staticmethod
    def build_askai_system_prompt(
        book_title: Optional[str] = None,
        chapter_title: Optional[str] = None,
    ) -> str:
        parts = [
            "You are a helpful reading assistant. Help the user understand and analyze the book content.",
            "Provide clear, thoughtful, and accurate responses.",
        ]
        if book_title:
            parts.insert(0, f"Current book: {book_title}")
        if chapter_title:
            parts.append(f"Current chapter: {chapter_title}")
        return "\n".join(parts)
