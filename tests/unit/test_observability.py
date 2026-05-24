"""单元测试: utils.metrics + database.observability_tools (P5.1)"""

import asyncio
import json

import pytest

from dbjavagenix.database.observability_tools import (
    handle_server_health,
    handle_server_metrics,
)
from dbjavagenix.utils.metrics import (
    GLOBAL_TOOL_METRICS,
    ToolCallMetrics,
    ToolStats,
    track_tool_call,
)


@pytest.fixture(autouse=True)
def reset_global():
    """每个测试前后重置全局 metrics"""
    GLOBAL_TOOL_METRICS.reset()
    yield
    GLOBAL_TOOL_METRICS.reset()


# ============================================================
# ToolStats
# ============================================================

class TestToolStats:
    def test_initial_state(self):
        s = ToolStats(name="x")
        assert s.calls == 0
        assert s.avg_duration_ms == 0.0
        assert s.error_rate == 0.0

    def test_record_single(self):
        s = ToolStats(name="x")
        s.record(duration_ms=10.5, is_error=False)
        assert s.calls == 1
        assert s.errors == 0
        assert s.total_duration_ms == 10.5
        assert s.last_duration_ms == 10.5
        assert s.min_duration_ms == 10.5
        assert s.max_duration_ms == 10.5

    def test_record_multiple_with_error(self):
        s = ToolStats(name="x")
        s.record(10.0, False)
        s.record(20.0, True)
        s.record(15.0, False)
        assert s.calls == 3
        assert s.errors == 1
        assert s.avg_duration_ms == 15.0
        assert s.error_rate == pytest.approx(1 / 3)
        assert s.min_duration_ms == 10.0
        assert s.max_duration_ms == 20.0

    def test_to_dict_has_required_keys(self):
        s = ToolStats(name="x")
        s.record(5.0, False)
        d = s.to_dict()
        for key in ("name", "calls", "errors", "error_rate", "avg_duration_ms"):
            assert key in d


# ============================================================
# ToolCallMetrics
# ============================================================

class TestToolCallMetrics:
    def test_uptime_increases(self):
        m = ToolCallMetrics()
        import time as _t
        _t.sleep(0.01)
        assert m.uptime_seconds > 0

    def test_record_and_retrieve(self):
        m = ToolCallMetrics()
        m.record("foo", 100.0, False)
        m.record("foo", 200.0, True)
        s = m.get_stats("foo")
        assert s.calls == 2
        assert s.errors == 1

    def test_snapshot_sorted_by_calls(self):
        m = ToolCallMetrics()
        m.record("less", 10.0, False)
        m.record("more", 10.0, False)
        m.record("more", 10.0, False)
        m.record("more", 10.0, False)
        snap = m.snapshot()
        assert snap["total_tool_calls"] == 4
        assert snap["tools"][0]["name"] == "more"
        assert snap["tools"][1]["name"] == "less"

    def test_reset(self):
        m = ToolCallMetrics()
        m.record("x", 10.0, False)
        m.reset()
        assert m.snapshot()["total_tool_calls"] == 0

    def test_overall_error_rate(self):
        m = ToolCallMetrics()
        m.record("x", 1.0, False)
        m.record("y", 1.0, True)
        snap = m.snapshot()
        assert snap["overall_error_rate"] == 0.5


# ============================================================
# 装饰器
# ============================================================

class TestTrackToolCall:
    def test_records_success(self):
        @track_tool_call("test_tool")
        async def my_handler():
            return "ok"

        result = asyncio.run(my_handler())
        assert result == "ok"
        stats = GLOBAL_TOOL_METRICS.get_stats("test_tool")
        assert stats.calls == 1
        assert stats.errors == 0

    def test_records_error_and_reraises(self):
        @track_tool_call("test_tool_err")
        async def failing():
            raise ValueError("oops")

        with pytest.raises(ValueError):
            asyncio.run(failing())

        stats = GLOBAL_TOOL_METRICS.get_stats("test_tool_err")
        assert stats.calls == 1
        assert stats.errors == 1


# ============================================================
# Handlers
# ============================================================

class TestServerMetricsHandler:
    def test_empty(self):
        result = asyncio.run(handle_server_metrics({}))
        payload = json.loads(result[0].text)
        assert payload["metrics"]["total_tool_calls"] == 0

    def test_after_recording(self):
        GLOBAL_TOOL_METRICS.record("x", 5.0, False)
        result = asyncio.run(handle_server_metrics({}))
        payload = json.loads(result[0].text)
        assert payload["metrics"]["total_tool_calls"] == 1

    def test_reset_flag(self):
        GLOBAL_TOOL_METRICS.record("x", 5.0, False)
        result = asyncio.run(handle_server_metrics({"reset": True}))
        payload = json.loads(result[0].text)
        assert payload.get("reset") is True
        # 二次读取应是 0
        result2 = asyncio.run(handle_server_metrics({}))
        payload2 = json.loads(result2[0].text)
        assert payload2["metrics"]["total_tool_calls"] == 0


class TestServerHealthHandler:
    def test_basic_structure(self):
        result = asyncio.run(handle_server_health({}))
        payload = json.loads(result[0].text)
        for key in ("status", "uptime_seconds", "server", "runtime", "modules", "database", "ai"):
            assert key in payload

    def test_status_ok_when_all_modules_load(self):
        result = asyncio.run(handle_server_health({}))
        payload = json.loads(result[0].text)
        # 当前测试环境模块都能 import → ok
        assert payload["status"] == "ok"

    def test_runtime_contains_python_version(self):
        result = asyncio.run(handle_server_health({}))
        payload = json.loads(result[0].text)
        assert payload["runtime"]["python_version"]
        assert "." in payload["runtime"]["python_version"]
