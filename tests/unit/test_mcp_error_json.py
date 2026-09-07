"""Regression tests for JSON-serializable MCP error envelopes."""

import json
from types import SimpleNamespace

import pytest

from dbjavagenix.core.exceptions import DatabaseConnectionError, DatabaseQueryError
from dbjavagenix.core.models import DatabaseType
from dbjavagenix.database import mcp_tools


def _raw_payload(response):
    text = response[0].text
    return json.loads(text.split("Raw Response:", 1)[1].strip())


@pytest.mark.asyncio
async def test_connection_error_raw_response_is_json(monkeypatch):
    def fail_create(_config):
        raise DatabaseConnectionError("invalid credentials")

    monkeypatch.setattr(mcp_tools.connection_manager, "create_connection", fail_create)

    response = await mcp_tools.handle_db_connect_test(
        {
            "database_type": "sqlite",
            "host": "",
            "port": 0,
            "username": "",
            "password": "secret",
            "database": ":memory:",
        }
    )

    assert _raw_payload(response) == {
        "success": False,
        "error": "connection_failed",
        "message": "[DB_CONNECTION_FAILED] invalid credentials",
    }


@pytest.mark.asyncio
async def test_database_list_error_raw_response_is_json(monkeypatch):
    monkeypatch.setattr(mcp_tools.connection_manager, "get_connection_info", lambda _id: None)

    response = await mcp_tools.handle_db_query_databases({"connection_id": "missing"})

    payload = _raw_payload(response)
    assert payload["success"] is False
    assert payload["error"] == "query_failed"
    assert "missing" in payload["message"]


@pytest.mark.asyncio
async def test_table_list_query_error_raw_response_is_json(monkeypatch):
    monkeypatch.setattr(
        mcp_tools.connection_manager,
        "get_connection_info",
        lambda _id: SimpleNamespace(type=DatabaseType.MYSQL),
    )

    def fail_query(*_args, **_kwargs):
        raise DatabaseQueryError("database unavailable")

    monkeypatch.setattr(mcp_tools.connection_manager, "execute_query", fail_query)

    response = await mcp_tools.handle_db_query_tables(
        {"connection_id": "conn-1", "database": "app"}
    )

    payload = _raw_payload(response)
    assert payload["success"] is False
    assert payload["error"] == "query_failed"
    assert payload["message"] == "[DB_QUERY_FAILED] database unavailable"


@pytest.mark.asyncio
async def test_query_execute_success_raw_response_is_json(monkeypatch):
    monkeypatch.setattr(
        mcp_tools.connection_manager,
        "execute_query",
        lambda *_args, **_kwargs: [{"id": 1, "name": "Alice"}],
    )

    response = await mcp_tools.handle_db_query_execute(
        {"connection_id": "sqlite-1", "query": "SELECT 1", "limit": 10}
    )

    payload = _raw_payload(response)
    assert payload["success"] is True
    assert payload["data"] == [{"id": 1, "name": "Alice"}]


@pytest.mark.asyncio
async def test_table_exists_success_raw_response_is_json(monkeypatch):
    monkeypatch.setattr(
        mcp_tools.connection_manager,
        "get_connection_info",
        lambda _id: SimpleNamespace(type=DatabaseType.SQLITE),
    )
    monkeypatch.setattr(
        mcp_tools.connection_manager,
        "execute_query",
        lambda *_args, **_kwargs: [{"count": 1}],
    )

    response = await mcp_tools.handle_db_query_table_exists(
        {"connection_id": "sqlite-1", "database": "app", "table": "users"}
    )

    payload = _raw_payload(response)
    assert payload == {
        "success": True,
        "database": "app",
        "table": "users",
        "schema": None,
        "exists": True,
    }
