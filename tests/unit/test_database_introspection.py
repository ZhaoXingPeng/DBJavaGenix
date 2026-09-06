"""Tests for the database-neutral metadata access layer."""

from __future__ import annotations

import pytest

from dbjavagenix.core.exceptions import DatabaseAnalysisError
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
        "CREATE UNIQUE INDEX orders_user_idx ON orders(user_id, created_at)",
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
        assert user_index["column_name"] == "user_id"
        assert user_index["seq_in_index"] == 1
        created_index = next(
            index
            for index in indexes
            if index["key_name"] == "orders_user_idx" and index["column_name"] == "created_at"
        )
        assert created_index["seq_in_index"] == 2
    finally:
        manager.close_connection(connection_id)


def test_sqlite_introspection_escapes_special_table_names():
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
    try:
        manager.execute_query(connection_id, 'CREATE TABLE "odd\'table" (id INTEGER)')
        introspector = DatabaseIntrospector(manager)
        columns = introspector.get_columns(connection_id, "odd'table")
        assert [column["name"] for column in columns] == ["id"]
        assert introspector.get_indexes(connection_id, "odd'table") == []
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


class MySQLIndexManager:
    def __init__(self):
        self.config = DatabaseConfig(
            type=DatabaseType.MYSQL,
            host="db.example",
            port=3306,
            database="app",
            username="reader",
            password="secret",
        )
        self.calls = []

    def get_connection_info(self, connection_id):
        return self.config

    def execute_query(self, connection_id, query, params=None):
        self.calls.append((query, params))
        return []


def test_mysql_index_introspection_quotes_identifier():
    manager = MySQLIndexManager()

    DatabaseIntrospector(manager).get_indexes("mysql-1", "odd`table")

    assert manager.calls == [("SHOW INDEX FROM `odd``table`", None)]


def test_mysql_index_introspection_rejects_control_character():
    manager = MySQLIndexManager()

    with pytest.raises(DatabaseAnalysisError, match="control characters"):
        DatabaseIntrospector(manager).get_indexes("mysql-1", "odd\ntable")

    assert manager.calls == []


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


def test_postgresql_composite_foreign_keys_pair_columns_by_position():
    manager = RecordingManager()
    original_execute_query = manager.execute_query

    def execute_query(connection_id, query, params=None):
        manager.calls.append((query, params))
        if "pg_catalog.pg_constraint" in query:
            return [
                {
                    "constraint_name": "orders_customer_fk",
                    "column_name": "tenant_id",
                    "referenced_table_name": "customers",
                    "referenced_column_name": "tenant_id",
                    "column_position": 1,
                },
                {
                    "constraint_name": "orders_customer_fk",
                    "column_name": "customer_id",
                    "referenced_table_name": "customers",
                    "referenced_column_name": "id",
                    "column_position": 2,
                },
            ]
        return original_execute_query(connection_id, query, params)

    manager.execute_query = execute_query
    foreign_keys = DatabaseIntrospector(manager).get_foreign_keys("pg-1", "orders", "tenant_a")

    assert foreign_keys == [
        {
            "constraint_name": "orders_customer_fk",
            "column_name": "tenant_id",
            "referenced_table": "customers",
            "referenced_column": "tenant_id",
        },
        {
            "constraint_name": "orders_customer_fk",
            "column_name": "customer_id",
            "referenced_table": "customers",
            "referenced_column": "id",
        },
    ]
    assert len(manager.calls) == 1
    query, params = manager.calls[0]
    assert "tgt_keys.ordinality = src_keys.ordinality" in query
    assert params == ("orders", "tenant_a")


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
