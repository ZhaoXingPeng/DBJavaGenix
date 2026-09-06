"""Tests for the public runtime database capability contract."""

import pytest
from typer.testing import CliRunner

from dbjavagenix import cli
from dbjavagenix.core.exceptions import DatabaseConnectionError
from dbjavagenix.core.models import DatabaseConfig, DatabaseType
from dbjavagenix.database.capabilities import (
    SUPPORTED_DATABASE_TYPES,
    supported_database_display_names,
    supported_database_type_values,
)
from dbjavagenix.database.connection_manager import ConnectionManager
from dbjavagenix.database.mcp_tools import get_connection_tools


def test_public_database_capabilities_are_derived_from_one_list():
    assert SUPPORTED_DATABASE_TYPES == (
        DatabaseType.MYSQL,
        DatabaseType.POSTGRESQL,
        DatabaseType.SQLITE,
    )
    assert supported_database_type_values() == ["mysql", "postgresql", "sqlite"]
    assert supported_database_display_names() == ["MySQL", "PostgreSQL", "SQLite"]


def test_connection_tool_schema_only_advertises_implemented_databases():
    connection_tool = next(
        tool for tool in get_connection_tools() if tool.name == "db_connect_test"
    )

    assert connection_tool.inputSchema["properties"]["database_type"]["enum"] == (
        supported_database_type_values()
    )


def test_cli_version_only_advertises_implemented_databases():
    result = CliRunner().invoke(cli.app, ["version"])

    assert result.exit_code == 0
    assert "MySQL, PostgreSQL, SQLite" in result.output
    assert "Oracle" not in result.output
    assert "SQL Server" not in result.output


def test_connection_manager_rejects_planned_but_unimplemented_database():
    config = DatabaseConfig(
        type=DatabaseType.ORACLE,
        host="db.example",
        port=1521,
        database="app",
        username="reader",
        password="secret",
    )

    with pytest.raises(DatabaseConnectionError, match="Supported database types"):
        ConnectionManager().create_connection(config)
