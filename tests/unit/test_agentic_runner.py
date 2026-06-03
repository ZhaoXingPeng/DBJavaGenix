"""Unit tests for server.agentic_runner."""
import os

import pytest

from dbjavagenix.server.agentic_runner import (
    AgenticConfig,
    AgenticResult,
    _filter_tools,
    is_agentic_available,
    run_agentic,
)


class TestAgenticConfig:
    def test_minimal_valid(self):
        c = AgenticConfig(goal="analyze schema")
        assert c.goal == "analyze schema"
        assert c.model == "claude-opus-4-7"
        assert c.max_iterations == 20
        assert c.allowed_tools is None
        assert c.dry_run is False

    def test_empty_goal_raises(self):
        with pytest.raises(ValueError, match="goal"):
            AgenticConfig(goal="")

    def test_non_string_goal_raises(self):
        with pytest.raises(ValueError):
            AgenticConfig(goal=123)  # type: ignore

    def test_max_iter_too_low(self):
        with pytest.raises(ValueError, match="max_iterations"):
            AgenticConfig(goal="x", max_iterations=0)

    def test_max_iter_too_high(self):
        with pytest.raises(ValueError):
            AgenticConfig(goal="x", max_iterations=101)


class TestAvailability:
    def test_no_api_key_returns_false(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        ok, reason = is_agentic_available()
        assert ok is False
        assert "ANTHROPIC_API_KEY" in reason


class TestFilterTools:
    def test_none_passes_all(self):
        r = {"a": 1, "b": 2}
        assert _filter_tools(r, None) == r

    def test_empty_list_passes_all(self):
        r = {"a": 1, "b": 2}
        assert _filter_tools(r, []) == r

    def test_filter_to_subset(self):
        r = {"a": 1, "b": 2, "c": 3}
        assert _filter_tools(r, ["a", "c"]) == {"a": 1, "c": 3}

    def test_unknown_name_silently_dropped(self):
        r = {"a": 1}
        assert _filter_tools(r, ["a", "nonexistent"]) == {"a": 1}


class TestDryRun:
    """dry_run 路径不需要真实 SDK,只验证配置和工具数量。"""

    def test_dry_run_with_key_succeeds(self, monkeypatch):
        # dry_run 走 is_agentic_available 前置,需要 key 才能进 dry_run 分支
        # 但 SDK 可能没装。我们直接让 is_agentic_available mock 为 True 的
        # 路径靠 monkeypatch 实现。
        monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-test-key")
        # 如果 sdk 没装 is_agentic_available 仍返回 False,我们 monkeypatch 它
        import dbjavagenix.server.agentic_runner as mod
        monkeypatch.setattr(mod, "is_agentic_available", lambda: (True, ""))

        config = AgenticConfig(goal="test goal", dry_run=True)
        result = run_agentic(config, tool_registry_factory=lambda: {"tool_a": {}, "tool_b": {}})
        assert result.success is True
        assert result.iterations_used == 0
        assert "test goal" in result.final_message
        assert "tools=2" in result.final_message

    def test_dry_run_respects_allowed_tools(self, monkeypatch):
        import dbjavagenix.server.agentic_runner as mod
        monkeypatch.setattr(mod, "is_agentic_available", lambda: (True, ""))

        config = AgenticConfig(
            goal="x", dry_run=True, allowed_tools=["tool_a"]
        )
        result = run_agentic(config, tool_registry_factory=lambda: {"tool_a": {}, "tool_b": {}})
        assert result.success is True
        assert "tools=1" in result.final_message


class TestUnavailable:
    def test_returns_error_result_when_unavailable(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        config = AgenticConfig(goal="x")
        result = run_agentic(config)
        assert result.success is False
        assert result.error is not None
        assert "unavailable" in result.error
