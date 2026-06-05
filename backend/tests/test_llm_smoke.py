"""Live smoke test (build-plan Phase 2 demo): get a structured Pydantic object back from the
DEFAULT provider via a real API call.

Skipped automatically unless GEMINI_API_KEY is set, so the suite stays green offline. To run
it for real:  GEMINI_API_KEY=AIza... .venv/bin/python -m pytest tests/test_llm_smoke.py -s
"""
from __future__ import annotations

import os

import pytest
from pydantic import BaseModel

from app.llm.factory import get_provider


class Person(BaseModel):
    name: str
    age: int
    occupation: str


@pytest.mark.skipif(not os.getenv("GEMINI_API_KEY"), reason="GEMINI_API_KEY not set")
async def test_structured_object_from_default_provider():
    provider = get_provider()  # default = GeminiProvider from Settings
    out = await provider.complete(
        [{"role": "user", "content": "Ada Lovelace, age 36, mathematician. Fill the schema."}],
        response_model=Person,
        tier="fast",        # Haiku 4.5 supports structured outputs — cheap + fast for a smoke test
        max_tokens=512,
    )
    assert isinstance(out.parsed, Person)
    assert out.parsed.name and out.parsed.age > 0
    print("\nStructured result from default provider:", out.parsed.model_dump())
