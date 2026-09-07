"""Contract checks for the executable java-codegen-from-db Skill."""

from pathlib import Path


SKILL_PATH = Path(__file__).parents[2] / ".claude" / "skills" / "java-codegen-from-db" / "SKILL.md"


def _skill_text() -> str:
    return SKILL_PATH.read_text(encoding="utf-8")


def test_skill_uses_available_semantic_tools():
    text = _skill_text()

    assert "当前 MCP server 已提供阶段 3 的 AI 工具" in text
    assert "当前 Phase 2 时这些工具尚未实现" not in text
    for tool_name in (
        "ai_summarize_schema",
        "ai_infer_business_names",
        "ai_recommend_template",
    ):
        assert f"`{tool_name}`" in text


def test_skill_documents_ai_tool_contracts_and_confirmation():
    text = _skill_text()

    for field in (
        "table_names",
        "foreign_keys",
        "table_column_counts",
        "prefer_llm",
        "hint_modern_stack",
        "recommended_template",
        "class_name",
        "confidence",
    ):
        assert f"`{field}`" in text or field in text
    assert "禁止默认接受" in text
