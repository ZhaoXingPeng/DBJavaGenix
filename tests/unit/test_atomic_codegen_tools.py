"""单元测试: database.atomic_codegen_tools (P2.2)

测试 7 个原子代码生成工具的:
- Tool 定义结构 (name/description/inputSchema)
- 渲染逻辑 (sb35-java21 + MybatisPlus-Mixed)
- mapper 工具按 template_category 分发
- 包路径重建与技术栈互斥规则
- context 容忍 JSON 字符串输入

不依赖数据库 — build_context handler 需要 DB 连接,这里用 unit fixture context dict 直接喂给 render_* 工具。
"""

import asyncio
import json
from pathlib import Path

import pytest

from dbjavagenix.database.atomic_codegen_tools import (
    _compute_file_path,
    _collect_all_table_names,
    _extract_context,
    _normalize_tech_flags,
    _rebuild_package_paths,
    get_atomic_codegen_tools,
    handle_codegen_render_controller,
    handle_codegen_render_dao,
    handle_codegen_render_dto,
    handle_codegen_render_entity,
    handle_codegen_render_mapper,
    handle_codegen_render_service,
    handle_codegen_build_context,
)
from dbjavagenix.core.models import ColumnInfo, TableInfo
from dbjavagenix.core.models import DatabaseType
from dbjavagenix.generator.template_context import TemplateContextBuilder


# ============================================================
# Fixtures
# ============================================================


@pytest.fixture
def simple_table():
    return TableInfo(
        name="sys_user",
        schema="test_db",
        comment="系统用户",
        columns=[
            ColumnInfo(
                name="id",
                data_type="BIGINT",
                java_type="Long",
                primary_key=True,
                nullable=False,
                comment="主键",
            ),
            ColumnInfo(
                name="username",
                data_type="VARCHAR(64)",
                java_type="String",
                nullable=False,
                comment="用户名",
            ),
        ],
        primary_keys=["id"],
    )


def _build_context(table, category: str):
    """构建一个完整模板上下文用于 render_* 测试"""
    ctx = TemplateContextBuilder(author="tester", package_name="com.example.app").build_context(
        table, category
    )
    ctx.update(
        {
            "templateCategory": category,
            "isDefault": category == "Default",
            "isMybatisPlus": category == "MybatisPlus",
            "isMybatisPlusMixed": category == "MybatisPlus-Mixed",
            "isSb35Java21": category == "sb35-java21",
            "useSwagger": True,
            "useLombok": True,
            "useMapStruct": False,
        }
    )
    _rebuild_package_paths(ctx, "com.example.app")
    _normalize_tech_flags(ctx)
    return ctx


class _TableNameCursor:
    def __init__(self):
        self.query = None

    def execute(self, query):
        self.query = query

    def fetchall(self):
        return [("users",), ("user_roles",)]

    def close(self):
        pass


class _TableNameConnection:
    def __init__(self):
        self.cursor_instance = _TableNameCursor()

    def cursor(self):
        return self.cursor_instance


class _TableNameManager:
    def __init__(self, connection):
        self.connection = connection

    def get_connection(self, _connection_id):
        return self.connection


# ============================================================
# Tool 定义结构
# ============================================================


class TestToolDefinitions:
    def test_returns_seven_tools(self):
        tools = get_atomic_codegen_tools()
        assert len(tools) == 7

    def test_tool_names(self):
        tools = get_atomic_codegen_tools()
        names = {t.name for t in tools}
        assert names == {
            "codegen_build_context",
            "codegen_render_entity",
            "codegen_render_dao",
            "codegen_render_service",
            "codegen_render_controller",
            "codegen_render_dto",
            "codegen_render_mapper",
        }

    def test_all_tools_have_description_and_schema(self):
        tools = get_atomic_codegen_tools()
        for t in tools:
            assert t.description and len(t.description) > 10
            assert t.inputSchema and t.inputSchema.get("type") == "object"

    def test_build_context_requires_table_name(self):
        tools = get_atomic_codegen_tools()
        build = next(t for t in tools if t.name == "codegen_build_context")
        assert "connection_id" in build.inputSchema["required"]
        assert "table_name" in build.inputSchema["required"]

    def test_render_tools_require_context(self):
        tools = get_atomic_codegen_tools()
        for t in tools:
            if t.name.startswith("codegen_render_"):
                assert "context" in t.inputSchema["required"]


def test_collect_all_table_names_supports_postgresql(monkeypatch):
    connection = _TableNameConnection()
    monkeypatch.setattr(
        "dbjavagenix.database.atomic_codegen_tools.connection_manager",
        _TableNameManager(connection),
    )

    names = _collect_all_table_names(
        "pg-1", type("Config", (), {"type": DatabaseType.POSTGRESQL})()
    )

    assert names == ["users", "user_roles"]
    assert "information_schema.tables" in connection.cursor_instance.query
    assert "pg_catalog" in connection.cursor_instance.query


