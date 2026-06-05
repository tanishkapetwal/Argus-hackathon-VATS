"""Anthropic (Claude) implementation of LLMProvider — the DEFAULT provider.

Build-plan task 2.2. Tier -> model:
  strong -> Settings.llm_model_strong (default claude-opus-4-8)
  fast   -> Settings.llm_model_fast   (default claude-haiku-4-5-20251001)

Notes grounded in the Anthropic SDK (claude-api skill):
  - Structured output uses `messages.parse(..., output_format=Model)` -> `.parsed_output`,
    which validates the response against the Pydantic model for us.
  - Opus 4.7 / 4.8 REJECT `temperature` / `top_p` / `top_k` (HTTP 400), so we only send
    `temperature` for models that still accept it (detected by `_supports_sampling`).
  - The client is created lazily so the factory/tests can be used without an API key.
"""
from __future__ import annotations

from typing import TypeVar

import anthropic
from pydantic import BaseModel

from app.core.config import Settings
from app.llm.base import LLMProvider, LLMResponse

T = TypeVar("T", bound=BaseModel)


def _supports_sampling(model: str) -> bool:
    """Opus 4.7/4.8 removed sampling params (sending them is a 400). Everything else is fine."""
    m = model.lower()
    return not ("opus-4-8" in m or "opus-4-7" in m)


def _split_system(messages: list[dict]) -> tuple[str | None, list[dict]]:
    """Pull any {"role": "system"} entries into the top-level `system` arg (Anthropic style)."""
    system_parts: list[str] = []
    convo: list[dict] = []
    for m in messages:
        if m.get("role") == "system":
            content = m.get("content", "")
            if isinstance(content, str) and content:
                system_parts.append(content)
        else:
            convo.append(m)
    return ("\n\n".join(system_parts) if system_parts else None), convo


def _text_of(content) -> str:
    """Concatenate the text blocks of a response (ignores thinking/tool_use blocks)."""
    parts = [
        getattr(b, "text", "") or ""
        for b in (content or [])
        if getattr(b, "type", None) == "text"
    ]
    return "".join(parts)


def _tool_calls_of(content) -> list[dict]:
    """Map Anthropic tool_use blocks into plain dicts for LLMResponse.tool_calls."""
    return [
        {"id": b.id, "name": b.name, "input": b.input}
        for b in (content or [])
        if getattr(b, "type", None) == "tool_use"
    ]


def _raw_of(resp) -> dict:
    usage = getattr(resp, "usage", None)
    return {
        "id": getattr(resp, "id", None),
        "model": getattr(resp, "model", None),
        "stop_reason": getattr(resp, "stop_reason", None),
        "usage": usage.model_dump() if hasattr(usage, "model_dump") else None,
    }


class AnthropicProvider(LLMProvider):
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._client: anthropic.AsyncAnthropic | None = None

    @property
    def client(self) -> anthropic.AsyncAnthropic:
        """Lazily construct the async client (so no key is needed just to build the provider)."""
        if self._client is None:
            self._client = anthropic.AsyncAnthropic(
                api_key=self.settings.anthropic_api_key or None
            )
        return self._client

    def _model_for(self, tier: str) -> str:
        return (
            self.settings.llm_model_strong if tier == "strong" else self.settings.llm_model_fast
        )

    async def complete(
        self,
        messages: list[dict],
        *,
        tier: str = "strong",
        tools: list[dict] | None = None,
        response_model: type[T] | None = None,
        temperature: float = 0.2,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        """Run a completion. Structured output (response_model) is validated into `parsed`.

        Plain text -> `LLMResponse.text`; tool calls (if any) -> `LLMResponse.tool_calls`.
        On a structured-output validation failure the model is re-asked once before raising.
        """
        model = self._model_for(tier)
        system_text, convo = _split_system(messages)

        kwargs: dict = {"model": model, "max_tokens": max_tokens, "messages": convo}
        if system_text:
            kwargs["system"] = system_text
        if tools:
            kwargs["tools"] = tools
        if _supports_sampling(model):  # Opus 4.7/4.8 would 400 on temperature
            kwargs["temperature"] = temperature

        if response_model is not None:
            resp = await self._parse_with_retry(kwargs, response_model)
            return LLMResponse(
                text=_text_of(resp.content),
                parsed=resp.parsed_output,
                tool_calls=_tool_calls_of(resp.content),
                raw=_raw_of(resp),
            )

        resp = await self.client.messages.create(**kwargs)
        return LLMResponse(
            text=_text_of(resp.content),
            tool_calls=_tool_calls_of(resp.content),
            raw=_raw_of(resp),
        )

    async def _parse_with_retry(self, kwargs: dict, response_model: type[T]):
        """Call messages.parse; re-ask once if the structured output comes back empty/invalid.

        API errors (auth, rate limit, etc.) propagate immediately — retrying won't help those.
        """
        async def _once():
            resp = await self.client.messages.parse(output_format=response_model, **kwargs)
            if resp.parsed_output is None:
                raise ValueError("structured output came back empty")
            return resp

        try:
            return await _once()
        except anthropic.APIError:
            raise
        except Exception:
            return await _once()  # single re-ask on a validation/empty failure
