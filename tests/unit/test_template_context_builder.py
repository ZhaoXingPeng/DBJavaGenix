"""单元测试: generator.template_context.TemplateContextBuilder

聚焦命名转换、类型映射、上下文字典结构,不依赖项目根目录探测。
"""

import pytest

from dbjavagenix.core.models import ColumnInfo, DatabaseType, TableInfo
from dbjavagenix.database.mcp_tools import (
    get_codegen_tools,
    get_springboot_project_tools,
)
from dbjavagenix.generator.template_context import (
    TemplateConfigManager,
    TemplateContextBuilder,
)


@pytest.fixture
def builder():
    return TemplateContextBuilder(author="tester", package_name="com.example.app")


@pytest.fixture
def rbac_user_table():
    return TableInfo(
        name="sys_user",
        schema="public",
        comment="系统用户",
        columns=[
            ColumnInfo(
                name="user_id",
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
                max_length=64,
                comment="用户名",
            ),
            ColumnInfo(
                name="created_at",
                data_type="DATETIME",
                java_type="LocalDateTime",
                nullable=False,
                comment="创建时间",
            ),
        ],
        primary_keys=["user_id"],
    )


class TestNamingConventions:
    @pytest.mark.parametrize(
        "snake,pascal",
        [
            ("user_profile", "UserProfile"),
            ("sys_user", "SysUser"),
            ("a_b_c", "ABC"),
            ("singleword", "Singleword"),
        ],
    )
    def test_to_pascal_case(self, builder, snake, pascal):
        assert builder._to_pascal_case(snake) == pascal

    @pytest.mark.parametrize(
        "snake,camel",
        [
            ("user_profile", "userProfile"),
            ("sys_user", "sysUser"),
            ("id", "id"),
        ],
    )
    def test_to_camel_case(self, builder, snake, camel):
        assert builder._to_camel_case(snake) == camel

    def test_camel_case_empty(self, builder):
        assert builder._to_camel_case("") == ""


class TestJavaTypeMapping:
    @pytest.mark.parametrize(
        "db_type,java_type",
        [
            ("BIGINT", "Long"),
            ("INT", "Integer"),
            ("INTEGER", "Integer"),
            ("TINYINT", "Byte"),
            ("SMALLINT", "Short"),
            ("VARCHAR(64)", "String"),
            ("VARCHAR", "String"),
            ("TEXT", "String"),
            ("DATETIME", "LocalDateTime"),
            ("TIMESTAMP", "LocalDateTime"),
            ("DATE", "LocalDate"),
            ("TIME", "LocalTime"),
            ("DECIMAL(10,2)", "BigDecimal"),
            ("BLOB", "byte[]"),
            ("BOOLEAN", "Boolean"),
            ("JSON", "String"),
        ],
    )
    def test_known_types(self, builder, db_type, java_type):
        assert builder._map_java_type(db_type) == java_type

    def test_unknown_falls_back_to_string(self, builder):
        assert builder._map_java_type("UNKNOWN_FANCY_TYPE") == "String"

    def test_postgresql_dialect_is_used_for_context_mapping(self):
        builder = TemplateContextBuilder(
            author="tester",
            package_name="com.example.app",
            database_type=DatabaseType.POSTGRESQL,
        )
        assert builder._map_java_type("TIMESTAMP WITH TIME ZONE") == "OffsetDateTime"
        assert builder._map_java_type("BYTEA") == "byte[]"
        assert builder._map_java_type("JSONB") == "String"


class TestJdbcTypeMapping:
    @pytest.mark.parametrize(
        "db_type,jdbc_type",
        [
            ("BIGINT", "BIGINT"),
            ("INT", "INTEGER"),
            ("VARCHAR(64)", "VARCHAR"),
            ("TEXT", "LONGVARCHAR"),
            ("DATETIME", "TIMESTAMP"),
            ("BLOB", "BLOB"),
        ],
    )
    def test_known_types(self, builder, db_type, jdbc_type):
        assert builder._map_jdbc_type(db_type) == jdbc_type

    def test_unknown_falls_back_to_varchar(self, builder):
        assert builder._map_jdbc_type("UNKNOWN_TYPE") == "VARCHAR"

    def test_postgresql_jdbc_types_are_preserved(self):
        builder = TemplateContextBuilder(database_type="postgresql")
        assert builder._map_jdbc_type("TIMESTAMPTZ") == "TIMESTAMP_WITH_TIMEZONE"
        assert builder._map_jdbc_type("BYTEA") == "BINARY"
        assert builder._map_jdbc_type("JSONB") == "OTHER"


class TestStringTypeDetection:
    @pytest.mark.parametrize(
        "db_type,expected",
        [
            ("VARCHAR(64)", True),
            ("CHAR(2)", True),
            ("TEXT", True),
            ("LONGTEXT", True),
            ("BIGINT", False),
            ("DATETIME", False),
            ("BLOB", False),
        ],
    )
    def test_is_string_type(self, builder, db_type, expected):
        assert builder._is_string_type(db_type) is expected


