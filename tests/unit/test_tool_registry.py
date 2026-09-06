"""单元测试: tool_registry + discovery_tools (P2.3)

测试:
- search_tools_by_query 关键词匹配与排序
- filter_tools_for_listing 在 progressive 模式下的过滤
- is_progressive_mode_enabled 环境变量解析
- handle_search_tools 返回格式
"""

import asyncio
import json
import os

import pytest

from dbjavagenix.database.discovery_tools import (
    get_discovery_tools,
    handle_search_tools,
)
from dbjavagenix.utils.tool_registry import (
    filter_tools_for_listing,
    get_all_metadata,
    get_always_visible_names,
    get_metadata,
    is_progressive_mode_enabled,
    search_tools_by_query,
)


@pytest.fixture(autouse=True)
def clear_progressive_env():
    """每个测试前后清理 progressive 环境变量"""
    original = os.environ.pop("DBJAVAGENIX_PROGRESSIVE", None)
    yield
    os.environ.pop("DBJAVAGENIX_PROGRESSIVE", None)
    if original is not None:
        os.environ["DBJAVAGENIX_PROGRESSIVE"] = original


class TestRegistryStructure:
    def test_all_metadata_loaded(self):
        all_meta = get_all_metadata()
        assert len(all_meta) >= 20

    def test_search_tools_in_registry(self):
        meta = get_metadata("search_tools")
        assert meta is not None
        assert meta.always_visible is True
        assert "search" in meta.tags

    def test_always_visible_names(self):
        names = get_always_visible_names()
        # 至少包含 SKILL 工作流前几步需要的核心工具
        for required in (
            "db_connect_test",
            "db_query_tables",
            "db_table_describe",
            "codegen_build_context",
            "springboot_validate_project",
            "search_tools",
        ):
            assert required in names, f"{required} should be always-visible"

    def test_metadata_unknown_returns_none(self):
        assert get_metadata("nonexistent_tool") is None


class TestSearchQuery:
    def test_exact_name_match_ranks_first(self):
        results = search_tools_by_query("codegen_render_dao")
        assert results[0]["name"] == "codegen_render_dao"

    def test_tag_search(self):
        results = search_tools_by_query("foreign")
        names = {r["name"] for r in results}
        assert "db_table_foreign_keys" in names

    def test_schema_algorithm_search(self):
        results = search_tools_by_query("topological")
        assert results[0]["name"] == "schema_topo_order"

    def test_multi_token_search(self):
        results = search_tools_by_query("render entity")
        names = [r["name"] for r in results]
        assert "codegen_render_entity" in names
        # render entity should be top 2
        assert names.index("codegen_render_entity") <= 2

    def test_empty_query_returns_always_visible(self):
        results = search_tools_by_query("")
        names = {r["name"] for r in results}
        assert names == get_always_visible_names()

    def test_no_match_returns_empty(self):
        results = search_tools_by_query("absolutely-no-such-tag-xyz")
        assert results == []

    def test_case_insensitive(self):
        upper = search_tools_by_query("CONNECT")
        lower = search_tools_by_query("connect")
        assert [r["name"] for r in upper] == [r["name"] for r in lower]

    def test_limit_respected(self):
        results = search_tools_by_query("render", limit=3)
        assert len(results) <= 3

    def test_score_field_present(self):
        results = search_tools_by_query("entity")
        assert all("score" in r for r in results)
        assert results[0]["score"] >= results[-1]["score"]


class TestProgressiveMode:
    def test_disabled_by_default(self):
        assert is_progressive_mode_enabled() is False

    def test_enabled_with_1(self):
        os.environ["DBJAVAGENIX_PROGRESSIVE"] = "1"
        assert is_progressive_mode_enabled() is True

    def test_enabled_with_true(self):
        os.environ["DBJAVAGENIX_PROGRESSIVE"] = "true"
        assert is_progressive_mode_enabled() is True

    def test_enabled_case_insensitive(self):
        os.environ["DBJAVAGENIX_PROGRESSIVE"] = "YES"
        assert is_progressive_mode_enabled() is True

    def test_disabled_with_random_value(self):
        os.environ["DBJAVAGENIX_PROGRESSIVE"] = "no"
        assert is_progressive_mode_enabled() is False


class TestFilterTools:
    def test_default_mode_returns_all(self):
        from mcp.types import Tool

        tools = [
            Tool(name="db_connect_test", description="d", inputSchema={"type": "object"}),
            Tool(name="codegen_render_entity", description="d", inputSchema={"type": "object"}),
        ]
        filtered = filter_tools_for_listing(tools)
        assert len(filtered) == 2

    def test_progressive_mode_filters(self):
        from mcp.types import Tool

        os.environ["DBJAVAGENIX_PROGRESSIVE"] = "1"
        tools = [
            Tool(name="db_connect_test", description="d", inputSchema={"type": "object"}),
            Tool(name="codegen_render_entity", description="d", inputSchema={"type": "object"}),
            Tool(name="search_tools", description="d", inputSchema={"type": "object"}),
        ]
        filtered = filter_tools_for_listing(tools)
        names = {t.name for t in filtered}
        assert "db_connect_test" in names
        assert "search_tools" in names
        assert "codegen_render_entity" not in names  # not always_visible


class TestDiscoveryTools:
    def test_get_discovery_tools_returns_one(self):
        tools = get_discovery_tools()
        assert len(tools) == 1
        assert tools[0].name == "search_tools"

    def test_search_tools_no_required_fields(self):
        tools = get_discovery_tools()
        schema = tools[0].inputSchema
        # query is optional
        assert schema.get("required") == []

    def test_handle_search_returns_json(self):
        result = asyncio.run(handle_search_tools({"query": "connect"}))
        assert len(result) == 1
        payload = json.loads(result[0].text)
        assert "results" in payload
        assert "query" in payload
        assert payload["query"] == "connect"
        names = [r["name"] for r in payload["results"]]
        assert "db_connect_test" in names

    def test_handle_search_with_empty_query(self):
        result = asyncio.run(handle_search_tools({"query": ""}))
        payload = json.loads(result[0].text)
        assert payload["result_count"] == len(get_always_visible_names())

    def test_handle_search_no_match_includes_hint(self):
        result = asyncio.run(handle_search_tools({"query": "no-tool-matches-xyz"}))
        payload = json.loads(result[0].text)
        assert payload["result_count"] == 0
        assert "hint" in payload

    def test_handle_search_respects_limit(self):
        result = asyncio.run(handle_search_tools({"query": "render", "limit": 2}))
        payload = json.loads(result[0].text)
        assert payload["result_count"] <= 2

    def test_handle_search_limit_clamped_to_max(self):
        result = asyncio.run(handle_search_tools({"query": "render", "limit": 999}))
        payload = json.loads(result[0].text)
        # 应被夹到 max=30,且结果 ≤ 实际匹配数
        assert payload["result_count"] <= 30
