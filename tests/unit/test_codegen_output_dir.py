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


def _stub_codegen_handler(monkeypatch, project: Path, generated_code: dict) -> None:
    """Install deterministic handler dependencies for write-result tests."""
    structure = _structure(project)
    config = SimpleNamespace(type=DatabaseType.SQLITE, database="app")

    monkeypatch.setattr(mcp_tools.connection_manager, "get_connection_info", lambda _id: config)
    monkeypatch.setattr(mcp_tools.connection_manager, "get_connection", lambda _id: _Connection())
    monkeypatch.setattr(mcp_tools, "_detect_project_structure", lambda _path=None: structure)
    monkeypatch.setattr(mcp_tools, "_collect_codegen_table_names", lambda *_args: ["users"])

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
            success_files = sum("error" not in info for info in generated_code.values())
            return {
                "generated_code": generated_code,
                "generation_statistics": {
                    "total_files": len(generated_code),
                    "success_files": success_files,
                    "error_files": len(generated_code) - success_files,
                },
            }

    import dbjavagenix.database.codegen_tools as codegen_tools

    monkeypatch.setattr(codegen_tools, "CodegenAnalyzer", FakeAnalyzer)
    monkeypatch.setattr(codegen_tools, "CodegenGenerator", FakeGenerator)


def test_collect_codegen_table_names_uses_shared_introspector(monkeypatch):
    calls = []

    class Introspector:
        def __init__(self, manager):
            assert manager is mcp_tools.connection_manager

        def list_tables(self, connection_id):
            calls.append(connection_id)
            return ["sys_user", "sys_role"]

    monkeypatch.setattr(mcp_tools, "DatabaseIntrospector", Introspector)

    assert mcp_tools._collect_codegen_table_names("pg-1", "sys_user") == [
        "sys_user",
        "sys_role",
    ]
    assert calls == ["pg-1"]


def test_collect_codegen_table_names_falls_back_on_empty_or_error(monkeypatch):
    class Introspector:
        def __init__(self, manager):
            pass

        def list_tables(self, connection_id):
            if connection_id == "empty":
                return []
            raise RuntimeError("metadata unavailable")

    monkeypatch.setattr(mcp_tools, "DatabaseIntrospector", Introspector)

    assert mcp_tools._collect_codegen_table_names("empty", "orders") == ["orders"]
    assert mcp_tools._collect_codegen_table_names("broken", "orders") == ["orders"]


@pytest.mark.asyncio
async def test_codegen_generate_writes_to_explicit_output_dir(monkeypatch, tmp_path):
    project = tmp_path / "project"
    output = tmp_path / "custom-output"
    _stub_codegen_handler(
        monkeypatch,
        project,
        {
            "entity.mustache": {
                "filename": "com/example/User.java",
                "code": "class User {}",
            },
            "mapper.xml.mustache": {
                "filename": "resources/mapper/User.xml",
                "code": "<mapper />",
            },
        },
    )

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


@pytest.mark.asyncio
async def test_codegen_generate_reports_actual_write_failures(monkeypatch, tmp_path):
    project = tmp_path / "project"
    output = tmp_path / "custom-output"
    _stub_codegen_handler(
        monkeypatch,
        project,
        {
            "entity.mustache": {
                "filename": "com/example/User.java",
                "code": "class User {}",
            },
            "mapper.xml.mustache": {
                "filename": "resources/mapper/User.xml",
                "code": "<mapper />",
            },
        },
    )

    real_writer = mcp_tools._write_codegen_file

    def flaky_writer(path: Path, code: str) -> None:
        if path.name == "User.xml":
            raise OSError("disk full")
        real_writer(path, code)

    monkeypatch.setattr(mcp_tools, "_write_codegen_file", flaky_writer)

    response = await mcp_tools.handle_db_codegen_generate(
        {
            "connection_id": "conn-1",
            "table_name": "users",
            "template_category": "Default",
            "package_name": "com.example",
            "project_path": str(project),
            "output_dir": str(output),
        }
    )

    text = response[0].text
    assert (output / "com" / "example" / "User.java").read_text(encoding="utf-8") == "class User {}"
    assert not (output / "resources" / "mapper" / "User.xml").exists()
    assert "Write Attempts: 2" in text
    assert "Write Succeeded: 1" in text
    assert "Write Failed: 1" in text
    assert "PARTIAL" in text
    assert "All files written" not in text


@pytest.mark.asyncio
async def test_codegen_generate_reports_rejected_paths_separately(monkeypatch, tmp_path):
    project = tmp_path / "project"
    output = tmp_path / "custom-output"
    _stub_codegen_handler(
        monkeypatch,
        project,
        {
            "entity.mustache": {
                "filename": "../outside/User.java",
                "code": "class User {}",
            },
        },
    )

    response = await mcp_tools.handle_db_codegen_generate(
        {
            "connection_id": "conn-1",
            "table_name": "users",
            "template_category": "Default",
            "package_name": "com.example",
            "project_path": str(project),
            "output_dir": str(output),
        }
    )

    text = response[0].text
    assert "Write Candidates: 1" in text
    assert "Write Attempts: 0" in text
    assert "Write Succeeded: 0" in text
    assert "Paths Rejected: 1" in text
    assert "Write Failed: 0" in text
    assert "path rejected" in text
    assert "FAILED: No generated files were written" in text
    assert not (tmp_path / "outside" / "User.java").exists()


def test_codegen_schema_exposes_output_dir():
    tool = next(
        tool for tool in mcp_tools.get_codegen_tools() if tool.name == "db_codegen_generate"
    )

    assert "output_dir" in tool.inputSchema["properties"]
