"""
Database connection manager for DBJavaGenix MCP tools
"""
from copy import deepcopy
from collections import OrderedDict
import re
from threading import RLock
import uuid
from typing import Dict, List, Any, Optional
import pymysql
import sqlite3
import logging
from contextlib import contextmanager

from ..core.models import DatabaseConfig, DatabaseType
from ..core.exceptions import DatabaseConnectionError, DatabaseQueryError
from ..utils.security import redact_sensitive_text
from .capabilities import SUPPORTED_DATABASE_TYPES, supported_database_type_values

logger = logging.getLogger(__name__)

_SCHEMA_CHANGE_PATTERN = re.compile(
    r"^\s*(?:CREATE|ALTER|DROP|RENAME|TRUNCATE|COMMENT)\b", re.IGNORECASE
)
_METADATA_CACHE_MAX_ENTRIES = 256


def _is_schema_change_query(query: object) -> bool:
    """Detect schema-changing SQL after optional leading comments."""
    if not isinstance(query, str):
        return False
    remaining = query.lstrip()
    while remaining:
        if remaining.startswith("--") or remaining.startswith("#"):
            newline = remaining.find("\n")
            if newline < 0:
                return False
            remaining = remaining[newline + 1 :].lstrip()
        elif remaining.startswith("/*"):
            end = remaining.find("*/", 2)
            if end < 0:
                return False
            remaining = remaining[end + 2 :].lstrip()
        else:
            break
    return bool(_SCHEMA_CHANGE_PATTERN.match(remaining))


