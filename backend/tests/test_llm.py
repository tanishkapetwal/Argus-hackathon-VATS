"""Tests for the LLM layer (build-plan 2.1-2.3): AnthropicProvider mapping + factory.

These are deterministic and network-free: a fake async client stands in for
`anthropic.AsyncAnthropic`, so we can assert the request we build (model, omitted sampling
params, extracted system prompt) and how we map the response into `LLMResponse`. The live
round-trip lives in test_llm_smoke.py (skipped without a key).
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from pydantic import BaseModel

from app.core.config import Settings
from app.llm.anthropic_provider import AnthropicProvider, _supports_sampling
from app.llm.base import LLMProvider
from app.llm.factory import get_provider


class Person(BaseModel):
    name: str
    age: int


def _text_block(text: str):
    return SimpleNamespace(type="text", text=text)


def _tool_block(id_: str, name: str, inp: dict):
    return SimpleNamespace(type="tool_use", id=id_, name=name, input=inp)


def _msg(content, *, model="claude-opus-4-8", parsed=None, stop="end_turn"):
    return SimpleNamespace(
        content=content, parsed_output=parsed, id="msg_1", model=model,
        stop_reason=stop, usage=None,
    )


class _FakeMessages:
    """Records the kwargs each call receives so tests can assert on the request shape."""

    def __init__(self, *, parse_results=None, create_result=None):
        self.calls: list[tuple[str, dict]] = []
        self._parse_results = list(parse_results or [])
        self._create_result = create_result

    async def parse(self, **kwargs):
        self.calls.append(("parse", kwargs))
        r = self._parse_results.pop(0)
        if isinstance(r, Exception):
            raise r
        return r

    async def create(self, **kwargs):
        self.calls.append(("create", kwargs))
        return self._create_result


class _FakeClient:
    def __init__(self, messages):
        self.messages = messages


def _provider_with(messages, **settings_overrides) -> tuple[AnthropicProvider, _FakeMessages]:
    prov = AnthropicProvider(Settings(**settings_overrides))
    prov._client = _FakeClient(messages)  # inject fake; bypasses lazy real-client creation
    return prov, messages


# ───────────────────────────── factory (2.3) ──────────────────────────────
def test_factory_returns_anthropic_provider():
    prov = get_provider(Settings(llm_provider="anthropic"))
    assert isinstance(prov, AnthropicProvider)
    assert isinstance(prov, LLMProvider)


def test_factory_unknown_provider_raises():
    with pytest.raises(ValueError):
        get_provider(Settings(llm_provider="bogus"))


def test_supports_sampling_excludes_opus_47_48():
    assert _supports_sampling("claude-opus-4-8") is False
    assert _supports_sampling("claude-opus-4-7") is False
    assert _supports_sampling("claude-haiku-4-5-20251001") is True
    assert _supports_sampling("claude-sonnet-4-6") is True


# ──────────────────────── structured output (2.2) ─────────────────────────
async def test_structured_output_is_parsed_and_validated():
    result = _msg([_text_block("{...}")], parsed=Person(name="Ada", age=36))
    prov, fake = _provider_with(
        _FakeMessages(parse_results=[result]), llm_model_strong="claude-opus-4-8"
    )

    out = await prov.complete([{"role": "user", "content": "make a person"}], response_model=Person)

    assert isinstance(out.parsed, Person)
    assert (out.parsed.name, out.parsed.age) == ("Ada", 36)
    method, kwargs = fake.calls[0]
    assert method == "parse"
    assert kwargs["output_format"] is Person
    assert "temperature" not in kwargs  # opus-4-8 would 400 on temperature


async def test_structured_output_reasks_once_when_empty():
    empty = _msg([], parsed=None)
    good = _msg([_text_block("{}")], parsed=Person(name="Bo", age=5))
    fake = _FakeMessages(parse_results=[empty, good])
    prov, fake = _provider_with(fake)

    out = await prov.complete([{"role": "user", "content": "x"}], response_model=Person)

    assert out.parsed.name == "Bo"
    assert len(fake.calls) == 2  # re-asked exactly once


# ─────────────────────────── plain + tools (2.2) ──────────────────────────
async def test_plain_completion_returns_text_and_sends_temperature_for_haiku():
    created = _msg([_text_block("hello world")], model="claude-haiku-4-5-20251001")
    prov, fake = _provider_with(_FakeMessages(create_result=created))

    out = await prov.complete([{"role": "user", "content": "hi"}], tier="fast")

    assert out.text == "hello world"
    assert out.parsed is None
    method, kwargs = fake.calls[0]
    assert method == "create"
    assert kwargs["temperature"] == 0.2  # haiku accepts sampling params


async def test_tool_use_blocks_are_mapped():
    content = [_text_block("checking"), _tool_block("t1", "get_weather", {"city": "Pune"})]
    created = _msg(content, model="claude-haiku-4-5-20251001", stop="tool_use")
    prov, fake = _provider_with(_FakeMessages(create_result=created))

    out = await prov.complete(
        [{"role": "user", "content": "weather?"}],
        tier="fast",
        tools=[{"name": "get_weather", "description": "x", "input_schema": {"type": "object"}}],
    )

    assert out.tool_calls == [{"id": "t1", "name": "get_weather", "input": {"city": "Pune"}}]
    assert "tools" in fake.calls[0][1]


async def test_system_message_is_lifted_to_top_level():
    fake = _FakeMessages(create_result=_msg([_text_block("ok")]))
    prov, fake = _provider_with(fake)

    await prov.complete(
        [{"role": "system", "content": "You are a dietitian."}, {"role": "user", "content": "hi"}]
    )

    _, kwargs = fake.calls[0]
    assert kwargs["system"] == "You are a dietitian."
    assert kwargs["messages"] == [{"role": "user", "content": "hi"}]
