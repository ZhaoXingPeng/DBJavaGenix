"""Unit tests for database.dialect."""

import pytest

from dbjavagenix.database.dialect import (
    DialectAdapter,
    MySQLDialect,
    PostgreSQLDialect,
    _strip_paren,
    get_dialect,
    list_supported_dialects,
)


class TestStripParen:
    def test_simple(self):
        assert _strip_paren("VARCHAR(64)") == "VARCHAR"

    def test_no_paren(self):
        assert _strip_paren("BIGINT") == "BIGINT"

    def test_double_args(self):
        assert _strip_paren("DECIMAL(10,2)") == "DECIMAL"

    def test_lowercases_then_upper(self):
        assert _strip_paren("varchar(10)") == "VARCHAR"


class TestRegistry:
    def test_known_dialects(self):
        assert "mysql" in list_supported_dialects()
        assert "postgresql" in list_supported_dialects()

    def test_get_mysql(self):
        assert isinstance(get_dialect("mysql"), MySQLDialect)

    def test_get_postgresql(self):
        assert isinstance(get_dialect("postgresql"), PostgreSQLDialect)

    def test_get_case_insensitive(self):
        assert isinstance(get_dialect("MySQL"), MySQLDialect)
        assert isinstance(get_dialect("PostgreSQL"), PostgreSQLDialect)

    def test_unknown_falls_back_to_mysql(self):
        # 向后兼容承诺
        assert isinstance(get_dialect("nonexistent"), MySQLDialect)


class TestMySQLDialect:
    def setup_method(self):
        self.d = MySQLDialect()

    def test_basic_integers(self):
        assert self.d.java_type_for("INT") == "Integer"
        assert self.d.java_type_for("BIGINT") == "Long"
        assert self.d.java_type_for("SMALLINT") == "Short"
        assert self.d.java_type_for("TINYINT") == "Byte"

    def test_tinyint_one_is_boolean(self):
        # MySQL 经典布尔约定
        assert self.d.java_type_for("TINYINT(1)") == "Boolean"

    def test_varchar_with_length(self):
        assert self.d.java_type_for("VARCHAR(64)") == "String"
        assert self.d.java_type_for("VARCHAR(255)") == "String"

    def test_datetime_family(self):
        assert self.d.java_type_for("DATETIME") == "LocalDateTime"
        assert self.d.java_type_for("TIMESTAMP") == "LocalDateTime"
        assert self.d.java_type_for("DATE") == "LocalDate"
        assert self.d.java_type_for("TIME") == "LocalTime"

    def test_decimal(self):
        assert self.d.java_type_for("DECIMAL(10,2)") == "BigDecimal"
        assert self.d.java_type_for("NUMERIC") == "BigDecimal"

    def test_blob_to_bytes(self):
        assert self.d.java_type_for("BLOB") == "byte[]"
        assert self.d.java_type_for("LONGBLOB") == "byte[]"

    def test_unknown_falls_back_to_string(self):
        assert self.d.java_type_for("WEIRD_CUSTOM_TYPE") == "String"

    def test_jdbc_type(self):
        assert self.d.jdbc_type_for("VARCHAR(64)") == "VARCHAR"
        assert self.d.jdbc_type_for("TEXT") == "LONGVARCHAR"
        assert self.d.jdbc_type_for("BIGINT") == "BIGINT"

    def test_is_string_type(self):
        assert self.d.is_string_type("VARCHAR(255)")
        assert self.d.is_string_type("TEXT")
        assert not self.d.is_string_type("INT")

    def test_is_date_type(self):
        assert self.d.is_date_type("DATETIME")
        assert not self.d.is_date_type("VARCHAR")

    def test_is_decimal_type(self):
        assert self.d.is_decimal_type("DECIMAL")
        assert not self.d.is_decimal_type("INT")


