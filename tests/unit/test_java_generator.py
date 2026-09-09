"""单元测试: generator.java_generator.JavaCodeGenerator

聚焦类别注册、路径计算与渲染产物结构,不依赖数据库。
"""

import pytest
from pathlib import Path

from dbjavagenix.core.models import (
    ColumnInfo,
    GenerationConfig,
    TableInfo,
    CodeStyle,
    TemplateEngine,
    MappingTool,
)
from dbjavagenix.generator.java_generator import JavaCodeGenerator


@pytest.fixture
def gen_config(tmp_path):
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
        generate_dto=True,
    )


@pytest.fixture
def gen(gen_config):
    return JavaCodeGenerator(gen_config)


@pytest.fixture
def simple_table():
    return TableInfo(
        name="account",
        schema="public",
        comment="账户",
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
                name="balance",
                data_type="DECIMAL(10,2)",
                java_type="BigDecimal",
                nullable=False,
                comment="余额",
            ),
        ],
        primary_keys=["id"],
    )


class TestCategoryRegistration:
    def test_supported_categories(self, gen):
        cats = gen.get_supported_categories()
        assert "Default" in cats
        assert "MybatisPlus" in cats
        assert "MybatisPlus-Mixed" in cats
        assert "sb35-java21" in cats

    @pytest.mark.parametrize(
        "category", ["Default", "MybatisPlus", "MybatisPlus-Mixed", "sb35-java21"]
    )
    def test_validate_category(self, gen, category):
        assert gen.validate_template_category(category) is True

    def test_unknown_category_invalid(self, gen):
        assert gen.validate_template_category("nope") is False

    def test_list_files_default(self, gen):
        files = gen.list_template_files("Default")
        assert "entity.mustache" in files
        assert "controller.mustache" in files

    def test_list_files_unknown_raises(self, gen):
        with pytest.raises(ValueError):
            gen.list_template_files("nope")


class TestPathResolution:
    def test_output_path_simple(self, gen, simple_table, gen_config):
        from dbjavagenix.generator.template_context import TemplateContextBuilder

        ctx = TemplateContextBuilder(
            author=gen_config.author, package_name=gen_config.package_name
        ).build_context(simple_table, "Default")
        path = gen._get_output_path("entity.mustache", ctx, gen_config.output_dir)
        # entity.mustache 路径模式: entity/{packageSuffix}/{className}.java
        assert path.endswith("Account.java")
        assert "entity" in path

    def test_unknown_template_uses_fallback(self, gen, simple_table, gen_config):
        from dbjavagenix.generator.template_context import TemplateContextBuilder

        ctx = TemplateContextBuilder(
            author=gen_config.author, package_name=gen_config.package_name
        ).build_context(simple_table, "Default")
        # 不在 mapping 中的模板名应走 generated/ 默认路径
        path = gen._get_output_path("brand_new.mustache", ctx, gen_config.output_dir)
        assert "generated" in path
        assert path.endswith("brand_new.java")

    def test_empty_package_suffix_does_not_create_empty_path_segment(
        self, gen, simple_table, gen_config
    ):
        from dbjavagenix.generator.template_context import TemplateContextBuilder

        context = TemplateContextBuilder(
            author=gen_config.author, package_name=gen_config.package_name
        ).build_context(simple_table, "Default")
        path = gen._get_output_path("entity.mustache", context, gen_config.output_dir)

        relative = Path(path).relative_to(Path(gen_config.output_dir)).as_posix()
        assert relative == "entity/Account.java"

    def test_package_suffix_remains_a_distinct_path_segment(self, gen, gen_config):
        from dbjavagenix.generator.template_context import TemplateContextBuilder

        table = TableInfo(
            name="sys_account",
            schema="public",
            columns=[
                ColumnInfo(
                    name="id",
                    data_type="BIGINT",
                    java_type="Long",
                    primary_key=True,
                )
            ],
        )
        context = TemplateContextBuilder(
            author=gen_config.author, package_name=gen_config.package_name
        ).build_context(
            table,
            "Default",
            all_table_names=["sys_account", "sys_role"],
        )
        path = gen._get_output_path("entity.mustache", context, gen_config.output_dir)

        relative = Path(path).relative_to(Path(gen_config.output_dir)).as_posix()
        assert relative == "entity/system/SysAccount.java"


class TestRealGeneration:
    """跑一次真实生成, 验证文件产生且包含关键 token"""

    def test_default_generates_entity_dao_service_controller(self, gen, simple_table, gen_config):
        output_dir = gen_config.output_dir
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        result = gen.generate_from_table(
            simple_table,
            output_dir=output_dir,
            template_category="Default",
            include_dto_vo=False,
        )
        # result: dict of template_file -> file_path
        assert "entity.mustache" in result
        assert "service.mustache" in result
        # 文件实际存在
        entity_path = Path(result["entity.mustache"])
        assert entity_path.exists()
        assert entity_path.relative_to(Path(output_dir)).as_posix() == "entity/Account.java"
        content = entity_path.read_text(encoding="utf-8")
        assert "class Account" in content
        assert "private Long id" in content

    def test_sb35_java21_generates_record_dto(self, gen, simple_table, gen_config):
        output_dir = gen_config.output_dir
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        result = gen.generate_from_table(
            simple_table,
            output_dir=output_dir,
            template_category="sb35-java21",
            include_dto_vo=False,
        )
        assert "dto.mustache" in result
        dto_content = Path(result["dto.mustache"]).read_text(encoding="utf-8")
        assert "public record AccountDTO" in dto_content

    def test_sb35_java21_entity_is_class_not_record(self, gen, simple_table, gen_config):
        """回归测试: P1.2 修复后 sb35-java21 entity 应为 class (JPA 兼容), 不是 record"""
        output_dir = gen_config.output_dir
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        result = gen.generate_from_table(
            simple_table,
            output_dir=output_dir,
            template_category="sb35-java21",
            include_dto_vo=False,
        )
        entity_content = Path(result["entity.mustache"]).read_text(encoding="utf-8")
        assert "public class Account" in entity_content
        assert "public record Account(" not in entity_content
        assert "@Entity" in entity_content
        assert "jakarta.persistence" in entity_content
