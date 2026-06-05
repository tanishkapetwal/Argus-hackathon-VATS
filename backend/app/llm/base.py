"""LLMProvider interface — the seam that decouples agents from any LLM vendor.

Spec: docs/architecture.md §2 (LLM layer), docs/tech-stack.md. Build-plan task 2.1.
Supports plain completion, tool/function calling, and structured output (parse into a Pydantic
model). Agents pass a tier; the provider maps tier -> concrete model from Settings.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


@dataclass
class LLMResponse:
    text: str
    parsed: BaseModel | None = None        # set when response_model was requested
    tool_calls: list[dict] = field(default_factory=list)
    raw: dict | None = None


class LLMProvider(ABC):
    """Implement once per vendor (anthropic_provider.py, openai_provider.py)."""

    @abstractmethod
    async def complete(
        self,
        messages: list[dict],
        *,
        tier: str = "strong",                 # "strong" | "fast" -> model via Settings
        tools: list[dict] | None = None,
        response_model: type[T] | None = None,
        temperature: float = 0.2,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        """Run a completion.

        - If `response_model` is given, instruct the model to return JSON matching that schema
          and parse it into `LLMResponse.parsed` (re-ask once on validation failure).
        - If `tools` is given, surface any tool calls in `LLMResponse.tool_calls`.
        """
        raise NotImplementedError
