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


def test_postgresql_java_mapping_normalizes_catalog_type_names():
    assert mcp_tools._get_java_type_mapping(
        DatabaseType.POSTGRESQL, "timestamp with time zone"
    ) == {"java_type": "OffsetDateTime", "imports": ["java.time.OffsetDateTime"]}
    assert mcp_tools._get_java_type_mapping(DatabaseType.POSTGRESQL, "uuid") == {
        "java_type": "UUID",
        "imports": ["java.util.UUID"],
    }
    assert mcp_tools._get_java_type_mapping(DatabaseType.POSTGRESQL, "jsonb") == {
        "java_type": "String",
        "imports": [],
    }
    assert mcp_tools._get_java_type_mapping(DatabaseType.POSTGRESQL, "character varying(255)") == {
        "java_type": "String",
        "imports": [],
    }
    assert mcp_tools._get_java_type_mapping(
        DatabaseType.POSTGRESQL, "timestamp(6) with time zone"
    ) == {"java_type": "OffsetDateTime", "imports": ["java.time.OffsetDateTime"]}


@pytest.mark.asyncio
async def test_table_describe_uses_normalized_introspection_with_schema(monkeypatch):
    class Introspector:
        def __init__(self, manager):
            assert manager is mcp_tools.connection_manager

        def get_config(self, connection_id):
            assert connection_id == "pg-1"
            return SimpleNamespace(type=DatabaseType.POSTGRESQL)

        def describe_table(self, connection_id, table, schema):
            assert (connection_id, table, schema) == ("pg-1", "users", "tenant_a")
            return {
                "name": "users",
                "schema": "tenant_a",
                "comment": "tenant users",
                "columns": [
                    {
                        "name": "id",
                        "type": "USER-DEFINED",
                        "column_type": "uuid",
                        "nullable": False,
                        "default_value": None,
                        "comment": "identifier",
                        "primary_key": True,
                        "precision": None,
                        "scale": None,
                        "max_length": None,
                    }
                ],
            }

    monkeypatch.setattr(mcp_tools, "DatabaseIntrospector", Introspector)
    response = await mcp_tools.handle_db_table_describe(
        {
            "connection_id": "pg-1",
            "database": "app",
            "schema": "tenant_a",
            "table": "users",
            "include_java_types": False,
        }
    )

    text = response[0].text
    assert "tenant_a" in text
    assert "tenant users" in text
    assert "USER-DEFINED" in text


@pytest.mark.asyncio
async def test_postgresql_table_detail_tools_forward_schema(monkeypatch):
    class Introspector:
        def __init__(self, manager):
            pass

        def get_columns(self, connection_id, table, schema):
            assert (connection_id, table, schema) == ("pg-1", "users", "tenant_a")
            return [
                {
                    "name": "id",
                    "type": "bigint",
                    "column_type": "bigint",
                    "nullable": False,
                    "default_value": None,
                    "comment": "",
                    "precision": None,
                    "scale": None,
                    "max_length": None,
                }
            ]

        def get_primary_keys(self, connection_id, table, schema):
            assert (connection_id, table, schema) == ("pg-1", "users", "tenant_a")
            return ["id"]

        def get_foreign_keys(self, connection_id, table, schema):
            assert (connection_id, table, schema) == ("pg-1", "users", "tenant_a")
            return [
                {
                    "column_name": "org_id",
                    "referenced_table": "orgs",
                    "referenced_column": "id",
                    "constraint_name": "users_org_fk",
                }
            ]

        def get_indexes(self, connection_id, table, schema):
            assert (connection_id, table, schema) == ("pg-1", "users", "tenant_a")
            return [
                {
                    "key_name": "users_pkey",
                    "column_name": "id",
                    "seq_in_index": 1,
                    "unique": True,
                    "index_type": "btree",
                }
            ]

    monkeypatch.setattr(mcp_tools, "DatabaseIntrospector", Introspector)
    monkeypatch.setattr(
        mcp_tools.connection_manager,
        "get_connection_info",
        lambda connection_id: SimpleNamespace(type=DatabaseType.POSTGRESQL),
    )
    common = {"connection_id": "pg-1", "database": "app", "schema": "tenant_a", "table": "users"}

    responses = await mcp_tools.handle_db_table_columns(common)
    assert "bigint" in responses[0].text
    responses = await mcp_tools.handle_db_table_primary_keys(common)
    assert "id" in responses[0].text
    responses = await mcp_tools.handle_db_table_foreign_keys(common)
    assert "orgs.id" in responses[0].text
    responses = await mcp_tools.handle_db_table_indexes(common)
    assert "users_pkey" in responses[0].text
