"""
MCP tools for database connection and basic query operations
"""
import json
import logging
import os
import re
from functools import lru_cache
from pathlib import Path, PureWindowsPath
from typing import Dict, Any, List, Optional
from ..utils.json_serialization import default as _query_result_json_default
from ..utils.json_serialization import dumps as _json_dumps

from mcp.types import Tool, TextContent, ImageContent, EmbeddedResource

from ..core.models import DatabaseConfig, DatabaseType
from ..utils.dependency_manager import DependencyManager
from ..core.exceptions import (
    DatabaseAnalysisError,
    DatabaseConnectionError,
    DatabaseQueryError,
    MCPServiceError,
)
from ..database.connection_manager import connection_manager
from ..database.introspection import DatabaseIntrospector
from ..database.dialect import get_dialect, list_supported_dialects
from ..database.sql_identifiers import quote_mysql_identifier
from ..database.capabilities import supported_database_type_values
from ..config.config_manager import ConfigManager
from ..utils.pom_analyzer import PomAnalyzer
from ..utils.security import redact_sensitive_data, redact_sensitive_text

logger = logging.getLogger(__name__)


_READ_ONLY_FORBIDDEN_WORDS = {
    "ALTER",
    "CREATE",
    "DELETE",
    "DROP",
    "GRANT",
    "INSERT",
    "MERGE",
    "REPLACE",
    "REVOKE",
    "TRUNCATE",
    "UPDATE",
}

_LOCKING_READ_CLAUSES = (
    ("FOR", "UPDATE"),
    ("FOR", "NO", "KEY", "UPDATE"),
    ("FOR", "SHARE"),
    ("FOR", "KEY", "SHARE"),
    ("LOCK", "IN", "SHARE", "MODE"),
)


def _resolve_codegen_output_path(base_dir: Path, relative_path: object) -> Path:
    """Resolve a generated filename while keeping it inside its output directory."""
    if not isinstance(relative_path, str) or not relative_path.strip():
        raise ValueError("generated filename must be a non-empty string")

    # Treat Windows separators consistently on every platform and reject rooted paths.
    normalized_path = relative_path.replace("\\", "/")
    windows_path = PureWindowsPath(relative_path)
    if (
        Path(normalized_path).is_absolute()
        or windows_path.is_absolute()
        or windows_path.root
        or windows_path.drive
    ):
        raise ValueError("generated filename must be relative")

    resolved_base = base_dir.resolve()
    resolved_output = (resolved_base / normalized_path).resolve()
    try:
        resolved_output.relative_to(resolved_base)
    except ValueError as exc:
        raise ValueError("generated filename escapes the output directory") from exc
    return resolved_output


def _display_codegen_path(path: Path, project_root: Path) -> str:
    """Prefer a project-relative path, falling back to an absolute custom path."""
    try:
        return str(path.relative_to(project_root))
    except ValueError:
        return str(path.absolute())