class TestPostgreSQLDialect:
    def setup_method(self):
        self.d = PostgreSQLDialect()

    def test_pg_integer_aliases(self):
        assert self.d.java_type_for("INT2") == "Short"
        assert self.d.java_type_for("INT4") == "Integer"
        assert self.d.java_type_for("INT8") == "Long"
        assert self.d.java_type_for("SMALLINT") == "Short"
        assert self.d.java_type_for("INTEGER") == "Integer"
        assert self.d.java_type_for("BIGINT") == "Long"

    def test_serial_family(self):
        assert self.d.java_type_for("SERIAL") == "Integer"
        assert self.d.java_type_for("BIGSERIAL") == "Long"
        assert self.d.java_type_for("SMALLSERIAL") == "Short"

    def test_native_boolean(self):
        # PG 不需要 TINYINT(1) hack
        assert self.d.java_type_for("BOOLEAN") == "Boolean"
        assert self.d.java_type_for("BOOL") == "Boolean"

    def test_double_precision(self):
        assert self.d.java_type_for("DOUBLE PRECISION") == "Double"
        assert self.d.java_type_for("FLOAT8") == "Double"
        assert self.d.java_type_for("REAL") == "Float"

    def test_timestamptz_to_offsetdatetime(self):
        # 跨时区场景必须保留时区
        assert self.d.java_type_for("TIMESTAMPTZ") == "OffsetDateTime"
        assert self.d.java_type_for("TIMESTAMP WITH TIME ZONE") == "OffsetDateTime"
        # 普通 TIMESTAMP 仍是 LocalDateTime
        assert self.d.java_type_for("TIMESTAMP") == "LocalDateTime"

    def test_information_schema_temporal_names(self):
        assert self.d.java_type_for("TIME WITHOUT TIME ZONE") == "LocalTime"
        assert self.d.java_type_for("TIMESTAMP WITHOUT TIME ZONE") == "LocalDateTime"
        assert self.d.jdbc_type_for("TIME WITHOUT TIME ZONE") == "TIME"
        assert self.d.jdbc_type_for("TIMESTAMP WITHOUT TIME ZONE") == "TIMESTAMP"

    def test_bytea(self):
        assert self.d.java_type_for("BYTEA") == "byte[]"

    def test_json_and_jsonb(self):
        assert self.d.java_type_for("JSON") == "String"
        assert self.d.java_type_for("JSONB") == "String"

    def test_uuid(self):
        assert self.d.java_type_for("UUID") == "String"

    def test_character_varying_alias(self):
        # PG 官方全名是 CHARACTER VARYING,VARCHAR 是别名
        assert self.d.java_type_for("CHARACTER VARYING") == "String"
        assert self.d.java_type_for("VARCHAR") == "String"

    def test_money(self):
        assert self.d.java_type_for("MONEY") == "BigDecimal"

    def test_jdbc_for_special_types(self):
        # PG 特有类型 JDBC 字符串
        assert self.d.jdbc_type_for("JSONB") == "OTHER"
        assert self.d.jdbc_type_for("UUID") == "OTHER"
        assert self.d.jdbc_type_for("INET") == "OTHER"
        assert self.d.jdbc_type_for("TIMESTAMPTZ") == "TIMESTAMP_WITH_TIMEZONE"

    def test_unknown_falls_back_to_string(self):
        assert self.d.java_type_for("WEIRD_PG_TYPE") == "String"


class TestCrossDialectIsolation:
    """确认两个方言的差异处不会互相串。"""

    def test_postgres_doesnt_have_tinyint(self):
        # PG 没有 TINYINT,fallback 到 String
        assert PostgreSQLDialect().java_type_for("TINYINT") == "String"

    def test_mysql_doesnt_have_bytea(self):
        # MySQL 没有 BYTEA,fallback
        assert MySQLDialect().java_type_for("BYTEA") == "String"

    def test_mysql_tinyint_one_boolean_not_in_postgres(self):
        # PG 不该把 TINYINT(1) 当 Boolean (它根本没 TINYINT)
        assert PostgreSQLDialect().java_type_for("TINYINT(1)") == "String"


class TestAbstractBase:
    def test_cannot_instantiate_abstract(self):
        with pytest.raises(TypeError):
            DialectAdapter()  # type: ignore
