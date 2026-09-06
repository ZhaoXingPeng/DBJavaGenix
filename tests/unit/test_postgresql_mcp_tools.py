"""Unit coverage for PostgreSQL MCP discovery tools without a live database."""

from types import SimpleNamespace

import pytest

from dbjavagenix.core.models import DatabaseType
from dbjavagenix.database import mcp_tools


@pytest.fixture
def postgres_info():
    return SimpleNamespace(type=DatabaseType.POSTGRESQL, database="app")


@pytest.mark.asyncio
async def test_connect_test_reports_postgresql_server(monkeypatch):
    class Cursor:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def execute(self, query):
            assert query == "SELECT version() AS version"

        def fetchone(self):
            return ("PostgreSQL 16.4",)

    monkeypatch.setattr(mcp_tools.connection_manager, "create_connection", lambda config: "pg-1")
    monkeypatch.setattr(mcp_tools.connection_manager, "get_connection", lambda cid: object())
    monkeypatch.setattr(mcp_tools.connection_manager, "get_cursor", lambda cid: Cursor())

    response = await mcp_tools.handle_db_connect_test(
        {
            "database_type": "postgresql",
            "host": "db.example",
            "port": 5432,
            "username": "reader",
            "password": "secret",
            "database": "app",
        }
    )

    assert "PostgreSQL 16.4" in response[0].text
    assert "pg-1" in response[0].text


@pytest.mark.asyncio
async def test_query_databases_uses_postgresql_catalog(monkeypatch, postgres_info):
    calls = []
    monkeypatch.setattr(
        mcp_tools.connection_manager, "get_connection_info", lambda cid: postgres_info
    )

    def execute_query(connection_id, query, params=None):
        calls.append((connection_id, query, params))
        return [{"database_name": "app"}, {"database_name": "audit"}]

    monkeypatch.setattr(mcp_tools.connection_manager, "execute_query", execute_query)

    response = await mcp_tools.handle_db_query_databases({"connection_id": "pg-1"})

    assert "Found 2 databases" in response[0].text
    assert calls[0][0] == "pg-1"
    assert "pg_database" in calls[0][1]
    assert calls[0][2] is None


@pytest.mark.asyncio
async def test_query_tables_uses_catalog_and_parameters(monkeypatch, postgres_info):
    calls = []
    monkeypatch.setattr(
        mcp_tools.connection_manager, "get_connection_info", lambda cid: postgres_info
    )

    def execute_query(connection_id, query, params=None):
        calls.append((connection_id, query, params))
        return [{"table_name": "users"}]

    monkeypatch.setattr(mcp_tools.connection_manager, "execute_query", execute_query)

    response = await mcp_tools.handle_db_query_tables({"connection_id": "pg-1", "database": "app"})

    assert "users" in response[0].text
    assert "information_schema.tables" in calls[0][1]
    assert calls[0][2] == ("app",)


@pytest.mark.asyncio
async def test_table_exists_uses_postgresql_catalog(monkeypatch, postgres_info):
    calls = []
    monkeypatch.setattr(
        mcp_tools.connection_manager, "get_connection_info", lambda cid: postgres_info
    )

    def execute_query(connection_id, query, params=None):
        calls.append((connection_id, query, params))
        return [{"count": 1}]

    monkeypatch.setattr(mcp_tools.connection_manager, "execute_query", execute_query)

    response = await mcp_tools.handle_db_query_table_exists(
        {"connection_id": "pg-1", "database": "app", "table": "users"}
    )

    assert "exists in database" in response[0].text
    assert calls[0][2] == ("app", "users")
