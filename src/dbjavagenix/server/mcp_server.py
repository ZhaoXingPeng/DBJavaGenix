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
from ..database.atomic_codegen_tools import (
    get_atomic_codegen_tools,
    handle_codegen_build_context,
    handle_codegen_render_entity,
    handle_codegen_render_dao,
    handle_codegen_render_service,
    handle_codegen_render_controller,
    handle_codegen_render_mapper,
)
from ..database.discovery_tools import (
    get_discovery_tools,
    handle_search_tools,
)
from ..database.visualization_tools import (
    get_visualization_tools,
    handle_db_render_er_diagram,
)
from ..database.ai_tools import (
    get_ai_tools,
    handle_ai_infer_business_names,
    handle_ai_metrics,
    handle_ai_recommend_template,
    handle_ai_summarize_schema,
)
from ..utils.tool_registry import filter_tools_for_listing

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
    
    # Add code generation tools (legacy: db_codegen_analyze + db_codegen_generate)
    tools.extend(get_codegen_tools())

    # Add atomic code generation tools (P2.2: build_context + 5 render_* layers)
    tools.extend(get_atomic_codegen_tools())

    # Add SpringBoot project validation tools
    tools.extend(get_springboot_project_tools())

    # Add visualization tools (P3.1: ER diagram via mcp-apps)
    tools.extend(get_visualization_tools())

    # Add AI semantic tools (P4: naming inference, template recommendation, schema summary)
    tools.extend(get_ai_tools())

    # Add discovery tools (P2.3: search_tools for progressive disclosure)
    tools.extend(get_discovery_tools())

    # Apply progressive-mode filter (env DBJAVAGENIX_PROGRESSIVE=1)
    visible_tools = filter_tools_for_listing(tools)
    if len(visible_tools) != len(tools):
        logger.info(
            f"Progressive mode active: exposing {len(visible_tools)}/{len(tools)} tools"
        )
    else:
        logger.info(f"Listed {len(tools)} available tools")
    return visible_tools


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
        
        # Code generation tools (legacy single-shot)
        elif name == "db_codegen_analyze":
            return await handle_db_codegen_analyze(arguments)
        elif name == "db_codegen_generate":
            return await handle_db_codegen_generate(arguments)

        # Atomic code generation tools (P2.2)
        elif name == "codegen_build_context":
            return await handle_codegen_build_context(arguments)
        elif name == "codegen_render_entity":
            return await handle_codegen_render_entity(arguments)
        elif name == "codegen_render_dao":
            return await handle_codegen_render_dao(arguments)
        elif name == "codegen_render_service":
            return await handle_codegen_render_service(arguments)
        elif name == "codegen_render_controller":
            return await handle_codegen_render_controller(arguments)
        elif name == "codegen_render_mapper":
            return await handle_codegen_render_mapper(arguments)
        
        # (deprecated/removed) java_check_dependencies was never implemented here;
        # dependency analysis is covered by springboot_* tools.
            
        # SpringBoot project validation tools
        elif name == "springboot_validate_project":
            return await handle_springboot_validate_project(arguments)
        elif name == "springboot_analyze_dependencies":
            return await handle_springboot_analyze_dependencies(arguments)
        elif name == "springboot_read_config":
            return await handle_springboot_read_config(arguments)

        # Visualization tools (P3.1: MCP Apps)
        elif name == "db_render_er_diagram":
            return await handle_db_render_er_diagram(arguments)

        # AI semantic tools (P4)
        elif name == "ai_infer_business_names":
            return await handle_ai_infer_business_names(arguments)
        elif name == "ai_recommend_template":
            return await handle_ai_recommend_template(arguments)
        elif name == "ai_summarize_schema":
            return await handle_ai_summarize_schema(arguments)
        elif name == "ai_metrics":
            return await handle_ai_metrics(arguments)

        # Discovery meta-tool (P2.3)
        elif name == "search_tools":
            return await handle_search_tools(arguments)

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
