"""Regression tests for explicit legacy code-generation output directories."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from mcp.types import TextContent

from dbjavagenix.core.models import DatabaseType
from dbjavagenix.database import mcp_tools


def _structure(root: Path) -> dict[str, Path]:
    java = root / "src" / "main" / "java"
    resources = root / "src" / "main" / "resources"
    test_dir = root / "src" / "test" / "java"
    for path in (java, resources, test_dir):
        path.mkdir(parents=True, exist_ok=True)
    return {
        "project_root": root,
        "java_source_dir": java,
        "resources_dir": resources,
        "test_dir": test_dir,
    }


class _Cursor:
    def execute(self, _query):
        return None

    def fetchall(self):
        return [("users",)]

    def close(self):
        return None


class _Connection:
    def cursor(self):
        return _Cursor()


@pytest.mark.asyncio
async def test_codegen_generate_writes_to_explicit_output_dir(monkeypatch, tmp_path):
    project = tmp_path / "project"
    output = tmp_path / "custom-output"
    structure = _structure(project)
    config = SimpleNamespace(type=DatabaseType.SQLITE, database="app")

    monkeypatch.setattr(mcp_tools.connection_manager, "get_connection_info", lambda _id: config)
    monkeypatch.setattr(mcp_tools.connection_manager, "get_connection", lambda _id: _Connection())
    monkeypatch.setattr(mcp_tools, "_detect_project_structure", lambda _path=None: structure)

    async def validate(_args):
        return [TextContent(type="text", text="Project Structure: ✅ OK")]

    async def dependencies(_args):
        return [TextContent(type="text", text="Missing Dependencies: 0")]

    monkeypatch.setattr(mcp_tools, "handle_springboot_validate_project", validate)
    monkeypatch.setattr(mcp_tools, "handle_springboot_analyze_dependencies", dependencies)

    class FakeAnalyzer:
        def __init__(self, _manager):
            pass

        async def analyze_table_for_codegen(self, *_args, **_kwargs):
            return {
                "table_name": "users",
                "template_context": {"package": "com.example", "packageSuffix": ""},
            }

    class FakeGenerator:
        async def generate_code(self, *_args, **_kwargs):
            return {
                "generated_code": {
                    "entity.mustache": {
                        "filename": "com/example/User.java",
                        "code": "class User {}",
                    },
                    "mapper.xml.mustache": {
                        "filename": "resources/mapper/User.xml",
                        "code": "<mapper />",
                    },
                },
                "generation_statistics": {"total_files": 2, "success_files": 2, "error_files": 0},
            }

    import dbjavagenix.database.codegen_tools as codegen_tools

    monkeypatch.setattr(codegen_tools, "CodegenAnalyzer", FakeAnalyzer)
    monkeypatch.setattr(codegen_tools, "CodegenGenerator", FakeGenerator)

    await mcp_tools.handle_db_codegen_generate(
        {
            "connection_id": "conn-1",
            "table_name": "users",
            "template_category": "Default",
            "package_name": "com.example",
            "project_path": str(project),
            "output_dir": str(output),
        }
    )

    assert (output / "com" / "example" / "User.java").read_text(encoding="utf-8") == "class User {}"
    assert (output / "resources" / "mapper" / "User.xml").read_text(
        encoding="utf-8"
    ) == "<mapper />"
    assert not (project / "src" / "main" / "java" / "com" / "example" / "User.java").exists()


def test_codegen_schema_exposes_output_dir():
    tool = next(
        tool for tool in mcp_tools.get_codegen_tools() if tool.name == "db_codegen_generate"
    )

    assert "output_dir" in tool.inputSchema["properties"]
