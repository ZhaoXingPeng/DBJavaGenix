"""Unit tests for schema_algorithms_tools (MCP tool wrappers)."""

import asyncio
import json

import pytest

from dbjavagenix.database.schema_algorithms_tools import (
    SCHEMA_ALGORITHM_TOOLS,
    handle_schema_check_cycles,
    handle_schema_cluster_tables,
    handle_schema_topo_order,
)


def _run(coro):
    return asyncio.run(coro)


class TestToolRegistration:
    def test_three_tools_exported(self):
        names = {t.name for t in SCHEMA_ALGORITHM_TOOLS}
        assert names == {
            "schema_topo_order",
            "schema_cluster_tables",
            "schema_check_cycles",
        }

    def test_tools_have_input_schema(self):
        for tool in SCHEMA_ALGORITHM_TOOLS:
            assert tool.inputSchema["type"] == "object"
            assert "tables" in tool.inputSchema["properties"]
            assert "fks" in tool.inputSchema["properties"]


class TestSchemaTopoOrder:
    def test_rbac_returns_json(self):
        result = _run(
            handle_schema_topo_order(
                {
                    "tables": ["sys_user", "sys_role", "sys_user_role"],
                    "fks": [
                        ["sys_user_role", "sys_user"],
                        ["sys_user_role", "sys_user"],
                    ],
                }
            )
        )
        assert len(result) == 1
        payload = json.loads(result[0].text)
        assert payload["has_cycle"] is False
        assert payload["order"][-1] == "sys_user_role"

    def test_detects_cycle(self):
        result = _run(
            handle_schema_topo_order({"tables": ["a", "b"], "fks": [["a", "b"], ["b", "a"]]})
        )
        payload = json.loads(result[0].text)
        assert payload["has_cycle"] is True
        assert set(payload["unresolved"]) == {"a", "b"}


class TestSchemaClusterTables:
    def test_returns_cluster_count(self):
        result = _run(
            handle_schema_cluster_tables(
                {
                    "tables": ["sys_user", "sys_role", "sys_user_role"],
                    "fks": [["sys_user_role", "sys_user"]],
                }
            )
        )
        payload = json.loads(result[0].text)
        assert payload["num_clusters"] == 2  # {sys_user, sys_user_role} + {sys_role}

    def test_cluster_has_name(self):
        result = _run(
            handle_schema_cluster_tables(
                {
                    "tables": ["biz_a", "biz_b"],
                    "fks": [["biz_b", "biz_a"]],
                }
            )
        )
        payload = json.loads(result[0].text)
        # Common prefix "biz_" → "biz_*"
        assert payload["clusters"][0]["name"] == "biz_*"


class TestSchemaCheckCycles:
    def test_safe_returns_true(self):
        result = _run(handle_schema_check_cycles({"tables": ["a", "b"], "fks": [["b", "a"]]}))
        payload = json.loads(result[0].text)
        assert payload["safe"] is True
        assert payload["cycle_count"] == 0

    def test_cycle_reported(self):
        result = _run(
            handle_schema_check_cycles(
                {
                    "tables": ["a", "b", "c"],
                    "fks": [["a", "b"], ["b", "c"], ["c", "a"]],
                }
            )
        )
        payload = json.loads(result[0].text)
        assert payload["safe"] is False
        assert payload["cycle_count"] == 1


class TestMalformedInput:
    def test_missing_fields_handled(self):
        result = _run(handle_schema_topo_order({}))
        payload = json.loads(result[0].text)
        assert payload["order"] == []

    def test_malformed_fk_tuple_skipped(self):
        # Not a 2-element list → skipped
        result = _run(handle_schema_topo_order({"tables": ["a"], "fks": [["a"], ["a", "b", "c"]]}))
        payload = json.loads(result[0].text)
        assert payload["order"] == ["a"]

    def test_string_containers_are_not_split_into_nodes(self):
        result = _run(handle_schema_topo_order({"tables": "users", "fks": "invalid"}))
        payload = json.loads(result[0].text)
        assert payload == {
            "order": [],
            "unresolved": [],
            "levels": {},
            "has_cycle": False,
        }

    def test_duplicate_tables_are_normalized_before_rendering(self):
        result = _run(
            handle_schema_cluster_tables(
                {
                    "tables": ["users", "users", "orders"],
                    "fks": [["orders", "users"], ["orders", "users"]],
                }
            )
        )
        payload = json.loads(result[0].text)
        assert payload["num_clusters"] == 1
        assert payload["clusters"][0]["members"] == ["orders", "users"]
