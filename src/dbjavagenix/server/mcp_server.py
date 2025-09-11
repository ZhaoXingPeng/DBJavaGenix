"""
DBJavaGenix MCP Server
Provides database analysis and Java code generation capabilities through MCP tools
"""
import asyncio
import logging
from typing import Any, Sequence

from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.types import Resource, Tool, TextContent, ImageContent, EmbeddedResource
import mcp.server.stdio

from ..database.mcp_tools import (
    get_connection_tools,
    get_table_analysis_tools,
    get_codegen_tools,
    get_springboot_project_tools,
    handle_db_connect_test,
    handle_db_query_databases,
    handle_db_query_tables, 
    handle_db_query_table_exists,
    handle_db_query_execute,
    handle_db_table_describe,
    handle_db_table_columns,
    handle_db_table_primary_keys,
    handle_db_table_foreign_keys,
    handle_db_table_indexes,
    handle_db_codegen_analyze,
    handle_db_codegen_generate,
    handle_springboot_validate_project,
    handle_springboot_analyze_dependencies,
    handle_springboot_read_config
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create MCP server instance
server = Server("dbjavagenix")


@server.list_tools()
async def handle_list_tools() -> list[Tool]:
    """
    List all available MCP tools
    
    Returns:
        List of available tools
    """
    tools = []
    
    # Add database connection and query tools
    tools.extend(get_connection_tools())
    
    # Add table structure analysis tools
    tools.extend(get_table_analysis_tools())
    
    # Add code generation tools
    tools.extend(get_codegen_tools())
    
    # Add SpringBoot project validation tools  
    tools.extend(get_springboot_project_tools())
    
    logger.info(f"Listed {len(tools)} available tools")
    return tools


@server.call_tool()
async def handle_call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent | ImageContent | EmbeddedResource]:
    """
    Handle tool execution
    
    Args:
        name: Tool name
        arguments: Tool arguments
        
    Returns:
        Tool execution results
    """
    logger.info(f"Calling tool: {name} with arguments: {arguments}")
    
    try:
        # Database connection and query tools
        if name == "db_connect_test":
            return await handle_db_connect_test(arguments)
        elif name == "db_query_databases":
            return await handle_db_query_databases(arguments)
        elif name == "db_query_tables":
            return await handle_db_query_tables(arguments)
        elif name == "db_query_table_exists":
            return await handle_db_query_table_exists(arguments)
        elif name == "db_query_execute":
            return await handle_db_query_execute(arguments)
        
        # Table structure analysis tools
        elif name == "db_table_describe":
            return await handle_db_table_describe(arguments)
        elif name == "db_table_columns":
            return await handle_db_table_columns(arguments)
        elif name == "db_table_primary_keys":
            return await handle_db_table_primary_keys(arguments)
        elif name == "db_table_foreign_keys":
            return await handle_db_table_foreign_keys(arguments)
        elif name == "db_table_indexes":
            return await handle_db_table_indexes(arguments)
        
        # Code generation tools
        elif name == "db_codegen_analyze":
            return await handle_db_codegen_analyze(arguments)
        elif name == "db_codegen_generate":
            return await handle_db_codegen_generate(arguments)
        
        # (deprecated/removed) java_check_dependencies was never implemented here;
        # dependency analysis is covered by springboot_* tools.
            
        # SpringBoot project validation tools
        elif name == "springboot_validate_project":
            return await handle_springboot_validate_project(arguments)
        elif name == "springboot_analyze_dependencies":
            return await handle_springboot_analyze_dependencies(arguments)
        elif name == "springboot_read_config":
            return await handle_springboot_read_config(arguments)
        else:
            raise ValueError(f"Unknown tool: {name}")
            
    except Exception as e:
        logger.error(f"Tool execution failed: {e}")
        return [TextContent(
            type="text",
            text=f"Tool execution failed: {str(e)}"
        )]


async def run_server():
    """
    Run the MCP server
    """
    logger.info("Starting DBJavaGenix MCP Server...")
    
    try:
        # Run the server using stdio transport
        async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
            from mcp.types import ServerCapabilities
            
            await server.run(
                read_stream, 
                write_stream,
                InitializationOptions(
                    server_name="dbjavagenix",
                    server_version="0.1.0",
                    capabilities=ServerCapabilities(
                        tools=dict(listChanged=False)
                    )
                )
            )
    except Exception as e:
        logger.error(f"Server startup error: {e}")
        import traceback
        logger.error(f"Stack trace: {traceback.format_exc()}")
        raise


def main():
    """
    Main entry point for the MCP server
    """
    try:
        asyncio.run(run_server())
    except KeyboardInterrupt:
        logger.info("Server shutdown requested")
    except Exception as e:
        logger.error(f"Server error: {e}")
        raise


if __name__ == "__main__":
    main()
