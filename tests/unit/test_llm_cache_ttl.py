"""Unit tests for cache_ttl parameter in llm_client.infer_names_via_llm."""
import pytest

from dbjavagenix.ai.llm_client import infer_names_via_llm


class TestCacheTtlValidation:
    """Tests for the cache_ttl parameter — these don't require ANTHROPIC_API_KEY
    since validation happens before the API call."""

    def test_default_is_5m(self):
        # Default arg = "5m" — calling with no cache_ttl should not raise
        # ValueError. It may return None (no API key) but that's fine.
        result = infer_names_via_llm(tables=[])
        # result is None either because no API key, or because tables is empty
        # The point is: no ValueError was raised
        assert result is None or result.inferences == []

    def test_explicit_5m_valid(self):
        result = infer_names_via_llm(tables=[], cache_ttl="5m")
        assert result is None or hasattr(result, "inferences")

    def test_explicit_1h_valid(self):
        result = infer_names_via_llm(tables=[], cache_ttl="1h")
        assert result is None or hasattr(result, "inferences")

    def test_invalid_ttl_raises(self):
        with pytest.raises(ValueError, match="cache_ttl"):
            infer_names_via_llm(tables=[], cache_ttl="30m")

    def test_invalid_ttl_24h_raises(self):
        with pytest.raises(ValueError):
            infer_names_via_llm(tables=[], cache_ttl="24h")

    def test_invalid_ttl_empty_raises(self):
        with pytest.raises(ValueError):
            infer_names_via_llm(tables=[], cache_ttl="")

    def test_invalid_ttl_none_raises(self):
        with pytest.raises(ValueError):
            infer_names_via_llm(tables=[], cache_ttl=None)
