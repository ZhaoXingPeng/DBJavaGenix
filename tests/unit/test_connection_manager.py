"""单元测试: database.connection_manager.ConnectionManager

使用 SQLite in-memory(`:memory:`)避免外部依赖。MySQL 路径留给集成测试。
"""

import pytest

from dbjavagenix.core.exceptions import DatabaseConnectionError, DatabaseQueryError
from dbjavagenix.core.models import DatabaseConfig, DatabaseType
from dbjavagenix.database.connection_manager import ConnectionManager


@pytest.fixture
def sqlite_config():
    return DatabaseConfig(
        type=DatabaseType.SQLITE,
        host="",
        port=0,
        database=":memory:",
        username="",
        password="secret-token",
    )


@pytest.fixture
def manager_with_conn(sqlite_config):
    mgr = ConnectionManager()
    cid = mgr.create_connection(sqlite_config)
    yield mgr, cid
    mgr.close_connection(cid)


class TestCreateConnection:
    def test_sqlite_in_memory(self, sqlite_config):
        mgr = ConnectionManager()
        cid = mgr.create_connection(sqlite_config)
        assert cid
        assert cid in mgr.connections
        assert cid in mgr.connection_configs
        mgr.close_connection(cid)

    def test_password_is_masked_in_stored_config(self, sqlite_config):
        mgr = ConnectionManager()
        cid = mgr.create_connection(sqlite_config)
        stored = mgr.get_connection_info(cid)
        assert stored is not None
        assert stored.password == "***"  # 脱敏
        # 原对象保持不变
        assert sqlite_config.password == "secret-token"
        mgr.close_connection(cid)

    def test_unsupported_type_raises(self):
        mgr = ConnectionManager()
        # PostgreSQL 没在 connection_manager 中实现,应抛 DatabaseConnectionError
        cfg = DatabaseConfig(
            type=DatabaseType.POSTGRESQL,
            host="localhost",
            port=5432,
            database="x",
            username="u",
            password="p",
        )
        with pytest.raises(DatabaseConnectionError):
            mgr.create_connection(cfg)


class TestGetConnection:
    def test_existing(self, manager_with_conn):
        mgr, cid = manager_with_conn
        conn = mgr.get_connection(cid)
        assert conn is not None

    def test_missing_raises(self):
        mgr = ConnectionManager()
        with pytest.raises(DatabaseConnectionError):
            mgr.get_connection("no-such-id")


class TestCloseConnection:
    def test_close_existing_returns_true(self, sqlite_config):
        mgr = ConnectionManager()
        cid = mgr.create_connection(sqlite_config)
        assert mgr.close_connection(cid) is True
        assert cid not in mgr.connections

    def test_close_missing_returns_false(self):
        mgr = ConnectionManager()
        assert mgr.close_connection("nope") is False


class TestMetadataCache:
    def test_cache_returns_copies_and_evicts_oldest_entry(self):
        mgr = ConnectionManager()
        payload = {"columns": [{"name": "id"}]}

        for index in range(257):
            mgr.cache_metadata("connection", f"table_{index}", None, payload)

        assert mgr.metadata_cache_size() == 256
        assert mgr.get_cached_metadata("connection", "table_0") is None
        cached = mgr.get_cached_metadata("connection", "table_1")
        assert cached == payload
        cached["columns"].clear()
        assert mgr.get_cached_metadata("connection", "table_1") == payload

    def test_invalidate_cache_is_connection_scoped(self):
        mgr = ConnectionManager()
        mgr.cache_metadata("connection-a", "users", None, {})
        mgr.cache_metadata("connection-b", "users", None, {})

        mgr.invalidate_metadata_cache("connection-a")

        assert mgr.get_cached_metadata("connection-a", "users") is None
        assert mgr.get_cached_metadata("connection-b", "users") == {}


class TestListConnections:
    def test_lists_active(self, sqlite_config):
        mgr = ConnectionManager()
        cid = mgr.create_connection(sqlite_config)
        listing = mgr.list_connections()
        assert cid in listing
        assert listing[cid]["status"] == "active"
        assert listing[cid]["type"] == DatabaseType.SQLITE
        mgr.close_connection(cid)

    def test_empty_when_no_conns(self):
        mgr = ConnectionManager()
        assert mgr.list_connections() == {}


