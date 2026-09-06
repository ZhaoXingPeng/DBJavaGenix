"""Regression tests for database identifier boundaries in MCP tools."""

from types import SimpleNamespace

import pytest

from dbjavagenix.core.models import DatabaseType
from dbjavagenix.database import mcp_tools


@pytest.fixture
def mysql_info():
    return SimpleNamespace(type=DatabaseType.MYSQL, database="app")


@pytest.mark.asyncio
async def test_mysql_table_listing_quotes_identifier(monkeypatch, mysql_info):
    calls = []
    monkeypatch.setattr(
        mcp_tools.connection_manager, "get_connection_info", lambda _cid: mysql_info
    )
    monkeypatch.setattr(
        mcp_tools.connection_manager,
        "execute_query",
        lambda connection_id, query, params=None: (
            calls.append((connection_id, query, params)) or []
        ),
    )

    await mcp_tools.handle_db_query_tables({"connection_id": "mysql-1", "database": "app`archive"})

    assert calls == [("mysql-1", "SHOW TABLES FROM `app``archive`", None)]


@pytest.mark.asyncio
async def test_mysql_table_listing_rejects_control_character(monkeypatch, mysql_info):
    calls = []
    monkeypatch.setattr(
        mcp_tools.connection_manager, "get_connection_info", lambda _cid: mysql_info
    )
    monkeypatch.setattr(
        mcp_tools.connection_manager,
        "execute_query",
        lambda *args: calls.append(args) or [],
    )

    response = await mcp_tools.handle_db_query_tables(
        {"connection_id": "mysql-1", "database": "app\narchive"}
    )

    assert "control characters" in response[0].text
    assert calls == []