# ============================================================
# 渲染逻辑
# ============================================================


class TestRenderEntity:
    def test_render_entity_sb35_java21(self, simple_table):
        ctx = _build_context(simple_table, "sb35-java21")
        result = asyncio.run(handle_codegen_render_entity({"context": ctx}))
        assert len(result) == 1
        payload = json.loads(result[0].text)
        assert payload["language"] == "java"
        assert len(payload["files"]) == 1
        file_info = payload["files"][0]
        assert file_info["template_file"] == "entity.mustache"
        assert "class SysUser" in file_info["code"]
        assert "@Entity" in file_info["code"]
        assert file_info["file_path"].endswith("SysUser.java")
        assert file_info["lines"] > 10

    def test_render_entity_default(self, simple_table):
        ctx = _build_context(simple_table, "Default")
        result = asyncio.run(handle_codegen_render_entity({"context": ctx}))
        payload = json.loads(result[0].text)
        files = payload["files"]
        assert len(files) == 1
        assert "class SysUser" in files[0]["code"]


class TestRenderDao:
    def test_render_dao_sb35_java21(self, simple_table):
        ctx = _build_context(simple_table, "sb35-java21")
        result = asyncio.run(handle_codegen_render_dao({"context": ctx}))
        payload = json.loads(result[0].text)
        assert len(payload["files"]) == 1
        code = payload["files"][0]["code"]
        assert "SysUserDao" in code
        assert "JpaRepository" in code

    def test_render_dao_mybatis_plus(self, simple_table):
        ctx = _build_context(simple_table, "MybatisPlus-Mixed")
        result = asyncio.run(handle_codegen_render_dao({"context": ctx}))
        payload = json.loads(result[0].text)
        assert len(payload["files"]) == 1


class TestRenderService:
    def test_render_service_returns_two_files(self, simple_table):
        ctx = _build_context(simple_table, "sb35-java21")
        result = asyncio.run(handle_codegen_render_service({"context": ctx}))
        payload = json.loads(result[0].text)
        files = payload["files"]
        assert len(files) == 2
        names = {f["template_file"] for f in files}
        assert names == {"service.mustache", "serviceImpl.mustache"}
        impl = next(f for f in files if f["template_file"] == "serviceImpl.mustache")
        assert "ServiceImpl" in impl["code"]
        assert impl["file_path"].endswith("ServiceImpl.java")


class TestRenderController:
    def test_render_controller_sb35(self, simple_table):
        ctx = _build_context(simple_table, "sb35-java21")
        result = asyncio.run(handle_codegen_render_controller({"context": ctx}))
        payload = json.loads(result[0].text)
        files = payload["files"]
        assert len(files) == 1
        code = files[0]["code"]
        assert "@RestController" in code
        assert "SysUserController" in code


class TestRenderDto:
    def test_render_dto_sb35_java21(self, simple_table):
        ctx = _build_context(simple_table, "sb35-java21")
        result = asyncio.run(handle_codegen_render_dto({"context": ctx}))
        payload = json.loads(result[0].text)

        assert payload["language"] == "java"
        assert len(payload["files"]) == 1
        file_info = payload["files"][0]
        assert file_info["template_file"] == "dto.mustache"
        assert file_info["file_path"].endswith("SysUserDTO.java")
        assert "public record SysUserDTO" in file_info["code"]
        assert "Long id" in file_info["code"]
        assert "String username" in file_info["code"]

    def test_render_dto_non_sb35_returns_empty(self, simple_table):
        ctx = _build_context(simple_table, "MybatisPlus-Mixed")
        result = asyncio.run(handle_codegen_render_dto({"context": ctx}))
        payload = json.loads(result[0].text)

        assert payload["files"] == []
        assert "record DTO" in payload["note"]


class TestRenderMapper:
    def test_mapper_default_returns_xml(self, simple_table):
        ctx = _build_context(simple_table, "Default")
        result = asyncio.run(handle_codegen_render_mapper({"context": ctx}))
        payload = json.loads(result[0].text)
        files = payload["files"]
        assert len(files) == 1
        assert files[0]["template_file"] == "mapper.xml.mustache"

    def test_mapper_mybatis_plus_mixed(self, simple_table):
        ctx = _build_context(simple_table, "MybatisPlus-Mixed")
        result = asyncio.run(handle_codegen_render_mapper({"context": ctx}))
        payload = json.loads(result[0].text)
        files = payload["files"]
        assert len(files) == 1
        assert files[0]["template_file"] == "mapper.mustache"

    def test_mapper_sb35_java21_empty(self, simple_table):
        ctx = _build_context(simple_table, "sb35-java21")
        result = asyncio.run(handle_codegen_render_mapper({"context": ctx}))
        payload = json.loads(result[0].text)
        assert payload["files"] == []
        assert "JpaRepository" in payload["note"]

    def test_mapper_with_mapstruct_adds_extra(self, simple_table):
        ctx = _build_context(simple_table, "MybatisPlus-Mixed")
        ctx["useMapStruct"] = True
        result = asyncio.run(handle_codegen_render_mapper({"context": ctx}))
        payload = json.loads(result[0].text)
        templates = {f["template_file"] for f in payload["files"]}
        assert "mapper.mustache" in templates
        assert "mapstruct_mapper.mustache" in templates


