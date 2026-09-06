"""Regression tests for explicit Spring Boot project path forwarding."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from dbjavagenix.core.models import DatabaseType
from dbjavagenix.database import mcp_tools


def _project_structure(root: Path) -> dict[str, Path]:
    java = root / "src" / "main" / "java"
    resources = root / "src" / "main" / "resources"
    tests = root / "src" / "test" / "java"
    for path in (java, resources, tests):
        path.mkdir(parents=True, exist_ok=True)
    return {
        "project_root": root,
        "java_source_dir": java,
        "resources_dir": resources,
        "test_dir": tests,
    }


def test_project_structure_helper_uses_explicit_path(tmp_path):
    (tmp_path / "src" / "main" / "java").mkdir(parents=True)

    structure = mcp_tools._detect_project_structure(str(tmp_path))

    assert structure["project_root"] == tmp_path


@pytest.mark.asyncio
async def test_codegen_analyze_forwards_project_path(monkeypatch, tmp_path):
    calls = []
    structure = _project_structure(tmp_path)

    monkeypatch.setattr(
        mcp_tools,
        "detect_springboot_project_structure",
        lambda start_dir=None: calls.append(start_dir) or structure,
    )
    monkeypatch.setattr(
        mcp_tools.connection_manager,
        "get_connection_info",
        lambda _connection_id: SimpleNamespace(database="app", type=DatabaseType.MYSQL),
    )

    class FakeAnalyzer:
        def __init__(self, _manager):
            pass

        async def analyze_table_for_codegen(self, *args, **kwargs):
            assert kwargs["project_root"] == str(tmp_path)
            return {
                "table_info": {
                    "name": "users",
                    "comment": "",
                    "columns": [{"name": "id", "type": "BIGINT"}],
                },
                "java_types": ["Long"],
                "imports_needed": [],
                "relationships": {"primary_keys": [], "foreign_keys": [], "indexes": []},
                "template_context": {
                    "columns": [{"javaType": "Long"}],
                    "className": "Users",
                    "lowerCaseName": "users",
                    "hasDateField": False,
                    "hasBigDecimalField": False,
                    "primaryKey": None,
                },
            }

    import dbjavagenix.database.codegen_tools as codegen_tools

    monkeypatch.setattr(codegen_tools, "CodegenAnalyzer", FakeAnalyzer)

    response = await mcp_tools.handle_db_codegen_analyze(
        {
            "connection_id": "conn-1",
            "table_name": "users",
            "project_path": str(tmp_path),
        }
    )

    assert response[0].text.startswith("Code Generation Analysis: users")
    assert calls == [tmp_path]


@pytest.mark.asyncio
async def test_validate_project_forwards_project_path(monkeypatch, tmp_path):
    calls = []
    structure = _project_structure(tmp_path)
    monkeypatch.setattr(
        mcp_tools,
        "detect_springboot_project_structure",
        lambda start_dir=None: calls.append(start_dir) or structure,
    )

    await mcp_tools.handle_springboot_validate_project(
        {
            "project_path": str(tmp_path),
            "check_dependencies": False,
            "create_missing_dirs": False,
        }
    )

    assert calls == [tmp_path]


@pytest.mark.asyncio
async def test_dependency_analysis_preserves_explicit_path(monkeypatch, tmp_path):
    calls = []
    structure = _project_structure(tmp_path)
    monkeypatch.setattr(
        mcp_tools,
        "detect_springboot_project_structure",
        lambda start_dir=None: calls.append(start_dir) or structure,
    )

    class FakeDependencyManager:
        def check_and_fix_dependencies(self, **kwargs):
            assert kwargs["project_root"] == str(tmp_path)
            return {
                "auto_add_result": {"success": True, "added_count": 0},
                "fix_result": {},
                "analysis_result": {"maven_xml": {}},
            }

        def get_dependency_health_report(self, project_root):
            assert project_root == str(tmp_path)
            return {
                "build_tool": "maven",
                "health_score": 100,
                "found_dependencies": 1,
                "total_dependencies": 1,
                "missing_required": 0,
                "missing_optional": 0,
            }

        def generate_migration_guide(self, project_root):
            assert project_root == str(tmp_path)
            return {"success": True, "total_suggestions": 0, "migration_suggestions": []}

    import dbjavagenix.utils.dependency_manager as dependency_manager

    monkeypatch.setattr(dependency_manager, "DependencyManager", FakeDependencyManager)

    await mcp_tools.handle_springboot_analyze_dependencies(
        {"project_path": str(tmp_path), "template_category": "Default", "database_type": "mysql"}
    )

    assert calls == [tmp_path]


def test_validation_tool_schema_exposes_project_path():
    tool = next(
        tool
        for tool in mcp_tools.get_springboot_project_tools()
        if tool.name == "springboot_validate_project"
    )

    assert "project_path" in tool.inputSchema["properties"]
