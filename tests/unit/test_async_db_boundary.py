"""Regression tests for the async MCP/database boundary."""

import asyncio
import threading
import time

import pytest

from dbjavagenix.core.models import DatabaseConfig, DatabaseType
from dbjavagenix.database.connection_manager import ConnectionManager
from dbjavagenix.database import mcp_tools


@pytest.fixture
def sqlite_config():
    return DatabaseConfig(
        type=DatabaseType.SQLITE,
        host="",
        port=0,
        database=":memory:",
        username="",
        password="",
    )


class _BlockingCursor:
    description = None

    def __init__(self, state):
        self.state = state

    def execute(self, _query, _params=()):
        with self.state["lock"]:
            self.state["active"] += 1
            self.state["max_active"] = max(self.state["max_active"], self.state["active"])
        self.state["entered"].set()
        self.state["release"].wait(timeout=2)
        with self.state["lock"]:
            self.state["active"] -= 1

    def close(self):
        self.state["closed_cursors"] += 1


class _BlockingConnection:
    closed = 0

    def __init__(self, state):
        self.state = state
        self.closed_event = threading.Event()

    def cursor(self):
        return _BlockingCursor(self.state)

    def close(self):
        self.closed = 1
        self.closed_event.set()


def _state():
    return {
        "lock": threading.Lock(),
        "active": 0,
        "max_active": 0,
        "entered": threading.Event(),
        "release": threading.Event(),
        "closed_cursors": 0,
    }


def _manager_with_fake_connection(config, state):
    manager = ConnectionManager()
    connection_id = manager.create_connection(config)
    manager.connections[connection_id] = _BlockingConnection(state)
    return manager, connection_id


@pytest.mark.asyncio
async def test_mcp_query_keeps_event_loop_running_during_blocking_driver(monkeypatch):
    started = threading.Event()

    def blocking_execute(connection_id, query):
        assert connection_id == "db-1"
        assert query.endswith("LIMIT 100")
        started.set()
        time.sleep(0.06)
        return []

    monkeypatch.setattr(mcp_tools.connection_manager, "execute_query", blocking_execute)

    ticks = 0

    async def heartbeat():
        nonlocal ticks
        deadline = asyncio.get_running_loop().time() + 0.04
        while asyncio.get_running_loop().time() < deadline:
            ticks += 1
            await asyncio.sleep(0.002)

    await asyncio.gather(
        mcp_tools.handle_db_query_execute({"connection_id": "db-1", "query": "SELECT 1"}),
        heartbeat(),
    )

    assert started.is_set()
    assert ticks >= 2


@pytest.mark.asyncio
async def test_sqlite_connection_can_be_used_by_worker_thread(sqlite_config):
    manager = ConnectionManager()
    connection_id = manager.create_connection(sqlite_config)
    try:
        rows = await asyncio.to_thread(manager.execute_query, connection_id, "SELECT 1 AS value")
        assert rows == [{"value": 1}]
    finally:
        manager.close_connection(connection_id)


@pytest.mark.asyncio
async def test_same_connection_queries_are_serialized(sqlite_config):
    first_state = _state()
    manager, connection_id = _manager_with_fake_connection(sqlite_config, first_state)

    first = asyncio.create_task(asyncio.to_thread(manager.execute_query, connection_id, "SELECT 1"))
    assert await asyncio.to_thread(first_state["entered"].wait, 1)
    second = asyncio.create_task(
        asyncio.to_thread(manager.execute_query, connection_id, "SELECT 2")
    )
    await asyncio.sleep(0.02)
    assert first_state["max_active"] == 1

    first_state["release"].set()
    await asyncio.gather(first, second)
    assert first_state["closed_cursors"] == 2
    manager.close_connection(connection_id)


@pytest.mark.asyncio
async def test_different_connections_can_execute_in_parallel(sqlite_config):
    first_state = _state()
    second_state = _state()
    manager, first_id = _manager_with_fake_connection(sqlite_config, first_state)
    second_id = manager.create_connection(sqlite_config)
    manager.connections[second_id] = _BlockingConnection(second_state)

    first = asyncio.create_task(asyncio.to_thread(manager.execute_query, first_id, "SELECT 1"))
    second = asyncio.create_task(asyncio.to_thread(manager.execute_query, second_id, "SELECT 2"))
    await asyncio.wait_for(
        asyncio.gather(
            asyncio.to_thread(first_state["entered"].wait, 1),
            asyncio.to_thread(second_state["entered"].wait, 1),
        ),
        timeout=1,
    )
    assert first_state["max_active"] == second_state["max_active"] == 1

    first_state["release"].set()
    second_state["release"].set()
    await asyncio.gather(first, second)
    manager.close_connection(first_id)
    manager.close_connection(second_id)


@pytest.mark.asyncio
async def test_close_waits_for_query_and_cleans_connection(sqlite_config):
    state = _state()
    manager, connection_id = _manager_with_fake_connection(sqlite_config, state)

    query = asyncio.create_task(asyncio.to_thread(manager.execute_query, connection_id, "SELECT 1"))
    assert await asyncio.to_thread(state["entered"].wait, 1)
    close = asyncio.create_task(asyncio.to_thread(manager.close_connection, connection_id))
    await asyncio.sleep(0.02)
    assert not close.done()

    state["release"].set()
    result, closed = await asyncio.gather(query, close)
    assert result == []
    assert closed is True
    assert connection_id not in manager.connections
    assert connection_id not in manager.connection_configs
    assert connection_id not in manager._connection_locks
    assert state["closed_cursors"] == 1
