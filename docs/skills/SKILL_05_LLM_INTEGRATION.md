# Skill 05: LLM Integration (Ollama + OpenAI + Claude)

## Mục Tiêu
Tích hợp nhiều LLM providers với fallback strategy.

---

## Provider Architecture

```python
from abc import ABC, abstractmethod
from typing import Optional
import json
import logging

logger = logging.getLogger(__name__)


class LLMProvider(ABC):
    """Abstract base class cho LLM providers."""
    
    @abstractmethod
    async def generate(self, prompt: str, temperature: float = 0.3,
                        max_tokens: int = 4096) -> str:
        """Generate text từ prompt."""
        pass
    
    async def generate_json(self, prompt: str, **kwargs) -> dict:
        """Generate và parse JSON response."""
        response = await self.generate(prompt, **kwargs)
        return parse_llm_json(response)
    
    @abstractmethod
    def is_available(self) -> bool:
        """Kiểm tra provider sẵn sàng."""
        pass
    
    @property
    @abstractmethod
    def name(self) -> str:
        pass


class OllamaProvider(LLMProvider):
    """Ollama local LLM provider."""
    
    def __init__(self, model: str = "llama3", 
                 base_url: str = "http://localhost:11434"):
        self.model = model
        self.base_url = base_url
        self._client = None
    
    @property
    def name(self) -> str:
        return f"ollama/{self.model}"
    
    def _get_client(self):
        if self._client is None:
            import ollama
            self._client = ollama.AsyncClient(host=self.base_url)
        return self._client
    
    async def generate(self, prompt: str, temperature: float = 0.3,
                        max_tokens: int = 4096) -> str:
        client = self._get_client()
        response = await client.generate(
            model=self.model,
            prompt=prompt,
            options={
                'temperature': temperature,
                'num_predict': max_tokens,
                'top_p': 0.9,
            }
        )
        return response['response']
    
    def is_available(self) -> bool:
        try:
            import ollama
            client = ollama.Client(host=self.base_url)
            models = client.list()
            return any(m['name'].startswith(self.model) 
                       for m in models.get('models', []))
        except Exception:
            return False


class OpenAIProvider(LLMProvider):
    """OpenAI API provider."""
    
    def __init__(self, model: str = "gpt-4o-mini", api_key: str = None):
        self.model = model
        self.api_key = api_key
        self._client = None
    
    @property
    def name(self) -> str:
        return f"openai/{self.model}"
    
    def _get_client(self):
        if self._client is None:
            from openai import AsyncOpenAI
            self._client = AsyncOpenAI(api_key=self.api_key)
        return self._client
    
    async def generate(self, prompt: str, temperature: float = 0.3,
                        max_tokens: int = 4096) -> str:
        client = self._get_client()
        response = await client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "Bạn là AI assistant chuyên phân tích video. Luôn trả lời bằng JSON khi được yêu cầu."},
                {"role": "user", "content": prompt}
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content
    
    def is_available(self) -> bool:
        return self.api_key is not None and len(self.api_key) > 10


class AnthropicProvider(LLMProvider):
    """Anthropic Claude provider."""
    
    def __init__(self, model: str = "claude-3-5-sonnet-20241022", 
                 api_key: str = None):
        self.model = model
        self.api_key = api_key
        self._client = None
    
    @property
    def name(self) -> str:
        return f"anthropic/{self.model}"
    
    def _get_client(self):
        if self._client is None:
            import anthropic
            self._client = anthropic.AsyncAnthropic(api_key=self.api_key)
        return self._client
    
    async def generate(self, prompt: str, temperature: float = 0.3,
                        max_tokens: int = 4096) -> str:
        client = self._get_client()
        response = await client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text
    
    def is_available(self) -> bool:
        return self.api_key is not None and len(self.api_key) > 10
```

---

## Provider Factory + Fallback

