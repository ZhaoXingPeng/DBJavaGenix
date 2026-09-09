"""Regression tests for JSON-serializable MCP error envelopes."""

from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
import json
from types import SimpleNamespace
from uuid import UUID

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
async def test_query_execute_serializes_real_driver_value_types(monkeypatch):
    monkeypatch.setattr(
        mcp_tools.connection_manager,
        "execute_query",
        lambda *_args, **_kwargs: [
            {
                "amount": Decimal("12.30"),
                "created_at": datetime(2026, 9, 8, 10, 0, tzinfo=timezone.utc),
                "event_date": date(2026, 9, 8),
                "event_time": time(10, 0, 1, 234_000),
                "event_id": UUID("12345678-1234-5678-1234-567812345678"),
                "payload": b"\x00\xff",
                "mutable_payload": bytearray(b"ok"),
                "view_payload": memoryview(b"view"),
                "duration": timedelta(days=1, seconds=2),
            }
        ],
    )

    response = await mcp_tools.handle_db_query_execute(
        {"connection_id": "postgresql-1", "query": "SELECT * FROM events", "limit": 5}
    )

    payload = _raw_payload(response)
    assert payload == {
        "success": True,
        "query": "SELECT * FROM events LIMIT 5",
        "row_count": 1,
        "data": [
            {
                "amount": "12.30",
                "created_at": "2026-09-08T10:00:00+00:00",
                "event_date": "2026-09-08",
                "event_time": "10:00:01.234000",
                "event_id": "12345678-1234-5678-1234-567812345678",
                "payload": {"encoding": "base64", "data": "AP8="},
                "mutable_payload": {"encoding": "base64", "data": "b2s="},
                "view_payload": {"encoding": "base64", "data": "dmlldw=="},
                "duration": "1 day, 0:00:02",
            }
        ],
    }


@pytest.mark.asyncio
async def test_metadata_handlers_serialize_driver_value_types(monkeypatch):
    config = SimpleNamespace(type=DatabaseType.POSTGRESQL, database="app")

    class Introspector:
        def __init__(self, _manager):
            pass

        def get_config(self, _connection_id):
            return config

        def describe_table(self, _connection_id, _table, _schema):
            return {
                "name": "events",
                "schema": "public",
                "comment": datetime(2026, 9, 8, 10, 0, tzinfo=timezone.utc),
                "columns": [
                    {
                        "name": "amount",
                        "type": "numeric",
                        "column_type": "numeric(10,2)",
                        "nullable": False,
                        "default_value": Decimal("12.30"),
                        "comment": UUID("12345678-1234-5678-1234-567812345678"),
                        "primary_key": False,
                        "precision": 10,
                        "scale": 2,
                        "max_length": None,
                    }
                ],
            }

        def get_columns(self, _connection_id, _table, _schema):
            return [
                {
                    "name": "amount",
                    "type": "numeric",
                    "column_type": "numeric(10,2)",
                    "nullable": False,
                    "default_value": memoryview(b"view"),
                    "comment": "created",
                    "precision": 10,
                    "scale": 2,
                    "max_length": None,
                }
            ]

        def get_primary_keys(self, _connection_id, _table, _schema):
            return ["id"]

        def get_foreign_keys(self, _connection_id, _table, _schema):
            return [
                {
                    "column_name": "owner_id",
                    "referenced_table": "users",
                    "referenced_column": "id",
                    "constraint_name": "events_owner_fk",
                }
            ]

        def get_indexes(self, _connection_id, _table, _schema):
            return [
                {
                    "key_name": "events_amount_idx",
                    "column_name": "amount",
                    "seq_in_index": 1,
                    "unique": False,
                    "index_type": "btree",
                }
            ]

    monkeypatch.setattr(mcp_tools, "DatabaseIntrospector", Introspector)
    monkeypatch.setattr(
        mcp_tools.connection_manager,
        "get_connection_info",
        lambda _id: config,
    )
    common = {
        "connection_id": "pg-1",
        "database": "app",
        "table": "events",
        "schema": "public",
    }

    describe = await mcp_tools.handle_db_table_describe(common)
    columns = await mcp_tools.handle_db_table_columns(common)
    primary_keys = await mcp_tools.handle_db_table_primary_keys(common)
    foreign_keys = await mcp_tools.handle_db_table_foreign_keys(common)
    indexes = await mcp_tools.handle_db_table_indexes(common)

    assert _raw_payload(describe)["columns"][0]["default_value"] == "12.30"
    assert _raw_payload(describe)["comment"] == "2026-09-08T10:00:00+00:00"
    assert _raw_payload(columns)["columns"][0]["COLUMN_DEFAULT"] == {
        "encoding": "base64",
        "data": "dmlldw==",
    }
    assert _raw_payload(columns)["columns"][0]["COLUMN_COMMENT"] == "created"
    assert _raw_payload(primary_keys)["primary_keys"] == ["id"]
    assert _raw_payload(foreign_keys)["foreign_keys"][0]["references_table"] == "users"
    assert _raw_payload(indexes)["indexes"][0]["name"] == "events_amount_idx"


@pytest.mark.asyncio
async def test_codegen_analysis_raw_response_serializes_driver_values(monkeypatch):
    class Analyzer:
        def __init__(self, _manager):
            pass

        async def analyze_table_for_codegen(self, *_args, **_kwargs):
            return {
                "table_name": "events",
                "table_info": {
                    "name": "events",
                    "comment": "event table",
                    "columns": [
                        {
                            "name": "amount",
                            "type": "numeric",
                            "default_value": Decimal("12.30"),
                        }
                    ],
                },
                "template_context": {
                    "columns": [{"javaType": "BigDecimal"}],
                    "className": "Event",
                    "lowerCaseName": "event",
                    "hasDateField": False,
                    "hasBigDecimalField": True,
                    "primaryKey": "id",
                },
                "java_types": ["BigDecimal"],
                "imports_needed": [],
                "relationships": {"primary_keys": ["id"], "foreign_keys": [], "indexes": []},
            }

    monkeypatch.setattr("dbjavagenix.database.codegen_tools.CodegenAnalyzer", Analyzer)
    monkeypatch.setattr(
        mcp_tools.connection_manager,
        "get_connection_info",
        lambda _id: SimpleNamespace(type=DatabaseType.POSTGRESQL, database="app"),
    )

    response = await mcp_tools.handle_db_codegen_analyze(
        {"connection_id": "pg-1", "table_name": "events"}
    )

    assert _raw_payload(response)["table_info"]["columns"][0]["default_value"] == "12.30"


def test_query_result_json_default_rejects_unknown_object():
    class UnknownDriverValue:
        pass

    with pytest.raises(TypeError, match="UnknownDriverValue"):
        mcp_tools._query_result_json_default(UnknownDriverValue())


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
