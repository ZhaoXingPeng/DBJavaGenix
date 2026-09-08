"""Unit tests for the public code-generation analysis workflow."""

import asyncio
from types import SimpleNamespace

import pytest

from dbjavagenix.core.models import DatabaseType
from dbjavagenix.database.codegen_tools import CodegenAnalyzer, CodegenGenerator
from dbjavagenix.database.atomic_codegen_tools import get_atomic_codegen_tools
from dbjavagenix.database.mcp_tools import get_codegen_tools


class _FakeIntrospector:
    def list_tables(self, _connection_id):
        return ["users", "broken"]

    def list_table_references(self, _connection_id):
        return [
            {"name": "users", "schema": None},
            {"name": "broken", "schema": None},
        ]


class _SchemaAwareIntrospector:
    """Record metadata calls so schema forwarding stays observable in one test."""

    def __init__(self):
        self.calls = []

    def get_config(self, _connection_id):
        return SimpleNamespace(type=DatabaseType.POSTGRESQL, database="app")

    def get_table(self, connection_id, table_name, schema=None):
        self.calls.append(("table", connection_id, table_name, schema))
        return {"name": table_name, "schema": schema, "comment": "Users"}

    def get_columns(self, connection_id, table_name, schema=None):
        self.calls.append(("columns", connection_id, table_name, schema))
        return [
            {
                "name": "id",
                "type": "integer",
                "nullable": False,
                "primary_key": False,
                "default_value": None,
                "comment": "Primary key",
                "auto_increment": False,
                "max_length": None,
            }
        ]

    def get_primary_keys(self, connection_id, table_name, schema=None):
        self.calls.append(("primary_keys", connection_id, table_name, schema))
        return ["id"]

    def get_foreign_keys(self, connection_id, table_name, schema=None):
        self.calls.append(("foreign_keys", connection_id, table_name, schema))
        return []

    def get_indexes(self, connection_id, table_name, schema=None):
        self.calls.append(("indexes", connection_id, table_name, schema))
        return []


class _BatchAnalyzer(CodegenAnalyzer):
    def __init__(self):
        super().__init__(connection_manager=object())
        self.introspector = _FakeIntrospector()

    async def analyze_table_for_codegen(
        self,
        connection_id,
        table_name,
        all_table_names=None,
        template_category="Default",
        project_root=None,
        schema=None,
    ):
        if table_name == "broken":
            raise RuntimeError("metadata unavailable")
        return {"table_name": table_name, "template_context": {}}


@pytest.mark.asyncio
async def test_batch_analysis_keeps_success_and_error_accounting():
    result = await _BatchAnalyzer().analyze_database_for_codegen("conn-1")

    assert result["database_info"] == {
        "total_tables": 2,
        "analyzed_tables": 2,
        "success_count": 1,
        "error_count": 1,
    }
    assert result["tables"]["users"]["table_name"] == "users"
    assert result["tables"]["broken"]["error"] == "metadata unavailable"


class _PostgresBatchAnalyzer(CodegenAnalyzer):
    def __init__(self):
        super().__init__(connection_manager=object())
        self.introspector = type(
            "PostgresIntrospector",
            (),
            {
                "list_table_references": lambda _self, _connection_id: [
                    {"name": "users", "schema": "tenant_a"},
                    {"name": "users", "schema": "tenant_b"},
                ]
            },
        )()
        self.calls = []

    async def analyze_table_for_codegen(
        self,
        connection_id,
        table_name,
        all_table_names=None,
        template_category="Default",
        project_root=None,
        schema=None,
    ):
        self.calls.append((connection_id, table_name, schema))
        return {"table_name": table_name, "table_info": {"schema": schema}}


