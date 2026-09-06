"""Regression tests for secret redaction at logging and MCP response boundaries."""

import json
import logging

import pytest

from dbjavagenix.core.exceptions import DatabaseConnectionError
from dbjavagenix.core.models import DatabaseConfig, DatabaseType
from dbjavagenix.database.connection_manager import ConnectionManager
from dbjavagenix.server import mcp_server
from dbjavagenix.database import mcp_tools
from dbjavagenix.utils.security import redact_sensitive_data, redact_sensitive_text


def test_codegen_output_path_stays_inside_base_directory(tmp_path):
    base_dir = tmp_path / "src" / "main" / "java"

    resolved = mcp_tools._resolve_codegen_output_path(base_dir, "com/example/Demo.java")

    assert resolved == base_dir.resolve() / "com" / "example" / "Demo.java"


@pytest.mark.parametrize(
    "filename",
    [
        "../outside.java",
        "C:\\outside.java",
        "C:outside.java",
        "\\\\server\\share\\outside.java",
    ],
)
def test_codegen_output_path_rejects_escape_and_rooted_paths(tmp_path, filename):
    base_dir = tmp_path / "missing" / "java"

    with pytest.raises(ValueError):
        mcp_tools._resolve_codegen_output_path(base_dir, filename)

    assert not base_dir.exists()


def test_redact_sensitive_data_handles_nested_values_without_mutating_input():
    payload = {
        "username": "reader",
        "password": "db-secret",
        "nested": {"api-key": "llm-secret", "value": 3},
        "token_count": 12,
        "items": [{"access_token": "token-value"}],
    }

    redacted = redact_sensitive_data(payload)

    assert redacted == {
        "username": "reader",
        "password": "***",
        "nested": {"api-key": "***", "value": 3},
        "token_count": 12,
        "items": [{"access_token": "***"}],
    }
    assert payload["password"] == "db-secret"


def test_redact_sensitive_text_replaces_known_secret_values():
    assert redact_sensitive_text("connect failed for db-secret", ["db-secret"]) == (
        "connect failed for ***"
    )
    assert redact_sensitive_text("jdbc:mysql://reader:db-secret@db/app") == (
        "jdbc:mysql://reader:***@db/app"
    )


def test_connection_error_masks_password_in_log_and_exception(monkeypatch, caplog):
    config = DatabaseConfig(
        type=DatabaseType.MYSQL,
        host="db.example",
        port=3306,
        database="app",
        username="reader",
        password="db-secret",
    )

    def fail_connect(**_kwargs):
        raise RuntimeError("access denied for db-secret")

    monkeypatch.setattr("dbjavagenix.database.connection_manager.pymysql.connect", fail_connect)
    with caplog.at_level(logging.ERROR):
        with pytest.raises(DatabaseConnectionError, match=r"\*\*\*") as exc_info:
            ConnectionManager().create_connection(config)

    assert "db-secret" not in str(exc_info.value)
    assert "db-secret" not in caplog.text


@pytest.mark.asyncio
async def test_mcp_call_logging_does_not_emit_credentials(monkeypatch, caplog):
    async def handler(arguments):
        return []

    monkeypatch.setattr(mcp_server, "_tool_handlers", lambda: {"test_tool": handler})
    with caplog.at_level(logging.INFO, logger=mcp_server.logger.name):
        await mcp_server.handle_call_tool(
            "test_tool",
            {"username": "reader", "password": "db-secret", "nested": {"api_key": "llm-secret"}},
        )

    message = "\n".join(record.getMessage() for record in caplog.records)
    assert "db-secret" not in message
    assert "llm-secret" not in message
    assert "***" in message


@pytest.mark.asyncio
async def test_spring_config_response_redacts_credentials(tmp_path, monkeypatch):
    resources = tmp_path / "src" / "main" / "resources"
    resources.mkdir(parents=True)
    (resources / "application.yml").write_text(
        "spring:\n"
        "  application:\n"
        "    name: demo\n"
        "  datasource:\n"
        "    url: jdbc:mysql://reader:db-secret@db/demo\n"
        "    username: reader\n"
        "    password: db-secret\n"
        "custom:\n"
        "  api-token: llm-secret\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        mcp_tools,
        "detect_springboot_project_structure",
        lambda _start_dir: {
            "project_root": tmp_path,
            "java_source_dir": None,
            "resources_dir": resources,
        },
    )

    response = await mcp_tools.handle_springboot_read_config({"project_path": str(tmp_path)})
    text = response[0].text

    assert "db-secret" not in text
    assert "llm-secret" not in text
    payload = json.loads(text.split("Raw Response:", 1)[1].strip())
    assert payload["effective"]["spring"]["datasource"]["password"] == "***"
    assert payload["raw_config"]["custom"]["api-token"] == "***"
    assert "reader:***@db/demo" in text
    assert "name=demo" in text
