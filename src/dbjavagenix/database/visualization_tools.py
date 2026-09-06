"""
P3.1: 可视化工具 - 跨表 ER 图生成。

工具:
  - db_render_er_diagram: 给定多个表名,生成 Mermaid erDiagram (附加 mcp-apps/mermaid meta)
"""

import logging
from typing import Any, Dict, List

from mcp.types import TextContent, Tool

from ..core.exceptions import DatabaseConnectionError, MCPServiceError
from ..core.models import DatabaseType
from ..database.connection_manager import connection_manager
from ..database.introspection import DatabaseIntrospector
from ..mcp_apps.er_diagram import (
    ERColumn,
    ERForeignKey,
    ERTable,
    render_er_diagram,
    render_summary_text,
)
from ..mcp_apps.meta_builder import attach_meta, build_mcp_app_meta

logger = logging.getLogger(__name__)


def get_visualization_tools() -> List[Tool]:
    """返回 P3.1 可视化工具列表"""
    return [
        Tool(
            name="db_render_er_diagram",
            description=(
                "生成多个表的 Mermaid ER 图 (MCP App: mermaid 组件)。"
                "调用前需已通过 db_connect_test 建立连接。支持 MCP Apps 的客户端会渲染图表;"
                "不支持的客户端会看到纯文本摘要 + mermaid 源码。"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "connection_id": {
                        "type": "string",
                        "description": "Database connection ID from db_connect_test",
                    },
                    "database": {
                        "type": "string",
                        "description": "Database name",
                    },
                    "tables": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "表名列表 (至少 1 个)",
                        "minItems": 1,
                    },
                    "include_non_pk_columns": {
                        "type": "boolean",
                        "description": "是否列出非主键/外键列 (默认 true)",
                        "default": True,
                    },
                },
                "required": ["connection_id", "database", "tables"],
            },
        ),
    ]


async def handle_db_render_er_diagram(arguments: Dict[str, Any]) -> List[TextContent]:
    """收集多表的列 + FK,生成 ER 图"""
    try:
        connection_id = arguments["connection_id"]
        database = arguments["database"]
        tables: List[str] = list(arguments["tables"])
        include_non_pk = arguments.get("include_non_pk_columns", True)

        config = connection_manager.get_connection_info(connection_id)
        if not config:
            raise DatabaseConnectionError(f"Connection {connection_id} not found")

        er_tables: List[ERTable] = []
        all_fks: List[ERForeignKey] = []

        for table_name in tables:
            columns, fks = _collect_table_for_er(
                connection_id, database, table_name, config.type, include_non_pk
            )
            er_tables.append(ERTable(name=table_name, columns=columns))
            all_fks.extend(fks)

        # 仅保留与所选表集合相关的 FK
        selected = set(tables)
        all_fks = [fk for fk in all_fks if fk.to_table in selected]

        mermaid_source = render_er_diagram(er_tables, all_fks)
        summary = render_summary_text(er_tables, all_fks)

        text = (
            f"{summary}\n\n"
            f"```mermaid\n{mermaid_source}\n```"
        )
        content = TextContent(type="text", text=text)
        meta = build_mcp_app_meta(
            "mermaid",
            source=mermaid_source,
            version="1.0",
        )
        return [attach_meta(content, meta)]

    except (DatabaseConnectionError, MCPServiceError) as e:
        return [TextContent(
            type="text",
            text=f"Failed to render ER diagram: {e}",
        )]
    except Exception as e:  # noqa: BLE001
        logger.error(f"db_render_er_diagram unexpected error: {e}")
        return [TextContent(
            type="text",
            text=f"Unexpected error: {e}",
        )]