@pytest.mark.asyncio
async def test_batch_analysis_keeps_postgresql_schema_identity():
    analyzer = _PostgresBatchAnalyzer()

    result = await analyzer.analyze_database_for_codegen("pg-1")

    assert analyzer.calls == [
        ("pg-1", "users", "tenant_a"),
        ("pg-1", "users", "tenant_b"),
    ]
    assert result["database_info"] == {
        "total_tables": 2,
        "analyzed_tables": 2,
        "success_count": 2,
        "error_count": 0,
    }
    assert set(result["tables"]) == {"tenant_a.users", "tenant_b.users"}


@pytest.mark.asyncio
async def test_table_analysis_forwards_schema_to_all_metadata_queries():
    analyzer = CodegenAnalyzer(object())
    introspector = _SchemaAwareIntrospector()
    analyzer.introspector = introspector

    result = await analyzer.analyze_table_for_codegen(
        "pg-1", "users", template_category="Default", schema="tenant_a"
    )

    assert [call[0] for call in introspector.calls] == [
        "table",
        "columns",
        "primary_keys",
        "foreign_keys",
        "indexes",
    ]
    assert {call[3] for call in introspector.calls} == {"tenant_a"}
    assert result["table_info"]["schema"] == "tenant_a"
    assert result["relationships"]["primary_keys"] == ["id"]


def test_table_analysis_keeps_column_metadata_typed():
    analyzer = CodegenAnalyzer(object())
    introspector = _SchemaAwareIntrospector()

    def get_columns(_connection_id, _table_name, _schema=None):
        return [
            {
                "name": "id",
                "type": "BIGINT",
                "nullable": False,
                "primary_key": True,
                "default_value": None,
                "comment": "Primary key",
                "auto_increment": True,
                "max_length": None,
                "precision": None,
                "scale": None,
            }
        ]

    introspector.get_columns = get_columns
    analyzer.introspector = introspector

    result = asyncio.run(
        analyzer.analyze_table_for_codegen("mysql-1", "users", template_category="Default")
    )

    column = result["table_info"]["columns"][0]
    assert column["auto_increment"] is True
    assert column["precision"] is None
    assert column["scale"] is None


def test_codegen_entrypoints_expose_optional_schema():
    atomic = next(
        tool for tool in get_atomic_codegen_tools() if tool.name == "codegen_build_context"
    )
    legacy = {
        tool.name: tool
        for tool in get_codegen_tools()
        if tool.name in {"db_codegen_analyze", "db_codegen_generate"}
    }

    assert "schema" in atomic.inputSchema["properties"]
    assert {"db_codegen_analyze", "db_codegen_generate"} == set(legacy)
    assert all("schema" in tool.inputSchema["properties"] for tool in legacy.values())


def test_analyzer_has_no_legacy_direct_metadata_methods():
    analyzer = CodegenAnalyzer(object())

    for method_name in (
        "_get_table_info",
        "_get_columns_info",
        "_get_primary_keys",
        "_get_foreign_keys",
        "_get_indexes",
    ):
        assert not hasattr(analyzer, method_name)


@pytest.mark.asyncio
async def test_generator_rejects_unknown_category_before_reading_analysis():
    with pytest.raises(ValueError, match="不支持的模板分类"):
        await CodegenGenerator().generate_code({}, template_category="UnknownCategory")


@pytest.mark.asyncio
async def test_generator_does_not_require_unused_table_info(monkeypatch):
    generator = CodegenGenerator()

    async def render_template(_template_file, _context, _category):
        return "// generated"

    monkeypatch.setattr(generator, "_render_template", render_template)
    result = await generator.generate_code(
        {
            "table_name": "users",
            "template_context": {
                "className": "User",
                "package": "com.example",
                "packageSuffix": "",
            },
        },
        template_category="MybatisPlus",
    )

    assert result["generation_statistics"] == {
        "total_files": 6,
        "success_files": 6,
        "error_files": 0,
    }


@pytest.mark.asyncio
async def test_generator_loads_mybatis_plus_config_from_common_templates():
    code = await CodegenGenerator()._render_template(
        "mybatis_plus_config.mustache", {"basePackage": "com.example"}, "common"
    )

    assert "package com.example.config;" in code
    assert "class MybatisPlusConfig" in code
