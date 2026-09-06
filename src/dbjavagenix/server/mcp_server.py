"""
DBJavaGenix MCP Server
Provides database analysis and Java code generation capabilities through MCP tools
"""
import asyncio
import json
import logging
from typing import Any, Callable, Sequence

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
from ..database.observability_tools import (
    get_observability_tools,
    handle_server_health,
    handle_server_metrics,
)
from ..database.schema_algorithms_tools import (
    get_schema_algorithm_tools,
    handle_schema_topo_order,
    handle_schema_cluster_tables,
    handle_schema_check_cycles,
)
from ..utils.metrics import GLOBAL_TOOL_METRICS
from ..utils.security import redact_sensitive_data, redact_sensitive_text
from ..utils.logging_config import configure_logging
from ..utils.tool_registry import filter_tools_for_listing

# Configure logging (P5.2: plain / json via DBJAVAGENIX_LOG_FORMAT)
configure_logging()
logger = logging.getLogger(__name__)

# Create MCP server instance
server = Server("dbjavagenix")


ToolFactory = Callable[[], list[Tool]]

_TOOL_FACTORIES: tuple[ToolFactory, ...] = (
    get_connection_tools,
    get_table_analysis_tools,
    get_codegen_tools,
    get_atomic_codegen_tools,
    get_springboot_project_tools,
    get_visualization_tools,
    get_ai_tools,
    get_observability_tools,
    get_schema_algorithm_tools,
    get_discovery_tools,
)


def _all_tools() -> list[Tool]:
    """Build the canonical tool list used by both listing and dispatch."""
    tools: list[Tool] = []
    names: set[str] = set()
    for factory in _TOOL_FACTORIES:
        for tool in factory():
            if tool.name in names:
                raise RuntimeError(f"Duplicate MCP tool name: {tool.name}")
            names.add(tool.name)
            tools.append(tool)
    return tools


def _tool_handlers(tools: list[Tool] | None = None) -> dict[str, Callable[..., Any]]:
    """Resolve handlers from the canonical tool names.

    The project convention is ``<tool name>`` -> ``handle_<tool name>``. Keeping
    this lookup derived from the tool list prevents list/dispatch drift when a
    new tool is added.
    """
    handlers: dict[str, Callable[..., Any]] = {}
    missing: list[str] = []
    for tool in tools if tools is not None else _all_tools():
        name = tool.name
        handler = globals().get(f"handle_{name}")
        if callable(handler):
            handlers[name] = handler
        else:
            missing.append(name)
    if missing:
        raise RuntimeError(f"Missing MCP handlers: {', '.join(sorted(missing))}")
    return handlers


def _tool_error_response(tool_name: str, error_code: str, error: object) -> list[TextContent]:
    """Build the stable error envelope exposed at the MCP boundary."""
    payload = {
        "success": False,
        "error": error_code,
        "tool": tool_name,
        "message": redact_sensitive_text(error),
    }
    return [TextContent(type="text", text=json.dumps(payload, ensure_ascii=False))]


@server.list_tools()
async def handle_list_tools() -> list[Tool]:
    """
    List all available MCP tools
    
    Returns:
        List of available tools
    """
    tools = _all_tools()
    _tool_handlers(tools)

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
    logger.info("Calling tool: %s with arguments: %s", name, redact_sensitive_data(arguments))
    import time as _time_for_metrics
    _start_perf = _time_for_metrics.perf_counter()
    _is_error = False
    try:
        handler = _tool_handlers().get(name)
        if handler is None:
            _is_error = True
            return _tool_error_response(name, "unknown_tool", f"Unknown tool: {name}")
        return await handler(arguments)
            
    except Exception as e:
        _is_error = True
        safe_message = redact_sensitive_text(e)
        logger.error("Tool execution failed for %s: %s", name, safe_message)
        return _tool_error_response(name, "tool_execution_failed", safe_message)
    finally:
        _duration_ms = (_time_for_metrics.perf_counter() - _start_perf) * 1000
        GLOBAL_TOOL_METRICS.record(name, _duration_ms, _is_error)


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
