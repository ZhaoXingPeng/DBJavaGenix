"""
Synchronous wrapper functions for MCP tools to be used in CLI
"""
import asyncio
from typing import Dict, Any, List, Optional
from .database.mcp_tools import (
    handle_db_connect_test as async_handle_db_connect_test,
    handle_db_query_databases as async_handle_db_query_databases,
    handle_db_query_tables as async_handle_db_query_tables,
    handle_db_codegen_analyze as async_handle_db_codegen_analyze,
    handle_db_codegen_generate as async_handle_db_codegen_generate
)
from .database.mcp_tools import (
    handle_springboot_read_config as async_handle_springboot_read_config
)


def handle_db_connect_test(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """
    Synchronous wrapper for db_connect_test
    """
    try:
        result = asyncio.run(async_handle_db_connect_test(arguments))
        if result and len(result) > 0:
            # Parse the response from TextContent
            response_text = result[0].text
            if "Raw Response:" in response_text:
                # Extract the JSON part after "Raw Response:"
                import json
                try:
                    json_part = response_text.split("Raw Response:")[-1].strip()
                    return json.loads(json_part)
                except:
                    # If parsing fails, create a response based on content
                    if "Connection successful" in response_text:
                        # Extract connection_id from the text
                        lines = response_text.split('\n')
                        connection_id = None
                        server_info = None
                        
                        for line in lines:
                            if "Connection ID:" in line:
                                connection_id = line.split("Connection ID:")[-1].strip()
                            elif "Server info:" in line:
                                server_info = line.split("Server info:")[-1].strip()
                        
                        return {
                            "success": True,
                            "connection_id": connection_id,
                            "server_info": server_info
                        }
                    else:
                        return {"success": False, "error": "Connection failed"}
            else:
                # Direct response
                return {"success": False, "error": response_text}
        return {"success": False, "error": "No response"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def handle_db_query_databases(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """
    Synchronous wrapper for db_query_databases
    """
    try:
        result = asyncio.run(async_handle_db_query_databases(arguments))
        if result and len(result) > 0:
            response_text = result[0].text
            if "Raw Response:" in response_text:
                import json
                try:
                    json_part = response_text.split("Raw Response:")[-1].strip()
                    return json.loads(json_part)
                except:
                    return {"success": False, "error": "Failed to parse response"}
            else:
                return {"success": False, "error": response_text}
        return {"success": False, "error": "No response"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def handle_db_query_tables(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """
    Synchronous wrapper for db_query_tables
    """
    try:
        result = asyncio.run(async_handle_db_query_tables(arguments))
        if result and len(result) > 0:
            response_text = result[0].text
            if "Raw Response:" in response_text:
                import json
                try:
                    json_part = response_text.split("Raw Response:")[-1].strip()
                    return json.loads(json_part)
                except:
                    return {"success": False, "error": "Failed to parse response"}
            else:
                return {"success": False, "error": response_text}
        return {"success": False, "error": "No response"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def handle_db_codegen_analyze(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """
    Synchronous wrapper for db_codegen_analyze
    """
    try:
        result = asyncio.run(async_handle_db_codegen_analyze(arguments))
        if result and len(result) > 0:
            response_text = result[0].text
            if "Raw Response:" in response_text:
                import json
                try:
                    json_part = response_text.split("Raw Response:")[-1].strip()
                    return json.loads(json_part)
                except:
                    return {"success": False, "error": "Failed to parse response"}
            else:
                # Try to parse as JSON directly
                import json
                try:
                    return json.loads(response_text)
                except:
                    return {"success": False, "error": response_text}
        return {"success": False, "error": "No response"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def handle_db_codegen_generate(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """
    Synchronous wrapper for db_codegen_generate
    """
    try:
        result = asyncio.run(async_handle_db_codegen_generate(arguments))
        if result and len(result) > 0:
            response_text = result[0].text
            if "Raw Response:" in response_text:
                import json
                try:
                    json_part = response_text.split("Raw Response:")[-1].strip()
                    return json.loads(json_part)
                except:
                    return {"success": False, "error": "Failed to parse response"}
            else:
                # Try to parse as JSON directly
                import json
                try:
                    return json.loads(response_text)
                except:
                    return {"success": False, "error": response_text}
        return {"success": False, "error": "No response"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def handle_springboot_read_config(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """
    Synchronous wrapper for springboot_read_config
    """
    try:
        result = asyncio.run(async_handle_springboot_read_config(arguments))
        if result and len(result) > 0:
            response_text = result[0].text
            if "Raw Response:" in response_text:
                import json
                try:
                    json_part = response_text.split("Raw Response:")[-1].strip()
                    return json.loads(json_part)
                except Exception:
                    return {"success": False, "error": "Failed to parse response"}
            else:
                return {"success": False, "error": response_text}
        return {"success": False, "error": "No response"}
    except Exception as e:
        return {"success": False, "error": str(e)}
