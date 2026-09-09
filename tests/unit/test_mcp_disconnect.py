"""Regression tests for the public MCP connection lifecycle tool."""

import json

import pytest

from dbjavagenix.core.models import DatabaseConfig, DatabaseType
from dbjavagenix.database import mcp_tools
from dbjavagenix.database.connection_manager import ConnectionManager
from dbjavagenix.utils.tool_registry import search_tools_by_query


def _raw_payload(response):
    return json.loads(response[0].text.split("Raw Response:", 1)[1].strip())


def _sqlite_config(database=":memory:"):
    return DatabaseConfig(
        type=DatabaseType.SQLITE,
        host="",
        port=0,
        database=database,
        username="",
        password="secret",
    )


def test_disconnect_tool_schema_requires_only_non_empty_connection_id():
    tool = next(tool for tool in mcp_tools.get_connection_tools() if tool.name == "db_disconnect")

    assert tool.inputSchema["required"] == ["connection_id"]
    assert tool.inputSchema["properties"] == {
        "connection_id": {
            "type": "string",
            "description": "Connection identifier returned by db_connect_test",
            "minLength": 1,
        }
    }


@pytest.mark.asyncio
async def test_disconnect_success_removes_connection_and_masked_config(monkeypatch):
    manager = ConnectionManager()
    connection_id = manager.create_connection(_sqlite_config())
    monkeypatch.setattr(mcp_tools, "connection_manager", manager)

    response = await mcp_tools.handle_db_disconnect({"connection_id": connection_id})

    assert _raw_payload(response) == {
        "success": True,
        "connection_id": connection_id,
        "message": "Connection closed successfully",
    }
    assert connection_id not in manager.connections
    assert connection_id not in manager.connection_configs


@pytest.mark.asyncio
@pytest.mark.parametrize("arguments", [{}, {"connection_id": ""}, {"connection_id": "   "}])
async def test_disconnect_empty_id_returns_connection_not_found(monkeypatch, arguments):
    def fail_if_called(_connection_id):
        raise AssertionError("empty IDs must be rejected before touching the manager")

    monkeypatch.setattr(mcp_tools.connection_manager, "close_connection", fail_if_called)

    response = await mcp_tools.handle_db_disconnect(arguments)

    assert _raw_payload(response) == {
        "success": False,
        "error": "connection_not_found",
        "connection_id": None,
        "message": "Connection not found",
    }


@pytest.mark.asyncio
async def test_disconnect_unknown_and_repeated_id_are_stable_failures(monkeypatch):
    manager = ConnectionManager()
    connection_id = manager.create_connection(_sqlite_config())
    monkeypatch.setattr(mcp_tools, "connection_manager", manager)

    first = _raw_payload(await mcp_tools.handle_db_disconnect({"connection_id": connection_id}))
    repeated = _raw_payload(await mcp_tools.handle_db_disconnect({"connection_id": connection_id}))
    unknown = _raw_payload(await mcp_tools.handle_db_disconnect({"connection_id": "missing"}))

    assert first["success"] is True
    assert repeated == {
        "success": False,
        "error": "connection_not_found",
        "connection_id": connection_id,
        "message": "Connection not found",
    }
    assert unknown["error"] == "connection_not_found"
    assert unknown["success"] is False


@pytest.mark.asyncio
async def test_disconnect_exception_is_redacted(monkeypatch):
    def fail(_connection_id):
        raise RuntimeError("jdbc:mysql://reader:db-secret@db/app")

    monkeypatch.setattr(mcp_tools.connection_manager, "close_connection", fail)

    response = await mcp_tools.handle_db_disconnect({"connection_id": "conn-1"})
    payload = _raw_payload(response)

    assert payload["success"] is False
    assert payload["error"] == "disconnect_failed"
    assert payload["message"] == "jdbc:mysql://reader:***@db/app"
    assert "db-secret" not in response[0].text


def test_disconnect_is_discoverable_by_progressive_registry():
    results = search_tools_by_query("disconnect")

    assert results
    assert results[0]["name"] == "db_disconnect"
