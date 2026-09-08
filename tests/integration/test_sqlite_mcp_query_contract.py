"""File-backed SQLite coverage for public MCP query handlers."""

from __future__ import annotations

import json
from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest

from dbjavagenix.core.models import DatabaseConfig, DatabaseType
from dbjavagenix.database import mcp_tools


SPECIAL_TABLE = "odd'table"


def _raw_payload(response: list[Any]) -> dict[str, Any]:
    return json.loads(response[0].text.split("Raw Response:", 1)[1].strip())


@pytest.fixture
def sqlite_mcp_query_file(tmp_path: Path) -> Generator[dict[str, str], None, None]:
    """Create one SQLite file through the same global manager used by handlers."""
    database_path = tmp_path / "mcp-query-contract.db"
    connection_id = mcp_tools.connection_manager.create_connection(
        DatabaseConfig(
            type=DatabaseType.SQLITE,
            host="",
            port=0,
            database=str(database_path),
            username="",
            password="",
        )
    )
    try:
        mcp_tools.connection_manager.execute_query(
            connection_id,
            'CREATE TABLE "odd\'table" (id INTEGER PRIMARY KEY, name TEXT NOT NULL)',
        )
        yield {
            "connection_id": connection_id,
            "database": str(database_path),
        }
    finally:
        mcp_tools.connection_manager.close_connection(connection_id)


@pytest.mark.asyncio
async def test_sqlite_mcp_discovery_raw_response_handles_special_table_name(
    sqlite_mcp_query_file: dict[str, str],
) -> None:
    fixture = sqlite_mcp_query_file

    tables = await mcp_tools.handle_db_query_tables(fixture)
    exists = await mcp_tools.handle_db_query_table_exists({**fixture, "table": SPECIAL_TABLE})
    missing = await mcp_tools.handle_db_query_table_exists({**fixture, "table": "missing_table"})

    assert _raw_payload(tables) == {
        "success": True,
        "database": fixture["database"],
        "schema": None,
        "tables": [SPECIAL_TABLE],
        "table_references": [{"table_name": SPECIAL_TABLE, "schema": None}],
        "count": 1,
    }
    assert _raw_payload(exists)["exists"] is True
    assert _raw_payload(missing)["exists"] is False


@pytest.mark.asyncio
async def test_sqlite_mcp_query_keeps_empty_result_json_and_rejects_insert(
    sqlite_mcp_query_file: dict[str, str],
) -> None:
    fixture = sqlite_mcp_query_file
    empty = await mcp_tools.handle_db_query_execute(
        {
            "connection_id": fixture["connection_id"],
            "query": "SELECT id, name FROM \"odd'table\" WHERE name = 'missing'",
            "limit": 2,
        }
    )
    rejected = await mcp_tools.handle_db_query_execute(
        {
            "connection_id": fixture["connection_id"],
            "query": "INSERT INTO \"odd'table\" (name) VALUES ('blocked')",
        }
    )

    assert _raw_payload(empty) == {
        "success": True,
        "query": "SELECT id, name FROM \"odd'table\" WHERE name = 'missing' LIMIT 2",
        "row_count": 0,
        "data": [],
    }
    assert _raw_payload(rejected)["success"] is False
    assert _raw_payload(rejected)["error"] == "query_failed"
    assert mcp_tools.connection_manager.execute_query(
        fixture["connection_id"], 'SELECT COUNT(*) AS count FROM "odd\'table"'
    ) == [{"count": 0}]