def _collect_table_for_er(
    connection_id: str,
    database: str,
    table: str,
    db_type: DatabaseType,
    include_non_pk: bool,
) -> tuple[List[ERColumn], List[ERForeignKey]]:
    """收集单表的列 + FK,转 ER* 模型"""
    columns_raw = _query_columns(connection_id, database, table, db_type)
    fks_raw = _query_foreign_keys(connection_id, database, table, db_type)

    fk_column_names = {fk["column"] for fk in fks_raw}
    er_columns: List[ERColumn] = []
    for c in columns_raw:
        is_pk = c["is_primary"]
        is_fk = c["name"] in fk_column_names
        if not include_non_pk and not (is_pk or is_fk):
            continue
        er_columns.append(ERColumn(
            name=c["name"],
            type=c["type"],
            is_primary=is_pk,
            is_foreign=is_fk,
        ))

    er_fks = [
        ERForeignKey(
            from_table=table,
            from_column=fk["column"],
            to_table=fk["to_table"],
            to_column=fk["to_column"],
        )
        for fk in fks_raw
    ]
    return er_columns, er_fks


def _query_columns(
    connection_id: str, database: str, table: str, db_type: DatabaseType
) -> List[Dict[str, Any]]:
    """查询表列信息 (跨数据库简化版)"""
    if db_type == DatabaseType.MYSQL:
        query = """
        SELECT COLUMN_NAME, COLUMN_TYPE, COLUMN_KEY
        FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
        ORDER BY ORDINAL_POSITION
        """
        rows = connection_manager.execute_query(connection_id, query, (database, table))
        return [
            {
                "name": r["COLUMN_NAME"],
                "type": r["COLUMN_TYPE"],
                "is_primary": r["COLUMN_KEY"] == "PRI",
            }
            for r in rows
        ]
    if db_type == DatabaseType.SQLITE:
        query = f"PRAGMA table_info('{table}')"
        rows = connection_manager.execute_query(connection_id, query)
        return [
            {
                "name": r.get("name", ""),
                "type": r.get("type", ""),
                "is_primary": r.get("pk", 0) > 0,
            }
            for r in rows
        ]
    raise MCPServiceError(f"ER column query not implemented for {db_type}")


def _query_foreign_keys(
    connection_id: str, database: str, table: str, db_type: DatabaseType
) -> List[Dict[str, Any]]:
    """查询表外键"""
    if db_type == DatabaseType.MYSQL:
        query = """
        SELECT COLUMN_NAME, REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME
        FROM information_schema.KEY_COLUMN_USAGE
        WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
          AND REFERENCED_TABLE_NAME IS NOT NULL
        ORDER BY ORDINAL_POSITION
        """
        rows = connection_manager.execute_query(connection_id, query, (database, table))
        return [
            {
                "column": r["COLUMN_NAME"],
                "to_table": r["REFERENCED_TABLE_NAME"],
                "to_column": r["REFERENCED_COLUMN_NAME"],
            }
            for r in rows
        ]
    if db_type == DatabaseType.SQLITE:
        query = f"PRAGMA foreign_key_list('{table}')"
        rows = connection_manager.execute_query(connection_id, query)
        return [
            {
                "column": r.get("from", ""),
                "to_table": r.get("table", ""),
                "to_column": r.get("to", ""),
            }
            for r in rows
        ]
    return []


def _query_columns(
    connection_id: str, database: str, table: str, db_type: DatabaseType
) -> List[Dict[str, Any]]:
    """Return normalized columns through the shared introspection layer."""
    introspector = DatabaseIntrospector(connection_manager)
    config = introspector.get_config(connection_id)
    if config.type != db_type:
        raise MCPServiceError(f"Connection type mismatch: expected {db_type}, got {config.type}")
    return [
        {
            "name": column["name"],
            "type": column["column_type"] or column["type"],
            "is_primary": column["primary_key"],
        }
        for column in introspector.get_columns(connection_id, table)
    ]


def _query_foreign_keys(
    connection_id: str, database: str, table: str, db_type: DatabaseType
) -> List[Dict[str, Any]]:
    """Return normalized foreign keys through the shared introspection layer."""
    introspector = DatabaseIntrospector(connection_manager)
    config = introspector.get_config(connection_id)
    if config.type != db_type:
        raise MCPServiceError(f"Connection type mismatch: expected {db_type}, got {config.type}")
    return [
        {
            "column": foreign_key["column_name"],
            "to_table": foreign_key["referenced_table"],
            "to_column": foreign_key["referenced_column"],
        }
        for foreign_key in introspector.get_foreign_keys(connection_id, table)
    ]
