"""Unit tests for mcp_apps.elicitation."""
import pytest

from dbjavagenix.mcp_apps.elicitation import (
    build_elicitation_request,
    missing_params_to_elicitation,
    to_meta_hint,
)


class TestBuildElicitationRequest:
    def test_minimal_valid(self):
        r = build_elicitation_request(
            "请填入数据库连接信息",
            {"type": "object", "properties": {"host": {"type": "string"}}},
        )
        assert r["message"] == "请填入数据库连接信息"
        assert r["requestedSchema"]["type"] == "object"
        assert "host" in r["requestedSchema"]["properties"]

    def test_empty_message_raises(self):
        with pytest.raises(ValueError, match="non-empty"):
            build_elicitation_request("", {"type": "object"})

    def test_non_string_message_raises(self):
        with pytest.raises(ValueError):
            build_elicitation_request(123, {"type": "object"})

    def test_non_dict_schema_raises(self):
        with pytest.raises(ValueError):
            build_elicitation_request("msg", "not a dict")

    def test_non_object_schema_raises(self):
        with pytest.raises(ValueError, match="type=object"):
            build_elicitation_request("msg", {"type": "string"})


class TestMissingParamsToElicitation:
    def test_all_present_returns_none(self):
        schema = {
            "type": "object",
            "required": ["host", "port"],
            "properties": {
                "host": {"type": "string"},
                "port": {"type": "integer"},
            },
        }
        received = {"host": "localhost", "port": 3306}
        assert missing_params_to_elicitation("db_connect_test", received, schema) is None

    def test_missing_one_param(self):
        schema = {
            "type": "object",
            "required": ["host", "port", "password"],
            "properties": {
                "host": {"type": "string"},
                "port": {"type": "integer"},
                "password": {"type": "string"},
            },
        }
        received = {"host": "localhost", "port": 3306}
        elic = missing_params_to_elicitation("db_connect_test", received, schema)
        assert elic is not None
        assert "password" in elic["message"]
        assert elic["requestedSchema"]["required"] == ["password"]
        assert "password" in elic["requestedSchema"]["properties"]

    def test_missing_multiple_params(self):
        schema = {
            "type": "object",
            "required": ["host", "port", "password"],
            "properties": {
                "host": {"type": "string"},
                "port": {"type": "integer"},
                "password": {"type": "string"},
            },
        }
        elic = missing_params_to_elicitation("db_connect_test", {}, schema)
        assert elic is not None
        assert set(elic["requestedSchema"]["required"]) == {"host", "port", "password"}

    def test_empty_string_treated_as_missing(self):
        schema = {
            "type": "object",
            "required": ["password"],
            "properties": {"password": {"type": "string"}},
        }
        received = {"password": ""}
        elic = missing_params_to_elicitation("t", received, schema)
        assert elic is not None
        assert "password" in elic["requestedSchema"]["required"]

    def test_none_value_treated_as_missing(self):
        schema = {
            "type": "object",
            "required": ["password"],
            "properties": {"password": {"type": "string"}},
        }
        received = {"password": None}
        elic = missing_params_to_elicitation("t", received, schema)
        assert elic is not None

    def test_no_required_field(self):
        schema = {"type": "object", "properties": {"x": {"type": "string"}}}
        assert missing_params_to_elicitation("t", {}, schema) is None


class TestMetaHint:
    def test_wraps_in_mcp_apps_namespace(self):
        elic = build_elicitation_request("msg", {"type": "object"})
        meta = to_meta_hint(elic)
        assert "mcp-apps/elicitation" in meta
        assert meta["mcp-apps/elicitation"] == elic
