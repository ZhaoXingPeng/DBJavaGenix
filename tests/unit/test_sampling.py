"""Unit tests for mcp_apps.sampling."""
import asyncio

import pytest

from dbjavagenix.mcp_apps.sampling import (
    ModelPreferences,
    SamplingClient,
    build_sampling_request,
)


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


class TestModelPreferences:
    def test_default_serialization(self):
        p = ModelPreferences()
        d = p.to_dict()
        assert d["intelligencePriority"] == 0.5
        assert d["speedPriority"] == 0.5
        assert "hints" not in d

    def test_hints_serialized_as_name_objects(self):
        p = ModelPreferences(hints=["claude-sonnet-4-6"])
        d = p.to_dict()
        assert d["hints"] == [{"name": "claude-sonnet-4-6"}]

    def test_custom_priorities(self):
        p = ModelPreferences(intelligence_priority=0.9, cost_priority=0.1)
        d = p.to_dict()
        assert d["intelligencePriority"] == 0.9
        assert d["costPriority"] == 0.1


class TestBuildSamplingRequest:
    def test_minimal(self):
        r = build_sampling_request("infer names for sys_user")
        assert r["maxTokens"] == 1024
        assert len(r["messages"]) == 1
        assert r["messages"][0]["role"] == "user"
        assert "systemPrompt" not in r
        assert "modelPreferences" not in r

    def test_with_system_prompt(self):
        r = build_sampling_request("hello", system_prompt="You are an expert.")
        assert r["systemPrompt"] == "You are an expert."

    def test_with_model_prefs(self):
        r = build_sampling_request("hello", model_prefs=ModelPreferences(intelligence_priority=0.9))
        assert r["modelPreferences"]["intelligencePriority"] == 0.9

    def test_empty_message_raises(self):
        with pytest.raises(ValueError):
            build_sampling_request("")

    def test_invalid_max_tokens(self):
        with pytest.raises(ValueError):
            build_sampling_request("hi", max_tokens=0)
        with pytest.raises(ValueError):
            build_sampling_request("hi", max_tokens=10000)


class TestSamplingClient:
    def test_sync_dispatcher(self):
        captured = {}

        def dispatcher(payload):
            captured["payload"] = payload
            return {"content": [{"type": "text", "text": "ok"}]}

        client = SamplingClient(dispatcher)
        result = _run(client.complete("ping"))
        assert result == "ok"
        assert captured["payload"]["messages"][0]["content"]["text"] == "ping"

    def test_async_dispatcher(self):
        async def dispatcher(payload):
            return {"content": [{"type": "text", "text": "async-ok"}]}

        client = SamplingClient(dispatcher)
        result = _run(client.complete("ping"))
        assert result == "async-ok"

    def test_non_callable_raises(self):
        with pytest.raises(TypeError):
            SamplingClient("not a function")

    def test_extracts_text_from_string_response(self):
        client = SamplingClient(lambda p: "plain string")
        result = _run(client.complete("ping"))
        assert result == "plain string"

    def test_extracts_text_from_text_key(self):
        client = SamplingClient(lambda p: {"text": "from-text-key"})
        result = _run(client.complete("ping"))
        assert result == "from-text-key"

    def test_none_response_returns_empty(self):
        client = SamplingClient(lambda p: None)
        result = _run(client.complete("ping"))
        assert result == ""

    def test_propagates_system_prompt(self):
        captured = {}
        def dispatcher(p):
            captured["p"] = p
            return {"text": "ok"}

        client = SamplingClient(dispatcher)
        _run(client.complete("ping", system_prompt="sys"))
        assert captured["p"]["systemPrompt"] == "sys"