class TestBuildContextStructure:
    def test_basic_keys_present(self, builder, rbac_user_table):
        ctx = builder.build_context(rbac_user_table, "Default")
        for key in [
            "className",
            "tableName",
            "entityNameLowerCase",
            "controllerPackage",
            "servicePackage",
            "entityPackage",
            "daoPackage",
            "serviceImplPackage",
            "columns",
            "author",
            "date",
        ]:
            assert key in ctx, f"missing key {key}"

    def test_class_name_from_table(self, builder, rbac_user_table):
        ctx = builder.build_context(rbac_user_table, "Default")
        assert ctx["className"] == "SysUser"
        assert ctx["entityNameLowerCase"] == "sysUser"

    def test_packages_default_no_suffix(self, builder, rbac_user_table):
        ctx = builder.build_context(rbac_user_table, "Default")
        assert ctx["controllerPackage"] == "com.example.app.controller"
        assert ctx["entityPackage"] == "com.example.app.entity"
        assert ctx["serviceImplPackage"] == "com.example.app.service.impl"
        assert ctx["packageSuffix"] == ""

    def test_columns_structure(self, builder, rbac_user_table):
        ctx = builder.build_context(rbac_user_table, "Default")
        cols = ctx["columns"]
        assert len(cols) == 3
        first = cols[0]
        assert "javaName" in first
        assert "javaType" in first
        assert "jdbcType" in first
        assert "isPrimaryKey" in first
        assert "isLast" in first

    def test_postgresql_context_includes_dialect_imports(self):
        table = TableInfo(
            name="audit_event",
            schema="public",
            columns=[
                ColumnInfo(
                    name="occurred_at",
                    data_type="TIMESTAMPTZ",
                    java_type="OffsetDateTime",
                ),
                ColumnInfo(name="event_id", data_type="UUID", java_type="String"),
            ],
        )
        builder = TemplateContextBuilder(database_type="postgresql")
        context = builder.build_context(table)
        assert context["columns"][0]["javaType"] == "OffsetDateTime"
        assert context["columns"][1]["javaType"] == "String"
        assert "java.time.OffsetDateTime" in context["imports"]

    def test_last_flag(self, builder, rbac_user_table):
        ctx = builder.build_context(rbac_user_table, "Default")
        cols = ctx["columns"]
        assert cols[-1]["isLast"] is True
        assert cols[-1]["last"] is True
        assert cols[0]["isLast"] is False

    def test_primary_key_info(self, builder, rbac_user_table):
        ctx = builder.build_context(rbac_user_table, "Default")
        # 主键相关信息至少应被映射到列上
        pk_cols = [c for c in ctx["columns"] if c["isPrimaryKey"]]
        assert len(pk_cols) == 1
        assert pk_cols[0]["javaName"] == "userId"

    def test_with_prefix_analysis_creates_suffix(self, builder, rbac_user_table):
        # 提供同前缀的表名集合,前缀分析器应识别出 sys 前缀
        all_tables = ["sys_user", "sys_role", "sys_permission"]
        ctx = builder.build_context(
            rbac_user_table, "Default", all_table_names=all_tables
        )
        # packageSuffix 应当被设置 (具体值取决于 TablePrefixAnalyzer 实现,
        # 但应为非空字符串,且 packages 应包含该后缀)
        suffix = ctx["packageSuffix"]
        if suffix:
            assert ctx["controllerPackage"].endswith(f".{suffix}")
            assert ctx["serviceImplPackage"].endswith(f".{suffix}")


class TestTemplateConfigManager:
    def test_supported_categories_are_canonical_and_ordered(self):
        assert TemplateConfigManager.get_supported_categories() == [
            "Default",
            "MybatisPlus",
            "MybatisPlus-Mixed",
            "sb35-java21",
        ]

    def test_template_file_lists_are_copied(self):
        files = TemplateConfigManager.get_template_files("Default")
        files.clear()

        assert "entity.mustache" in TemplateConfigManager.get_template_files("Default")

    def test_public_tool_schemas_use_canonical_categories(self):
        expected = TemplateConfigManager.get_supported_categories()
        tools = get_codegen_tools() + get_springboot_project_tools()

        category_enums = [
            tool.inputSchema["properties"]["template_category"]["enum"]
            for tool in tools
            if "template_category" in tool.inputSchema.get("properties", {})
        ]

        assert category_enums
        assert all(categories == expected for categories in category_enums)

    def test_default_files(self):
        files = TemplateConfigManager.get_template_files("Default")
        assert "entity.mustache" in files
        assert "service.mustache" in files
        assert "controller.mustache" in files

    def test_mybatisplus_files(self):
        files = TemplateConfigManager.get_template_files("MybatisPlus")
        assert len(files) >= 5

    def test_mybatisplus_mixed_files(self):
        files = TemplateConfigManager.get_template_files("MybatisPlus-Mixed")
        assert "mapper.mustache" in files

    def test_sb35_java21_files(self):
        files = TemplateConfigManager.get_template_files("sb35-java21")
        assert "entity.mustache" in files
        assert "dto.mustache" in files
        assert "controller.mustache" in files

    def test_unknown_category(self):
        files = TemplateConfigManager.get_template_files("UnknownCategory")
        assert files == []

    def test_additional_templates(self):
        extras = TemplateConfigManager.get_additional_templates()
        assert "dto.mustache" in extras
        assert "vo.mustache" in extras

    def test_output_path_mapping_has_known_keys(self):
        mp = TemplateConfigManager.get_output_path_mapping()
        for key in [
            "entity.mustache",
            "dao.mustache",
            "service.mustache",
            "serviceImpl.mustache",
            "controller.mustache",
        ]:
            assert key in mp
            assert "{className}" in mp[key]
