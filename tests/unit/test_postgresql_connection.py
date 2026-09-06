"""Unit coverage for the PostgreSQL connection path without a live database."""

import sys
import types

import pytest

from dbjavagenix.core.exceptions import DatabaseConnectionError
from dbjavagenix.core.models import DatabaseConfig, DatabaseType
from dbjavagenix.database.connection_manager import ConnectionManager


class FakePostgresConnection:
    def __init__(self):
        self.autocommit = False
        self.closed = 0

    def close(self):
        self.closed = 1

    def cursor(self):
        raise AssertionError("cursor should not be needed for this unit test")


@pytest.fixture
def postgres_config():
    return DatabaseConfig(
        type=DatabaseType.POSTGRESQL,
        host="db.example",
        port=5432,
        database="app",
        username="reader",
        password="secret",
    )


def test_create_postgresql_connection_uses_psycopg2(monkeypatch, postgres_config):
    calls = []
    connection = FakePostgresConnection()

    def connect(**kwargs):
        calls.append(kwargs)
        return connection

    monkeypatch.setitem(sys.modules, "psycopg2", types.SimpleNamespace(connect=connect))

    manager = ConnectionManager()
    connection_id = manager.create_connection(postgres_config)

    assert connection_id in manager.connections
    assert connection.autocommit is True
    assert calls == [
        {
            "host": "db.example",
            "port": 5432,
            "user": "reader",
            "password": "secret",
            "dbname": "app",
            "connect_timeout": 10,
        }
    ]
    manager.close_connection(connection_id)


def test_connection_info_returns_a_safe_copy(monkeypatch, postgres_config):
    connection = FakePostgresConnection()
    monkeypatch.setitem(
        sys.modules,
        "psycopg2",
        types.SimpleNamespace(connect=lambda **kwargs: connection),
    )

    manager = ConnectionManager()
    connection_id = manager.create_connection(postgres_config)
    returned = manager.get_connection_info(connection_id)
    assert returned is not None
    assert returned.password == "***"

    returned.password = "changed"
    assert manager.get_connection_info(connection_id).password == "***"
    manager.close_connection(connection_id)


def test_closed_postgresql_connection_is_removed(monkeypatch, postgres_config):
    connection = FakePostgresConnection()
    monkeypatch.setitem(
        sys.modules,
        "psycopg2",
        types.SimpleNamespace(connect=lambda **kwargs: connection),
    )

    manager = ConnectionManager()
    connection_id = manager.create_connection(postgres_config)
    connection.closed = 1

    with pytest.raises(DatabaseConnectionError, match="no longer valid"):
        manager.get_connection(connection_id)

    assert connection_id not in manager.connections
    assert connection_id not in manager.connection_configs
