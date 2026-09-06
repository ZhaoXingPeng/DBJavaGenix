"""Database metadata access shared by code generation and MCP tools.

The public methods return database-neutral dictionaries.  Dialect-specific SQL
stays in this module so callers do not need to branch on vendor details.
"""

from __future__ import annotations

from typing import Any, Dict, List

from ..core.exceptions import DatabaseAnalysisError, DatabaseConnectionError
from ..core.models import DatabaseConfig, DatabaseType


class DatabaseIntrospector:
    """Read table metadata through a :class:`ConnectionManager` boundary."""

    def __init__(self, connection_manager: Any):
        self.connection_manager = connection_manager

    def _config(self, connection_id: str) -> DatabaseConfig:
        config = self.connection_manager.get_connection_info(connection_id)
        if config is None:
            raise DatabaseConnectionError(f"Connection {connection_id} not found")
        return config

    def get_config(self, connection_id: str) -> DatabaseConfig:
        """Return the connection configuration needed by callers."""
        return self._config(connection_id)

    @staticmethod
    def _value(row: Dict[str, Any], *names: str, default: Any = None) -> Any:
        """Read a result key without depending on driver-specific casing."""
        for name in names:
            if name in row:
                return row[name]
            upper = name.upper()
            if upper in row:
                return row[upper]
            lower = name.lower()
            if lower in row:
                return row[lower]
        return default

    @staticmethod
    def _sqlite_identifier(value: str) -> str:
        """Quote a SQLite identifier used by PRAGMA statements."""
        return value.replace("'", "''")

    def list_tables(self, connection_id: str) -> List[str]:
        config = self._config(connection_id)
        if config.type == DatabaseType.MYSQL:
            rows = self.connection_manager.execute_query(connection_id, "SHOW TABLES")
        elif config.type == DatabaseType.POSTGRESQL:
            rows = self.connection_manager.execute_query(
                connection_id,
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_catalog = current_database()
                  AND table_type = 'BASE TABLE'
                  AND table_schema NOT IN ('pg_catalog', 'information_schema')
                ORDER BY table_schema, table_name
                """,
            )
        elif config.type == DatabaseType.SQLITE:
            rows = self.connection_manager.execute_query(
                connection_id,
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name",
            )
        else:
            raise DatabaseAnalysisError(f"Listing tables not implemented for {config.type}")

        return [
            str(self._value(row, "table_name", "name", default=next(iter(row.values()), "")))
            for row in rows
        ]

    def get_table(self, connection_id: str, table_name: str) -> Dict[str, Any]:
        config = self._config(connection_id)
        if config.type == DatabaseType.MYSQL:
            rows = self.connection_manager.execute_query(
                connection_id,
                """
                SELECT TABLE_NAME, TABLE_COMMENT, ENGINE, TABLE_COLLATION
                FROM information_schema.TABLES
                WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
                """,
                (config.database, table_name),
            )
        elif config.type == DatabaseType.POSTGRESQL:
            rows = self.connection_manager.execute_query(
                connection_id,
                """
                SELECT table_name, table_schema, '' AS table_comment,
                       '' AS engine, '' AS table_collation
                FROM information_schema.tables
                WHERE table_catalog = current_database()
                  AND table_type = 'BASE TABLE'
                  AND table_schema NOT IN ('pg_catalog', 'information_schema')
                  AND table_name = %s
                """,
                (table_name,),
            )
        elif config.type == DatabaseType.SQLITE:
            rows = self.connection_manager.execute_query(
                connection_id,
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
                (table_name,),
            )
        else:
            raise DatabaseAnalysisError(f"Table metadata not implemented for {config.type}")

        if not rows:
            raise DatabaseAnalysisError(f"Table {table_name} not found")
        row = rows[0]
        return {
            "name": self._value(row, "TABLE_NAME", "table_name", "name", default=table_name),
            "schema": self._value(row, "TABLE_SCHEMA", "table_schema", default=config.database),
            "comment": self._value(row, "TABLE_COMMENT", "table_comment", default="") or "",
            "engine": self._value(row, "ENGINE", "engine"),
            "collation": self._value(row, "TABLE_COLLATION", "table_collation"),
        }

    def get_columns(self, connection_id: str, table_name: str) -> List[Dict[str, Any]]:
        config = self._config(connection_id)
        if config.type == DatabaseType.MYSQL:
            rows = self.connection_manager.execute_query(
                connection_id,
                """
                SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE, COLUMN_DEFAULT,
                       COLUMN_COMMENT, COLUMN_TYPE, NUMERIC_PRECISION, NUMERIC_SCALE,
                       CHARACTER_MAXIMUM_LENGTH, COLUMN_KEY, EXTRA
                FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
                ORDER BY ORDINAL_POSITION
                """,
                (config.database, table_name),
            )
        elif config.type == DatabaseType.POSTGRESQL:
            rows = self.connection_manager.execute_query(
                connection_id,
                """
                SELECT column_name, data_type, is_nullable, column_default,
                       '' AS column_comment, data_type AS column_type,
                       numeric_precision, numeric_scale, character_maximum_length,
                       '' AS column_key,
                       CASE WHEN column_default LIKE 'nextval(%' THEN 'auto_increment' ELSE '' END AS extra
                FROM information_schema.columns
                WHERE table_catalog = current_database()
                  AND table_schema NOT IN ('pg_catalog', 'information_schema')
                  AND table_name = %s
                ORDER BY ordinal_position
                """,
                (table_name,),
            )
        elif config.type == DatabaseType.SQLITE:
            rows = self.connection_manager.execute_query(
                connection_id,
                f"PRAGMA table_info('{self._sqlite_identifier(table_name)}')",
            )
        else:
            raise DatabaseAnalysisError(f"Column metadata not implemented for {config.type}")

        columns = []
        for row in rows:
            name = self._value(row, "COLUMN_NAME", "column_name", "name", default="")
            data_type = self._value(row, "DATA_TYPE", "data_type", "type", default="") or ""
            nullable = self._value(row, "IS_NULLABLE", "is_nullable")
            primary_key = self._value(row, "COLUMN_KEY", "column_key", default="") == "PRI"
            if nullable is None:
                nullable = not bool(self._value(row, "notnull", default=0))
            elif isinstance(nullable, str):
                nullable = nullable.upper() == "YES"
            extra = self._value(row, "EXTRA", "extra", default="") or ""
            columns.append(
                {
                    "name": name,
                    "type": data_type,
                    "nullable": bool(nullable),
                    "default_value": self._value(row, "COLUMN_DEFAULT", "column_default", "dflt_value"),
                    "comment": self._value(row, "COLUMN_COMMENT", "column_comment", default="") or "",
                    "column_type": self._value(row, "COLUMN_TYPE", "column_type", "type", default=data_type),
                    "precision": self._value(row, "NUMERIC_PRECISION", "numeric_precision"),
                    "scale": self._value(row, "NUMERIC_SCALE", "numeric_scale"),
                    "max_length": self._value(
                        row, "CHARACTER_MAXIMUM_LENGTH", "character_maximum_length"
                    ),
                    "column_key": self._value(row, "COLUMN_KEY", "column_key", default=""),
                    "extra": extra,
                    "primary_key": primary_key or bool(self._value(row, "pk", default=0)),
                    "auto_increment": "auto_increment" in str(extra).lower()
                    or str(self._value(row, "type", default="")).upper() == "INTEGER AUTOINCREMENT",
                }
            )
        return columns

    def get_primary_keys(self, connection_id: str, table_name: str) -> List[str]:
        config = self._config(connection_id)
        if config.type == DatabaseType.MYSQL:
            rows = self.connection_manager.execute_query(
                connection_id,
                """
                SELECT COLUMN_NAME
                FROM information_schema.KEY_COLUMN_USAGE
                WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
                  AND CONSTRAINT_NAME = 'PRIMARY'
                ORDER BY ORDINAL_POSITION
                """,
                (config.database, table_name),
            )
        elif config.type == DatabaseType.POSTGRESQL:
            rows = self.connection_manager.execute_query(
                connection_id,
                """
                SELECT kcu.column_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                  ON tc.constraint_catalog = kcu.constraint_catalog
                 AND tc.constraint_schema = kcu.constraint_schema
                 AND tc.constraint_name = kcu.constraint_name
                 AND tc.table_name = kcu.table_name
                WHERE tc.table_catalog = current_database()
                  AND tc.constraint_type = 'PRIMARY KEY'
                  AND tc.table_schema NOT IN ('pg_catalog', 'information_schema')
                  AND tc.table_name = %s
                ORDER BY kcu.ordinal_position
                """,
                (table_name,),
            )
        elif config.type == DatabaseType.SQLITE:
            rows = self.connection_manager.execute_query(
                connection_id,
                f"PRAGMA table_info('{self._sqlite_identifier(table_name)}')",
            )
            rows = sorted((row for row in rows if row.get("pk", 0)), key=lambda row: row["pk"])
        else:
            raise DatabaseAnalysisError(f"Primary key metadata not implemented for {config.type}")
        return [str(self._value(row, "COLUMN_NAME", "column_name", "name")) for row in rows]

    def get_foreign_keys(self, connection_id: str, table_name: str) -> List[Dict[str, Any]]:
        config = self._config(connection_id)
        if config.type == DatabaseType.MYSQL:
            rows = self.connection_manager.execute_query(
                connection_id,
                """
                SELECT CONSTRAINT_NAME, COLUMN_NAME, REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME
                FROM information_schema.KEY_COLUMN_USAGE
                WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
                  AND REFERENCED_TABLE_NAME IS NOT NULL
                ORDER BY CONSTRAINT_NAME, ORDINAL_POSITION
                """,
                (config.database, table_name),
            )
        elif config.type == DatabaseType.POSTGRESQL:
            rows = self.connection_manager.execute_query(
                connection_id,
                """
                SELECT tc.constraint_name, kcu.column_name,
                       ccu.table_name AS referenced_table_name,
                       ccu.column_name AS referenced_column_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                  ON tc.constraint_catalog = kcu.constraint_catalog
                 AND tc.constraint_schema = kcu.constraint_schema
                 AND tc.constraint_name = kcu.constraint_name
                 AND tc.table_name = kcu.table_name
                JOIN information_schema.constraint_column_usage ccu
                  ON tc.constraint_catalog = ccu.constraint_catalog
                 AND tc.constraint_schema = ccu.constraint_schema
                 AND tc.constraint_name = ccu.constraint_name
                WHERE tc.table_catalog = current_database()
                  AND tc.constraint_type = 'FOREIGN KEY'
                  AND tc.table_schema NOT IN ('pg_catalog', 'information_schema')
                  AND tc.table_name = %s
                ORDER BY tc.constraint_name, kcu.ordinal_position
                """,
                (table_name,),
            )
        elif config.type == DatabaseType.SQLITE:
            rows = self.connection_manager.execute_query(
                connection_id,
                f"PRAGMA foreign_key_list('{self._sqlite_identifier(table_name)}')",
            )
        else:
            raise DatabaseAnalysisError(f"Foreign key metadata not implemented for {config.type}")

        return [
            {
                "constraint_name": str(
                    self._value(row, "CONSTRAINT_NAME", "constraint_name", "id", default="")
                ),
                "column_name": self._value(row, "COLUMN_NAME", "column_name", "from", default=""),
                "referenced_table": self._value(
                    row, "REFERENCED_TABLE_NAME", "referenced_table_name", "table", default=""
                ),
                "referenced_column": self._value(
                    row, "REFERENCED_COLUMN_NAME", "referenced_column_name", "to", default=""
                ),
            }
            for row in rows
        ]

    def get_indexes(self, connection_id: str, table_name: str) -> List[Dict[str, Any]]:
        config = self._config(connection_id)
        if config.type == DatabaseType.MYSQL:
            rows = self.connection_manager.execute_query(
                connection_id, f"SHOW INDEX FROM `{table_name.replace('`', '``')}`"
            )
            return [
                {
                    "key_name": self._value(row, "Key_name", "key_name", default=""),
                    "column_name": self._value(row, "Column_name", "column_name", default=""),
                    "unique": not bool(self._value(row, "Non_unique", "non_unique", default=1)),
                    "seq_in_index": self._value(row, "Seq_in_index", "seq_in_index", default=1),
                    "index_type": self._value(row, "Index_type", "index_type", default="BTREE"),
                }
                for row in rows
            ]
        if config.type == DatabaseType.POSTGRESQL:
            rows = self.connection_manager.execute_query(
                connection_id,
                """
                SELECT idx.relname AS key_name, att.attname AS column_name,
                       i.indisunique AS is_unique, keys.ordinality AS seq_in_index,
                       am.amname AS index_type
                FROM pg_class tbl
                JOIN pg_namespace ns ON ns.oid = tbl.relnamespace
                JOIN pg_index i ON i.indrelid = tbl.oid
                JOIN pg_class idx ON idx.oid = i.indexrelid
                JOIN pg_am am ON am.oid = idx.relam
                CROSS JOIN LATERAL unnest(i.indkey) WITH ORDINALITY AS keys(attnum, ordinality)
                JOIN pg_attribute att ON att.attrelid = tbl.oid AND att.attnum = keys.attnum
                WHERE ns.nspname NOT IN ('pg_catalog', 'information_schema')
                  AND tbl.relname = %s
                ORDER BY idx.relname, keys.ordinality
                """,
                (table_name,),
            )
            return [
                {
                    "key_name": self._value(row, "key_name", default=""),
                    "column_name": self._value(row, "column_name", default=""),
                    "unique": bool(self._value(row, "is_unique", default=False)),
                    "seq_in_index": self._value(row, "seq_in_index", default=1),
                    "index_type": self._value(row, "index_type", default="btree"),
                }
                for row in rows
            ]
        if config.type == DatabaseType.SQLITE:
            rows = self.connection_manager.execute_query(
                connection_id,
                f"PRAGMA index_list('{self._sqlite_identifier(table_name)}')",
            )
            return [
                {
                    "key_name": self._value(row, "name", default=""),
                    "column_name": "",
                    "unique": bool(self._value(row, "unique", default=0)),
                    "seq_in_index": self._value(row, "seq", default=0),
                    "index_type": "btree",
                }
                for row in rows
            ]
        raise DatabaseAnalysisError(f"Index metadata not implemented for {config.type}")
