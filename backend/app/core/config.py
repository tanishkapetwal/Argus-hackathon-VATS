"""Typed application settings loaded from the environment / .env.

Spec: ../../.env.example, docs/tech-stack.md. Implements build-plan.md task 0.2.
"""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # LLM provider selection
    llm_provider: str = "gemini"
    gemini_api_key: str = ""
    llm_model_strong: str = "gemini-2.5-flash"
    llm_model_fast: str = "gemini-2.5-flash"
    # OpenAI (optional)
    openai_api_key: str = ""
    openai_model_strong: str = "gpt-4o"
    openai_model_fast: str = "gpt-4o-mini"

    # Tools
    usda_fdc_api_key: str = "DEMO_KEY"
    tavily_api_key: str = ""
    use_seeded_prices: bool = True

    # Orchestration
    max_refinement_rounds: int = 3

    # App
    frontend_origin: str = "http://localhost:5173"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    log_level: str = "INFO"


_settings: Settings | None = None


def get_settings() -> Settings:
    """Cached settings accessor."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
