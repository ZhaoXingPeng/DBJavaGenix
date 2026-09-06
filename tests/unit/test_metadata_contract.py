"""Cross-dialect contract tests for normalized table metadata."""

from __future__ import annotations

import pytest

from dbjavagenix.core.models import DatabaseConfig, DatabaseType
from dbjavagenix.database.connection_manager import ConnectionManager
from dbjavagenix.database.introspection import DatabaseIntrospector


class StubMetadataManager:
    def __init__(self, database_type: DatabaseType):
        self.config = DatabaseConfig(
            type=database_type,
            host="db.example",
            port=5432,
            database="app",
            username="reader",
            password="secret",
        )

    def get_connection_info(self, connection_id: str):
        return self.config

    def execute_query(self, connection_id: str, query: str, params=None):
        if self.config.type == DatabaseType.MYSQL:
            if "information_schema.TABLES" in query:
                return [{"TABLE_NAME": "users", "TABLE_COMMENT": "users", "ENGINE": "InnoDB"}]
            if "information_schema.COLUMNS" in query:
                return [
                    {
                        "COLUMN_NAME": "id",
                        "DATA_TYPE": "BIGINT",
                        "COLUMN_TYPE": "bigint",
                        "IS_NULLABLE": "NO",
                        "COLUMN_KEY": "PRI",
                    }
                ]
            if "KEY_COLUMN_USAGE" in query and "REFERENCED_TABLE_NAME" in query:
                return []
            if "KEY_COLUMN_USAGE" in query:
                return [{"COLUMN_NAME": "id"}]
            if "SHOW INDEX" in query:
                return [{"Key_name": "PRIMARY", "Column_name": "id", "Non_unique": 0}]
        if self.config.type == DatabaseType.POSTGRESQL:
            if "information_schema.tables" in query:
                return [{"table_name": "users", "table_schema": "public"}]
            if "information_schema.columns" in query:
                return [{"column_name": "id", "data_type": "bigint", "is_nullable": "NO"}]
            if "table_constraints" in query and "PRIMARY KEY" in query:
                return [{"column_name": "id"}]
            if "table_constraints" in query and "FOREIGN KEY" in query:
                return []
            if "pg_index" in query:
                return [{"key_name": "users_pkey", "column_name": "id", "is_unique": True}]
        return []


def _assert_contract(metadata: dict):
    assert set(metadata) >= {
        "name",
        "schema",
        "comment",
        "columns",
        "primary_keys",
        "foreign_keys",
        "indexes",
    }
    assert metadata["name"] == "users"
    assert metadata["primary_keys"] == ["id"]
    assert metadata["columns"][0]["name"] == "id"
    assert metadata["columns"][0]["primary_key"] is True
    assert metadata["indexes"]
    assert all(
        {"key_name", "column_name", "unique", "seq_in_index", "index_type"} <= set(index)
        for index in metadata["indexes"]
    )


@pytest.mark.parametrize("database_type", [DatabaseType.MYSQL, DatabaseType.POSTGRESQL])
def test_stubbed_dialects_share_normalized_metadata_contract(database_type):
    manager = StubMetadataManager(database_type)
    _assert_contract(DatabaseIntrospector(manager).describe_table("db-1", "users"))


def test_sqlite_shares_normalized_metadata_contract():
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
        manager.execute_query(
            connection_id,
            "CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT NOT NULL)",
        )
        manager.execute_query(connection_id, "CREATE INDEX users_name_idx ON users(name)")
        _assert_contract(DatabaseIntrospector(manager).describe_table(connection_id, "users"))
    finally:
        manager.close_connection(connection_id)