class ConnectionManager:
    """Manages database connections for MCP tools"""
    
    def __init__(self):
        self.connections: Dict[str, Any] = {}
        self.connection_configs: Dict[str, DatabaseConfig] = {}
        self._metadata_cache: OrderedDict[
            tuple[str, str, Optional[str]], Dict[str, Any]
        ] = OrderedDict()
        self._metadata_cache_lock = RLock()

    def get_cached_metadata(
        self, connection_id: str, table_name: str, schema: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Return a deep copy of one connection-scoped metadata entry, if present."""
        key = (connection_id, table_name, schema)
        with self._metadata_cache_lock:
            cached = self._metadata_cache.get(key)
            if cached is None:
                return None
            self._metadata_cache.move_to_end(key)
            return deepcopy(cached)

    def cache_metadata(
        self,
        connection_id: str,
        table_name: str,
        schema: Optional[str],
        metadata: Dict[str, Any],
    ) -> None:
        """Store a complete metadata document without sharing mutable references."""
        key = (connection_id, table_name, schema)
        with self._metadata_cache_lock:
            self._metadata_cache.pop(key, None)
            self._metadata_cache[key] = deepcopy(metadata)
            while len(self._metadata_cache) > _METADATA_CACHE_MAX_ENTRIES:
                self._metadata_cache.popitem(last=False)

    def invalidate_metadata_cache(self, connection_id: Optional[str] = None) -> None:
        """Invalidate all metadata or only entries belonging to one connection."""
        with self._metadata_cache_lock:
            if connection_id is None:
                self._metadata_cache.clear()
                return
            stale_keys = [
                key for key in self._metadata_cache if key[0] == connection_id
            ]
            for key in stale_keys:
                self._metadata_cache.pop(key, None)

    def metadata_cache_size(self) -> int:
        """Return the number of cached metadata documents for diagnostics/tests."""
        with self._metadata_cache_lock:
            return len(self._metadata_cache)
    
    def create_connection(self, config: DatabaseConfig) -> str:
        """
        Create a new database connection
        
        Args:
            config: Database configuration
            
        Returns:
            connection_id: Unique connection identifier
            
        Raises:
            DatabaseConnectionError: If connection fails
        """
        connection_id = str(uuid.uuid4())
        if config.type not in SUPPORTED_DATABASE_TYPES:
            supported_types = ", ".join(supported_database_type_values())
            raise DatabaseConnectionError(
                f"Unsupported database type: {config.type.value}. "
                f"Supported database types: {supported_types}"
            )
        
        try:
            if config.type == DatabaseType.MYSQL:
                connection = pymysql.connect(
                    host=config.host,
                    port=config.port,
                    user=config.username,
                    password=config.password,
                    database=config.database if config.database else None,
                    charset=config.charset,
                    autocommit=True,
                    connect_timeout=10
                )
            elif config.type == DatabaseType.POSTGRESQL:
                try:
                    import psycopg2
                except ImportError as exc:
                    raise DatabaseConnectionError(
                        "PostgreSQL support requires the psycopg2-binary dependency"
                    ) from exc

                connection = psycopg2.connect(
                    host=config.host,
                    port=config.port,
                    user=config.username,
                    password=config.password,
                    dbname=config.database,
                    connect_timeout=10,
                )
                connection.autocommit = True
            elif config.type == DatabaseType.SQLITE:
                connection = sqlite3.connect(config.database)
                connection.row_factory = sqlite3.Row  # Enable dict-like access
            else:
                raise DatabaseConnectionError(f"Unsupported database type: {config.type}")
            
            self.connections[connection_id] = connection
            # Store config without sensitive data for reference
            safe_config = config.model_copy()
            safe_config.password = "***"  # Mask password
            self.connection_configs[connection_id] = safe_config
            
            logger.info(f"Created connection {connection_id} to {config.type}://{config.host}:{config.port}")
            return connection_id
            
        except Exception as e:
            safe_error = redact_sensitive_text(e, (config.password,))
            logger.error("Failed to create connection: %s", safe_error)
            raise DatabaseConnectionError(f"Failed to connect to database: {safe_error}") from e
    
    def get_connection(self, connection_id: str) -> Any:
        """
        Get connection by ID
        
        Args:
            connection_id: Connection identifier
            
        Returns:
            Database connection object
            
        Raises:
            DatabaseConnectionError: If connection not found
        """
        if connection_id not in self.connections:
            raise DatabaseConnectionError(f"Connection {connection_id} not found")
        
        connection = self.connections[connection_id]
        
        # Test connection is still alive
        try:
            if getattr(connection, "closed", 0):
                raise DatabaseConnectionError("connection is closed")
            if hasattr(connection, 'ping'):
                connection.ping(reconnect=True)
        except Exception as e:
            logger.warning(f"Connection {connection_id} is dead, removing: {e}")
            self.close_connection(connection_id)
            raise DatabaseConnectionError(f"Connection {connection_id} is no longer valid")
        
        return connection
    
    def close_connection(self, connection_id: str) -> bool:
        """
        Close a connection
        
        Args:
            connection_id: Connection identifier
            
        Returns:
            True if connection was closed, False if not found
        """
        if connection_id not in self.connections:
            self.invalidate_metadata_cache(connection_id)
            return False
        
        try:
            connection = self.connections[connection_id]
            connection.close()
            self.connections.pop(connection_id, None)
            self.connection_configs.pop(connection_id, None)
            self.invalidate_metadata_cache(connection_id)
            logger.info(f"Closed connection {connection_id}")
            return True
        except Exception as e:
            logger.error(f"Error closing connection {connection_id}: {e}")
            # Remove from dict anyway
            self.connections.pop(connection_id, None)
            self.connection_configs.pop(connection_id, None)
            self.invalidate_metadata_cache(connection_id)
            return True
    
    def get_connection_info(self, connection_id: str) -> Optional[DatabaseConfig]:
        """
        Get connection configuration (with masked password)
        
        Args:
            connection_id: Connection identifier
            
        Returns:
            Database configuration or None if not found
        """
        config = self.connection_configs.get(connection_id)
        return config.model_copy(deep=True) if config else None
    
    def list_connections(self) -> Dict[str, Dict[str, Any]]:
        """
        List all active connections
        
        Returns:
            Dict of connection_id -> connection_info
        """
        result = {}
        for conn_id, config in self.connection_configs.items():
            result[conn_id] = {
                "type": config.type,
                "host": config.host,
                "port": config.port,
                "database": config.database,
                "username": config.username,
                "status": "active" if conn_id in self.connections else "closed"
            }
        return result
    
    @contextmanager
    def get_cursor(self, connection_id: str):
        """
        Get cursor for database operations
        
        Args:
            connection_id: Connection identifier
            
        Yields:
            Database cursor
        """
        connection = self.get_connection(connection_id)
        cursor = connection.cursor()
        try:
            yield cursor
        finally:
            cursor.close()
    
    def execute_query(self, connection_id: str, query: str, params: Optional[tuple] = None) -> List[Dict[str, Any]]:
        """
        Execute a query and return results
        
        Args:
            connection_id: Connection identifier
            query: SQL query string
            params: Query parameters
            
        Returns:
            List of result rows as dictionaries
            
        Raises:
            DatabaseQueryError: If query execution fails
        """
        schema_change = _is_schema_change_query(query)
        try:
            with self.get_cursor(connection_id) as cursor:
                cursor.execute(query, params or ())
                
                # Get column names
                if hasattr(cursor, 'description') and cursor.description:
                    columns = [desc[0] for desc in cursor.description]
                    rows = cursor.fetchall()
                    
                    # Convert to list of dictionaries
                    result = []
                    for row in rows:
                        if isinstance(row, dict):  # SQLite with row_factory
                            result.append(dict(row))
                        else:  # MySQL
                            result.append(dict(zip(columns, row)))
                    
                    if schema_change:
                        self.invalidate_metadata_cache(connection_id)
                    return result
                else:
                    if schema_change:
                        self.invalidate_metadata_cache(connection_id)
                    return []  # No results (e.g., INSERT/UPDATE/DELETE)
                    
        except Exception as e:
            if schema_change:
                self.invalidate_metadata_cache(connection_id)
            logger.error(f"Query execution failed: {e}")
            raise DatabaseQueryError(f"Failed to execute query: {str(e)}")
    
    def __del__(self):
        """Clean up connections on destruction"""
        for connection_id in list(self.connections.keys()):
            try:
                self.close_connection(connection_id)
            except Exception:
                pass


# Global connection manager instance
connection_manager = ConnectionManager()
