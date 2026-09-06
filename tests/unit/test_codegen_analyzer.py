"""Unit tests for the public code-generation analysis workflow."""

import pytest

from dbjavagenix.database.codegen_tools import CodegenAnalyzer, CodegenGenerator


class _FakeIntrospector:
    def list_tables(self, _connection_id):
        return ["users", "broken"]


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
