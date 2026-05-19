"""单元测试: mustache_engine.MustacheTemplateEngine 与 TemplateContext

聚焦纯计算逻辑(模板渲染、context 构建),不依赖外部 DB/网络。
"""

import pytest
from pathlib import Path

from dbjavagenix.core.exceptions import TemplateError
from dbjavagenix.core.models import (
    ColumnInfo,
    GenerationConfig,
    TableInfo,
    CodeStyle,
    TemplateEngine,
    MappingTool,
)
from dbjavagenix.generator.mustache_engine import (
    MustacheTemplateEngine,
    TemplateContext,
)


@pytest.fixture
def template_dir(tmp_path):
    """构造一个临时模板目录,放几个 mustache 文件"""
    d = tmp_path / "tpl"
    d.mkdir()
    (d / "hello.mustache").write_text("Hello {{name}}!", encoding="utf-8")
    (d / "loop.mustache").write_text(
        "{{#items}}- {{.}}\n{{/items}}", encoding="utf-8"
    )
    sub = d / "java"
    sub.mkdir()
    (sub / "entity.mustache").write_text(
        "package {{pkg}}; class {{cls}} {}", encoding="utf-8"
    )
    return d


class TestMustacheTemplateEngineInit:
    def test_no_dir_init(self):
        """无目录初始化应成功,template_dir 为 None"""
        engine = MustacheTemplateEngine()
        assert engine.template_dir is None

    def test_with_dir_init(self, template_dir):
        engine = MustacheTemplateEngine(template_dir=str(template_dir))
        assert engine.template_dir == template_dir

    def test_missing_dir_raises(self, tmp_path):
        missing = tmp_path / "does_not_exist"
        with pytest.raises(TemplateError):
            MustacheTemplateEngine(template_dir=str(missing))


class TestMustacheTemplateEngineRender:
    def test_render_simple(self, template_dir):
        engine = MustacheTemplateEngine(template_dir=str(template_dir))
        out = engine.render_template("hello", {"name": "World"})
        assert out == "Hello World!"

    def test_render_loop(self, template_dir):
        engine = MustacheTemplateEngine(template_dir=str(template_dir))
        out = engine.render_template("loop", {"items": ["a", "b", "c"]})
        assert "- a" in out and "- b" in out and "- c" in out

    def test_render_missing_template_raises(self, template_dir):
        engine = MustacheTemplateEngine(template_dir=str(template_dir))
        with pytest.raises(TemplateError):
            engine.render_template("nope", {})

    def test_render_file_caches(self, template_dir):
        engine = MustacheTemplateEngine(template_dir=str(template_dir))
        path = str(template_dir / "hello.mustache")
        first = engine.render_file(path, {"name": "X"})
        second = engine.render_file(path, {"name": "Y"})
        assert first == "Hello X!"
        assert second == "Hello Y!"
        assert path in engine._template_cache

    def test_render_file_missing_raises(self, template_dir):
        engine = MustacheTemplateEngine(template_dir=str(template_dir))
        with pytest.raises(TemplateError):
            engine.render_file(str(template_dir / "missing.mustache"), {})


class TestMustacheTemplateEngineDiscovery:
    def test_list_templates_includes_subdirs(self, template_dir):
        engine = MustacheTemplateEngine(template_dir=str(template_dir))
        names = engine.list_templates()
        assert "hello" in names
        assert "loop" in names
        joined = "\n".join(names)
        assert "entity" in joined

    def test_validate_template_ok(self, template_dir):
        engine = MustacheTemplateEngine(template_dir=str(template_dir))
        assert engine.validate_template("hello") is True

    def test_validate_template_missing(self, template_dir):
        engine = MustacheTemplateEngine(template_dir=str(template_dir))
        assert engine.validate_template("nope") is False


@pytest.fixture
def sample_table():
    return TableInfo(
        name="user_profile",
        schema="public",
        comment="用户资料",
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
                name="user_name",
                data_type="VARCHAR(64)",
                java_type="String",
                nullable=False,
                max_length=64,
                comment="姓名",
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


@pytest.fixture
def sample_config(tmp_path):
    return GenerationConfig(
        output_dir=str(tmp_path / "out"),
        package_name="com.example.app",
        code_style=CodeStyle.SPRING_BOOT,
        template_engine=TemplateEngine.MUSTACHE,
        mapping_tool=MappingTool.MAPSTRUCT,
        author="tester",
        use_lombok=True,
        use_jpa=True,
        use_swagger=True,
    )


class TestTemplateContextEntity:
    def test_basic_fields(self, sample_table, sample_config):
        ctx = TemplateContext.build_entity_context(sample_table, sample_config)
        assert ctx["package"] == "com.example.app"
        assert ctx["className"] == "UserProfile"
        assert ctx["tableName"] == "user_profile"
        assert ctx["author"] == "tester"
        assert ctx["useLombok"] is True

    def test_columns_mapped(self, sample_table, sample_config):
        ctx = TemplateContext.build_entity_context(sample_table, sample_config)
        cols = ctx["columns"]
        assert len(cols) == 3
        first = next(c for c in cols if c["name"] == "user_id")
        assert first["javaName"] == "userId"
        assert first["javaType"] == "Long"
        assert first["isPrimaryKey"] is True

    def test_imports_include_lombok_when_enabled(self, sample_table, sample_config):
        ctx = TemplateContext.build_entity_context(sample_table, sample_config)
        assert any("lombok" in imp.lower() for imp in ctx["imports"])

    def test_imports_include_localdatetime(self, sample_table, sample_config):
        ctx = TemplateContext.build_entity_context(sample_table, sample_config)
        assert "java.time.LocalDateTime" in ctx["imports"]

    def test_comment_fallback(self, sample_config):
        t = TableInfo(
            name="orders",
            schema="public",
            comment=None,
            columns=[
                ColumnInfo(name="id", data_type="BIGINT", java_type="Long", primary_key=True)
            ],
        )
        ctx = TemplateContext.build_entity_context(t, sample_config)
        assert "entity" in ctx["comment"].lower()


class TestTemplateContextDto:
    def test_excludes_primary_key(self, sample_table, sample_config):
        ctx = TemplateContext.build_dto_context(sample_table, sample_config)
        col_names = [c["name"] for c in ctx["columns"]]
        assert "user_id" not in col_names
        assert "user_name" in col_names

    def test_package_appends_dto(self, sample_table, sample_config):
        ctx = TemplateContext.build_dto_context(sample_table, sample_config)
        assert ctx["package"].endswith(".dto")
        assert ctx["className"].endswith("DTO")


class TestTemplateContextMapper:
    def test_names(self, sample_table, sample_config):
        ctx = TemplateContext.build_mapper_context(sample_table, sample_config)
        assert ctx["mapperName"] == "UserProfileMapper"
        assert ctx["dtoName"] == "UserProfileDTO"
        assert ctx["voName"] == "UserProfileVO"

    def test_mapstruct_imports_present(self, sample_table, sample_config):
        ctx = TemplateContext.build_mapper_context(sample_table, sample_config)
        assert "org.mapstruct.Mapper" in ctx["imports"]


class TestCamelCase:
    @pytest.mark.parametrize(
        "snake,expected",
        [
            ("user_name", "userName"),
            ("created_at", "createdAt"),
            ("id", "id"),
            ("multi_word_field", "multiWordField"),
        ],
    )
    def test_to_camel_case(self, snake, expected):
        assert TemplateContext._to_camel_case(snake) == expected
