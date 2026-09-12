"""
Database connection manager for DBJavaGenix MCP tools
"""
import uuid
import threading
from collections import OrderedDict
from copy import deepcopy
from typing import Dict, List, Any, Optional
import pymysql
import sqlite3
import logging
import re
from contextlib import contextmanager

from ..core.models import DatabaseConfig, DatabaseType
from ..core.exceptions import DatabaseConnectionError, DatabaseQueryError
from ..utils.security import redact_sensitive_text
from .capabilities import SUPPORTED_DATABASE_TYPES, supported_database_type_values

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages database connections for MCP tools"""
    
    def __init__(self):
        self.connections: Dict[str, Any] = {}
        self.connection_configs: Dict[str, DatabaseConfig] = {}
        self._registry_lock = threading.RLock()
        self._connection_locks: Dict[str, Any] = {}
        self._metadata_cache: OrderedDict[tuple[str, str, str | None], Dict[str, Any]] = OrderedDict()
        self._metadata_cache_limit = 256

    def cache_metadata(
        self, connection_id: str, table_name: str, schema: str | None, metadata: Dict[str, Any]
    ) -> None:
        """Store a defensive copy of table metadata in the bounded LRU cache."""
        key = (connection_id, table_name, schema)
        with self._registry_lock:
            self._metadata_cache[key] = deepcopy(metadata)
            self._metadata_cache.move_to_end(key)
            while len(self._metadata_cache) > self._metadata_cache_limit:
                self._metadata_cache.popitem(last=False)

    def get_cached_metadata(
        self, connection_id: str, table_name: str, schema: str | None = None
    ) -> Dict[str, Any] | None:
        """Return a defensive copy of cached metadata, if present."""
        key = (connection_id, table_name, schema)
        with self._registry_lock:
            metadata = self._metadata_cache.get(key)
            if metadata is None:
                return None
            self._metadata_cache.move_to_end(key)
            return deepcopy(metadata)

    def metadata_cache_size(self) -> int:
        with self._registry_lock:
            return len(self._metadata_cache)

    def invalidate_metadata_cache(self, connection_id: str) -> None:
        """Invalidate all table metadata associated with one connection."""
        with self._registry_lock:
            for key in [key for key in self._metadata_cache if key[0] == connection_id]:
                self._metadata_cache.pop(key, None)
    
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
                # MCP handlers may execute this connection in a worker thread.
                connection = sqlite3.connect(config.database, check_same_thread=False)
                connection.row_factory = sqlite3.Row  # Enable dict-like access
            else:
                raise DatabaseConnectionError(f"Unsupported database type: {config.type}")
            
            with self._registry_lock:
                self.connections[connection_id] = connection
                self._connection_locks[connection_id] = threading.RLock()
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
        lock = self._connection_lock_for(connection_id)
        with lock:
            with self._registry_lock:
                connection = self.connections.get(connection_id)
            if connection is None:
                raise DatabaseConnectionError(f"Connection {connection_id} not found")

            try:
                if getattr(connection, "closed", 0):
                    raise DatabaseConnectionError("connection is closed")
                if hasattr(connection, "ping"):
                    connection.ping(reconnect=True)
            except Exception as exc:
                logger.warning("Connection %s is dead, removing: %s", connection_id, exc)
                self._remove_connection(connection_id, connection)
                raise DatabaseConnectionError(
                    f"Connection {connection_id} is no longer valid"
                ) from exc
            return connection

    def _connection_lock_for(self, connection_id: str) -> Any:
        """Return a per-connection lock, including for legacy test doubles."""
        with self._registry_lock:
            if connection_id not in self.connections:
                raise DatabaseConnectionError(f"Connection {connection_id} not found")
            # A few integrations inject a connection directly into the public
            # mapping. Lazily creating the lock preserves that compatibility.
            return self._connection_locks.setdefault(connection_id, threading.RLock())

    def _remove_connection(self, connection_id: str, connection: Any) -> None:
        """Close and remove a connection while its per-connection lock is held."""
        try:
            connection.close()
        except Exception as exc:
            logger.error("Error closing connection %s: %s", connection_id, exc)
        finally:
            with self._registry_lock:
                self.connections.pop(connection_id, None)
                self.connection_configs.pop(connection_id, None)
                self._connection_locks.pop(connection_id, None)
                self.invalidate_metadata_cache(connection_id)
        logger.info("Closed connection %s", connection_id)
    
    def close_connection(self, connection_id: str) -> bool:
        """
        Close a connection
        
        Args:
            connection_id: Connection identifier
            
        Returns:
            True if connection was closed, False if not found
        """
        with self._registry_lock:
            if connection_id not in self.connections:
                return False
            lock = self._connection_locks.setdefault(connection_id, threading.RLock())

        with lock:
            with self._registry_lock:
                connection = self.connections.get(connection_id)
            if connection is None:
                return False
            self._remove_connection(connection_id, connection)
            return True
    
    def get_connection_info(self, connection_id: str) -> Optional[DatabaseConfig]:
        """
        Get connection configuration (with masked password)
        
        Args:
            connection_id: Connection identifier
            
        Returns:
            Database configuration or None if not found
        """
        with self._registry_lock:
            config = self.connection_configs.get(connection_id)
        return config.model_copy(deep=True) if config else None
    
    def list_connections(self) -> Dict[str, Dict[str, Any]]:
        """
        List all active connections
        
        Returns:
            Dict of connection_id -> connection_info
        """
        with self._registry_lock:
            configs = list(self.connection_configs.items())
            active_ids = set(self.connections)
        result = {}
        for conn_id, config in configs:
            result[conn_id] = {
                "type": config.type,
                "host": config.host,
                "port": config.port,
                "database": config.database,
                "username": config.username,
                "status": "active" if conn_id in active_ids else "closed"
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
        lock = self._connection_lock_for(connection_id)
        with lock:
            with self._registry_lock:
                connection = self.connections.get(connection_id)
            if connection is None:
                raise DatabaseConnectionError(f"Connection {connection_id} not found")
            try:
                if getattr(connection, "closed", 0):
                    raise DatabaseConnectionError("connection is closed")
                if hasattr(connection, "ping"):
                    connection.ping(reconnect=True)
            except Exception as exc:
                logger.warning("Connection %s is dead, removing: %s", connection_id, exc)
                self._remove_connection(connection_id, connection)
                raise DatabaseConnectionError(
                    f"Connection {connection_id} is no longer valid"
                ) from exc
            try:
                cursor = connection.cursor()
            except Exception as exc:
                self._remove_connection(connection_id, connection)
                raise DatabaseConnectionError(
                    f"Connection {connection_id} is no longer valid"
                ) from exc
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
        connection = None
        try:
            # SQLite defaults to an implicit transaction.  Keep its writes
            # durable at this boundary without changing the caller's SQL API.
            connection = self.get_connection(connection_id)
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
                    
                else:
                    result = []  # No results (e.g., INSERT/UPDATE/DELETE)

                if isinstance(connection, sqlite3.Connection):
                    connection.commit()
                statement = re.sub(
                    r"^\s*(?:(?:/\*.*?\*/)|(?:--[^\n]*(?:\n|$)))\s*",
                    "",
                    query,
                    flags=re.DOTALL,
                ).upper()
                if re.match(r"(?:ALTER|CREATE|DROP|RENAME|TRUNCATE)\b", statement):
                    self.invalidate_metadata_cache(connection_id)
                return result
                    
        except Exception as e:
            if isinstance(connection, sqlite3.Connection):
                try:
                    connection.rollback()
                except Exception as rollback_error:
                    logger.warning("SQLite rollback failed after query error: %s", rollback_error)
            logger.error(f"Query execution failed: {e}")
            raise DatabaseQueryError(f"Failed to execute query: {str(e)}")
    
    def __del__(self):
        """Clean up connections on destruction"""
        try:
            with self._registry_lock:
                connection_ids = list(self.connections.keys())
        except Exception:
            connection_ids = []
        for connection_id in connection_ids:
            try:
                self.close_connection(connection_id)
            except Exception:
                pass


# Global connection manager instance
connection_manager = ConnectionManager()
