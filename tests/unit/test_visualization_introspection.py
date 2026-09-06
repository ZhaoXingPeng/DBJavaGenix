"""Regression tests for ER diagram metadata reuse."""

from types import SimpleNamespace

from dbjavagenix.core.models import DatabaseType
from dbjavagenix.database import visualization_tools


def test_postgresql_er_queries_use_shared_introspection(monkeypatch):
    calls = []
    config = SimpleNamespace(type=DatabaseType.POSTGRESQL, database="app")

    monkeypatch.setattr(
        visualization_tools.connection_manager,
        "get_connection_info",
        lambda connection_id: config,
    )

    def execute_query(connection_id, query, params=None):
        calls.append((query, params))
        if "information_schema.columns" in query:
            return [
                {
                    "column_name": "id",
                    "data_type": "bigint",
                    "column_type": "bigint",
                    "is_nullable": "NO",
                    "column_key": "",
                }
            ]
        return [
            {
                "constraint_name": "orders_user_id_fkey",
                "column_name": "user_id",
                "referenced_table_name": "users",
                "referenced_column_name": "id",
            }
        ]

    monkeypatch.setattr(visualization_tools.connection_manager, "execute_query", execute_query)

    columns = visualization_tools._query_columns(
        "pg-1", "app", "orders", DatabaseType.POSTGRESQL
    )
    foreign_keys = visualization_tools._query_foreign_keys(
        "pg-1", "app", "orders", DatabaseType.POSTGRESQL
    )

    assert columns == [{"name": "id", "type": "bigint", "is_primary": False}]
    assert foreign_keys == [
        {"column": "user_id", "to_table": "users", "to_column": "id"}
    ]
    assert len(calls) == 2
    assert all("SHOW TABLES" not in query for query, _ in calls)
