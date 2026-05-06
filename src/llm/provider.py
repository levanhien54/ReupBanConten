"""
LLM Provider — Abstract base + implementations.

Hỗ trợ: Ollama (local), OpenAI, Anthropic.
Fallback chain khi provider chính fail.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import aiohttp
from abc import ABC, abstractmethod
from typing import Any, Optional

from src.core.errors import (
    LLMError,
    LLMProviderUnavailableError,
    LLMResponseParseError,
    LLMTimeoutError,
)
from src.core.logging import get_logger, log_duration

logger = get_logger(__name__)


# ──────────────────────────────────────────────
#  Abstract Base
# ──────────────────────────────────────────────

class LLMProvider(ABC):
    """Abstract base class cho tất cả LLM providers."""

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        *,
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> str:
        """Generate text từ prompt."""
        ...

    async def generate_json(self, prompt: str, **kwargs: Any) -> dict:
        """Generate và parse JSON response."""
        response = await self.generate(prompt, **kwargs)
        return parse_llm_json(response)

    @abstractmethod
    def is_available(self) -> bool:
        """Kiểm tra provider sẵn sàng."""
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider display name."""
        ...


# ──────────────────────────────────────────────
#  Ollama Provider
# ──────────────────────────────────────────────

class OllamaProvider(LLMProvider):
    """Ollama local LLM provider."""

    def __init__(
        self,
        model: str = "llama3",
        base_url: str = "http://localhost:11434",
    ) -> None:
        self._model = model
        self._base_url = base_url
        self._client: Any = None

    @property
    def name(self) -> str:
        return f"ollama/{self._model}"

    def _get_client(self) -> Any:
        if self._client is None:
            import ollama
            self._client = ollama.AsyncClient(host=self._base_url)
        return self._client

    @log_duration(msg_template="Ollama generate {func_name}")
    async def generate(
        self,
        prompt: str,
        *,
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> str:
        client = self._get_client()
        try:
            response = await client.generate(
                model=self._model,
                prompt=prompt,
                options={
                    "temperature": temperature,
                    "num_predict": max_tokens,
                    "top_p": 0.9,
                },
            )
            return response["response"]
        except Exception as e:
            raise LLMError(
                f"Ollama generation failed: {e}",
                context={"model": self._model},
            ) from e

    def is_available(self) -> bool:
        try:
            import ollama
            client = ollama.Client(host=self._base_url)
            models = client.list()
            available = [m.get("name", "") for m in models.get("models", [])]
            return any(self._model in m for m in available)
        except Exception:
            return False


# ──────────────────────────────────────────────
#  OpenAI Provider
# ──────────────────────────────────────────────

class OpenAIProvider(LLMProvider):
    """OpenAI API provider."""

    def __init__(
        self,
        model: str = "gpt-4o-mini",
        api_key: Optional[str] = None,
    ) -> None:
        self._model = model
        self._api_key = api_key or os.getenv("OPENAI_API_KEY", "")
        self._client: Any = None

    @property
    def name(self) -> str:
        return f"openai/{self._model}"

    def _get_client(self) -> Any:
        if self._client is None:
            from openai import AsyncOpenAI
            self._client = AsyncOpenAI(api_key=self._api_key)
        return self._client

    @log_duration(msg_template="OpenAI generate {func_name}")
    async def generate(
        self,
        prompt: str,
        *,
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> str:
        client = self._get_client()
        try:
            response = await client.chat.completions.create(
                model=self._model,
                messages=[
                    {
                        "role": "system",
                        "content": "Bạn là AI assistant chuyên phân tích video. "
                        "Luôn trả lời bằng JSON khi được yêu cầu.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            raise LLMError(
                f"OpenAI generation failed: {e}",
                context={"model": self._model},
            ) from e

    def is_available(self) -> bool:
        return bool(self._api_key) and len(self._api_key) > 10


# ──────────────────────────────────────────────
#  Anthropic Provider
# ──────────────────────────────────────────────

class AnthropicProvider(LLMProvider):
    """Anthropic Claude provider."""

    def __init__(
        self,
        model: str = "claude-3-5-sonnet-20241022",
        api_key: Optional[str] = None,
    ) -> None:
        self._model = model
        self._api_key = api_key or os.getenv("ANTHROPIC_API_KEY", "")
        self._client: Any = None

    @property
    def name(self) -> str:
        return f"anthropic/{self._model}"

    def _get_client(self) -> Any:
        if self._client is None:
            import anthropic
            self._client = anthropic.AsyncAnthropic(api_key=self._api_key)
        return self._client

    @log_duration(msg_template="Anthropic generate {func_name}")
    async def generate(
        self,
        prompt: str,
        *,
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> str:
        client = self._get_client()
        try:
            response = await client.messages.create(
                model=self._model,
                max_tokens=max_tokens,
                temperature=temperature,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.content[0].text
        except Exception as e:
            raise LLMError(
                f"Anthropic generation failed: {e}",
                context={"model": self._model},
            ) from e

    def is_available(self) -> bool:
        return bool(self._api_key) and len(self._api_key) > 10


# ──────────────────────────────────────────────
#  Gemini Provider
# ──────────────────────────────────────────────

class GeminiProvider(LLMProvider):
    """Google Gemini AI provider."""

    def __init__(
        self,
        model: str = "gemini-1.5-flash",
        api_key: Optional[str] = None,
    ) -> None:
        self._model_name = model
        self._api_key = api_key or os.getenv("GOOGLE_API_KEY", "")
        self._client: Any = None

    @property
    def name(self) -> str:
        return f"gemini/{self._model_name}"

    def _get_client(self) -> Any:
        if self._client is None:
            import google.generativeai as genai
            genai.configure(api_key=self._api_key)
            self._client = genai.GenerativeModel(self._model_name)
        return self._client

    @log_duration(msg_template="Gemini generate {func_name}")
    async def generate(
        self,
        prompt: str,
        *,
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> str:
        model = self._get_client()
        try:
            # Gemini dùng async bằng cách gọi to_thread hoặc dùng Async client nếu có 
            # (Thư viện chính thức dùng sync nhưng có async version)
            # Dùng awaitable wrapper nếu cần
            generation_config = {
                "temperature": temperature,
                "max_output_tokens": max_tokens,
            }
            
            # Chạy sync method trong thread để không block event loop
            response = await asyncio.to_thread(
                model.generate_content,
                prompt, 
                generation_config=generation_config
            )
            return response.text
        except Exception as e:
            raise LLMError(
                f"Gemini generation failed: {e}",
                context={"model": self._model_name},
            ) from e

    def is_available(self) -> bool:
        return bool(self._api_key) and len(self._api_key) > 10


# ──────────────────────────────────────────────
#  Fallback Provider
# ──────────────────────────────────────────────

class FallbackProvider(LLMProvider):
    """Provider wrapper với fallback chain."""

    def __init__(self, providers: list[LLMProvider]) -> None:
        if not providers:
            raise ValueError("At least one provider is required")
        self._providers = providers

    @property
    def name(self) -> str:
        names = [p.name for p in self._providers]
        return f"fallback({' → '.join(names)})"

    async def generate(
        self,
        prompt: str,
        *,
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> str:
        last_error: Optional[Exception] = None

        for provider in self._providers:
            if not provider.is_available():
                logger.debug(f"Skipping unavailable provider: {provider.name}")
                continue

            try:
                result = await provider.generate(
                    prompt, temperature=temperature, max_tokens=max_tokens
                )
                logger.info(f"LLM success via {provider.name}")
                return result
            except Exception as e:
                logger.warning(f"LLM failed ({provider.name}): {e}")
                last_error = e

        raise LLMProviderUnavailableError(
            f"All LLM providers failed. Last error: {last_error}",
            context={"providers": [p.name for p in self._providers]},
        )

    def is_available(self) -> bool:
        return any(p.is_available() for p in self._providers)


# ──────────────────────────────────────────────
#  Factory
# ──────────────────────────────────────────────

class LLMFactory:
    """Factory tạo LLM provider."""

    _registry: dict[str, type[LLMProvider]] = {
        "ollama": OllamaProvider,
        "openai": OpenAIProvider,
        "anthropic": AnthropicProvider,
        "gemini": GeminiProvider,
    }

    @classmethod
    def create(cls, provider: str = "ollama", **kwargs: Any) -> LLMProvider:
        """Tạo provider instance."""
        provider_cls = cls._registry.get(provider)
        if provider_cls is None:
            raise ValueError(
                f"Unknown provider: {provider}. "
                f"Available: {list(cls._registry.keys())}"
            )
        return provider_cls(**kwargs)

    @classmethod
    def create_with_fallback(
        cls,
        primary: str = "ollama",
        fallbacks: Optional[list[str]] = None,
        **kwargs: Any,
    ) -> FallbackProvider:
        """Tạo provider với fallback chain."""
        fallbacks = fallbacks or ["openai"]

        providers = [cls.create(primary, **kwargs)]
        for fb in fallbacks:
            try:
                providers.append(cls.create(fb))
            except Exception:
                pass

        return FallbackProvider(providers)


# ──────────────────────────────────────────────
#  JSON Parsing Utilities
# ──────────────────────────────────────────────

def parse_llm_json(response: str) -> dict:
    """
    Parse JSON từ LLM response với multi-fallback.

    Thử theo thứ tự:
    1. Direct JSON parse
    2. Markdown code block extraction
    3. Regex JSON object extraction
    4. Regex JSON array extraction
    """
    response = response.strip()

    # 1. Direct parse
    try:
        return json.loads(response)
    except json.JSONDecodeError:
        pass

    # 2. Markdown code block
    match = re.search(r"```(?:json)?\s*\n?([\s\S]*?)\n?```", response)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            pass

    # 3. JSON object
    match = re.search(r"(\{[\s\S]*\})", response)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # 4. JSON array
    match = re.search(r"(\[[\s\S]*\])", response)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    raise LLMResponseParseError(
        f"Cannot parse JSON from LLM response",
        context={"response_preview": response[:300]},
    )


async def generate_with_retry(
    provider: LLMProvider,
    prompt: str,
    *,
    max_retries: int = 3,
) -> dict:
    """Generate JSON từ LLM với retry + temperature escalation."""
    temperatures = [0.3, 0.5, 0.7]

    for attempt in range(max_retries):
        temp = temperatures[min(attempt, len(temperatures) - 1)]
        try:
            response = await provider.generate(prompt, temperature=temp)
            return parse_llm_json(response)
        except LLMResponseParseError as e:
            logger.warning(f"Retry {attempt + 1}/{max_retries}: JSON parse failed")
            if attempt == max_retries - 1:
                raise
        except LLMError:
            if attempt == max_retries - 1:
                raise

    raise LLMError("Max retries exceeded")
