"""Gemini implementation of LLMProvider.

Build-plan task 2.2. Tier -> model:
  strong -> Settings.llm_model_strong (default gemini-2.5-pro)
  fast   -> Settings.llm_model_fast   (default gemini-2.5-flash)
"""
from __future__ import annotations

import json
from typing import TypeVar

from google import genai
from google.genai import types
from pydantic import BaseModel

from app.core.config import Settings
from app.llm.base import LLMProvider, LLMResponse

T = TypeVar("T", bound=BaseModel)


def _split_system(messages: list[dict]) -> tuple[str | None, list[dict]]:
    """Pull any {"role": "system"} entries into the top-level `system_instruction`."""
    system_parts: list[str] = []
    convo: list[dict] = []
    for m in messages:
        if m.get("role") == "system":
            content = m.get("content", "")
            if isinstance(content, str) and content:
                system_parts.append(content)
        else:
            role = "user" if m.get("role") == "user" else "model"
            convo.append({"role": role, "parts": [{"text": m.get("content", "")}]})
    return ("\n\n".join(system_parts) if system_parts else None), convo


class GeminiProvider(LLMProvider):
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._client: genai.Client | None = None

    @property
    def client(self) -> genai.Client:
        if self._client is None:
            self._client = genai.Client(api_key=self.settings.gemini_api_key or None)
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
        model = self._model_for(tier)
        system_text, convo = _split_system(messages)

        config_dict = {
            "temperature": temperature,
        }
        if system_text:
            config_dict["system_instruction"] = system_text

        if response_model is not None:
            config_dict["response_mime_type"] = "application/json"
            
            # Inject schema into the system instructions to bypass response_schema truncation bugs
            schema_json = json.dumps(response_model.model_json_schema())
            instruction = config_dict.get("system_instruction", "")
            config_dict["system_instruction"] = f"{instruction}\n\nYou MUST return ONLY valid JSON matching this schema:\n{schema_json}"
            
            resp = await self._parse_with_retry(model, convo, config_dict, response_model)
            # Since we dropped response_schema, the SDK won't auto-parse, so we parse manually
            parsed = None
            if resp.text:
                parsed = response_model.model_validate_json(resp.text)
                
            return LLMResponse(
                text=resp.text or "",
                parsed=parsed,
                raw={"text": resp.text}
            )

        # Non-structured output
        config = types.GenerateContentConfig(**config_dict)
        resp = await self.client.aio.models.generate_content(
            model=model, contents=convo, config=config
        )
        return LLMResponse(text=resp.text, raw={"text": resp.text})

    async def _parse_with_retry(self, model: str, convo: list[dict], config_dict: dict, response_model: type[T]):
        """Call generate_content; re-ask once if the structured output validation fails."""
        config = types.GenerateContentConfig(**config_dict)
        async def _once():
            resp = await self.client.aio.models.generate_content(
                model=model, contents=convo, config=config
            )
            # Try parsing it early so we can catch errors
            if not resp.text:
                raise ValueError(f"Empty response. Candidates: {getattr(resp, 'candidates', [])}")
            response_model.model_validate_json(resp.text)
            return resp

        try:
            return await _once()
        except Exception:
            return await _once()
