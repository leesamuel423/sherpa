from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from sherpa.config import settings

DEFAULT_MODELS: dict[str, str] = {
    "groq": "llama-3.3-70b-versatile",
    "openai": "gpt-4o-mini",
    "anthropic": "claude-sonnet-4-20250514",
}


@runtime_checkable
class LLMClient(Protocol):
    async def chat(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        response_format: dict[str, str] | None = None,
        max_tokens: int = 2000,
    ) -> str: ...


def _resolve_model(provider: str, explicit: str | None = None) -> str:
    return explicit or settings.llm_model or DEFAULT_MODELS[provider]


class GroqClient:
    def __init__(self) -> None:
        import groq

        self._client = groq.AsyncGroq(api_key=settings.groq_api_key)

    async def chat(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        response_format: dict[str, str] | None = None,
        max_tokens: int = 2000,
    ) -> str:
        kwargs: dict[str, Any] = {
            "model": _resolve_model("groq", model),
            "messages": messages,
            "max_tokens": max_tokens,
        }
        if response_format:
            kwargs["response_format"] = response_format

        response = await self._client.chat.completions.create(**kwargs)
        return response.choices[0].message.content or ""


class OpenAIClient:
    def __init__(self) -> None:
        import openai

        self._client = openai.AsyncOpenAI(api_key=settings.openai_api_key)

    async def chat(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        response_format: dict[str, str] | None = None,
        max_tokens: int = 2000,
    ) -> str:
        kwargs: dict[str, Any] = {
            "model": _resolve_model("openai", model),
            "messages": messages,
            "max_tokens": max_tokens,
        }
        if response_format:
            kwargs["response_format"] = response_format

        response = await self._client.chat.completions.create(**kwargs)
        return response.choices[0].message.content or ""


class AnthropicClient:
    def __init__(self) -> None:
        import anthropic

        self._client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    async def chat(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        response_format: dict[str, str] | None = None,
        max_tokens: int = 2000,
    ) -> str:
        system_parts = []
        non_system = []
        for msg in messages:
            if msg["role"] == "system":
                system_parts.append(msg["content"])
            else:
                non_system.append(msg)

        if response_format and response_format.get("type") == "json_object":
            if non_system and non_system[-1]["role"] == "user":
                non_system[-1] = {
                    **non_system[-1],
                    "content": non_system[-1]["content"]
                    + "\n\nRespond with valid JSON only.",
                }
            non_system.append({"role": "assistant", "content": "{"})

        kwargs: dict[str, Any] = {
            "model": _resolve_model("anthropic", model),
            "messages": non_system,
            "max_tokens": max_tokens,
        }
        if system_parts:
            kwargs["system"] = "\n\n".join(system_parts)

        response = await self._client.messages.create(**kwargs)
        text = response.content[0].text

        if response_format and response_format.get("type") == "json_object":
            text = "{" + text

        return text


def create_llm_client() -> LLMClient:
    provider = settings.llm_provider.lower()
    if provider == "groq":
        return GroqClient()
    elif provider == "openai":
        return OpenAIClient()
    elif provider == "anthropic":
        return AnthropicClient()
    else:
        raise ValueError(
            f"Unknown LLM provider: {provider!r}. "
            f"Supported: {', '.join(DEFAULT_MODELS)}"
        )