# ============================================================
# 错误处理与辅助函数
# ============================================================


class TestErrorHandling:
    def test_build_context_rejects_unknown_category_before_connection_lookup(self):
        result = asyncio.run(
            handle_codegen_build_context(
                {
                    "connection_id": "not-used",
                    "table_name": "users",
                    "template_category": "UnknownCategory",
                }
            )
        )
        payload = json.loads(result[0].text)

        assert payload["stage"] == "build_context"
        assert "不支持的模板分类" in payload["error"]

    def test_render_rejects_unknown_category(self):
        result = asyncio.run(
            handle_codegen_render_entity({"context": {"templateCategory": "UnknownCategory"}})
        )
        payload = json.loads(result[0].text)

        assert payload["error"] == "unsupported template category"
        assert payload["supported_categories"][-1] == "sb35-java21"

    def test_render_without_context_returns_error(self):
        result = asyncio.run(handle_codegen_render_entity({}))
        payload = json.loads(result[0].text)
        assert "error" in payload

    def test_render_with_invalid_json_string_context(self):
        result = asyncio.run(handle_codegen_render_entity({"context": "not-json"}))
        payload = json.loads(result[0].text)
        assert "error" in payload

    def test_render_with_json_string_context_works(self, simple_table):
        ctx = _build_context(simple_table, "sb35-java21")
        result = asyncio.run(handle_codegen_render_entity({"context": json.dumps(ctx)}))
        payload = json.loads(result[0].text)
        assert payload.get("files"), f"expected files, got {payload}"


class TestExtractContext:
    def test_extract_dict_unchanged(self):
        ctx = {"a": 1}
        assert _extract_context({"context": ctx}) == {"a": 1}

    def test_extract_json_string(self):
        assert _extract_context({"context": '{"a": 1}'}) == {"a": 1}

    def test_extract_missing(self):
        assert _extract_context({}) is None

    def test_extract_invalid_json_returns_none(self):
        assert _extract_context({"context": "{not-json"}) is None


class TestRebuildPackagePaths:
    def test_no_suffix(self):
        ctx = {"packageSuffix": ""}
        _rebuild_package_paths(ctx, "com.demo")
        assert ctx["package"] == "com.demo"
        assert ctx["entityPackage"] == "com.demo.entity"
        assert ctx["serviceImplPackage"] == "com.demo.service.impl"

    def test_with_suffix(self):
        ctx = {"packageSuffix": "system"}
        _rebuild_package_paths(ctx, "com.demo")
        assert ctx["entityPackage"] == "com.demo.entity.system"
        assert ctx["serviceImplPackage"] == "com.demo.service.impl.system"


class TestNormalizeTechFlags:
    def test_springdoc_wins_over_swagger2(self):
        ctx = {"hasSpringDoc": True, "hasSwagger2": True}
        _normalize_tech_flags(ctx)
        assert ctx["hasSpringDoc"] is True
        assert ctx["hasSwagger2"] is False

    def test_jakarta_wins_over_javax(self):
        ctx = {"hasJakarta": True, "hasJavax": True}
        _normalize_tech_flags(ctx)
        assert ctx["hasJakarta"] is True
        assert ctx["hasJavax"] is False

    def test_javax_when_no_jakarta(self):
        ctx = {"hasJavax": True}
        _normalize_tech_flags(ctx)
        assert ctx["hasJavax"] is True


class TestComputeFilePath:
    def test_entity_path_includes_package(self):
        mapping = {"entity.mustache": "entity/{packageSuffix}/{className}.java"}
        ctx = {
            "className": "SysUser",
            "packageSuffix": "",
            "package": "com.example.app",
        }
        path = _compute_file_path("entity.mustache", ctx, mapping)
        assert "com/example/app" in path
        assert path.endswith("SysUser.java")

    def test_xml_path_uses_resources_prefix(self):
        mapping = {"mapper.mustache": "mapper/{className}Dao.xml"}
        ctx = {"className": "SysUser", "package": "com.demo", "packageSuffix": ""}
        path = _compute_file_path("mapper.mustache", ctx, mapping)
        assert path.startswith("resources/")
        assert path.endswith("SysUserDao.xml")

    def test_unknown_template_fallback(self):
        ctx = {"className": "X", "package": "com.demo", "packageSuffix": ""}
        path = _compute_file_path("foo.mustache", ctx, {})
        assert path == "foo.java"