def _write_codegen_file(path: Path, code: str) -> None:
    """Create the parent directory and write one generated file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(code, encoding="utf-8")


def _tokenize_read_only_sql(query: str) -> List[tuple[str, str]]:
    """Tokenize enough SQL to enforce the single, read-only statement contract."""
    tokens: List[tuple[str, str]] = []
    index = 0
    length = len(query)

    while index < length:
        char = query[index]
        if char.isspace():
            index += 1
            continue

        if query.startswith("/*", index) or query.startswith("--", index) or char == "#":
            raise MCPServiceError("SQL comments are not allowed in read-only queries")

        if char in "'\"`":
            quote = char
            start = index
            index += 1
            while index < length:
                if query[index] == "\\" and quote == "'":
                    index += 2
                    continue
                if query[index] == quote:
                    if index + 1 < length and query[index + 1] == quote:
                        index += 2
                        continue
                    index += 1
                    break
                index += 1
            else:
                raise MCPServiceError("Unterminated quoted value in SQL query")
            tokens.append(("quoted", query[start:index]))
            continue

        if char.isalpha() or char == "_":
            start = index
            index += 1
            while index < length and (query[index].isalnum() or query[index] in "_$"):
                index += 1
            tokens.append(("word", query[start:index].upper()))
            continue

        if char == ";":
            tokens.append(("symbol", char))
        else:
            tokens.append(("symbol", char))
        index += 1

    return tokens


def _contains_locking_read_clause(tokens: List[tuple[str, str]]) -> bool:
    """Return whether a token stream contains a row-locking SELECT clause."""
    for clause in _LOCKING_READ_CLAUSES:
        clause_length = len(clause)
        for start in range(len(tokens) - clause_length + 1):
            if all(
                tokens[start + offset] == ("word", keyword)
                for offset, keyword in enumerate(clause)
            ):
                return True
    return False


def _validate_read_only_query(query: Any) -> str:
    """Validate and normalize one SQL SELECT statement for the public query tool."""
    if not isinstance(query, str):
        raise MCPServiceError("The query must be a SQL string")

    normalized = query.strip()
    if not normalized:
        raise MCPServiceError("The query must not be empty")

    tokens = _tokenize_read_only_sql(normalized)
    if not tokens:
        raise MCPServiceError("The query must not be empty")

    semicolon_indexes = [index for index, token in enumerate(tokens) if token == ("symbol", ";")]
    if semicolon_indexes:
        if semicolon_indexes != [len(tokens) - 1]:
            raise MCPServiceError("Only one SQL statement is allowed")
        normalized = normalized[: normalized.rfind(";")].rstrip()
        tokens = tokens[:-1]

    first_word = next((value for kind, value in tokens if kind == "word"), None)
    if first_word not in {"SELECT", "WITH"}:
        raise MCPServiceError("Only SELECT queries are allowed for security reasons")

    if _contains_locking_read_clause(tokens):
        raise MCPServiceError("Only non-locking read-only SELECT queries are allowed")

    depth = 0
    top_level_select = first_word == "SELECT"
    for kind, value in tokens:
        if kind == "symbol":
            if value == "(":
                depth += 1
            elif value == ")":
                depth -= 1
                if depth < 0:
                    raise MCPServiceError("Invalid SQL query parentheses")
            continue

        if kind != "word":
            continue
        if value in _READ_ONLY_FORBIDDEN_WORDS or value == "INTO":
            raise MCPServiceError("Only read-only SELECT queries are allowed")
        if first_word == "WITH" and value == "SELECT" and depth == 0:
            top_level_select = True

    if depth != 0:
        raise MCPServiceError("Invalid SQL query parentheses")
    if first_word == "WITH" and not top_level_select:
        raise MCPServiceError("WITH queries must contain a top-level SELECT statement")

    return normalized


def _has_top_level_limit_clause(query: str) -> bool:
    tokens = _tokenize_read_only_sql(query)
    depth = 0
    for index, (kind, value) in enumerate(tokens):
        if kind == "symbol":
            if value == "(":
                depth += 1
            elif value == ")":
                depth -= 1
        elif kind == "word" and value == "LIMIT" and depth == 0:
            next_token = tokens[index + 1] if index + 1 < len(tokens) else None
            if next_token and (next_token[0] == "symbol" or next_token[1] == "ALL"):
                return True
    return False


def _top_level_limit_span(query: str) -> tuple[int, int, int | None] | None:
    """Return the value span for a simple top-level LIMIT clause.

    Quoted values are masked before matching so a literal such as ``'LIMIT 9'``
    cannot affect the server-side result cap. The optional ``LIMIT offset,count``
    form returns the row-count span rather than the offset span.
    """
    masked = list(query)
    index = 0
    while index < len(masked):
        if masked[index] not in "'\"`":
            index += 1
            continue
        quote = masked[index]
        index += 1
        while index < len(masked):
            masked[index] = " "
            if query[index] == quote:
                if index + 1 < len(masked) and query[index + 1] == quote:
                    masked[index + 1] = " "
                    index += 2
                    continue
                index += 1
                break
            if query[index] == "\\" and quote == "'" and index + 1 < len(masked):
                masked[index + 1] = " "
                index += 2
                continue
            index += 1

    masked_query = "".join(masked)

    def is_top_level(position: int) -> bool:
        depth = 0
        for char in masked_query[:position]:
            if char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
        return depth == 0

    offset_form = re.compile(r"\bLIMIT\s+\d+\s*,\s*(\d+)\b", re.IGNORECASE)
    for match in offset_form.finditer(masked_query):
        if is_top_level(match.start()):
            return match.start(1), match.end(1), int(match.group(1))

    simple_form = re.compile(r"\bLIMIT\s+(ALL|\d+)\b", re.IGNORECASE)
    for match in simple_form.finditer(masked_query):
        if is_top_level(match.start()):
            value = match.group(1).upper()
            return match.start(1), match.end(1), None if value == "ALL" else int(value)
    return None


def _apply_query_limit(query: str, limit: int) -> str:
    """Ensure a validated read-only query cannot exceed the requested limit."""
    span = _top_level_limit_span(query)
    if span is None:
        return f"{query} LIMIT {limit}"

    start, end, existing_limit = span
    if existing_limit is None or existing_limit > limit:
        return f"{query[:start]}{limit}{query[end:]}"
    return query


def _quote_mysql_identifier(identifier: Any) -> str:
    """Adapt shared identifier validation to the MCP error contract."""
    try:
        return quote_mysql_identifier(identifier)
    except ValueError as exc:
        raise MCPServiceError(str(exc)) from exc


def get_connection_tools() -> List[Tool]:
    """
    Get list of database connection and basic query MCP tools
    
    Returns:
        List of MCP Tool objects
    """
    return [
        Tool(
            name="db_connect_test",
            description="Test database connection and create connection session",
            inputSchema={
                "type": "object",
                "properties": {
                    "host": {
                        "type": "string",
                        "description": "Database host address"
                    },
                    "port": {
                        "type": "integer",
                        "description": "Database port number"
                    },
                    "username": {
                        "type": "string", 
                        "description": "Database username"
                    },
                    "password": {
                        "type": "string",
                        "description": "Database password"
                    },
                    "database": {
                        "type": "string",
                        "description": "Database name (optional for initial connection)",
                        "default": ""
                    },
                    "database_type": {
                        "type": "string",
                        "enum": supported_database_type_values(),
                        "description": "Database type"
                    },
                    "charset": {
                        "type": "string",
                        "description": "Character encoding",
                        "default": "utf8mb4"
                    }
                },
                "required": ["host", "port", "username", "password", "database_type"]
            }
        ),
        
        Tool(
            name="db_query_databases",
            description="List all databases on the server",
            inputSchema={
                "type": "object",
                "properties": {
                    "connection_id": {
                        "type": "string",
                        "description": "Connection identifier from db_connect_test"
                    }
                },
                "required": ["connection_id"]
            }
        ),
        
        Tool(
            name="db_query_tables",
            description="List all tables in a specific database",
            inputSchema={
                "type": "object",
                "properties": {
                    "connection_id": {
                        "type": "string",
                        "description": "Connection identifier from db_connect_test"
                    },
                    "database": {
                        "type": "string",
                        "description": "Database name"
                    },
                    "schema": {
                        "type": "string",
                        "description": "PostgreSQL schema (optional)"
                    }
                },
                "required": ["connection_id", "database"]
            }
        ),
        
        Tool(
            name="db_query_table_exists",
            description="Check if a table exists in the database",
            inputSchema={
                "type": "object",
                "properties": {
                    "connection_id": {
                        "type": "string",
                        "description": "Connection identifier from db_connect_test"
                    },
                    "database": {
                        "type": "string",
                        "description": "Database name"
                    },
                    "table": {
                        "type": "string",
                        "description": "Table name"
                    },
                    "schema": {
                        "type": "string",
                        "description": "PostgreSQL schema (optional)"
                    }
                },
                "required": ["connection_id", "database", "table"]
            }
        ),
        
        Tool(
            name="db_query_execute",
            description="Execute custom SQL query (SELECT only for safety)",
            inputSchema={
                "type": "object",
                "properties": {
                    "connection_id": {
                        "type": "string",
                        "description": "Connection identifier from db_connect_test"
                    },
                    "query": {
                        "type": "string",
                        "description": "SQL SELECT query to execute"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of rows to return",
                        "default": 100
                    }
                },
                "required": ["connection_id", "query"]
            }
        )
    ]


def get_table_analysis_tools() -> List[Tool]:
    """
    Get list of table structure analysis MCP tools
    
    Returns:
        List of MCP Tool objects
    """
    return [
        Tool(
            name="db_table_describe",
            description="Get complete table structure information including columns, types, constraints",
            inputSchema={
                "type": "object",
                "properties": {
                    "connection_id": {
                        "type": "string",
                        "description": "Connection identifier from db_connect_test"
                    },
                    "database": {
                        "type": "string",
                        "description": "Database name"
                    },
                    "table": {
                        "type": "string",
                        "description": "Table name"
                    },
                    "schema": {
                        "type": "string",
                        "description": "PostgreSQL schema (defaults to the resolved table schema)"
                    },
                    "include_java_types": {
                        "type": "boolean",
                        "description": "Include Java type mapping for columns",
                        "default": True
                    }
                },
                "required": ["connection_id", "database", "table"]
            }
        ),
        
        Tool(
            name="db_table_columns", 
            description="Get detailed column information for a table",
            inputSchema={
                "type": "object",
                "properties": {
                    "connection_id": {
                        "type": "string",
                        "description": "Connection identifier from db_connect_test"
                    },
                    "database": {
                        "type": "string",
                        "description": "Database name"
                    },
                    "table": {
                        "type": "string",
                        "description": "Table name"
                    },
                    "schema": {
                        "type": "string",
                        "description": "PostgreSQL schema (optional)"
                    }
                },
                "required": ["connection_id", "database", "table"]
            }
        ),
        
        Tool(
            name="db_table_primary_keys",
            description="Get primary key information for a table",
            inputSchema={
                "type": "object",
                "properties": {
                    "connection_id": {
                        "type": "string",
                        "description": "Connection identifier from db_connect_test"
                    },
                    "database": {
                        "type": "string",
                        "description": "Database name"
                    },
                    "table": {
                        "type": "string",
                        "description": "Table name"
                    },
                    "schema": {
                        "type": "string",
                        "description": "PostgreSQL schema (optional)"
                    }
                },
                "required": ["connection_id", "database", "table"]
            }
        ),
        
        Tool(
            name="db_table_foreign_keys",
            description="Get foreign key relationships for a table",
            inputSchema={
                "type": "object",
                "properties": {
                    "connection_id": {
                        "type": "string",
                        "description": "Connection identifier from db_connect_test"
                    },
                    "database": {
                        "type": "string",
                        "description": "Database name"
                    },
                    "table": {
                        "type": "string",
                        "description": "Table name"
                    },
                    "schema": {
                        "type": "string",
                        "description": "PostgreSQL schema (optional)"
                    }
                },
                "required": ["connection_id", "database", "table"]
            }
        ),
        
        Tool(
            name="db_table_indexes",
            description="Get index information for a table", 
            inputSchema={
                "type": "object",
                "properties": {
                    "connection_id": {
                        "type": "string",
                        "description": "Connection identifier from db_connect_test"
                    },
                    "database": {
                        "type": "string",
                        "description": "Database name"
                    },
                    "table": {
                        "type": "string",
                        "description": "Table name"
                    },
                    "schema": {
                        "type": "string",
                        "description": "PostgreSQL schema (optional)"
                    }
                },
                "required": ["connection_id", "database", "table"]
            }
        )
    ]


async def handle_db_connect_test(arguments: Dict[str, Any]) -> List[TextContent]:
    """
    Handle database connection test
    
    Args:
        arguments: Tool arguments
        
    Returns:
        Connection result with connection_id
    """
    try:
        # Create database config
        config = DatabaseConfig(
            type=DatabaseType(arguments["database_type"]),
            host=arguments["host"],
            port=arguments["port"],
            username=arguments["username"],
            password=arguments["password"],
            database=arguments.get("database", ""),
            charset=arguments.get("charset", "utf8mb4")
        )
        
        # Create connection
        connection_id = connection_manager.create_connection(config)
        
        # Test basic connectivity
        connection = connection_manager.get_connection(connection_id)
        
        # Get server information
        server_info = ""
        try:
            if config.type == DatabaseType.MYSQL:
                with connection_manager.get_cursor(connection_id) as cursor:
                    cursor.execute("SELECT VERSION() as version")
                    result = cursor.fetchone()
                    if result:
                        server_info = f"MySQL {result[0] if isinstance(result, tuple) else result['version']}"

            elif config.type == DatabaseType.POSTGRESQL:
                with connection_manager.get_cursor(connection_id) as cursor:
                    cursor.execute("SELECT version() AS version")
                    result = cursor.fetchone()
                    if result:
                        server_info = (
                            f"PostgreSQL {result[0] if isinstance(result, tuple) else result['version']}"
                        )

            elif config.type == DatabaseType.SQLITE:
                server_info = "SQLite"
                
        except Exception as e:
            logger.warning(f"Could not get server info: {e}")
            server_info = f"{config.type.value} (version unknown)"
        
        response = {
            "success": True,
            "connection_id": connection_id,
            "server_info": server_info,
            "database_type": config.type.value,
            "host": config.host,
            "port": config.port,
            "message": f"Successfully connected to {config.type.value} database"
        }
        
        return [TextContent(
            type="text",
            text=f"Database connection successful!\n\nConnection Details:\n"
                 f"- Connection ID: {connection_id}\n"
                 f"- Server: {server_info}\n"
                 f"- Host: {config.host}:{config.port}\n"
                 f"- Type: {config.type.value}\n\n"
                 f"Use this connection_id for subsequent database operations.\n\n"
                 f"Raw Response: {_json_dumps(response, ensure_ascii=False)}"
        )]
        
    except DatabaseConnectionError as e:
        safe_error = redact_sensitive_text(e)
        error_response = {
            "success": False,
            "error": "connection_failed",
            "message": safe_error
        }
        return [TextContent(
            type="text",
            text=f"Database connection failed: {safe_error}\n\nRaw Response: {_json_dumps(error_response, ensure_ascii=False)}"
        )]
        
    except Exception as e:
        logger.error(f"Unexpected error in db_connect_test: {e}")
        safe_error = redact_sensitive_text(e)
        error_response = {
            "success": False,
            "error": "unexpected_error",
            "message": f"Unexpected error: {safe_error}"
        }
        return [TextContent(
            type="text",
            text=f"Unexpected error: {safe_error}\n\nRaw Response: {_json_dumps(error_response, ensure_ascii=False)}"
        )]


async def handle_db_query_databases(arguments: Dict[str, Any]) -> List[TextContent]:
    """
    Handle listing databases
    
    Args:
        arguments: Tool arguments
        
    Returns:
        List of databases
    """
    try:
        connection_id = arguments["connection_id"]
        
        # Get connection info to determine database type
        config = connection_manager.get_connection_info(connection_id)
        if not config:
            raise DatabaseConnectionError(f"Connection {connection_id} not found")
        
        # Query databases based on database type
        if config.type == DatabaseType.MYSQL:
            query = "SHOW DATABASES"

        elif config.type == DatabaseType.POSTGRESQL:
            query = """
            SELECT datname AS database_name
            FROM pg_database
            WHERE datallowconn = TRUE AND NOT datistemplate
            ORDER BY datname
            """
        elif config.type == DatabaseType.SQLITE:
            # SQLite doesn't have multiple databases concept
            response = {
                "success": True,
                "databases": [config.database],
                "count": 1,
            }
            return [TextContent(
                type="text",
                text=f"SQLite databases: [{config.database}]\n\nRaw Response: {_json_dumps(response, ensure_ascii=False)}"
            )]
        else:
            raise MCPServiceError(f"Listing databases not implemented for {config.type}")
        
        results = connection_manager.execute_query(connection_id, query)
        
        # Extract database names
        databases = []
        for row in results:
            if isinstance(row, dict):
                # Get the first column value (database name)
                db_name = list(row.values())[0]
                databases.append(db_name)
        
        response = {
            "success": True,
            "databases": databases,
            "count": len(databases)
        }
        
        return [TextContent(
            type="text",
            text=f"Found {len(databases)} databases:\n" +
                 "\n".join(f"- {db}" for db in databases) +
                 f"\n\nRaw Response: {_json_dumps(response, ensure_ascii=False)}"
        )]
        
    except (DatabaseConnectionError, DatabaseQueryError) as e:
        error_response = {
            "success": False,
            "error": "query_failed",
            "message": str(e)
        }
        return [TextContent(
            type="text",
            text=f"Failed to list databases: {str(e)}\n\nRaw Response: {_json_dumps(error_response, ensure_ascii=False)}"
        )]
        
    except Exception as e:
        logger.error(f"Unexpected error in db_query_databases: {e}")
        error_response = {
            "success": False,
            "error": "unexpected_error",
            "message": f"Unexpected error: {str(e)}"
        }
        return [TextContent(
            type="text",
            text=f"Unexpected error: {str(e)}\n\nRaw Response: {_json_dumps(error_response, ensure_ascii=False)}"
        )]


async def handle_db_query_tables(arguments: Dict[str, Any]) -> List[TextContent]:
    """
    Handle listing tables in a database
    
    Args:
        arguments: Tool arguments
        
    Returns:
        List of tables
    """
    try:
        connection_id = arguments["connection_id"]
        database = arguments["database"]
        schema = arguments.get("schema")
        
        # Get connection info to determine database type
        config = connection_manager.get_connection_info(connection_id)
        if not config:
            raise DatabaseConnectionError(f"Connection {connection_id} not found")
        
        # Query tables based on database type
        schema_filter = "AND table_schema = %s" if schema else ""
        if config.type == DatabaseType.MYSQL:
            query = f"SHOW TABLES FROM {_quote_mysql_identifier(database)}"
            params = None

        elif config.type == DatabaseType.POSTGRESQL:
            query = """
            SELECT table_name, table_schema
            FROM information_schema.tables
            WHERE table_catalog = %s
              AND table_type = 'BASE TABLE'
              AND table_schema NOT IN ('pg_catalog', 'information_schema')
              {schema_filter}
            ORDER BY table_schema, table_name
            """.format(schema_filter=schema_filter)
            params = (database, schema) if schema else (database,)
        elif config.type == DatabaseType.SQLITE:
            query = "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            params = None
        else:
            raise MCPServiceError(f"Listing tables not implemented for {config.type}")
        
        if params is None:
            results = connection_manager.execute_query(connection_id, query)
        else:
            results = connection_manager.execute_query(connection_id, query, params)
        
        # Extract table names
        tables = []
        table_references = []
        for row in results:
            if isinstance(row, dict):
                # Get the first column value (table name)
                table_name = row.get("table_name", list(row.values())[0])
                tables.append(table_name)
                table_references.append(
                    {
                        "table_name": table_name,
                        "schema": row.get("table_schema"),
                    }
                )
        
        response = {
            "success": True,
            "database": database,
            "schema": schema,
            "tables": tables,
            "table_references": table_references,
            "count": len(tables)
        }
        
        return [TextContent(
            type="text",
            text=f"Found {len(tables)} tables in database '{database}'" +
                 (f" schema '{schema}'" if schema else "") + ":\n" +
                 "\n".join(f"- {table}" for table in tables) +
                 f"\n\nRaw Response: {_json_dumps(response, ensure_ascii=False)}"
        )]
        
    except (DatabaseConnectionError, DatabaseQueryError) as e:
        error_response = {
            "success": False,
            "error": "query_failed", 
            "message": str(e)
        }
        return [TextContent(
            type="text",
            text=f"Failed to list tables: {str(e)}\n\nRaw Response: {_json_dumps(error_response, ensure_ascii=False)}"
        )]
        
    except Exception as e:
        logger.error(f"Unexpected error in db_query_tables: {e}")
        error_response = {
            "success": False,
            "error": "unexpected_error",
            "message": f"Unexpected error: {str(e)}"
        }
        return [TextContent(
            type="text",
            text=f"Unexpected error: {str(e)}\n\nRaw Response: {_json_dumps(error_response, ensure_ascii=False)}"
        )]


async def handle_db_query_table_exists(arguments: Dict[str, Any]) -> List[TextContent]:
    """
    Handle checking if table exists
    
    Args:
        arguments: Tool arguments
        
    Returns:
        Boolean result indicating if table exists
    """
    try:
        connection_id = arguments["connection_id"]
        database = arguments["database"]
        table = arguments["table"]
        schema = arguments.get("schema") or None

        # Get connection info to determine database type  
        config = connection_manager.get_connection_info(connection_id)
        if not config:
            raise DatabaseConnectionError(f"Connection {connection_id} not found")
        
        # Query table existence based on database type
        if config.type == DatabaseType.MYSQL:
            query = """
            SELECT COUNT(*) as count
            FROM information_schema.TABLES
            WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
            """
            results = connection_manager.execute_query(connection_id, query, (database, table))

        elif config.type == DatabaseType.POSTGRESQL:
            schema_filter = "AND table_schema = %s" if schema else ""
            query = """
            SELECT COUNT(*) AS count
            FROM information_schema.tables
            WHERE table_catalog = %s
              AND table_name = %s
              AND table_schema NOT IN ('pg_catalog', 'information_schema')
              {schema_filter}
            """.format(schema_filter=schema_filter)
            params = (database, table, schema) if schema else (database, table)
            results = connection_manager.execute_query(connection_id, query, params)
            
        elif config.type == DatabaseType.SQLITE:
            query = """
            SELECT COUNT(*) as count 
            FROM sqlite_master 
            WHERE type='table' AND name = ?
            """
            results = connection_manager.execute_query(connection_id, query, (table,))
            
        else:
            raise MCPServiceError(f"Table existence check not implemented for {config.type}")
        
        exists = results[0]["count"] > 0 if results else False
        
        response = {
            "success": True,
            "database": database,
            "table": table,
            "schema": schema,
            "exists": exists
        }
        
        status = "exists" if exists else "does not exist"
        return [TextContent(
            type="text",
            text=(
                f"Table '{table}' {status} in database '{database}'\n\n"
                f"Raw Response: {_json_dumps(response, ensure_ascii=False)}"
            )
        )]
        
    except (DatabaseConnectionError, DatabaseQueryError) as e:
        error_response = {
            "success": False,
            "error": "query_failed",
            "message": str(e)
        }
        return [TextContent(
            type="text",
            text=f"Failed to check table existence: {str(e)}\n\nRaw Response: {_json_dumps(error_response, ensure_ascii=False)}"
        )]
        
    except Exception as e:
        logger.error(f"Unexpected error in db_query_table_exists: {e}")
        error_response = {
            "success": False,
            "error": "unexpected_error",
            "message": f"Unexpected error: {str(e)}"
        }
        return [TextContent(
            type="text",
            text=f"Unexpected error: {str(e)}\n\nRaw Response: {_json_dumps(error_response, ensure_ascii=False)}"
        )]


async def handle_db_query_execute(arguments: Dict[str, Any]) -> List[TextContent]:
    """
    Handle custom SQL query execution (SELECT only)
    
    Args:
        arguments: Tool arguments
        
    Returns:
        Query results
    """
    try:
        connection_id = arguments["connection_id"]
        query = _validate_read_only_query(arguments["query"])
        limit = arguments.get("limit", 100)

        if isinstance(limit, bool) or not isinstance(limit, int) or not 0 <= limit <= 10_000:
            raise MCPServiceError("The limit must be an integer between 0 and 10000")

        query = _apply_query_limit(query, limit)

        results = connection_manager.execute_query(connection_id, query)
        
        response = {
            "success": True,
            "query": query,
            "row_count": len(results),
            "data": results[:limit]  # Ensure we don't exceed limit
        }
        
        # Format results for display
        if results:
            # Show column headers
            headers = list(results[0].keys())
            result_text = f"Query executed successfully. Found {len(results)} rows.\n\n"
            result_text += "Columns: " + ", ".join(headers) + "\n\n"
            
            # Show first few rows
            display_rows = min(10, len(results))  # Show max 10 rows in text
            for i, row in enumerate(results[:display_rows]):
                result_text += f"Row {i+1}: {dict(row)}\n"
            
            if len(results) > display_rows:
                result_text += f"\n... and {len(results) - display_rows} more rows"
                
        else:
            result_text = "Query executed successfully. No rows returned."
        
        result_text += "\n\nRaw Response: " + _json_dumps(
            response, ensure_ascii=False
        )
        
        return [TextContent(
            type="text",
            text=result_text
        )]
        
    except (DatabaseAnalysisError, DatabaseConnectionError, DatabaseQueryError, MCPServiceError) as e:
        error_response = {
            "success": False,
            "error": "query_failed",
            "message": str(e)
        }
        return [TextContent(
            type="text",
            text=f"Failed to execute query: {str(e)}\n\nRaw Response: {_json_dumps(error_response, ensure_ascii=False)}"
        )]
        
    except Exception as e:
        logger.error(f"Unexpected error in db_query_execute: {e}")
        error_response = {
            "success": False,
            "error": "unexpected_error",
            "message": f"Unexpected error: {str(e)}"
        }
        return [TextContent(
            type="text", 
            text=f"Unexpected error: {str(e)}\n\nRaw Response: {_json_dumps(error_response, ensure_ascii=False)}"
        )]


def _get_java_type_mapping(db_type: DatabaseType, column_type: str, precision: Optional[int] = None, scale: Optional[int] = None) -> Dict[str, Any]:
    """
    Get Java type mapping for database column type
    
    Args:
        db_type: Database type
        column_type: Database column type
        precision: Numeric precision
        scale: Numeric scale
        
    Returns:
        Dict with java_type and imports

    Supported runtime dialects use the same adapter as code generation. The
    legacy YAML mapping remains a fallback for dialects without a registered
    runtime adapter.
    """
    try:
        db_key = (
            db_type.value.lower()
            if isinstance(db_type, DatabaseType)
            else str(db_type).lower()
        )
        if db_key in list_supported_dialects():
            dialect = get_dialect(db_key)
            return {
                "java_type": dialect.java_type_for(column_type),
                "imports": dialect.java_imports_for(column_type),
            }

        config_manager = ConfigManager()
        if hasattr(config_manager, "get_type_mapping"):
            type_mapping = config_manager.get_type_mapping()
        else:
            type_mapping = _load_default_type_mapping()
        
        column_type_upper = column_type.upper().strip()
        base_type = re.sub(r"\([^)]*\)", "", column_type_upper)
        base_type = re.sub(r"\s+", " ", base_type).strip()
        type_candidates = [
            column_type_upper,
            base_type,
            column_type_upper.replace(" ", "_"),
            base_type.replace(" ", "_"),
        ]
        
        if db_key in type_mapping:
            db_mapping = type_mapping[db_key]
            
            # Search in all categories
            for category in db_mapping.values():
                if not isinstance(category, dict):
                    continue
                for candidate in type_candidates:
                    if candidate in category:
                        mapping = category[candidate]
                        return {
                            "java_type": mapping.get("java_type", "Object"),
                            "imports": mapping.get("imports", []),
                        }
        
        # Default fallback
        return {"java_type": "Object", "imports": []}
        
    except Exception as e:
        logger.warning(f"Failed to get Java type mapping: {e}")
        return {"java_type": "Object", "imports": []}


@lru_cache(maxsize=1)
def _load_default_type_mapping() -> Dict[str, Any]:
    """Load the YAML mapping blocks embedded in the project reference file."""
    try:
        import yaml

        path = Path(__file__).resolve().parents[1] / "config" / "default_type_mapping.yaml"
        text = path.read_text(encoding="utf-8")
        mapping: Dict[str, Any] = {}
        for block in re.findall(r"```yaml\s*(.*?)```", text, flags=re.DOTALL):
            loaded = yaml.safe_load(block)
            if isinstance(loaded, dict):
                mapping.update(loaded)
        return mapping
    except Exception as exc:
        logger.warning("Failed to load default type mapping: %s", exc)
        return {}


async def handle_db_table_describe(arguments: Dict[str, Any]) -> List[TextContent]:
    """
    Handle table structure description
    
    Args:
        arguments: Tool arguments
        
    Returns:
        Complete table structure information
    """
    try:
        connection_id = arguments["connection_id"]
        database = arguments["database"]
        table = arguments["table"]
        schema = arguments.get("schema") or None
        include_java_types = arguments.get("include_java_types", True)
        introspector = DatabaseIntrospector(connection_manager)
        config = introspector.get_config(connection_id)
        metadata = introspector.describe_table(connection_id, table, schema)
        columns = []
        java_imports = set()

        for row in metadata["columns"]:
            column_info = {
                "name": row["name"],
                "data_type": row["type"],
                "column_type": row["column_type"],
                "nullable": row["nullable"],
                "default_value": row["default_value"],
                "comment": row["comment"],
                "is_primary_key": row["primary_key"],
                "precision": row["precision"],
                "scale": row["scale"],
                "max_length": row["max_length"],
            }

            # Add Java type mapping if requested
            if include_java_types:
                java_mapping = _get_java_type_mapping(
                    config.type,
                    row["column_type"] or row["type"],
                    row["precision"],
                    row["scale"],
                )
                column_info["java_type"] = java_mapping["java_type"]
                java_imports.update(java_mapping["imports"])

            columns.append(column_info)

        response = {
            "success": True,
            "database": database,
            "table": table,
            "schema": metadata["schema"],
            "comment": metadata["comment"],
            "columns": columns,
            "column_count": len(columns),
            "java_imports": sorted(list(java_imports)) if include_java_types else []
        }
        
        # Format display text
        result_text = f"Table Structure: {database}.{table}\n"
        if metadata["comment"]:
            result_text += f"Comment: {metadata['comment']}\n"
        result_text += f"\nColumns ({len(columns)}):\n\n"
        
        for i, col in enumerate(columns, 1):
            result_text += f"{i:2d}. {col['name']}\n"
            result_text += f"    Type: {col['column_type']} ({col['data_type']})\n"
            if include_java_types:
                result_text += f"    Java: {col['java_type']}\n"
            result_text += f"    Nullable: {col['nullable']}\n"
            if col['is_primary_key']:
                result_text += "    Primary Key: YES\n"
            if col['default_value'] is not None:
                result_text += f"    Default: {col['default_value']}\n"
            if col['comment']:
                result_text += f"    Comment: {col['comment']}\n"
            result_text += "\n"
        
        if include_java_types and java_imports:
            result_text += "Required Java imports:\n"
            for imp in sorted(java_imports):
                result_text += f"import {imp};\n"
        
        result_text += f"\nRaw Response: {_json_dumps(response, ensure_ascii=False)}"
        
        return [TextContent(
            type="text",
            text=result_text
        )]
        
    except (DatabaseAnalysisError, DatabaseConnectionError, DatabaseQueryError, MCPServiceError) as e:
        error_response = {
            "success": False,
            "error": "analysis_failed",
            "message": str(e)
        }
        return [TextContent(
            type="text",
            text=f"Failed to describe table: {str(e)}\n\nRaw Response: {_json_dumps(error_response, ensure_ascii=False)}"
        )]
        
    except Exception as e:
        logger.error(f"Unexpected error in db_table_describe: {e}")
        error_response = {
            "success": False,
            "error": "unexpected_error",
            "message": f"Unexpected error: {str(e)}"
        }
        return [TextContent(
            type="text",
            text=f"Unexpected error: {str(e)}\n\nRaw Response: {_json_dumps(error_response, ensure_ascii=False)}"
        )]


async def handle_db_table_columns(arguments: Dict[str, Any]) -> List[TextContent]:
    """
    Handle getting detailed column information
    
    Args:
        arguments: Tool arguments
        
    Returns:
        Detailed column information
    """
    try:
        connection_id = arguments["connection_id"]
        database = arguments["database"]
        table = arguments["table"]
        schema = arguments.get("schema") or None

        # Get connection info to determine database type
        config = connection_manager.get_connection_info(connection_id)
        if not config:
            raise DatabaseConnectionError(f"Connection {connection_id} not found")
        
        # Query column information
        if config.type == DatabaseType.MYSQL:
            query = """
            SELECT 
                COLUMN_NAME,
                DATA_TYPE,
                COLUMN_TYPE,
                IS_NULLABLE,
                COLUMN_DEFAULT,
                COLUMN_COMMENT,
                NUMERIC_PRECISION,
                NUMERIC_SCALE,
                CHARACTER_MAXIMUM_LENGTH,
                ORDINAL_POSITION
            FROM information_schema.COLUMNS 
            WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
            ORDER BY ORDINAL_POSITION
            """
            results = connection_manager.execute_query(connection_id, query, (database, table))

        elif config.type == DatabaseType.POSTGRESQL:
            columns = DatabaseIntrospector(connection_manager).get_columns(
                connection_id, table, schema
            )
            results = [
                {
                    "COLUMN_NAME": column["name"],
                    "DATA_TYPE": column["type"],
                    "COLUMN_TYPE": column["column_type"],
                    "IS_NULLABLE": "YES" if column["nullable"] else "NO",
                    "COLUMN_DEFAULT": column["default_value"],
                    "COLUMN_COMMENT": column["comment"],
                    "NUMERIC_PRECISION": column["precision"],
                    "NUMERIC_SCALE": column["scale"],
                    "CHARACTER_MAXIMUM_LENGTH": column["max_length"],
                    "ORDINAL_POSITION": position,
                }
                for position, column in enumerate(columns, 1)
            ]
            
        elif config.type == DatabaseType.SQLITE:
            columns = DatabaseIntrospector(connection_manager).get_columns(
                connection_id, table, schema
            )
            results = [
                {
                    "COLUMN_NAME": column["name"],
                    "DATA_TYPE": column["type"],
                    "COLUMN_TYPE": column["column_type"],
                    "IS_NULLABLE": "YES" if column["nullable"] else "NO",
                    "COLUMN_DEFAULT": column["default_value"],
                    "COLUMN_COMMENT": column["comment"],
                    "NUMERIC_PRECISION": column["precision"],
                    "NUMERIC_SCALE": column["scale"],
                    "CHARACTER_MAXIMUM_LENGTH": column["max_length"],
                    "ORDINAL_POSITION": position,
                }
                for position, column in enumerate(columns, 1)
            ]
        else:
            raise MCPServiceError(f"Column analysis not implemented for {config.type}")
        
        if not results:
            raise DatabaseQueryError(f"Table '{table}' not found in database '{database}'")
        
        response = {
            "success": True,
            "database": database,
            "table": table,
            "columns": [dict(row) for row in results]
        }
        
        # Format display
        result_text = f"Columns for table: {database}.{table}\n\n"
        for row in results:
            result_text += f"Column: {row['COLUMN_NAME']}\n"
            result_text += f"  Type: {row['COLUMN_TYPE']}\n"
            result_text += f"  Nullable: {row['IS_NULLABLE']}\n"
            if row['COLUMN_DEFAULT'] is not None:
                result_text += f"  Default: {row['COLUMN_DEFAULT']}\n"
            if row.get('COLUMN_COMMENT'):
                result_text += f"  Comment: {row['COLUMN_COMMENT']}\n"
            result_text += "\n"
        
        result_text += f"Raw Response: {_json_dumps(response, ensure_ascii=False)}"
        
        return [TextContent(
            type="text",
            text=result_text
        )]
        
    except (DatabaseAnalysisError, DatabaseConnectionError, DatabaseQueryError, MCPServiceError) as e:
        error_response = {
            "success": False,
            "error": "query_failed",
            "message": str(e)
        }
        return [TextContent(
            type="text",
            text=f"Failed to get column information: {str(e)}\n\nRaw Response: {_json_dumps(error_response, ensure_ascii=False)}"
        )]
        
    except Exception as e:
        logger.error(f"Unexpected error in db_table_columns: {e}")
        error_response = {
            "success": False,
            "error": "unexpected_error",
            "message": f"Unexpected error: {str(e)}"
        }
        return [TextContent(
            type="text",
            text=f"Unexpected error: {str(e)}\n\nRaw Response: {_json_dumps(error_response, ensure_ascii=False)}"
        )]


async def handle_db_table_primary_keys(arguments: Dict[str, Any]) -> List[TextContent]:
    """
    Handle getting primary key information
    
    Args:
        arguments: Tool arguments
        
    Returns:
        Primary key information
    """
    try:
        connection_id = arguments["connection_id"]
        database = arguments["database"]
        table = arguments["table"]
        schema = arguments.get("schema") or None

        # Get connection info to determine database type
        config = connection_manager.get_connection_info(connection_id)
        if not config:
            raise DatabaseConnectionError(f"Connection {connection_id} not found")
        
        # Query primary keys
        if config.type == DatabaseType.MYSQL:
            query = """
            SELECT 
                COLUMN_NAME,
                ORDINAL_POSITION
            FROM information_schema.KEY_COLUMN_USAGE
            WHERE TABLE_SCHEMA = %s 
              AND TABLE_NAME = %s 
              AND CONSTRAINT_NAME = 'PRIMARY'
            ORDER BY ORDINAL_POSITION
            """
            results = connection_manager.execute_query(connection_id, query, (database, table))

        elif config.type == DatabaseType.POSTGRESQL:
            primary_keys = DatabaseIntrospector(connection_manager).get_primary_keys(
                connection_id, table, schema
            )
            results = [
                {"COLUMN_NAME": column_name, "ORDINAL_POSITION": position}
                for position, column_name in enumerate(primary_keys, 1)
            ]
            
        elif config.type == DatabaseType.SQLITE:
            primary_keys = DatabaseIntrospector(connection_manager).get_primary_keys(
                connection_id, table, schema
            )
            results = [
                {"COLUMN_NAME": column_name, "ORDINAL_POSITION": position}
                for position, column_name in enumerate(primary_keys, 1)
            ]
        else:
            raise MCPServiceError(f"Primary key analysis not implemented for {config.type}")
        
        primary_keys = [row["COLUMN_NAME"] for row in results]
        
        response = {
            "success": True,
            "database": database,
            "table": table,
            "primary_keys": primary_keys,
            "key_count": len(primary_keys)
        }
        
        if primary_keys:
            key_list = ", ".join(primary_keys)
            result_text = f"Primary keys for table {database}.{table}:\n{key_list}\n"
        else:
            result_text = f"No primary keys found for table {database}.{table}\n"
        
        result_text += f"\nRaw Response: {_json_dumps(response, ensure_ascii=False)}"
        
        return [TextContent(
            type="text",
            text=result_text
        )]
        
    except (DatabaseAnalysisError, DatabaseConnectionError, DatabaseQueryError, MCPServiceError) as e:
        error_response = {
            "success": False,
            "error": "query_failed",
            "message": str(e)
        }
        return [TextContent(
            type="text",
            text=f"Failed to get primary keys: {str(e)}\n\nRaw Response: {_json_dumps(error_response, ensure_ascii=False)}"
        )]
        
    except Exception as e:
        logger.error(f"Unexpected error in db_table_primary_keys: {e}")
        error_response = {
            "success": False,
            "error": "unexpected_error",
            "message": f"Unexpected error: {str(e)}"
        }
        return [TextContent(
            type="text",
            text=f"Unexpected error: {str(e)}\n\nRaw Response: {_json_dumps(error_response, ensure_ascii=False)}"
        )]


async def handle_db_table_foreign_keys(arguments: Dict[str, Any]) -> List[TextContent]:
    """
    Handle getting foreign key information
    
    Args:
        arguments: Tool arguments
        
    Returns:
        Foreign key relationship information
    """
    try:
        connection_id = arguments["connection_id"]
        database = arguments["database"]
        table = arguments["table"]
        schema = arguments.get("schema") or None

        # Get connection info to determine database type
        config = connection_manager.get_connection_info(connection_id)
        if not config:
            raise DatabaseConnectionError(f"Connection {connection_id} not found")
        
        # Query foreign keys
        if config.type == DatabaseType.MYSQL:
            query = """
            SELECT 
                kcu.COLUMN_NAME,
                kcu.REFERENCED_TABLE_SCHEMA,
                kcu.REFERENCED_TABLE_NAME,
                kcu.REFERENCED_COLUMN_NAME,
                rc.CONSTRAINT_NAME,
                rc.UPDATE_RULE,
                rc.DELETE_RULE
            FROM information_schema.KEY_COLUMN_USAGE kcu
            JOIN information_schema.REFERENTIAL_CONSTRAINTS rc 
                ON kcu.CONSTRAINT_NAME = rc.CONSTRAINT_NAME
                AND kcu.TABLE_SCHEMA = rc.CONSTRAINT_SCHEMA
            WHERE kcu.TABLE_SCHEMA = %s 
              AND kcu.TABLE_NAME = %s
              AND kcu.REFERENCED_TABLE_NAME IS NOT NULL
            ORDER BY kcu.ORDINAL_POSITION
            """
            results = connection_manager.execute_query(connection_id, query, (database, table))

        elif config.type == DatabaseType.POSTGRESQL:
            foreign_keys = DatabaseIntrospector(connection_manager).get_foreign_keys(
                connection_id, table, schema
            )
            results = [
                {
                    "COLUMN_NAME": foreign_key["column_name"],
                    "REFERENCED_TABLE_SCHEMA": schema or "",
                    "REFERENCED_TABLE_NAME": foreign_key["referenced_table"],
                    "REFERENCED_COLUMN_NAME": foreign_key["referenced_column"],
                    "CONSTRAINT_NAME": foreign_key["constraint_name"],
                    "UPDATE_RULE": "",
                    "DELETE_RULE": "",
                }
                for foreign_key in foreign_keys
            ]
            
        elif config.type == DatabaseType.SQLITE:
            foreign_keys = DatabaseIntrospector(connection_manager).get_foreign_keys(
                connection_id, table, schema
            )
            results = [
                {
                    "COLUMN_NAME": foreign_key["column_name"],
                    "REFERENCED_TABLE_SCHEMA": database,
                    "REFERENCED_TABLE_NAME": foreign_key["referenced_table"],
                    "REFERENCED_COLUMN_NAME": foreign_key["referenced_column"],
                    "CONSTRAINT_NAME": foreign_key["constraint_name"],
                    "UPDATE_RULE": "",
                    "DELETE_RULE": "",
                }
                for foreign_key in foreign_keys
            ]
        else:
            raise MCPServiceError(f"Foreign key analysis not implemented for {config.type}")
        
        foreign_keys = []
        for row in results:
            foreign_keys.append({
                "column": row["COLUMN_NAME"],
                "references_table": row["REFERENCED_TABLE_NAME"],
                "references_column": row["REFERENCED_COLUMN_NAME"],
                "constraint_name": row["CONSTRAINT_NAME"],
                "on_update": row.get("UPDATE_RULE", ""),
                "on_delete": row.get("DELETE_RULE", "")
            })
        
        response = {
            "success": True,
            "database": database,
            "table": table,
            "foreign_keys": foreign_keys,
            "fk_count": len(foreign_keys)
        }
        
        if foreign_keys:
            result_text = f"Foreign keys for table {database}.{table}:\n\n"
            for i, fk in enumerate(foreign_keys, 1):
                result_text += f"{i}. {fk['column']} → {fk['references_table']}.{fk['references_column']}\n"
                result_text += f"   Constraint: {fk['constraint_name']}\n"
                if fk['on_update']:
                    result_text += f"   On Update: {fk['on_update']}\n"
                if fk['on_delete']:
                    result_text += f"   On Delete: {fk['on_delete']}\n"
                result_text += "\n"
        else:
            result_text = f"No foreign keys found for table {database}.{table}\n"
        
        result_text += f"Raw Response: {_json_dumps(response, ensure_ascii=False)}"
        
        return [TextContent(
            type="text",
            text=result_text
        )]
        
    except (DatabaseAnalysisError, DatabaseConnectionError, DatabaseQueryError, MCPServiceError) as e:
        error_response = {
            "success": False,
            "error": "query_failed",
            "message": str(e)
        }
        return [TextContent(
            type="text",
            text=f"Failed to get foreign keys: {str(e)}\n\nRaw Response: {_json_dumps(error_response, ensure_ascii=False)}"
        )]
        
    except Exception as e:
        logger.error(f"Unexpected error in db_table_foreign_keys: {e}")
        error_response = {
            "success": False,
            "error": "unexpected_error", 
            "message": f"Unexpected error: {str(e)}"
        }
        return [TextContent(
            type="text",
            text=f"Unexpected error: {str(e)}\n\nRaw Response: {_json_dumps(error_response, ensure_ascii=False)}"
        )]


async def handle_db_table_indexes(arguments: Dict[str, Any]) -> List[TextContent]:
    """
    Handle getting table index information
    
    Args:
        arguments: Tool arguments
        
    Returns:
        Index information for the table
    """
    try:
        connection_id = arguments["connection_id"]
        database = arguments["database"]
        table = arguments["table"]
        schema = arguments.get("schema") or None

        # Get connection info to determine database type
        config = connection_manager.get_connection_info(connection_id)
        if not config:
            raise DatabaseConnectionError(f"Connection {connection_id} not found")
        
        # Query indexes based on database type
        if config.type == DatabaseType.MYSQL:
            query = """
            SELECT 
                INDEX_NAME,
                COLUMN_NAME,
                SEQ_IN_INDEX,
                NON_UNIQUE,
                INDEX_TYPE,
                NULLABLE,
                INDEX_COMMENT
            FROM information_schema.STATISTICS
            WHERE TABLE_SCHEMA = %s 
              AND TABLE_NAME = %s
            ORDER BY INDEX_NAME, SEQ_IN_INDEX
            """
            results = connection_manager.execute_query(connection_id, query, (database, table))

        elif config.type == DatabaseType.POSTGRESQL:
            indexes = DatabaseIntrospector(connection_manager).get_indexes(
                connection_id, table, schema
            )
            results = [
                {
                    "INDEX_NAME": index["key_name"],
                    "COLUMN_NAME": index["column_name"],
                    "SEQ_IN_INDEX": index["seq_in_index"],
                    "NON_UNIQUE": 0 if index["unique"] else 1,
                    "INDEX_TYPE": index["index_type"],
                    "NULLABLE": "",
                    "INDEX_COMMENT": "",
                }
                for index in indexes
            ]

        elif config.type == DatabaseType.SQLITE:
            indexes = DatabaseIntrospector(connection_manager).get_indexes(
                connection_id, table, schema
            )
            results = [
                {
                    "INDEX_NAME": index["key_name"],
                    "COLUMN_NAME": index["column_name"],
                    "SEQ_IN_INDEX": index["seq_in_index"],
                    "NON_UNIQUE": 0 if index["unique"] else 1,
                    "INDEX_TYPE": index["index_type"],
                    "NULLABLE": "",
                    "INDEX_COMMENT": "",
                }
                for index in indexes
            ]
        else:
            raise MCPServiceError(f"Index analysis not implemented for {config.type}")
        
        # Process index information
        indexes = {}
        for row in results:
            index_name = row["INDEX_NAME"]
            if index_name not in indexes:
                indexes[index_name] = {
                    "name": index_name,
                    "unique": row["NON_UNIQUE"] == 0,
                    "type": row.get("INDEX_TYPE", "BTREE"),
                    "comment": row.get("INDEX_COMMENT", ""),
                    "columns": []
                }
            
            indexes[index_name]["columns"].append({
                "name": row["COLUMN_NAME"],
                "position": row["SEQ_IN_INDEX"],
                "nullable": row.get("NULLABLE", "")
            })
        
        # Sort columns within each index by position
        for index_info in indexes.values():
            index_info["columns"].sort(key=lambda x: x["position"])
        
        index_list = list(indexes.values())
        
        response = {
            "success": True,
            "database": database,
            "table": table,
            "indexes": index_list,
            "index_count": len(index_list)
        }
        
        # Format display
        if index_list:
            result_text = f"Indexes for table {database}.{table}:\n\n"
            for i, idx in enumerate(index_list, 1):
                result_text += f"{i}. Index: {idx['name']}\n"
                result_text += f"   Type: {idx['type']}\n"
                result_text += f"   Unique: {'Yes' if idx['unique'] else 'No'}\n"
                
                columns = [col['name'] for col in idx['columns']]
                result_text += f"   Columns: {', '.join(columns)}\n"
                
                if idx['comment']:
                    result_text += f"   Comment: {idx['comment']}\n"
                result_text += "\n"
        else:
            result_text = f"No indexes found for table {database}.{table}\n"
        
        result_text += f"Raw Response: {_json_dumps(response, ensure_ascii=False)}"
        
        return [TextContent(
            type="text",
            text=result_text
        )]
        
    except (DatabaseConnectionError, DatabaseQueryError, MCPServiceError) as e:
        error_response = {
            "success": False,
            "error": "query_failed",
            "message": str(e)
        }
        return [TextContent(
            type="text",
            text=f"Failed to get table indexes: {str(e)}\n\nRaw Response: {_json_dumps(error_response, ensure_ascii=False)}"
        )]
        
    except Exception as e:
        logger.error(f"Unexpected error in db_table_indexes: {e}")
        error_response = {
            "success": False,
            "error": "unexpected_error",
            "message": f"Unexpected error: {str(e)}"
        }
        return [TextContent(
            type="text",
            text=f"Unexpected error: {str(e)}\n\nRaw Response: {_json_dumps(error_response, ensure_ascii=False)}"
        )]


def get_codegen_tools() -> List[Tool]:
    """
    Get list of code generation MCP tools
    
    Returns:
        List of code generation MCP Tool objects
    """
    from ..generator.template_context import TemplateConfigManager

    template_categories = TemplateConfigManager.get_supported_categories()
    return [
        Tool(
            name="db_codegen_analyze",
            description="Analyze database table structure for code generation with template context",
            inputSchema={
                "type": "object",
                "properties": {
                    "connection_id": {
                        "type": "string",
                        "description": "Database connection ID"
                    },
                    "table_name": {
                        "type": "string",
                        "description": "Table name to analyze"
                    },
                    "database": {
                        "type": "string",
                        "description": "Database name (optional, uses connection default if not specified)"
                    },
                    "schema": {
                        "type": "string",
                        "description": "PostgreSQL schema (optional; required for ambiguous table names)"
                    },
                    "template_category": {
                        "type": "string",
                        "description": "Template category to use for context building",
                        "enum": template_categories,
                        "default": "MybatisPlus-Mixed"
                    },
                    "author": {
                        "type": "string",
                        "description": "Author name for code generation",
                        "default": "ZXP"
                    },
                    "package_name": {
                        "type": "string",
                        "description": "Java package name for generated code",
                        "default": "com.example.generated"
                    },
                    "generate_dto": {
                        "type": "boolean",
                        "description": "Generate a DTO artifact when supported",
                        "default": False
                    },
                    "generate_vo": {
                        "type": "boolean",
                        "description": "Generate a VO artifact when supported",
                        "default": False
                    },
                    "project_path": {
                        "type": "string",
                        "description": "Target Spring Boot project path (with src/main/java)",
                        "default": "test_project"
                    }
                },
                "required": ["connection_id", "table_name"]
            }
        ),
        Tool(
            name="db_codegen_generate",
            description=(
                "[Legacy / single-shot] Generate Java code from database table analysis using templates. "
                "Prefer the atomic workflow: codegen_build_context + codegen_render_entity/dao/service/"
                "controller/mapper (P2.2). This single-shot tool also writes files to disk in one go, "
                "with no preview/edit cycle."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "connection_id": {
                        "type": "string",
                        "description": "Database connection ID"
                    },
                    "table_name": {
                        "type": "string", 
                        "description": "Table name to generate code for"
                    },
                    "database": {
                        "type": "string",
                        "description": "Database name (optional, uses connection default if not specified)"
                    },
                    "schema": {
                        "type": "string",
                        "description": "PostgreSQL schema (optional; required for ambiguous table names)"
                    },
                    "template_category": {
                        "type": "string",
                        "description": "Template category to use for code generation",
                        "enum": template_categories,
                        "default": "MybatisPlus-Mixed"
                    },
                    "author": {
                        "type": "string",
                        "description": "Author name for generated code",
                        "default": "ZXP"
                    },
                    "package_name": {
                        "type": "string",
                        "description": "Java package name for generated code",
                        "default": "com.example.generated"
                    },
                    "project_path": {
                        "type": "string",
                        "description": "Target Spring Boot project path (with src/main/java)",
                        "default": "test_project"
                    },
                    "output_dir": {
                        "type": "string",
                        "description": "Optional explicit output directory; defaults to the project source structure"
                    },
                    "generate_dto": {
                        "type": "boolean",
                        "description": "Generate a DTO artifact when supported",
                        "default": False
                    },
                    "generate_vo": {
                        "type": "boolean",
                        "description": "Generate a VO artifact when supported",
                        "default": False
                    },
                    "include_swagger": {
                        "type": "boolean",
                        "description": "Include Swagger annotations in generated code",
                        "default": True
                    },
                    "include_lombok": {
                        "type": "boolean",
                        "description": "Include Lombok annotations in generated code",
                        "default": True
                    },
                    "include_mapstruct": {
                        "type": "boolean",
                        "description": "Include MapStruct mappers in generated code",
                        "default": True
                    }
                },
                "required": ["connection_id", "table_name"]
            }
        )
    ]


async def handle_db_codegen_analyze(arguments: Dict[str, Any]) -> List[TextContent]:
    """
    Handle analyzing database table structure for code generation
    
    Args:
        arguments: Tool arguments
        
    Returns:
        Code generation analysis results with template context
    """
    try:
        from .codegen_tools import CodegenAnalyzer
        
        connection_id = arguments["connection_id"]
        table_name = arguments["table_name"]
        database = arguments.get("database")
        schema = arguments.get("schema") or None
        template_category = arguments.get("template_category", "MybatisPlus-Mixed")
        author = arguments.get("author", "ZXP")
        package_name = arguments.get("package_name", "com.example.generated")
        generate_dto = arguments.get("generate_dto")
        generate_vo = arguments.get("generate_vo")
        
        # Validate connection exists
        config = connection_manager.get_connection_info(connection_id)
        if not config:
            raise DatabaseConnectionError(f"Connection {connection_id} not found")
        
        # Use database from connection if not specified
        if not database:
            database = config.database or "information_schema"
        
        # Initialize analyzer
        analyzer = CodegenAnalyzer(connection_manager)
        
        # Analyze table for code generation (with project stack detection)
        project_path = arguments.get("project_path")
        proj_struct = _detect_project_structure(project_path)
        project_root = str(proj_struct["project_root"]) if proj_struct.get("project_root") else None
        analysis_result = await analyzer.analyze_table_for_codegen(
            connection_id,
            table_name,
            template_category=template_category,
            project_root=project_root,
            schema=schema,
        )
        
        # Update template context with user-provided values
        analysis_result["template_context"].update({
            "author": author,
            "packageName": package_name,
            "hasPackageName": bool(package_name),
            "templateCategory": template_category,
            "isDefault": template_category == "Default",
            "isMybatisPlus": template_category == "MybatisPlus",
            "isMybatisPlusMixed": template_category == "MybatisPlus-Mixed",
            "isSb35Java21": template_category == "sb35-java21",
        })
        from ..generator.template_context import apply_generation_options

        apply_generation_options(
            analysis_result["template_context"],
            generate_dto=generate_dto,
            generate_vo=generate_vo,
        )
        
        # Format response text
        result_text = f"Code Generation Analysis: {table_name}\n"
        result_text += f"Template Category: {template_category}\n"
        result_text += f"Package Name: {package_name}\n"
        result_text += f"Author: {author}\n\n"
        
        # Table info
        table_info = analysis_result["table_info"]
        result_text += f"Table: {table_info['name']}\n"
        if table_info.get("comment"):
            result_text += f"Comment: {table_info['comment']}\n"
        result_text += f"Columns: {len(table_info['columns'])}\n\n"
        
        # Java types and imports
        java_types = analysis_result["java_types"]
        result_text += f"Java Types Used: {', '.join(java_types)}\n"
        
        imports = analysis_result["imports_needed"]
        if imports:
            result_text += f"Required Imports: {', '.join(imports)}\n"
        
        result_text += "\nColumn Details:\n"
        for col in table_info['columns']:
            result_text += f"  {col['name']} ({col['type']}) -> Java: {analysis_result['template_context']['columns'][table_info['columns'].index(col)]['javaType']}\n"
        
        # Relationships
        relationships = analysis_result["relationships"]
        if relationships["primary_keys"]:
            result_text += f"\nPrimary Keys: {', '.join(relationships['primary_keys'])}\n"
        
        if relationships["foreign_keys"]:
            result_text += f"Foreign Keys: {len(relationships['foreign_keys'])} relationships\n"
        
        if relationships["indexes"]:
            result_text += f"Indexes: {len(relationships['indexes'])} indexes\n"
        
        # Template context summary
        context = analysis_result["template_context"]
        result_text += "\nTemplate Context Generated:\n"
        result_text += f"  Entity Class Name: {context.get('className', context.get('name', 'Unknown'))}\n"
        result_text += f"  Variable Name: {context.get('lowerCaseName', context.get('entityNameLowerCase', 'unknown'))}\n"
        result_text += f"  Has Date Fields: {context.get('hasDateField', False)}\n"
        result_text += f"  Has BigDecimal Fields: {context.get('hasBigDecimalField', False)}\n"
        result_text += f"  Has Primary Key: {'Yes' if context.get('primaryKey') else 'No'}\n"
        
        # Keep a structured payload for non-MCP callers such as the CLI.
        result_text += "\n\nRaw Response: " + _json_dumps(
            {"success": True, **analysis_result}, ensure_ascii=False
        )
        
        return [TextContent(
            type="text",
            text=result_text
        )]
        
    except (DatabaseConnectionError, DatabaseQueryError, MCPServiceError) as e:
        error_response = {
            "success": False,
            "error": "analysis_failed",
            "message": str(e)
        }
        return [TextContent(
            type="text",
            text=f"Failed to analyze table for code generation: {str(e)}\n\nRaw Response: {_json_dumps(error_response, ensure_ascii=False)}"
        )]
        
    except Exception as e:
        logger.error(f"Unexpected error in db_codegen_analyze: {e}")
        error_response = {
            "success": False,
            "error": "unexpected_error",
            "message": f"Unexpected error: {str(e)}"
        }
        return [TextContent(
            type="text",
            text=f"Unexpected error: {str(e)}\n\nRaw Response: {_json_dumps(error_response, ensure_ascii=False)}"
        )]


async def handle_db_codegen_generate(arguments: Dict[str, Any]) -> List[TextContent]:
    """
    Handle generating Java code from database table analysis
    Enhanced with pre-generation project validation
    
    Args:
        arguments: Tool arguments
        
    Returns:
        Generated Java code files with project validation
    """
    try:
        from .codegen_tools import CodegenAnalyzer, CodegenGenerator
        
        connection_id = arguments["connection_id"]
        table_name = arguments["table_name"]
        database = arguments.get("database")
        schema = arguments.get("schema") or None
        template_category = arguments.get("template_category", "MybatisPlus-Mixed")
        author = arguments.get("author", "ZXP")
        package_name = arguments.get("package_name", "com.example.generated")
        include_swagger = arguments.get("include_swagger", True)
        include_lombok = arguments.get("include_lombok", True)
        include_mapstruct = arguments.get("include_mapstruct", True)
        generate_dto = arguments.get("generate_dto")
        generate_vo = arguments.get("generate_vo")
        project_path = arguments.get("project_path")
        output_dir_arg = arguments.get("output_dir")
        
        # Validate connection exists
        config = connection_manager.get_connection_info(connection_id)
        if not config:
            raise DatabaseConnectionError(f"Connection {connection_id} not found")
        
        # Use database from connection if not specified
        if not database:
            database = config.database or "information_schema"
        
        # ===== STEP 0: 项目环境预检查（包含依赖分析） =====
        logger.info("🔍 Starting comprehensive project environment validation...")
        validation_args = {
            "check_dependencies": True,
            "create_missing_dirs": True,
            "template_category": template_category
        }
        if project_path:
            validation_args["project_path"] = project_path
        
        validation_result = await handle_springboot_validate_project(validation_args)
        validation_text = validation_result[0].text if validation_result else "Validation failed"
        
        # 仅当项目结构不可用时阻断；依赖问题仅提示
        structure_ok = ("Project Structure: ✅ OK" in validation_text) or ("✅ Project Root" in validation_text)
        if not structure_ok:
            return [TextContent(
                type="text",
                text=(
                    "❌ Code generation aborted: project structure not ready.\n\n"
                    + validation_text +
                    "\n\n💡 Try 'springboot_validate_project' with create_missing_dirs=true."
                )
            )]
        
        # ===== STEP 0.5: 智能依赖分析 =====
        logger.info("🔍 Performing intelligent dependency analysis...")
        dependency_args = {
            "template_category": template_category,
            "database_type": config.type.name.lower(),
            "include_swagger": include_swagger,
            "include_lombok": include_lombok,
            "include_mapstruct": include_mapstruct
        }
        if project_path:
            dependency_args["project_path"] = project_path
        
        dependency_analysis = await handle_springboot_analyze_dependencies(dependency_args)
        dependency_text = dependency_analysis[0].text if dependency_analysis else "Dependency analysis failed"
        
        # 从新的智能适配系统提取信息
        needs_attention = "需要关注" in dependency_text or "Critical" in dependency_text
        gaps_found_match = re.search(r'Missing Dependencies: (\d+)', dependency_text)
        gaps_count = int(gaps_found_match.group(1)) if gaps_found_match else 0
        
        # 计算健康度（基于缺口数量）
        if gaps_count == 0:
            health_score = 100
        elif gaps_count <= 2:
            health_score = 80
        elif gaps_count <= 5:
            health_score = 60
        else:
            health_score = 40
        
        # 如果依赖健康度低于60%，给出警告但不阻止生成
        dependency_warnings = []
        if health_score < 60:
            dependency_warnings.append(f"⚠️ Dependency Health Score: {health_score}% - Consider reviewing dependencies")
        
        if needs_attention:
            dependency_warnings.append("⚠️ Multiple dependency issues detected - Generated code may not compile correctly")
        
        # ===== STEP 1: 获取数据库所有表名以支持前缀分析 =====
        logger.info("🔍 Getting all table names for package structure optimization...")
        all_table_names = _collect_codegen_table_names(connection_id, table_name)
        logger.info(f"Found {len(all_table_names)} tables for prefix analysis: {all_table_names}")
        
        # ===== STEP 2: 分析表结构（包含前缀优化） =====
        # Initialize analyzer and generator
        analyzer = CodegenAnalyzer(connection_manager)
        generator = CodegenGenerator()
        
        # Step 1: Analyze table structure with all table names for prefix optimization
        _ps = _detect_project_structure(project_path)
        analysis_result = await analyzer.analyze_table_for_codegen(
            connection_id,
            table_name,
            all_table_names=all_table_names,  # 传递所有表名用于前缀分析
            template_category=template_category,
            project_root=str(_ps["project_root"]) if _ps.get("project_root") else None,
            schema=schema,
        )
        
        # Step 2: Update template context with user preferences
        analysis_result["template_context"].update({
            "author": author,
            "packageName": package_name,
            "hasPackageName": bool(package_name),
            "templateCategory": template_category,
            "isDefault": template_category == "Default",
            "isSb35Java21": template_category == "sb35-java21",
            "isMybatisPlus": template_category == "MybatisPlus",
            "isMybatisPlusMixed": template_category == "MybatisPlus-Mixed",
            "useSwagger": include_swagger,
            "useLombok": include_lombok,
            "useMapStruct": include_mapstruct,
        })

        # Recompute package-related paths based on provided package_name
        try:
            ctx = analysis_result["template_context"]
            base_pkg = package_name or ctx.get("packageName") or ctx.get("package") or "com.example"
            suffix = ctx.get("packageSuffix") or ""
            def with_suffix(kind: str) -> str:
                return f"{base_pkg}.{kind}.{suffix}" if suffix else f"{base_pkg}.{kind}"
            ctx.update({
                "package": base_pkg,
                "packageName": base_pkg,
                "basePackage": base_pkg,
                "controllerPackage": with_suffix("controller"),
                "servicePackage": with_suffix("service"),
                "entityPackage": with_suffix("entity"),
                "daoPackage": with_suffix("dao"),
                "dtoPackage": with_suffix("dto"),
                "voPackage": with_suffix("vo"),
                "serviceImplPackage": (f"{base_pkg}.service.impl.{suffix}" if suffix else f"{base_pkg}.service.impl"),
            })
            # Normalize tech flags to avoid mixing stacks: prefer SpringDoc over Swagger2 when both present
            if ctx.get("hasSpringDoc"):
                ctx["hasSwagger2"] = False
            elif ctx.get("hasSwagger2"):
                ctx["hasSpringDoc"] = False
            # Prefer Jakarta over Javax when both present
            if ctx.get("hasJakarta"):
                ctx["hasJavax"] = False
            elif ctx.get("hasJavax"):
                ctx["hasJakarta"] = False
        except Exception:
            pass

        from ..generator.template_context import apply_generation_options

        apply_generation_options(
            analysis_result["template_context"],
            generate_dto=generate_dto,
            generate_vo=generate_vo,
        )

        # ===== STEP 3: 生成代码 =====
        generation_config = {
            "author": author,
            "package_name": package_name,
            "output_dir": output_dir_arg or "generated_output",
            "generate_dto": generate_dto,
            "generate_vo": generate_vo,
        }
        
        generation_result = await generator.generate_code(
            analysis_result, 
            template_category, 
            generation_config
        )
        
        # ===== STEP 4: 使用环境检查结果进行智能文件写入（支持包结构优化） =====
        from pathlib import Path
        
        # 重新获取项目结构（可能在验证过程中已创建）
        # Allow caller to pin the target project root
        project_structure = _detect_project_structure(project_path)
        
        # 确定输出目录
        if output_dir_arg:
            output_root = Path(output_dir_arg).expanduser()
            java_source_dir = output_root
            resources_dir = output_root / "resources"
            java_source_dir.mkdir(parents=True, exist_ok=True)
            resources_dir.mkdir(parents=True, exist_ok=True)
        elif project_structure["java_source_dir"] and project_structure["java_source_dir"].exists():
            java_source_dir = project_structure["java_source_dir"]
            resources_dir = project_structure["resources_dir"]
        else:
            # 如果仍然没有检测到，使用当前目录创建
            current_dir = Path(project_path).expanduser() if project_path else Path.cwd()
            java_source_dir = current_dir / "src" / "main" / "java"
            resources_dir = current_dir / "src" / "main" / "resources"
            java_source_dir.mkdir(parents=True, exist_ok=True)
            resources_dir.mkdir(parents=True, exist_ok=True)
        
        written_files = []
        resource_files = []
        
        generated_files = generation_result.get("generated_code", {})
        for template_file, file_info in generated_files.items():
            if "error" not in file_info:
                # 获取相对文件路径（包含包结构）
                raw_relative_path = file_info.get("filename")
                normalized_relative_path = (
                    raw_relative_path.replace("\\", "/")
                    if isinstance(raw_relative_path, str)
                    else raw_relative_path
                )
                
                # 判断文件类型并选择正确的输出目录
                if (
                    isinstance(normalized_relative_path, str)
                    and (
                        normalized_relative_path.endswith(('.xml', '.yml', '.yaml', '.properties'))
                        or normalized_relative_path.startswith('resources/')
                        or normalized_relative_path.startswith('mapper/')
                        or '/mapper/' in normalized_relative_path
                    )
                ):
                    # 资源文件放到resources目录
                    if normalized_relative_path.startswith('resources/'):
                        normalized_relative_path = normalized_relative_path[10:]
                    output_dir = resources_dir
                else:
                    # Java文件：路径已包含包结构，直接写入源码目录
                    output_dir = java_source_dir

                try:
                    full_output_path = _resolve_codegen_output_path(
                        output_dir, normalized_relative_path
                    )
                except ValueError as path_error:
                    file_info["write_error"] = f"Unsafe output path: {path_error}"
                    file_info["write_error_kind"] = "unsafe_path"
                    logger.warning(
                        "Rejected generated file path %r for %s: %s",
                        raw_relative_path,
                        output_dir,
                        path_error,
                    )
                    continue

                # Register a path only after both directory creation and the write succeed.
                try:
                    _write_codegen_file(full_output_path, file_info["code"])
                    if output_dir == resources_dir:
                        resource_files.append(str(full_output_path))
                    else:
                        written_files.append(str(full_output_path))
                    logger.info(f"Successfully wrote file: {full_output_path}")
                except Exception as write_error:
                    logger.error(f"Failed to write file {full_output_path}: {write_error}")
                    file_info["write_error"] = str(write_error)
                    file_info["write_error_kind"] = "write_failed"
        
        # ===== STEP 5: 格式化增强响应（包含包结构优化信息） =====
        result_text = f"🚀 Code Generation Complete: {table_name}\n"
        result_text += f"Template Category: {template_category}\n"
        result_text += f"Package: {package_name}\n"
        result_text += f"Author: {author}\n"
        result_text += f"Swagger: {'Yes' if include_swagger else 'No'}\n"
        result_text += f"Lombok: {'Yes' if include_lombok else 'No'}\n"
        result_text += f"MapStruct: {'Yes' if include_mapstruct else 'No'}\n"
        
        # 显示包结构优化信息
        package_suffix = analysis_result["template_context"].get("packageSuffix", "")
        if package_suffix:
            result_text += "📦 Package Structure Optimization: ENABLED\n"
            result_text += f"   Package Suffix: {package_suffix}\n"
            result_text += f"   Tables Analyzed: {len(all_table_names)}\n"
            
            # 显示前缀映射信息
            from ..utils.table_prefix_analyzer import TablePrefixAnalyzer
            analyzer = TablePrefixAnalyzer()
            prefix_groups = analyzer.analyze_table_prefixes(all_table_names)
            
            if prefix_groups:
                result_text += f"   Prefix Groups Found: {len(prefix_groups)}\n"
                for prefix, group in prefix_groups.items():
                    if table_name in group.tables:
                        result_text += f"   → {group.prefix} → {group.package_name} ({len(group.tables)} tables)\n"
                        break
        else:
            result_text += "📦 Package Structure: Standard (no prefix optimization)\n"
        
        result_text += "\n"
        
        # 项目验证和依赖分析摘要
        result_text += "✅ Project Environment: VALIDATED\n"
        result_text += f"📦 Dependency Health: {health_score}% {'✅ Good' if health_score >= 80 else '⚠️ Needs Review' if health_score >= 60 else '❌ Critical'}\n"
        
        if project_structure["project_root"]:
            result_text += f"   📁 Project Root: {project_structure['project_root'].name}/\n"
            result_text += f"   ☕ Java Source: {_display_codegen_path(java_source_dir, project_structure['project_root'])}/\n"
            result_text += f"   📄 Resources: {_display_codegen_path(resources_dir, project_structure['project_root'])}/\n"
        
        # 显示依赖警告
        if dependency_warnings:
            result_text += "\n🔔 Dependency Warnings:\n"
            for warning in dependency_warnings:
                result_text += f"   {warning}\n"
            result_text += "   💡 Run 'springboot_analyze_dependencies' for detailed recommendations\n"
        
        # Generation summary
        if "generation_statistics" not in generation_result:
            raise ValueError("Generation result missing 'generation_statistics' field")
        
        stats = generation_result["generation_statistics"]
        summary = {
            "total_templates": stats["total_files"],
            "success_count": stats["success_files"],
            "error_count": stats["error_files"]
        }
        result_text += "\n📊 Generation Summary:\n"
        result_text += f"  Total Templates: {summary['total_templates']}\n"
        result_text += f"  Successfully Generated: {summary['success_count']}\n"
        result_text += f"  Errors: {summary['error_count']}\n\n"
        
        # Generated files with correct paths
        if "generated_code" not in generation_result:
            raise ValueError("Generation result missing 'generated_code' field")
        
        generated_files = generation_result["generated_code"]
        result_text += "📂 Generated Files:\n"
        
        java_file_count = 0
        resource_file_count = 0
        
        for template_file, file_info in generated_files.items():
            if "error" in file_info:
                result_text += f"  ❌ {template_file}: {file_info['error']}\n"
            elif "write_error" in file_info:
                error_kind = file_info.get("write_error_kind", "write_failed")
                label = "Path rejected" if error_kind == "unsafe_path" else "Write failed"
                result_text += (
                    f"  ⚠️ {file_info['filename']}: Generated but {label.lower()} - "
                    f"{file_info['write_error']}\n"
                )
            else:
                filename = file_info["filename"]
                code_lines = len(file_info["code"].split('\n'))
                
                if filename.endswith(('.xml', '.yml', '.yaml', '.properties')):
                    # 资源文件
                    written_path = str(resources_dir / filename.replace('resources/', ''))
                    result_text += f"  📄 {written_path} ({code_lines} lines)\n"
                    resource_file_count += 1
                else:
                    # Java文件
                    written_path = str(java_source_dir / filename)
                    result_text += f"  ☕ {written_path} ({code_lines} lines)\n"
                    java_file_count += 1
        
        # 文件统计
        total_written = len(written_files) + len(resource_files)
        write_candidate_count = sum("error" not in file_info for file_info in generated_files.values())
        path_rejected_count = sum(
            file_info.get("write_error_kind") == "unsafe_path"
            for file_info in generated_files.values()
        )
        write_failure_count = sum(
            file_info.get("write_error_kind") == "write_failed"
            for file_info in generated_files.values()
        )
        write_attempt_count = write_candidate_count - path_rejected_count
        result_text += "\n📈 File Writing Summary:\n"
        result_text += f"  Write Candidates: {write_candidate_count}\n"
        result_text += f"  Write Attempts: {write_attempt_count}\n"
        result_text += f"  Write Succeeded: {total_written}\n"
        result_text += f"  Paths Rejected: {path_rejected_count}\n"
        result_text += f"  Write Failed: {write_failure_count}\n"
        result_text += f"  Java Files: {java_file_count} written to {java_source_dir.absolute()}\n"
        result_text += f"  Resource Files: {resource_file_count} written to {resources_dir.absolute()}\n"
        result_text += f"  Total Files: {total_written}\n"

        generation_failure_count = stats["error_files"]
        if (
            generation_failure_count == 0
            and path_rejected_count == 0
            and write_failure_count == 0
            and total_written == write_candidate_count
        ):
            result_text += "\n🎉 SUCCESS: All files written to SpringBoot project structure!\n"
            result_text += f"📁 Working Directory: {Path.cwd().absolute()}\n"
        elif total_written > 0:
            result_text += "\n⚠️ PARTIAL: Some generated files were not written. Review the file errors above.\n"
        else:
            result_text += "\n❌ FAILED: No generated files were written. Review the file errors above.\n"
        
        # 简化的代码预览（仅显示文件名，不显示完整代码）
        result_text += "\n📝 Generated Code Preview:\n"
        result_text += "Files are ready in your SpringBoot project structure.\n"
        result_text += "Use your IDE to view and edit the generated code.\n"
        
        # 依赖管理提醒
        if health_score < 80:
            result_text += "\n🔧 Important: Review and fix dependency issues before compiling:\n"
            result_text += "   • Run 'springboot_analyze_dependencies' for detailed Maven XML snippets\n"
            result_text += "   • Update your pom.xml with missing/outdated dependencies\n"
            result_text += "   • Consider migrating from deprecated javax.* to jakarta.* packages\n"
        
        # P3.4: package tree MCP App meta
        from ..mcp_apps.package_tree import build_package_tree_data
        from ..mcp_apps.meta_builder import attach_meta, build_mcp_app_meta
        gen_file_paths = []
        for _info in generated_files.values():
            if "error" not in _info and "filename" in _info:
                gen_file_paths.append(_info["filename"])
        tree_data = build_package_tree_data(
            gen_file_paths,
            project_root=str(project_structure.get("project_root")) if project_structure.get("project_root") else None,
        )
        tree_meta = build_mcp_app_meta(
            "tree",
            version="1.0",
            data=tree_data,
        )
        content_obj = TextContent(type="text", text=result_text)
        return [attach_meta(content_obj, tree_meta)]
        
    except (DatabaseConnectionError, DatabaseQueryError, MCPServiceError) as e:
        error_response = {
            "success": False,
            "error": "generation_failed",
            "message": str(e)
        }
        return [TextContent(
            type="text",
            text=f"Failed to generate code: {str(e)}\n\nRaw Response: {_json_dumps(error_response, ensure_ascii=False)}"
        )]
        
    except Exception as e:
        logger.error(f"Unexpected error in db_codegen_generate: {e}")
        error_response = {
            "success": False,
            "error": "unexpected_error",
            "message": f"Unexpected error: {str(e)}"
        }
        return [TextContent(
            type="text",
            text=f"Unexpected error: {str(e)}\n\nRaw Response: {_json_dumps(error_response, ensure_ascii=False)}"
        )]


def detect_springboot_project_structure(start_dir: Path = None) -> Dict[str, Path]:
    """
    检测SpringBoot项目结构
    
    Args:
        start_dir: 起始搜索目录，默认为当前工作目录
        
    Returns:
        包含项目结构路径的字典
    """
    if start_dir is None:
        start_dir = Path.cwd()
    
    result = {
        "project_root": None,
        "java_source_dir": None,
        "resources_dir": None,
        "test_dir": None
    }
    
    # 从当前目录开始向上搜索，寻找项目根目录
    current = start_dir
    for _ in range(5):  # 最多向上搜索5级目录
        # 检查是否为SpringBoot项目根目录的标志
        indicators = [
            current / "pom.xml",
            current / "build.gradle",
            current / "src" / "main" / "java"
        ]
        
        if any(indicator.exists() for indicator in indicators):
            result["project_root"] = current
            result["java_source_dir"] = current / "src" / "main" / "java"
            result["resources_dir"] = current / "src" / "main" / "resources"
            result["test_dir"] = current / "src" / "test" / "java"
            break
            
        # 向上一级目录
        parent = current.parent
        if parent == current:  # 已到达根目录
            break
        current = parent
    
    # 如果没找到，检查是否在子目录中（如test_project）
    if result["project_root"] is None:
        subdirs_to_check = ["test_project", "demo", "example"]
        for subdir in subdirs_to_check:
            candidate = start_dir / subdir
            if candidate.exists() and (candidate / "src" / "main" / "java").exists():
                result["project_root"] = candidate
                result["java_source_dir"] = candidate / "src" / "main" / "java"
                result["resources_dir"] = candidate / "src" / "main" / "resources"
                result["test_dir"] = candidate / "src" / "test" / "java"
                break
    
    return result


def _detect_project_structure(project_path: Optional[str] = None) -> Dict[str, Path]:
    """Resolve project structure from an explicit path or the current directory."""
    start_dir = Path(project_path).expanduser() if project_path else None
    return detect_springboot_project_structure(start_dir)


def _collect_codegen_table_names(connection_id: str, fallback_table: str) -> List[str]:
    """Collect table names through the shared introspection contract."""
    try:
        table_names = DatabaseIntrospector(connection_manager).list_tables(connection_id)
        return table_names or [fallback_table]
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to get all table names for prefix analysis: %s", exc)
        return [fallback_table]


def get_springboot_project_tools() -> List[Tool]:
    """
    Get SpringBoot project validation and environment check tools
    
    Returns:
        List of SpringBoot project MCP Tool objects
    """
    from ..generator.template_context import TemplateConfigManager

    template_categories = TemplateConfigManager.get_supported_categories()
    return [
        Tool(
            name="springboot_validate_project",
            description="Validate SpringBoot project structure and dependencies before code generation",
            inputSchema={
                "type": "object",
                "properties": {
                    "check_dependencies": {
                        "type": "boolean",
                        "description": "Whether to check project dependencies (default: True)",
                        "default": True
                    },
                    "create_missing_dirs": {
                        "type": "boolean",
                        "description": "Whether to create missing standard directories (default: True)",
                        "default": True
                    },
                    "template_category": {
                        "type": "string",
                        "description": "Template category to check dependencies for",
                        "enum": template_categories,
                        "default": "MybatisPlus-Mixed"
                    },
                    "project_path": {
                        "type": "string",
                        "description": "Path to project root (optional, defaults to current directory)",
                        "default": "."
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="springboot_analyze_dependencies",
            description="Analyze project dependencies and generate intelligent recommendations for code generation",
            inputSchema={
                "type": "object",
                "properties": {
                    "template_category": {
                        "type": "string",
                        "description": "Template category for dependency analysis",
                        "enum": template_categories,
                        "default": "MybatisPlus-Mixed"
                    },
                    "database_type": {
                        "type": "string",
                        "description": "Database type for driver dependencies",
                        "enum": ["mysql", "postgresql", "sqlite"],
                        "default": "mysql"
                    },
                    "include_swagger": {
                        "type": "boolean",
                        "description": "Whether to include Swagger/OpenAPI dependencies",
                        "default": True
                    },
                    "include_lombok": {
                        "type": "boolean",
                        "description": "Whether to include Lombok dependencies",
                        "default": True
                    },
                    "include_mapstruct": {
                        "type": "boolean",
                        "description": "Whether to include MapStruct dependencies",
                        "default": True
                    },
                    "project_path": {
                        "type": "string",
                        "description": "Path to project root (optional, defaults to current directory)",
                        "default": "."
                    }
                },
                "required": ["template_category", "database_type"]
            }
        ),
        Tool(
            name="springboot_read_config",
            description="Read Spring Boot project configuration (YAML/Properties/Bootstrap) and infer base package",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_path": {
                        "type": "string",
                        "description": "Optional explicit project root to scan"
                    },
                    "active_profile": {
                        "type": "string",
                        "description": "Profile name to overlay (e.g. dev, prod)",
                        "default": ""
                    },
                    "include_profiles": {
                        "type": "boolean",
                        "description": "Whether to collect all available profile files",
                        "default": True
                    },
                    "merge_strategy": {
                        "type": "string",
                        "enum": ["overlay", "base_only", "profile_only"],
                        "description": "How to merge base and profile configs",
                        "default": "overlay"
                    }
                },
                "required": []
            }
        )
    ]


async def handle_springboot_validate_project(arguments: Dict[str, Any]) -> List[TextContent]:
    """
    Handle SpringBoot project validation and environment setup
    
    Args:
        arguments: Tool arguments
        
    Returns:
        Project validation results and recommendations
    """
    try:
        check_dependencies = arguments.get("check_dependencies", True)
        create_missing_dirs = arguments.get("create_missing_dirs", True)
        template_category = arguments.get("template_category", "MybatisPlus-Mixed")
        project_path = arguments.get("project_path")
        
        # 1. 检测项目结构
        project_structure = _detect_project_structure(project_path)
        current_dir = Path(project_path).expanduser() if project_path else Path.cwd()
        
        validation_results = {
            "project_structure": {},
            "dependencies": {},
            "recommendations": [],
            "created_directories": [],
            "validation_passed": True
        }
        
        # 2. 验证项目结构
        structure_issues = []
        
        if project_structure["project_root"] is None:
            structure_issues.append("No SpringBoot project root detected")
            validation_results["validation_passed"] = False
            
            if create_missing_dirs:
                # 创建标准SpringBoot结构
                std_dirs = [
                    "src/main/java",
                    "src/main/resources",
                    "src/main/resources/mapper",
                    "src/test/java"
                ]
                
                for dir_path in std_dirs:
                    full_path = current_dir / dir_path
                    if not full_path.exists():
                        full_path.mkdir(parents=True, exist_ok=True)
                        validation_results["created_directories"].append(str(full_path))
                
                # 重新检测结构
                project_structure = _detect_project_structure(project_path)
        
        # 检查关键目录
        required_dirs = {
            "java_source": project_structure.get("java_source_dir"),
            "resources": project_structure.get("resources_dir"),
            "test_dir": project_structure.get("test_dir")
        }
        
        for dir_name, dir_path in required_dirs.items():
            if dir_path is None or not dir_path.exists():
                structure_issues.append(f"Missing {dir_name} directory")
                if create_missing_dirs and project_structure.get("project_root"):
                    # 创建缺失目录
                    if dir_name == "java_source":
                        missing_dir = project_structure["project_root"] / "src" / "main" / "java"
                    elif dir_name == "resources":
                        missing_dir = project_structure["project_root"] / "src" / "main" / "resources"
                    elif dir_name == "test_dir":
                        missing_dir = project_structure["project_root"] / "src" / "test" / "java"
                    
                    missing_dir.mkdir(parents=True, exist_ok=True)
                    validation_results["created_directories"].append(str(missing_dir))
                    
                    # 为resources创建mapper子目录
                    if dir_name == "resources":
                        mapper_dir = missing_dir / "mapper"
                        mapper_dir.mkdir(exist_ok=True)
                        validation_results["created_directories"].append(str(mapper_dir))
        
        validation_results["project_structure"] = {
            "project_root": str(project_structure["project_root"]) if project_structure["project_root"] else None,
            "java_source_dir": str(project_structure["java_source_dir"]) if project_structure["java_source_dir"] else None,
            "resources_dir": str(project_structure["resources_dir"]) if project_structure["resources_dir"] else None,
            "test_dir": str(project_structure["test_dir"]) if project_structure["test_dir"] else None,
            "issues": structure_issues
        }
        
        # 3. 检查项目依赖（如果启用）
        if check_dependencies and project_structure["project_root"]:
            try:
                from ..utils.dependency_manager import DependencyManager
                manager = DependencyManager()
                
                dep_check = manager.get_dependency_health_report(str(project_structure["project_root"]))
                validation_results["dependencies"] = dep_check
                
                # 检查健康分数
                health_score = dep_check.get("health_score", 0)
                if health_score < 60:
                    validation_results["recommendations"].append(
                        f"Dependency health score is {health_score}%, consider adding missing dependencies"
                    )
                    validation_results["validation_passed"] = False
                        
            except Exception as dep_error:
                logger.warning(f"Dependency check failed: {dep_error}")
                validation_results["dependencies"] = {"error": str(dep_error)}
        
        # 4. 生成建议
        if structure_issues:
            validation_results["recommendations"].extend([
                "Fix project structure issues before generating code",
                "Consider running with create_missing_dirs=true to auto-create directories"
            ])
        
        # 5. 格式化响应
        result_text = "🔍 SpringBoot Project Validation\n"
        result_text += f"Template Category: {template_category}\n"
        result_text += f"Working Directory: {current_dir.absolute()}\n\n"
        
        # 项目结构状态
        result_text += "📁 Project Structure:\n"
        if project_structure["project_root"]:
            result_text += f"   ✅ Project Root: {project_structure['project_root'].absolute()}\n"
            result_text += f"   ✅ Java Source: {project_structure['java_source_dir'].absolute()}\n"
            result_text += f"   ✅ Resources: {project_structure['resources_dir'].absolute()}\n"
            result_text += f"   ✅ Test Directory: {project_structure['test_dir'].absolute()}\n"
        else:
            result_text += "   ❌ No SpringBoot project detected\n"
        
        # 结构问题
        if structure_issues:
            result_text += f"\n⚠️ Structure Issues ({len(structure_issues)}):\n"
            for issue in structure_issues:
                result_text += f"   - {issue}\n"
        
        # 创建的目录
        if validation_results["created_directories"]:
            result_text += f"\n📂 Created Directories ({len(validation_results['created_directories'])}):\n"
            for created_dir in validation_results["created_directories"]:
                result_text += f"   + {created_dir}\n"
        
        # 依赖检查结果
        if check_dependencies and "dependencies" in validation_results:
            dep_result = validation_results["dependencies"]
            if "error" in dep_result:
                result_text += f"\n⚠️ Dependency Check: Failed - {dep_result['error']}\n"
            else:
                health_score = dep_result.get("health_score", 0)
                result_text += f"\n📦 Dependencies: Health Score {health_score}%\n"
                
                found_deps = dep_result.get("found_dependencies", 0)
                if found_deps:
                    result_text += f"   Found {found_deps} dependencies\n"
                
                missing_required = dep_result.get("missing_required", 0)
                if missing_required:
                    result_text += f"   ❌ Missing {missing_required} required dependencies\n"
        
        # 验证结果
        if validation_results["validation_passed"]:
            result_text += "\n✅ Project validation PASSED - Ready for code generation\n"
        else:
            result_text += "\n❌ Project validation FAILED - Please fix issues before generating code\n"
        
        # 建议
        recommendations = validation_results["recommendations"]
        if recommendations:
            result_text += f"\n💡 Recommendations ({len(recommendations)}):\n"
            for rec in recommendations:
                result_text += f"   - {rec}\n"
        
        result_text += "\n📋 Validation Summary:\n"
        result_text += f"   Project Structure: {'✅ OK' if not structure_issues else '❌ Issues Found'}\n"
        if check_dependencies:
            if "dependencies" in validation_results and not validation_results["dependencies"].get("error"):
                result_text += f"   Dependencies: {'✅ OK' if validation_results['validation_passed'] else '⚠️ Needs Attention'}\n"
            else:
                result_text += "   Dependencies: ❓ Check Failed\n"
        result_text += f"   Overall Status: {'✅ READY' if validation_results['validation_passed'] else '❌ NOT READY'}\n"
        
        result_text += f"\nRaw Validation Result: {validation_results}"
        
        return [TextContent(
            type="text",
            text=result_text
        )]
        
    except Exception as e:
        logger.error(f"Unexpected error in springboot_validate_project: {e}")
        error_response = {
            "success": False,
            "error": "validation_failed",
            "message": f"Unexpected error: {str(e)}"
        }
        return [TextContent(
            type="text",
            text=f"Project validation failed: {str(e)}\n\nRaw Response: {_json_dumps(error_response, ensure_ascii=False)}"
        )]


async def handle_springboot_analyze_dependencies(arguments: Dict[str, Any]) -> List[TextContent]:
    """
    Handle SpringBoot project dependency analysis using intelligent adaptation
    
    Args:
        arguments: Tool arguments
        
    Returns:
        Intelligent dependency analysis with adaptive recommendations
    """
    try:
        template_category = arguments.get("template_category", "MybatisPlus-Mixed")
        database_type = arguments.get("database_type", "mysql")
        include_swagger = arguments.get("include_swagger", True)
        include_lombok = arguments.get("include_lombok", True)
        include_mapstruct = arguments.get("include_mapstruct", True)
        requested_project_path = arguments.get("project_path")
        project_path = requested_project_path or "."
        
        # 导入依赖管理器
        from ..utils.dependency_manager import DependencyManager
        
        # 检测项目结构
        project_structure = _detect_project_structure(project_path)
        if project_structure["project_root"]:
            project_path = str(project_structure["project_root"])
        elif requested_project_path:
            project_path = str(Path(requested_project_path).expanduser())
        else:
            project_path = str(Path.cwd())
        
        # 使用整合依赖管理器进行分析和修复
        manager = DependencyManager()
        
        # 检查并修复依赖
        check_and_fix_result = manager.check_and_fix_dependencies(
            project_root=project_path,
            template_category=template_category,
            database_type=database_type,
            include_swagger=include_swagger,
            include_lombok=include_lombok,
            include_mapstruct=include_mapstruct
        )
        
        # 获取依赖健康报告
        health_report = manager.get_dependency_health_report(project_path)
        
        # 获取迁移指南
        migration_guide = manager.generate_migration_guide(project_path)
        
        # 格式化响应
        result_text = "🎯 智能依赖分析与修复\n"
        result_text += f"Project Path: {project_path}\n"
        result_text += f"Template Category: {template_category}\n"
        result_text += f"Database Type: {database_type}\n\n"
        
        # 依赖健康报告
        result_text += "📊 依赖健康报告:\n"
        result_text += f"   Build Tool: {health_report.get('build_tool', 'Unknown')}\n"
        result_text += f"   Health Score: {health_report.get('health_score', 0)}%\n"
        result_text += f"   Found Dependencies: {health_report.get('found_dependencies', 0)}/{health_report.get('total_dependencies', 0)}\n"
        result_text += f"   Missing Required: {health_report.get('missing_required', 0)}\n"
        result_text += f"   Missing Optional: {health_report.get('missing_optional', 0)}\n\n"
        
        # 自动修复结果
        auto_add_result = check_and_fix_result.get("auto_add_result", {})
        if auto_add_result.get("success"):
            added_count = auto_add_result.get("added_count", 0)
            if added_count > 0:
                result_text += f"🔧 自动添加依赖: 成功添加 {added_count} 个缺失依赖\n\n"
            else:
                result_text += "✅ 依赖完整性: 所有必需依赖已存在\n\n"
        
        fix_result = check_and_fix_result.get("fix_result", {})
        if fix_result.get("success") and "修复" in fix_result.get("message", ""):
            result_text += f"🔄 自动修复过时依赖: {fix_result.get('message')}\n\n"
        
        # 迁移指南
        if migration_guide.get("success") and migration_guide.get("total_suggestions", 0) > 0:
            result_text += f"💡 迁移建议 ({migration_guide['total_suggestions']}):\n"
            for suggestion in migration_guide.get("migration_suggestions", []):
                result_text += f"   • {suggestion['dependency']} → {suggestion['recommendation']}\n"
            result_text += "\n"
        
        # Maven XML推荐（如果需要补全依赖）
        analysis_result = check_and_fix_result.get("analysis_result", {})
        maven_xml_blocks = analysis_result.get("maven_xml", {})
        
        if maven_xml_blocks.get("missing_dependencies"):
            result_text += "📄 Maven Dependencies to Add:\n"
            result_text += "``xml\n"
            result_text += "<dependencies>\n"
            for dep_block in maven_xml_blocks["missing_dependencies"]:
                result_text += f"    <!-- {dep_block['description']} -->\n"
                result_text += f"{dep_block['xml']}\n\n"
            result_text += "</dependencies>\n"
            result_text += "```\n\n"
        
        # 依赖健康度评估
        health_score = health_report.get("health_score", 0)
        if health_score >= 90:
            result_text += f"🎉 依赖健康度: 优秀 ({health_score}%) - 项目依赖配置完整且现代化\n"
        elif health_score >= 70:
            result_text += f"✅ 依赖健康度: 良好 ({health_score}%) - 项目依赖配置基本完整\n"
        elif health_score >= 50:
            result_text += f"⚠️ 依赖健康度: 一般 ({health_score}%) - 建议补充缺失依赖\n"
        else:
            result_text += f"❌ 依赖健康度: 较差 ({health_score}%) - 需要紧急处理依赖问题\n"
        
        result_text += "\n💡 智能依赖管理: 自动检查、修复和优化项目依赖配置"
        
        # P3.2: dashboard MCP App meta
        from ..mcp_apps.dashboard import build_dependency_dashboard_data
        from ..mcp_apps.meta_builder import attach_meta, build_mcp_app_meta
        dashboard_data = build_dependency_dashboard_data(
            health_report,
            migration_guide.get("migration_suggestions", []) if isinstance(migration_guide, dict) else [],
            (maven_xml_blocks.get("missing_dependencies", []) if isinstance(maven_xml_blocks, dict) else []),
        )
        dashboard_meta = build_mcp_app_meta(
            "dashboard",
            version="1.0",
            data=dashboard_data,
        )
        content_obj = TextContent(type="text", text=result_text)
        return [attach_meta(content_obj, dashboard_meta)]
        
    except Exception as e:
        logger.error(f"Unexpected error in springboot_analyze_dependencies: {e}")
        error_response = {
            "success": False,
            "error": "dependency_analysis_failed", 
            "message": f"Unexpected error: {str(e)}"
        }
        return [TextContent(
            type="text",
            text=f"Dependency analysis failed: {str(e)}\n\nRaw Response: {_json_dumps(error_response, ensure_ascii=False)}"
        )]


def _read_text_file(path: Path) -> Optional[str]:
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        try:
            return path.read_text(encoding="gbk")
        except Exception:
            return None


def _set_nested(d: Dict[str, Any], dotted_key: str, value: Any) -> None:
    parts = [p for p in dotted_key.split('.') if p]
    cur = d
    for i, part in enumerate(parts):
        if i == len(parts) - 1:
            cur[part] = value
        else:
            if part not in cur or not isinstance(cur[part], dict):
                cur[part] = {}
            cur = cur[part]


def _parse_properties_file(path: Path) -> Dict[str, Any]:
    data: Dict[str, Any] = {}
    text = _read_text_file(path)
    if text is None:
        return data
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith('#') or line.startswith('!'):
            continue
        sep_idx = -1
        for sep in ('=', ':'):
            if sep in line:
                sep_idx = line.find(sep)
                break
        if sep_idx == -1:
            parts = line.split()
            if len(parts) < 2:
                continue
            key = parts[0]
            value = ' '.join(parts[1:])
        else:
            key = line[:sep_idx].strip()
            value = line[sep_idx + 1 :].strip()
        _set_nested(data, key, value)
    return data


def _parse_yaml_file(path: Path) -> Dict[str, Any]:
    try:
        import yaml
    except Exception:
        return {}
    text = _read_text_file(path)
    if text is None:
        return {}
    try:
        loaded = yaml.safe_load(text)
        return loaded or {}
    except Exception:
        return {}


def _deep_merge(dst: Dict[str, Any], src: Dict[str, Any]) -> Dict[str, Any]:
    for k, v in src.items():
        if isinstance(v, dict) and isinstance(dst.get(k), dict):
            _deep_merge(dst[k], v)
        else:
            dst[k] = v
    return dst


def _find_base_package(java_src: Optional[Path]) -> Optional[str]:
    if not java_src or not java_src.exists():
        return None
    candidates: list[Path] = []
    try:
        for p in java_src.rglob('*.java'):
            candidates.append(p)
            if len(candidates) >= 200:
                break
    except Exception:
        candidates = []
    for p in candidates:
        text = _read_text_file(p)
        if not text:
            continue
        if '@SpringBootApplication' in text or 'SpringApplication.run' in text:
            for line in text.splitlines():
                line = line.strip()
                if line.startswith('package '):
                    pkg = line[len('package '):].rstrip(';').strip()
                    if pkg:
                        return pkg
    try:
        top_levels = [d for d in java_src.iterdir() if d.is_dir()]
        if top_levels:
            for d in top_levels:
                java_files = list(d.rglob('*.java'))
                if java_files:
                    rel = java_files[0].relative_to(java_src).parent
                    if rel.parts:
                        return '.'.join(part for part in rel.parts if part)
    except Exception:
        pass
    return None


async def handle_springboot_read_config(arguments: Dict[str, Any]) -> List[TextContent]:
    try:
        start_dir = Path(arguments.get('project_path')) if arguments.get('project_path') else None
        profile = (arguments.get('active_profile') or '').strip()
        include_profiles = bool(arguments.get('include_profiles', True))
        merge_strategy = arguments.get('merge_strategy', 'overlay')

        proj = detect_springboot_project_structure(start_dir if start_dir else None)
        project_root: Optional[Path] = proj.get('project_root')
        java_src: Optional[Path] = proj.get('java_source_dir')
        resources_dir: Optional[Path] = proj.get('resources_dir')

        build_tool = None
        spring_boot_version = None
        if project_root:
            if (project_root / 'pom.xml').exists():
                build_tool = 'maven'
            elif (project_root / 'build.gradle').exists() or (project_root / 'build.gradle.kts').exists():
                build_tool = 'gradle'
            try:
                analyzer = PomAnalyzer()
                if build_tool == 'maven':
                    spring_boot_version = analyzer._extract_spring_boot_version(project_root / 'pom.xml')
                elif build_tool == 'gradle':
                    spring_boot_version = analyzer._extract_gradle_spring_boot_version(
                        project_root / ('build.gradle' if (project_root / 'build.gradle').exists() else 'build.gradle.kts')
                    )
            except Exception:
                spring_boot_version = None

        base_package = _find_base_package(java_src)

        files_scanned: list[str] = []
        configs: Dict[str, Any] = {}
        profiles_found: Dict[str, Dict[str, Any]] = {}

        def load_file(path: Path) -> Dict[str, Any]:
            files_scanned.append(str(path))
            if path.suffix in ('.yml', '.yaml'):
                return _parse_yaml_file(path)
            elif path.suffix == '.properties':
                return _parse_properties_file(path)
            return {}

        if resources_dir and resources_dir.exists():
            base_candidates = [
                resources_dir / 'application.yml',
                resources_dir / 'application.yaml',
                resources_dir / 'application.properties',
                resources_dir / 'bootstrap.yml',
                resources_dir / 'bootstrap.yaml',
                resources_dir / 'bootstrap.properties',
            ]
            for f in base_candidates:
                if f.exists():
                    cfg = load_file(f)
                    _deep_merge(configs, cfg)

            if include_profiles:
                try:
                    for f in resources_dir.iterdir():
                        name = f.name
                        if not f.is_file():
                            continue
                        if name.startswith('application-') and (name.endswith('.yml') or name.endswith('.yaml') or name.endswith('.properties')):
                            prof = name[len('application-'):].split('.')[0]
                            profiles_found.setdefault(prof, {})
                            profiles_found[prof] = load_file(f)
                        elif name.startswith('bootstrap-') and (name.endswith('.yml') or name.endswith('.yaml') or name.endswith('.properties')):
                            prof = name[len('bootstrap-'):].split('.')[0]
                            existing = profiles_found.get(prof, {})
                            _deep_merge(existing, load_file(f))
                            profiles_found[prof] = existing
                except Exception:
                    pass

        effective_config: Dict[str, Any] = {}
        if merge_strategy == 'base_only':
            effective_config = configs.copy()
        elif merge_strategy == 'profile_only':
            if profile and profile in profiles_found:
                effective_config = profiles_found[profile]
            else:
                effective_config = {}
        else:
            effective_config = configs.copy()
            if profile and profile in profiles_found:
                _deep_merge(effective_config, profiles_found[profile])

        def _get(d: Dict[str, Any], path: str, default=None):
            cur = d
            for part in path.split('.'):
                if not isinstance(cur, dict) or part not in cur:
                    return default
                cur = cur[part]
            return cur

        extracted = {
            'spring': {
                'application': {
                    'name': _get(effective_config, 'spring.application.name')
                },
                'profiles': {
                    'active': _get(effective_config, 'spring.profiles.active')
                },
                'datasource': {
                    'url': _get(effective_config, 'spring.datasource.url'),
                    'username': _get(effective_config, 'spring.datasource.username'),
                    'password': _get(effective_config, 'spring.datasource.password'),
                    'driver-class-name': _get(effective_config, 'spring.datasource.driver-class-name')
                }
            },
            'server': {
                'port': _get(effective_config, 'server.port'),
                'servlet': {
                    'context-path': _get(effective_config, 'server.servlet.context-path')
                }
            },
            'mybatis': _get(effective_config, 'mybatis', {}),
            'mybatis-plus': _get(effective_config, 'mybatis-plus', {}),
            'logging': _get(effective_config, 'logging', {}),
        }

        # Configuration files can contain database passwords, API keys, and tokens.
        # Keep the full structure useful for callers while ensuring no secret crosses
        # the MCP response boundary.
        safe_effective_config = redact_sensitive_data(effective_config)
        safe_extracted = redact_sensitive_data(extracted)

        response = {
            'success': True,
            'project_root': str(project_root) if project_root else None,
            'java_source_dir': str(java_src) if java_src else None,
            'resources_dir': str(resources_dir) if resources_dir else None,
            'build_tool': build_tool,
            'spring_boot_version': spring_boot_version,
            'base_package': base_package,
            'files_scanned': files_scanned,
            'profiles_available': sorted(list(profiles_found.keys())),
            'active_profile': profile or _get(effective_config, 'spring.profiles.active'),
            'effective': safe_extracted,
            'raw_config': safe_effective_config,
        }

        text_lines = []
        text_lines.append('📖 Spring Boot Project Configuration')
        text_lines.append(f"Project Root: {response['project_root']}")
        text_lines.append(f"Build Tool: {build_tool or 'Unknown'}  | Spring Boot: {spring_boot_version or 'Unknown'}")
        text_lines.append(f"Base Package: {base_package or 'Unknown'}")
        text_lines.append(f"Profiles: {', '.join(response['profiles_available']) if response['profiles_available'] else 'None'}")
        eff = safe_extracted
        text_lines.append('— Effective —')
        text_lines.append(f"app.name={eff.get('spring',{}).get('application',{}).get('name')}")
        text_lines.append(f"server.port={eff.get('server',{}).get('port')}")
        text_lines.append(f"context-path={eff.get('server',{}).get('servlet',{}).get('context-path')}")
        ds = eff.get('spring',{}).get('datasource',{})
        text_lines.append(f"datasource.url={ds.get('url')}")
        text_lines.append(f"mapper config present: {'mybatis' in eff or 'mybatis-plus' in eff}")

        return [TextContent(
            type="text",
            text='\n'.join(text_lines)
            + f"\n\nRaw Response: {_json_dumps(response, ensure_ascii=False)}"
        )]

    except Exception as e:
        err = {
            'success': False,
            'error': 'config_read_failed',
            'message': str(e)
        }
        return [TextContent(
            type="text",
            text=f"Failed to read Spring Boot config: {e}\n\nRaw Response: {_json_dumps(err, ensure_ascii=False)}"
        )]

