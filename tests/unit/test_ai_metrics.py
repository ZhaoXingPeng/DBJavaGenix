"""单元测试: ai_metrics (P4.4)"""

import asyncio
import json

from dbjavagenix.ai.llm_client import GLOBAL_LLM_STATS, LLMMetrics
from dbjavagenix.database.ai_tools import handle_ai_metrics


def _reset_global_stats():
    GLOBAL_LLM_STATS.total_calls = 0
    GLOBAL_LLM_STATS.total_input_tokens = 0
    GLOBAL_LLM_STATS.total_output_tokens = 0
    GLOBAL_LLM_STATS.total_cache_read = 0
    GLOBAL_LLM_STATS.total_cache_creation = 0
    GLOBAL_LLM_STATS.total_errors = 0


class TestAiMetricsHandler:
    def setup_method(self):
        _reset_global_stats()

    def teardown_method(self):
        _reset_global_stats()

    def test_empty_metrics(self):
        result = asyncio.run(handle_ai_metrics({}))
        payload = json.loads(result[0].text)
        assert "metrics" in payload
        assert "llm_available" in payload
        assert payload["metrics"]["ai.calls_total"] == 0
        assert payload["metrics"]["ai.cache_hit_rate"] == 0.0

    def test_metrics_after_some_calls(self):
        GLOBAL_LLM_STATS.record(LLMMetrics(
            input_tokens=100, output_tokens=50,
            cache_read_input_tokens=200, cache_creation_input_tokens=30,
        ))
        GLOBAL_LLM_STATS.record(LLMMetrics(
            input_tokens=80, output_tokens=40,
            cache_read_input_tokens=300, cache_creation_input_tokens=0,
        ))

        result = asyncio.run(handle_ai_metrics({}))
        payload = json.loads(result[0].text)
        metrics = payload["metrics"]
        assert metrics["ai.calls_total"] == 2
        assert metrics["ai.tokens.input_total"] == 180
        assert metrics["ai.tokens.output_total"] == 90
        assert metrics["ai.tokens.cache_read_total"] == 500
        assert metrics["ai.tokens.cache_creation_total"] == 30
        # cache_hit_rate = 500 / (500 + 30 + 180) = 500/710
        assert abs(metrics["ai.cache_hit_rate"] - 500 / 710) < 1e-3
        assert metrics["ai.tokens_saved_via_cache"] == 500

    def test_reset_clears_stats(self):
        GLOBAL_LLM_STATS.record(LLMMetrics(input_tokens=50))
        result = asyncio.run(handle_ai_metrics({"reset": True}))
        payload = json.loads(result[0].text)
        assert payload.get("reset") is True
        # 二次读取应是 0
        result2 = asyncio.run(handle_ai_metrics({}))
        payload2 = json.loads(result2[0].text)
        assert payload2["metrics"]["ai.calls_total"] == 0

    def test_errors_counted(self):
        GLOBAL_LLM_STATS.record(LLMMetrics(error="json_decode_failed"))
        result = asyncio.run(handle_ai_metrics({}))
        payload = json.loads(result[0].text)
        assert payload["metrics"]["ai.errors_total"] == 1