class TestExecuteQuery:
    def test_create_table_and_insert_select(self, manager_with_conn):
        mgr, cid = manager_with_conn
        # 写 DDL/DML 不返回行
        mgr.execute_query(cid, "CREATE TABLE t (id INTEGER PRIMARY KEY, name TEXT)")
        mgr.execute_query(cid, "INSERT INTO t (id, name) VALUES (1, 'alice')")
        mgr.execute_query(cid, "INSERT INTO t (id, name) VALUES (2, 'bob')")
        rows = mgr.execute_query(cid, "SELECT id, name FROM t ORDER BY id")
        assert len(rows) == 2
        assert rows[0]["name"] == "alice"
        assert rows[1]["id"] == 2

    def test_query_with_params(self, manager_with_conn):
        mgr, cid = manager_with_conn
        mgr.execute_query(cid, "CREATE TABLE u (id INTEGER, score REAL)")
        mgr.execute_query(cid, "INSERT INTO u VALUES (?, ?)", (1, 9.5))
        rows = mgr.execute_query(cid, "SELECT * FROM u WHERE id = ?", (1,))
        assert len(rows) == 1
        assert rows[0]["score"] == 9.5

    def test_bad_sql_raises(self, manager_with_conn):
        mgr, cid = manager_with_conn
        with pytest.raises(DatabaseQueryError):
            mgr.execute_query(cid, "INVALID SQL STATEMENT")
        # A statement error must not evict an otherwise healthy connection.
        assert cid in mgr.connections

    def test_failed_sql_rolls_back_pending_sqlite_transaction(self, manager_with_conn):
        mgr, cid = manager_with_conn
        mgr.execute_query(cid, "CREATE TABLE pending (id INTEGER PRIMARY KEY, value TEXT)")

        # Simulate a caller-owned transaction started on the same connection.
        connection = mgr.get_connection(cid)
        connection.execute("INSERT INTO pending (id, value) VALUES (1, 'uncommitted')")

        with pytest.raises(DatabaseQueryError):
            mgr.execute_query(cid, "INVALID SQL STATEMENT")

        assert mgr.execute_query(cid, "SELECT * FROM pending") == []

    def test_empty_result_table(self, manager_with_conn):
        mgr, cid = manager_with_conn
        mgr.execute_query(cid, "CREATE TABLE e (x INT)")
        rows = mgr.execute_query(cid, "SELECT * FROM e")
        assert rows == []

    def test_sqlite_file_writes_survive_connection_reopen(self, tmp_path):
        database = tmp_path / "persisted.db"
        config = DatabaseConfig(
            type=DatabaseType.SQLITE,
            host="",
            port=0,
            database=str(database),
            username="",
            password="",
        )

        first = ConnectionManager()
        first_id = first.create_connection(config)
        first.execute_query(first_id, "CREATE TABLE items (id INTEGER PRIMARY KEY, name TEXT)")
        first.execute_query(first_id, "INSERT INTO items (id, name) VALUES (?, ?)", (1, "saved"))
        first.close_connection(first_id)

        second = ConnectionManager()
        second_id = second.create_connection(config)
        try:
            assert second.execute_query(second_id, "SELECT name FROM items") == [{"name": "saved"}]
        finally:
            second.close_connection(second_id)

    def test_sqlite_returning_write_is_committed(self, tmp_path):
        database = tmp_path / "returning.db"
        config = DatabaseConfig(
            type=DatabaseType.SQLITE,
            host="",
            port=0,
            database=str(database),
            username="",
            password="",
        )
        manager = ConnectionManager()
        connection_id = manager.create_connection(config)
        try:
            manager.execute_query(connection_id, "CREATE TABLE items (id INTEGER PRIMARY KEY)")
            assert manager.execute_query(
                connection_id, "INSERT INTO items DEFAULT VALUES RETURNING id"
            ) == [{"id": 1}]
        finally:
            manager.close_connection(connection_id)

        reopened = ConnectionManager()
        reopened_id = reopened.create_connection(config)
        try:
            assert reopened.execute_query(reopened_id, "SELECT id FROM items") == [{"id": 1}]
        finally:
            reopened.close_connection(reopened_id)


class TestGetCursor:
    def test_context_manager_yields_cursor(self, manager_with_conn):
        mgr, cid = manager_with_conn
        with mgr.get_cursor(cid) as cur:
            cur.execute("SELECT 1")
            row = cur.fetchone()
            # SQLite Row 支持 indexing
            assert row[0] == 1
