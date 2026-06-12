"""
P9.2: Database dialect adapters.

为何独立成模块:
  - v0.1 ~ v0.2 时期 SQL→Java 类型映射散落在 template_context.py 里,只考虑 MySQL
  - PostgreSQL 引入后,差异点:
      * 整数: INT2/INT4/INT8 vs MySQL 的 INT/BIGINT
      * 序列: SERIAL/BIGSERIAL (PG 自增惯例,无 AUTO_INCREMENT 关键字)
      * 布尔: PG 原生 BOOLEAN, MySQL 用 TINYINT(1) 模拟
      * 二进制: BYTEA vs BLOB 系列
      * JSON: JSON + JSONB (两种,PG 推荐 JSONB)
      * UUID: PG 原生 UUID, MySQL 没有 → CHAR(36) 存
      * 时区: TIMESTAMPTZ → OffsetDateTime,普通 TIMESTAMP → LocalDateTime
  - 把方言策略和模板上下文剥离开,后续要加 Oracle / SQLServer 时加一个 adapter 就行

调用方:
  - template_context.py (TODO 下个迭代切过去,保持向后兼容)
  - codegen_tools.py / atomic_codegen_tools.py
  - 集成测试 (PostgreSQL Testcontainers 跑出来的类型也用同一套映射)
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from typing import Dict


_PAREN_PATTERN = re.compile(r"\([^)]*\)")


def _strip_paren(db_type: str) -> str:
    """剥离 `VARCHAR(64)` 这种带长度的括号部分,统一小写无空格。"""
    return _PAREN_PATTERN.sub("", db_type.upper()).strip()


# ============================================================
# 基类
# ============================================================


class DialectAdapter(ABC):
    """方言适配器基类。每个 DB 厂家一个子类。"""

    name: str = "abstract"

    @property
    @abstractmethod
    def type_to_java(self) -> Dict[str, str]:
        """SQL base type → Java type. base type 已 strip 括号。"""

    @property
    @abstractmethod
    def type_to_jdbc(self) -> Dict[str, str]:
        """SQL base type → JDBC type 字符串 (用于 MyBatis Plus jdbcType)。"""

    @property
    def string_types(self) -> set[str]:
        """该方言下视为 String 的类型集合 (base type)。"""
        return {k for k, v in self.type_to_java.items() if v == "String"}

    @property
    def date_types(self) -> set[str]:
        """日期/时间类型 (用于决定是否 import LocalDate 等)。"""
        return {
            k
            for k, v in self.type_to_java.items()
            if v in {"LocalDate", "LocalTime", "LocalDateTime", "OffsetDateTime", "Instant"}
        }

    @property
    def decimal_types(self) -> set[str]:
        return {k for k, v in self.type_to_java.items() if v == "BigDecimal"}

    def java_type_for(self, db_type: str) -> str:
        """主入口: 给一个数据库声明类型,返回 Java 类型 (找不到默认 String)。"""
        base = _strip_paren(db_type)
        # TINYINT(1) 是 MySQL 布尔约定 — 单独判
        if db_type.upper().replace(" ", "") == "TINYINT(1)":
            return self.type_to_java.get("TINYINT(1)", self.type_to_java.get(base, "String"))
        return self.type_to_java.get(base, "String")

    def jdbc_type_for(self, db_type: str) -> str:
        base = _strip_paren(db_type)
        return self.type_to_jdbc.get(base, "VARCHAR")

    def is_string_type(self, db_type: str) -> bool:
        return _strip_paren(db_type) in self.string_types

    def is_date_type(self, db_type: str) -> bool:
        return _strip_paren(db_type) in self.date_types

    def is_decimal_type(self, db_type: str) -> bool:
        return _strip_paren(db_type) in self.decimal_types


# ============================================================
# MySQL (从 template_context.py 抽出来的现有逻辑)
# ============================================================


class MySQLDialect(DialectAdapter):
    name = "mysql"

    @property
    def type_to_java(self) -> Dict[str, str]:
        return {
            # 整数
            "TINYINT": "Byte",
            "TINYINT(1)": "Boolean",  # 经典 MySQL 布尔约定
            "SMALLINT": "Short",
            "MEDIUMINT": "Integer",
            "INT": "Integer",
            "INTEGER": "Integer",
            "BIGINT": "Long",
            # 浮点
            "FLOAT": "Float",
            "DOUBLE": "Double",
            "DECIMAL": "BigDecimal",
            "NUMERIC": "BigDecimal",
            # 字符串
            "CHAR": "String",
            "VARCHAR": "String",
            "TEXT": "String",
            "LONGTEXT": "String",
            "MEDIUMTEXT": "String",
            "TINYTEXT": "String",
            "NCHAR": "String",
            "NVARCHAR": "String",
            "ENUM": "String",
            "SET": "String",
            # 日期
            "DATE": "LocalDate",
            "TIME": "LocalTime",
            "DATETIME": "LocalDateTime",
            "TIMESTAMP": "LocalDateTime",
            "YEAR": "Integer",
            # 布尔
            "BOOLEAN": "Boolean",
            "BOOL": "Boolean",
            # 二进制
            "BINARY": "byte[]",
            "VARBINARY": "byte[]",
            "BLOB": "byte[]",
            "LONGBLOB": "byte[]",
            "MEDIUMBLOB": "byte[]",
            "TINYBLOB": "byte[]",
            # JSON
            "JSON": "String",
        }

    @property
    def type_to_jdbc(self) -> Dict[str, str]:
        return {
            "TINYINT": "TINYINT",
            "SMALLINT": "SMALLINT",
            "MEDIUMINT": "INTEGER",
            "INT": "INTEGER",
            "INTEGER": "INTEGER",
            "BIGINT": "BIGINT",
            "FLOAT": "FLOAT",
            "DOUBLE": "DOUBLE",
            "DECIMAL": "DECIMAL",
            "NUMERIC": "NUMERIC",
            "CHAR": "CHAR",
            "VARCHAR": "VARCHAR",
            "TEXT": "LONGVARCHAR",
            "LONGTEXT": "LONGVARCHAR",
            "MEDIUMTEXT": "LONGVARCHAR",
            "TINYTEXT": "VARCHAR",
            "NCHAR": "NCHAR",
            "NVARCHAR": "NVARCHAR",
            "DATE": "DATE",
            "TIME": "TIME",
            "DATETIME": "TIMESTAMP",
            "TIMESTAMP": "TIMESTAMP",
            "BOOLEAN": "BOOLEAN",
            "TINYINT(1)": "BOOLEAN",
            "BLOB": "BLOB",
            "JSON": "LONGVARCHAR",
        }


# ============================================================
# PostgreSQL
# ============================================================


class PostgreSQLDialect(DialectAdapter):
    """PostgreSQL 12+ 方言。

    主要差异 vs MySQL:
      - 整数族用 INT2/INT4/INT8 (官方别名 SMALLINT/INTEGER/BIGINT 也支持)
      - SERIAL/BIGSERIAL: 自增列,JDBC 端按 Integer/Long 处理
      - BOOLEAN 原生支持 (不需要 TINYINT(1) hack)
      - BYTEA 替代 BLOB
      - JSONB 推荐 (二进制 JSON,带索引能力);JSON 也保留
      - UUID 原生支持
      - TIMESTAMPTZ → OffsetDateTime (跨时区场景必须保留时区)
      - "CHARACTER VARYING" 是 VARCHAR 的官方全名
    """

    name = "postgresql"

    @property
    def type_to_java(self) -> Dict[str, str]:
        return {
            # 整数
            "INT2": "Short",
            "SMALLINT": "Short",
            "INT4": "Integer",
            "INT": "Integer",
            "INTEGER": "Integer",
            "INT8": "Long",
            "BIGINT": "Long",
            # SERIAL 系列 (PG 自增惯例) - JDBC 上和普通整数一致
            "SMALLSERIAL": "Short",
            "SERIAL": "Integer",
            "BIGSERIAL": "Long",
            # 浮点
            "REAL": "Float",
            "FLOAT4": "Float",
            "DOUBLE PRECISION": "Double",
            "FLOAT8": "Double",
            "NUMERIC": "BigDecimal",
            "DECIMAL": "BigDecimal",
            "MONEY": "BigDecimal",
            # 字符串
            "CHAR": "String",
            "CHARACTER": "String",
            "VARCHAR": "String",
            "CHARACTER VARYING": "String",
            "TEXT": "String",
            "BPCHAR": "String",  # internal name for CHAR
            # 日期
            "DATE": "LocalDate",
            "TIME": "LocalTime",
            "TIMETZ": "OffsetTime",
            "TIMESTAMP": "LocalDateTime",
            "TIMESTAMPTZ": "OffsetDateTime",  # 跨时区必须 OffsetDateTime
            "TIMESTAMP WITH TIME ZONE": "OffsetDateTime",
            # 布尔
            "BOOL": "Boolean",
            "BOOLEAN": "Boolean",
            # 二进制
            "BYTEA": "byte[]",
            # JSON
            "JSON": "String",
            "JSONB": "String",
            # UUID
            "UUID": "String",
            # 网络
            "INET": "String",
            "CIDR": "String",
            # 数组占位 — Java 端建议 String,具体由模板决定
            "ARRAY": "String",
        }

    @property
    def type_to_jdbc(self) -> Dict[str, str]:
        return {
            "INT2": "SMALLINT",
            "SMALLINT": "SMALLINT",
            "INT4": "INTEGER",
            "INT": "INTEGER",
            "INTEGER": "INTEGER",
            "INT8": "BIGINT",
            "BIGINT": "BIGINT",
            "SMALLSERIAL": "SMALLINT",
            "SERIAL": "INTEGER",
            "BIGSERIAL": "BIGINT",
            "REAL": "REAL",
            "FLOAT4": "REAL",
            "DOUBLE PRECISION": "DOUBLE",
            "FLOAT8": "DOUBLE",
            "NUMERIC": "NUMERIC",
            "DECIMAL": "DECIMAL",
            "MONEY": "DECIMAL",
            "CHAR": "CHAR",
            "CHARACTER": "CHAR",
            "BPCHAR": "CHAR",
            "VARCHAR": "VARCHAR",
            "CHARACTER VARYING": "VARCHAR",
            "TEXT": "LONGVARCHAR",
            "DATE": "DATE",
            "TIME": "TIME",
            "TIMETZ": "TIME_WITH_TIMEZONE",
            "TIMESTAMP": "TIMESTAMP",
            "TIMESTAMPTZ": "TIMESTAMP_WITH_TIMEZONE",
            "TIMESTAMP WITH TIME ZONE": "TIMESTAMP_WITH_TIMEZONE",
            "BOOL": "BOOLEAN",
            "BOOLEAN": "BOOLEAN",
            "BYTEA": "BINARY",
            "JSON": "OTHER",
            "JSONB": "OTHER",
            "UUID": "OTHER",
            "INET": "OTHER",
            "CIDR": "OTHER",
        }


# ============================================================
# Registry
# ============================================================


_REGISTRY: Dict[str, DialectAdapter] = {
    "mysql": MySQLDialect(),
    "postgresql": PostgreSQLDialect(),
}


def get_dialect(db_type: str) -> DialectAdapter:
    """根据 DatabaseType 字符串 (mysql / postgresql / ...) 取适配器。

    未识别的 db_type 退回 MySQL — 保持向后兼容,避免老调用方崩。
    """
    return _REGISTRY.get(db_type.lower(), _REGISTRY["mysql"])


def list_supported_dialects() -> list[str]:
    return sorted(_REGISTRY.keys())
