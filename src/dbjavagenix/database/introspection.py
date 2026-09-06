"""Database metadata access shared by code generation and MCP tools.

The public methods return database-neutral dictionaries.  Dialect-specific SQL
stays in this module so callers do not need to branch on vendor details.
"""

from __future__ import annotations

from typing import Any, Dict, List

from ..core.exceptions import DatabaseAnalysisError, DatabaseConnectionError
from ..core.models import DatabaseConfig, DatabaseType
from .sql_identifiers import quote_mysql_identifier


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

    @staticmethod
    def _mysql_identifier(value: str) -> str:
        """Quote a MySQL identifier using the metadata error contract."""
        try:
            return quote_mysql_identifier(value)
        except ValueError as exc:
            raise DatabaseAnalysisError(str(exc)) from exc

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

    def get_table(
        self, connection_id: str, table_name: str, schema: str | None = None
    ) -> Dict[str, Any]:
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
            schema_filter = "AND table_schema = %s" if schema else ""
            params = (table_name, schema) if schema else (table_name,)
            rows = self.connection_manager.execute_query(
                connection_id,
                f"""
                SELECT t.table_name, t.table_schema,
                       COALESCE(obj_description(c.oid, 'pg_class'), '') AS table_comment,
                       '' AS engine, '' AS table_collation
                FROM information_schema.tables t
                JOIN pg_catalog.pg_namespace n ON n.nspname = t.table_schema
                JOIN pg_catalog.pg_class c
                  ON c.relnamespace = n.oid AND c.relname = t.table_name
                WHERE t.table_catalog = current_database()
                  AND t.table_type = 'BASE TABLE'
                  AND t.table_schema NOT IN ('pg_catalog', 'information_schema')
                  AND t.table_name = %s
                  {schema_filter}
                ORDER BY t.table_schema
                """,
                params,
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
        if config.type == DatabaseType.POSTGRESQL and schema is None and len(rows) > 1:
            public_rows = [row for row in rows if self._value(row, "table_schema") == "public"]
            if len(public_rows) == 1:
                rows = public_rows
            else:
                raise DatabaseAnalysisError(
                    f"Table {table_name} exists in multiple schemas; specify schema explicitly"
                )
        row = rows[0]
        return {
            "name": self._value(row, "TABLE_NAME", "table_name", "name", default=table_name),
            "schema": self._value(row, "TABLE_SCHEMA", "table_schema", default=config.database),
            "comment": self._value(row, "TABLE_COMMENT", "table_comment", default="") or "",
            "engine": self._value(row, "ENGINE", "engine"),
            "collation": self._value(row, "TABLE_COLLATION", "table_collation"),
        }

    def get_columns(
        self, connection_id: str, table_name: str, schema: str | None = None
    ) -> List[Dict[str, Any]]:
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
            schema_filter = "AND c.table_schema = %s" if schema else ""
            params = (table_name, schema) if schema else (table_name,)
            rows = self.connection_manager.execute_query(
                connection_id,
                f"""
                SELECT c.column_name, c.data_type, c.udt_name, c.is_nullable,
                       c.column_default,
                       COALESCE(col_description(a.attrelid, a.attnum), '') AS column_comment,
                       format_type(a.atttypid, a.atttypmod) AS column_type,
                       c.numeric_precision, c.numeric_scale,
                       c.character_maximum_length, '' AS column_key,
                       CASE WHEN c.column_default LIKE 'nextval(%' THEN 'auto_increment' ELSE '' END AS extra
                FROM information_schema.columns c
                JOIN pg_catalog.pg_namespace n ON n.nspname = c.table_schema
                JOIN pg_catalog.pg_class tbl
                  ON tbl.relnamespace = n.oid AND tbl.relname = c.table_name
                JOIN pg_catalog.pg_attribute a
                  ON a.attrelid = tbl.oid AND a.attname = c.column_name
                 AND a.attnum > 0 AND NOT a.attisdropped
                WHERE c.table_catalog = current_database()
                  AND c.table_schema NOT IN ('pg_catalog', 'information_schema')
                  AND c.table_name = %s
                  {schema_filter}
                ORDER BY c.ordinal_position
                """,
                params,
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
                    "default_value": self._value(
                        row, "COLUMN_DEFAULT", "column_default", "dflt_value"
                    ),
                    "comment": self._value(row, "COLUMN_COMMENT", "column_comment", default="")
                    or "",
                    "column_type": self._value(
                        row, "COLUMN_TYPE", "column_type", "type", default=data_type
                    ),
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

    def get_primary_keys(
        self, connection_id: str, table_name: str, schema: str | None = None
    ) -> List[str]:
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
            schema_filter = "AND tc.constraint_schema = %s" if schema else ""
            params = (table_name, schema) if schema else (table_name,)
            rows = self.connection_manager.execute_query(
                connection_id,
                f"""
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
                  {schema_filter}
                ORDER BY kcu.ordinal_position
                """,
                params,
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

    def get_foreign_keys(
        self, connection_id: str, table_name: str, schema: str | None = None
    ) -> List[Dict[str, Any]]:
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
            schema_filter = "AND src_ns.nspname = %s" if schema else ""
            params = (table_name, schema) if schema else (table_name,)
            rows = self.connection_manager.execute_query(
                connection_id,
                f"""
                SELECT con.conname AS constraint_name,
                       src_att.attname AS column_name,
                       tgt_tbl.relname AS referenced_table_name,
                       tgt_att.attname AS referenced_column_name,
                       src_keys.ordinality AS column_position
                FROM pg_catalog.pg_constraint con
                JOIN pg_catalog.pg_class src_tbl
                  ON src_tbl.oid = con.conrelid
                JOIN pg_catalog.pg_namespace src_ns
                  ON src_ns.oid = src_tbl.relnamespace
                JOIN pg_catalog.pg_class tgt_tbl
                  ON tgt_tbl.oid = con.confrelid
                JOIN pg_catalog.pg_namespace tgt_ns
                  ON tgt_ns.oid = tgt_tbl.relnamespace
                CROSS JOIN LATERAL unnest(con.conkey)
                  WITH ORDINALITY AS src_keys(attnum, ordinality)
                JOIN LATERAL unnest(con.confkey)
                  WITH ORDINALITY AS tgt_keys(attnum, ordinality)
                  ON tgt_keys.ordinality = src_keys.ordinality
                JOIN pg_catalog.pg_attribute src_att
                  ON src_att.attrelid = src_tbl.oid
                 AND src_att.attnum = src_keys.attnum
                JOIN pg_catalog.pg_attribute tgt_att
                  ON tgt_att.attrelid = tgt_tbl.oid
                 AND tgt_att.attnum = tgt_keys.attnum
                WHERE con.contype = 'f'
                  AND src_ns.nspname NOT IN ('pg_catalog', 'information_schema')
                  AND src_tbl.relname = %s
                  {schema_filter}
                ORDER BY con.conname, src_keys.ordinality
                """,
                params,
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

    def get_indexes(
        self, connection_id: str, table_name: str, schema: str | None = None
    ) -> List[Dict[str, Any]]:
        config = self._config(connection_id)
        if config.type == DatabaseType.MYSQL:
            rows = self.connection_manager.execute_query(
                connection_id, f"SHOW INDEX FROM {self._mysql_identifier(table_name)}"
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
            schema_filter = "AND ns.nspname = %s" if schema else ""
            params = (table_name, schema) if schema else (table_name,)
            rows = self.connection_manager.execute_query(
                connection_id,
                f"""
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
                  {schema_filter}
                ORDER BY idx.relname, keys.ordinality
                """,
                params,
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
            index_rows = self.connection_manager.execute_query(
                connection_id,
                f"PRAGMA index_list('{self._sqlite_identifier(table_name)}')",
            )
            indexes: List[Dict[str, Any]] = []
            for index_row in index_rows:
                index_name = str(self._value(index_row, "name", default=""))
                unique = bool(self._value(index_row, "unique", default=0))
                index_info = self.connection_manager.execute_query(
                    connection_id,
                    f"PRAGMA index_info('{self._sqlite_identifier(index_name)}')",
                )
                if index_info:
                    indexes.extend(
                        {
                            "key_name": index_name,
                            "column_name": self._value(info, "name", default=""),
                            "unique": unique,
                            "seq_in_index": self._value(info, "seqno", default=0) + 1,
                            "index_type": "btree",
                        }
                        for info in index_info
                    )
                else:
                    # Expression indexes have no column name in PRAGMA index_info.
                    indexes.append(
                        {
                            "key_name": index_name,
                            "column_name": "",
                            "unique": unique,
                            "seq_in_index": 1,
                            "index_type": "btree",
                        }
                    )
            return indexes
        raise DatabaseAnalysisError(f"Index metadata not implemented for {config.type}")

    def describe_table(
        self, connection_id: str, table_name: str, schema: str | None = None
    ) -> Dict[str, Any]:
        """Return one normalized metadata document for a table."""
        table = self.get_table(connection_id, table_name, schema)
        resolved_schema = schema or table.get("schema")
        columns = self.get_columns(connection_id, table_name, resolved_schema)
        primary_keys = self.get_primary_keys(connection_id, table_name, resolved_schema)
        foreign_keys = self.get_foreign_keys(connection_id, table_name, resolved_schema)
        indexes = self.get_indexes(connection_id, table_name, resolved_schema)
        primary_key_set = set(primary_keys)
        for column in columns:
            column["primary_key"] = (
                column.get("primary_key", False) or column["name"] in primary_key_set
            )
        return {
            "name": table["name"],
            "schema": resolved_schema,
            "comment": table.get("comment", ""),
            "engine": table.get("engine"),
            "collation": table.get("collation"),
            "columns": columns,
            "primary_keys": primary_keys,
            "foreign_keys": foreign_keys,
            "indexes": indexes,
        }
