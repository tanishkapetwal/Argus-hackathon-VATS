"""get_provider() — selects the LLMProvider impl from Settings.llm_provider.

Adding a provider: implement LLMProvider, add a branch here, add env vars. No agent changes
(docs/contributing.md §C). Build-plan task 2.3.
"""
from __future__ import annotations

from app.core.config import Settings, get_settings
from app.llm.base import LLMProvider


def get_provider(settings: Settings | None = None) -> LLMProvider:
    settings = settings or get_settings()
    if settings.llm_provider == "gemini":
        from app.llm.gemini_provider import GeminiProvider  # noqa: WPS433
        return GeminiProvider(settings)
    if settings.llm_provider == "openai":
        from app.llm.openai_provider import OpenAIProvider  # noqa: WPS433
        return OpenAIProvider(settings)
    if settings.llm_provider == "scripted":
        # Offline/keyless demo provider (canned structured output). See scripted_provider.py.
        from app.llm.scripted_provider import ScriptedProvider  # noqa: WPS433
        return ScriptedProvider(settings)
    raise ValueError(f"Unknown LLM_PROVIDER: {settings.llm_provider!r}")
