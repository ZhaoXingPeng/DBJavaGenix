"""Integration test: PostgreSQL real-type → Java type mapping end-to-end.

Spins up PostgreSQL 16 via Testcontainers, creates a table with all the
PG-specific types our dialect adapter cares about (SERIAL / BIGSERIAL /
JSONB / UUID / BYTEA / TIMESTAMPTZ / NUMERIC ...), reads back what PG
reports through information_schema.columns, then verifies that
PostgreSQLDialect.java_type_for() produces the expected Java type for each.

Why this matters:
  - PG reports types in lowercase, sometimes with full names ("integer",
    "bigint", "timestamp with time zone", "character varying"). We need to
    confirm our dialect handles those exact strings, not just the abbreviated
    forms we hard-coded.
  - Catches regressions: if PG adds a new pg_type or renames one, this test
    fails before users hit it.

Skipped when Docker / testcontainers not available (see conftest).
"""

from __future__ import annotations

import pytest

from dbjavagenix.database.dialect import get_dialect


pytest.importorskip("psycopg2", reason="psycopg2 required to talk to PG")


CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS dialect_check (
    id              BIGSERIAL PRIMARY KEY,
    small_int_col   SMALLINT,
    int_col         INTEGER,
    big_int_col     BIGINT,
    serial_col      SERIAL,
    big_serial_col  BIGSERIAL,
    real_col        REAL,
    double_col      DOUBLE PRECISION,
    numeric_col     NUMERIC(10, 2),
    money_col       MONEY,
    varchar_col     VARCHAR(64),
    text_col        TEXT,
    char_col        CHAR(8),
    date_col        DATE,
    time_col        TIME,
    timestamp_col   TIMESTAMP,
    timestamptz_col TIMESTAMPTZ,
    bool_col        BOOLEAN,
    bytea_col       BYTEA,
    json_col        JSON,
    jsonb_col       JSONB,
    uuid_col        UUID,
    inet_col        INET
);
"""


# 期望表: PG information_schema.columns 上报的 data_type 字符串 → 期望的 Java 类型
# 这些字符串来自 PG 16,实测值;若 PG 升级有变化此处会失败,需要更新 dialect.py
EXPECTED_MAPPINGS = {
    # column_name: (expected_pg_data_type_uppercase, expected_java_type)
    "id": ("BIGINT", "Long"),
    "small_int_col": ("SMALLINT", "Short"),
    "int_col": ("INTEGER", "Integer"),
    "big_int_col": ("BIGINT", "Long"),
    "serial_col": ("INTEGER", "Integer"),
    "big_serial_col": ("BIGINT", "Long"),
    "real_col": ("REAL", "Float"),
    "double_col": ("DOUBLE PRECISION", "Double"),
    "numeric_col": ("NUMERIC", "BigDecimal"),
    "money_col": ("MONEY", "BigDecimal"),
    "varchar_col": ("CHARACTER VARYING", "String"),
    "text_col": ("TEXT", "String"),
    "char_col": ("CHARACTER", "String"),
    "date_col": ("DATE", "LocalDate"),
    "time_col": ("TIME WITHOUT TIME ZONE", "LocalTime"),
    "timestamp_col": ("TIMESTAMP WITHOUT TIME ZONE", "LocalDateTime"),
    "timestamptz_col": ("TIMESTAMP WITH TIME ZONE", "OffsetDateTime"),
    "bool_col": ("BOOLEAN", "Boolean"),
    "bytea_col": ("BYTEA", "byte[]"),
    "json_col": ("JSON", "String"),
    "jsonb_col": ("JSONB", "String"),
    "uuid_col": ("UUID", "String"),
    "inet_col": ("INET", "String"),
}


@pytest.fixture(scope="module")
def pg_connection(postgres_container):
    """psycopg2 connection to the container, with the test table created."""
    import psycopg2

    conn = psycopg2.connect(
        host=postgres_container["host"],
        port=postgres_container["port"],
        user=postgres_container["username"],
        password=postgres_container["password"],
        dbname=postgres_container["database"],
    )
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute(CREATE_TABLE_SQL)
    yield conn
    conn.close()


def _read_column_types(conn) -> dict[str, str]:
    """Return {column_name: data_type_uppercase} from information_schema."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = 'dialect_check'
            """
        )
        return {row[0]: row[1].upper() for row in cur.fetchall()}


def test_pg_reports_expected_data_types(pg_connection):
    """Sanity: PG 16 information_schema reports the data types we expect."""
    actual = _read_column_types(pg_connection)
    for col, (expected_pg_type, _) in EXPECTED_MAPPINGS.items():
        assert col in actual, f"column {col!r} missing from information_schema"
        assert actual[col] == expected_pg_type, (
            f"column {col!r}: PG reports {actual[col]!r}, expected {expected_pg_type!r}"
        )


def test_dialect_maps_pg_types_to_correct_java_types(pg_connection):
    """End-to-end: PG-reported type → PostgreSQLDialect → expected Java type."""
    actual = _read_column_types(pg_connection)
    dialect = get_dialect("postgresql")

    mismatches = []
    for col, (_, expected_java) in EXPECTED_MAPPINGS.items():
        pg_type = actual[col]
        java_type = dialect.java_type_for(pg_type)
        if java_type != expected_java:
            mismatches.append(f"  {col} ({pg_type}): got {java_type!r}, expected {expected_java!r}")

    assert not mismatches, "type mapping mismatches:\n" + "\n".join(mismatches)


def test_serial_columns_have_default_nextval(pg_connection):
    """Verify SERIAL/BIGSERIAL columns get the standard sequence default —
    relevant for future codegen support of auto-increment annotations.
    """
    with pg_connection.cursor() as cur:
        cur.execute(
            """
            SELECT column_name, column_default
            FROM information_schema.columns
            WHERE table_name = 'dialect_check'
              AND column_name IN ('serial_col', 'big_serial_col', 'id')
            """
        )
        rows = dict(cur.fetchall())

    for col in ("serial_col", "big_serial_col", "id"):
        default = rows.get(col, "")
        assert default and "nextval" in default, (
            f"{col} expected to have nextval default, got {default!r}"
        )
