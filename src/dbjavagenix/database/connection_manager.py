"""
Database connection manager for DBJavaGenix MCP tools
"""
import uuid
from typing import Dict, List, Any, Optional
import pymysql
import sqlite3
import logging
from contextlib import contextmanager

from ..core.models import DatabaseConfig, DatabaseType
from ..core.exceptions import DatabaseConnectionError, DatabaseQueryError

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages database connections for MCP tools"""
    
    def __init__(self):
        self.connections: Dict[str, Any] = {}
        self.connection_configs: Dict[str, DatabaseConfig] = {}
    
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
            logger.error(f"Failed to create connection: {e}")
            raise DatabaseConnectionError(f"Failed to connect to database: {str(e)}")
    
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
            return False
        
        try:
            connection = self.connections[connection_id]
            connection.close()
            del self.connections[connection_id]
            del self.connection_configs[connection_id]
            logger.info(f"Closed connection {connection_id}")
            return True
        except Exception as e:
            logger.error(f"Error closing connection {connection_id}: {e}")
            # Remove from dict anyway
            self.connections.pop(connection_id, None)
            self.connection_configs.pop(connection_id, None)
            return True
    
    def get_connection_info(self, connection_id: str) -> Optional[DatabaseConfig]:
        """
        Get connection configuration (with masked password)
        
        Args:
            connection_id: Connection identifier
            
        Returns:
            Database configuration or None if not found
        """
        return self.connection_configs.get(connection_id)
    
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
                    
                    return result
                else:
                    return []  # No results (e.g., INSERT/UPDATE/DELETE)
                    
        except Exception as e:
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