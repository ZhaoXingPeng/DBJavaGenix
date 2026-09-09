"""Regression tests for the shared DTO/VO generation option contract."""

import pytest

from dbjavagenix.database.atomic_codegen_tools import get_atomic_codegen_tools
from dbjavagenix.database.codegen_tools import CodegenGenerator
from dbjavagenix.database.mcp_tools import get_codegen_tools
from dbjavagenix.core.models import ColumnInfo, TableInfo
from dbjavagenix.generator.template_context import TemplateContextBuilder, apply_generation_options


def _analysis(category: str = "Default") -> dict:
    return {
        "table_name": "users",
        "template_context": {
            "className": "User",
            "package": "com.example",
            "packageName": "com.example",
            "packageSuffix": "",
            "templateCategory": category,
            "useMapStruct": False,
        },
    }


def test_apply_generation_options_preserves_legacy_aliases():
    context = {"generateDto": False, "generateVo": False}

    apply_generation_options(context, include_dto_vo=True)

    assert context["generateDto"] is True
    assert context["generateVo"] is True
    assert context["includeDtoVo"] is True
    assert context["include_dto_vo"] is True


def test_apply_generation_options_explicit_switches_override_alias():
    context = {}

    apply_generation_options(context, generate_dto=False, generate_vo=True, include_dto_vo=True)

    assert context["generateDto"] is False
    assert context["generateVo"] is True
    assert context["hasDto"] is False
    assert context["hasVo"] is True


@pytest.mark.asyncio
async def test_codegen_generator_supports_dto_only_and_rebuilds_package(monkeypatch):
    generator = CodegenGenerator()
    rendered = []

    async def render(template_file, _context, _category):
        rendered.append(template_file)
        return template_file

    monkeypatch.setattr(generator, "_render_template", render)

    result = await generator.generate_code(
        _analysis(),
        template_category="Default",
        generation_config={"package_name": "org.demo", "generate_dto": True},
    )

    assert "dto.mustache" in result["generated_code"]
    assert "vo.mustache" not in result["generated_code"]
    assert result["generated_code"]["dto.mustache"]["filename"] == "org/demo/dto/UserDTO.java"
    assert rendered.count("dto.mustache") == 1


@pytest.mark.asyncio
async def test_codegen_generator_supports_vo_only(monkeypatch):
    generator = CodegenGenerator()

    async def render(template_file, _context, _category):
        return template_file

    monkeypatch.setattr(generator, "_render_template", render)

    result = await generator.generate_code(
        _analysis(),
        template_category="Default",
        generation_config={"generate_vo": True},
    )

    assert "dto.mustache" not in result["generated_code"]
    assert "vo.mustache" in result["generated_code"]


@pytest.mark.asyncio
async def test_codegen_generator_honors_context_legacy_alias(monkeypatch):
    generator = CodegenGenerator()
    analysis = _analysis()
    analysis["template_context"]["includeDtoVo"] = True

    async def render(template_file, _context, _category):
        return template_file

    monkeypatch.setattr(generator, "_render_template", render)

    result = await generator.generate_code(analysis, template_category="Default")

    assert "dto.mustache" in result["generated_code"]
    assert "vo.mustache" in result["generated_code"]


@pytest.mark.asyncio
async def test_codegen_generator_does_not_duplicate_sb35_dto(monkeypatch):
    generator = CodegenGenerator()
    rendered = []

    async def render(template_file, _context, _category):
        rendered.append(template_file)
        return template_file

    monkeypatch.setattr(generator, "_render_template", render)

    result = await generator.generate_code(
        _analysis("sb35-java21"),
        template_category="sb35-java21",
        generation_config={"generate_dto": True},
    )

    assert rendered.count("dto.mustache") == 1
    assert result["generation_statistics"]["total_files"] == 6


@pytest.mark.asyncio
async def test_codegen_generator_renders_common_dto_and_vo():
    table = TableInfo(
        name="users",
        schema="public",
        comment="Users",
        columns=[
            ColumnInfo(
                name="id",
                data_type="BIGINT",
                java_type="Long",
                primary_key=True,
                nullable=False,
            )
        ],
        primary_keys=["id"],
    )
    context = TemplateContextBuilder(package_name="com.example").build_context(table, "Default")

    result = await CodegenGenerator().generate_code(
        {"table_name": "users", "template_context": context},
        template_category="Default",
        generation_config={
            "package_name": "org.demo",
            "generate_dto": True,
            "generate_vo": True,
        },
    )

    assert result["generation_statistics"] == {
        "total_files": 8,
        "success_files": 8,
        "error_files": 0,
    }
    assert "package org.demo.dto;" in result["generated_code"]["dto.mustache"]["code"]
    assert "class UsersDTO" in result["generated_code"]["dto.mustache"]["code"]
    assert "package org.demo.vo;" in result["generated_code"]["vo.mustache"]["code"]
    assert "class UsersVO" in result["generated_code"]["vo.mustache"]["code"]


def test_codegen_schemas_expose_individual_dto_vo_switches():
    legacy = {tool.name: tool for tool in get_codegen_tools()}
    atomic = {tool.name: tool for tool in get_atomic_codegen_tools()}

    for name in ("db_codegen_analyze", "db_codegen_generate"):
        properties = legacy[name].inputSchema["properties"]
        assert properties["generate_dto"]["default"] is False
        assert properties["generate_vo"]["default"] is False

    properties = atomic["codegen_build_context"].inputSchema["properties"]
    assert properties["generate_dto"]["default"] is False
    assert properties["generate_vo"]["default"] is False
