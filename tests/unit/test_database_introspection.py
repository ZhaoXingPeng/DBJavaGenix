"""Tests for the database-neutral metadata access layer."""

from __future__ import annotations

from dbjavagenix.core.models import DatabaseConfig, DatabaseType
from dbjavagenix.database.connection_manager import ConnectionManager
from dbjavagenix.database.introspection import DatabaseIntrospector


def _sqlite_manager() -> tuple[ConnectionManager, str]:
    manager = ConnectionManager()
    connection_id = manager.create_connection(
        DatabaseConfig(
            type=DatabaseType.SQLITE,
            host="",
            port=0,
            database=":memory:",
            username="",
            password="",
        )
    )
    manager.execute_query(connection_id, "PRAGMA foreign_keys = ON")
    manager.execute_query(
        connection_id,
        "CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT NOT NULL)",
    )
    manager.execute_query(
        connection_id,
        "CREATE TABLE orders (id INTEGER PRIMARY KEY, user_id INTEGER, "
        "created_at TIMESTAMP, FOREIGN KEY(user_id) REFERENCES users(id))",
    )
    manager.execute_query(
        connection_id,
        "CREATE UNIQUE INDEX orders_user_idx ON orders(user_id)",
    )
    return manager, connection_id


def test_sqlite_introspection_returns_normalized_metadata():
    manager, connection_id = _sqlite_manager()
    try:
        introspector = DatabaseIntrospector(manager)
        assert introspector.list_tables(connection_id) == ["orders", "users"]
        table = introspector.get_table(connection_id, "orders")
        assert table["name"] == "orders"

        columns = introspector.get_columns(connection_id, "orders")
        assert [column["name"] for column in columns] == ["id", "user_id", "created_at"]
        assert columns[0]["primary_key"] is True
        assert columns[1]["nullable"] is True
        assert introspector.get_primary_keys(connection_id, "orders") == ["id"]

        foreign_keys = introspector.get_foreign_keys(connection_id, "orders")
        assert foreign_keys == [
            {
                "constraint_name": "0",
                "column_name": "user_id",
                "referenced_table": "users",
                "referenced_column": "id",
            }
        ]

        indexes = introspector.get_indexes(connection_id, "orders")
        user_index = next(index for index in indexes if index["key_name"] == "orders_user_idx")
        assert user_index["unique"] is True
    finally:
        manager.close_connection(connection_id)


class RecordingManager:
    def __init__(self):
        self.config = DatabaseConfig(
            type=DatabaseType.POSTGRESQL,
            host="db.example",
            port=5432,
            database="app",
            username="reader",
            password="secret",
        )
        self.calls = []

    def get_connection_info(self, connection_id):
        return self.config

    def execute_query(self, connection_id, query, params=None):
        self.calls.append((query, params))
        if "information_schema.tables" in query:
            return [{"table_name": "users", "table_schema": "public"}]
        if "information_schema.columns" in query:
            return [{"column_name": "id", "data_type": "bigint", "is_nullable": "NO"}]
        if "table_constraints" in query and "PRIMARY KEY" in query:
            return [{"column_name": "id"}]
        if "pg_index" in query:
            return [{"key_name": "users_pkey", "column_name": "id", "is_unique": True}]
        return []


def test_postgresql_introspection_uses_catalog_queries():
    manager = RecordingManager()
    introspector = DatabaseIntrospector(manager)

    assert introspector.list_tables("pg-1") == ["users"]
    assert introspector.get_table("pg-1", "users")["schema"] == "public"
    assert introspector.get_columns("pg-1", "users")[0]["type"] == "bigint"
    assert introspector.get_primary_keys("pg-1", "users") == ["id"]
    assert introspector.get_indexes("pg-1", "users")[0]["key_name"] == "users_pkey"

    assert len(manager.calls) == 5
    assert all("SHOW TABLES" not in query for query, _ in manager.calls)


class SchemaAwarePostgresManager(RecordingManager):
    def execute_query(self, connection_id, query, params=None):
        self.calls.append((query, params))
        if "information_schema.tables" in query:
            return [
                {"table_name": "users", "table_schema": params[1] if len(params) > 1 else "public"}
            ]
        if "information_schema.columns" in query:
            return [
                {
                    "column_name": "id",
                    "data_type": "USER-DEFINED",
                    "is_nullable": "NO",
                    "column_type": "uuid",
                    "column_comment": "stable identifier",
                },
                {
                    "column_name": "created_at",
                    "data_type": "timestamp with time zone",
                    "is_nullable": "NO",
                    "column_type": "timestamp with time zone",
                },
            ]
        if "table_constraints" in query and "PRIMARY KEY" in query:
            return [{"column_name": "id"}]
        if "pg_index" in query:
            return [{"key_name": "users_pkey", "column_name": "id", "is_unique": True}]
        return []


def test_postgresql_describe_table_scopes_all_catalog_queries_to_schema():
    manager = SchemaAwarePostgresManager()
    metadata = DatabaseIntrospector(manager).describe_table("pg-1", "users", "tenant_a")

    assert metadata["schema"] == "tenant_a"
    assert metadata["comment"] == ""
    assert metadata["primary_keys"] == ["id"]
    assert metadata["columns"][0]["column_type"] == "uuid"
    assert metadata["columns"][0]["comment"] == "stable identifier"
    assert metadata["columns"][0]["primary_key"] is True
    assert all(params == ("users", "tenant_a") for _, params in manager.calls if params)


def test_postgresql_get_table_rejects_ambiguous_schema():
    manager = RecordingManager()

    def execute_query(connection_id, query, params=None):
        if "information_schema.tables" in query:
            return [
                {"table_name": "users", "table_schema": "tenant_a"},
                {"table_name": "users", "table_schema": "tenant_b"},
            ]
        return []

    manager.execute_query = execute_query
    introspector = DatabaseIntrospector(manager)

    try:
        introspector.get_table("pg-1", "users")
    except Exception as exc:
        assert "multiple schemas" in str(exc)
    else:
        raise AssertionError("ambiguous PostgreSQL table should require schema")