```python
class LLMFactory:
    """Factory tạo LLM provider với fallback chain."""
    
    @staticmethod
    def create(provider: str = "ollama", **kwargs) -> LLMProvider:
        providers = {
            'ollama': OllamaProvider,
            'openai': OpenAIProvider,
            'anthropic': AnthropicProvider,
        }
        
        cls = providers.get(provider)
        if cls is None:
            raise ValueError(f"Unknown provider: {provider}")
        
        return cls(**kwargs)
    
    @staticmethod
    def create_with_fallback(primary: str = "ollama",
                              fallbacks: list[str] = None,
                              **kwargs) -> 'FallbackProvider':
        """Tạo provider với fallback chain."""
        fallbacks = fallbacks or ['openai']
        
        providers = [LLMFactory.create(primary, **kwargs)]
        for fb in fallbacks:
            try:
                providers.append(LLMFactory.create(fb, **kwargs))
            except Exception:
                pass
        
        return FallbackProvider(providers)


class FallbackProvider(LLMProvider):
    """Provider wrapper với fallback chain."""
    
    def __init__(self, providers: list[LLMProvider]):
        self.providers = providers
    
    @property
    def name(self) -> str:
        names = [p.name for p in self.providers]
        return f"fallback({' -> '.join(names)})"
    
    async def generate(self, prompt: str, **kwargs) -> str:
        last_error = None
        
        for provider in self.providers:
            if not provider.is_available():
                continue
            try:
                result = await provider.generate(prompt, **kwargs)
                logger.info(f"LLM success: {provider.name}")
                return result
            except Exception as e:
                logger.warning(f"LLM failed ({provider.name}): {e}")
                last_error = e
        
        raise RuntimeError(f"All LLM providers failed. Last: {last_error}")
    
    def is_available(self) -> bool:
        return any(p.is_available() for p in self.providers)
```

---

## JSON Parsing Utilities

```python
import re

def parse_llm_json(response: str) -> dict:
    """Parse JSON từ LLM response với nhiều fallback."""
    
    # Clean response
    response = response.strip()
    
    # 1. Thử parse trực tiếp
    try:
        return json.loads(response)
    except json.JSONDecodeError:
        pass
    
    # 2. Tìm trong markdown code block
    match = re.search(r'```(?:json)?\s*\n?([\s\S]*?)\n?```', response)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            pass
    
    # 3. Tìm JSON object {...}
    match = re.search(r'(\{[\s\S]*\})', response)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    
    # 4. Tìm JSON array [...]
    match = re.search(r'(\[[\s\S]*\])', response)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    
    raise ValueError(f"Cannot parse JSON from response: {response[:300]}")


async def llm_generate_with_retry(provider: LLMProvider, prompt: str,
                                    max_retries: int = 3) -> dict:
    """Generate JSON từ LLM với retry logic."""
    temperatures = [0.3, 0.5, 0.7]
    
    for i in range(max_retries):
        try:
            temp = temperatures[min(i, len(temperatures) - 1)]
            response = await provider.generate(prompt, temperature=temp)
            return parse_llm_json(response)
        except (ValueError, json.JSONDecodeError) as e:
            logger.warning(f"Retry {i+1}/{max_retries}: {e}")
            if i == max_retries - 1:
                raise
        except Exception as e:
            logger.error(f"LLM error: {e}")
            if i == max_retries - 1:
                raise
    
    raise RuntimeError("Max retries exceeded")
```

---

## Prompt Manager

```python
import os

class PromptManager:
    """Quản lý và load prompt templates."""
    
    def __init__(self, prompts_dir: str = "config/prompts"):
        self.prompts_dir = prompts_dir
        self._cache = {}
    
    def get(self, name: str, **kwargs) -> str:
        """Load và format prompt template."""
        if name not in self._cache:
            path = os.path.join(self.prompts_dir, f"{name}.txt")
            with open(path, 'r', encoding='utf-8') as f:
                self._cache[name] = f.read()
        
        template = self._cache[name]
        
        if kwargs:
            return template.format(**kwargs)
        return template
    
    def list_prompts(self) -> list[str]:
        """Liệt kê tất cả prompt templates."""
        return [
            f.replace('.txt', '')
            for f in os.listdir(self.prompts_dir)
            if f.endswith('.txt')
        ]
```

---

## Sử Dụng

```python
# Quick start
provider = LLMFactory.create("ollama", model="llama3")

# Với fallback
provider = LLMFactory.create_with_fallback(
    primary="ollama",
    fallbacks=["openai"],
    model="llama3"
)

# Generate
result = await llm_generate_with_retry(
    provider, 
    "Phân tích video này... Trả về JSON"
)
```
