"""Synchronous adapters for MCP handlers used by the command-line interface."""

import asyncio
import json
import re
from typing import Any, Awaitable, Callable, Dict, List, Optional

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
from .utils.security import redact_sensitive_text


_AsyncHandler = Callable[[Dict[str, Any]], Awaitable[List[Any]]]


def _parse_json_object(response_text: str) -> Optional[Dict[str, Any]]:
    """Extract the first JSON object from an MCP text response.

    MCP handlers normally append a JSON object after ``Raw Response:``.  A
    direct JSON response is also accepted for compatibility with lightweight
    adapters and test doubles.
    """
    normalized = response_text.strip()
    candidates = []
    if "Raw Response:" in normalized:
        candidates.append(normalized.rsplit("Raw Response:", 1)[1].strip())
    candidates.append(normalized)

    for candidate in candidates:
        try:
            payload = json.loads(candidate)
        except (TypeError, json.JSONDecodeError):
            continue
        if isinstance(payload, dict):
            return payload
    return None


def _parse_connection_text(response_text: str) -> Optional[Dict[str, Any]]:
    """Recover a successful connection result from human-readable MCP text."""
    if not re.search(r"database\s+connection\s+successful", response_text, re.IGNORECASE):
        return None

    connection_match = re.search(
        r"connection\s+id\s*:\s*(?P<value>[^\s]+)", response_text, re.IGNORECASE
    )
    if connection_match is None:
        return None

    server_match = re.search(r"server(?:\s+info)?\s*:\s*(?P<value>[^\r\n]+)", response_text, re.IGNORECASE)
    return {
        "success": True,
        "connection_id": connection_match.group("value"),
        "server_info": server_match.group("value").strip() if server_match else None,
    }


def _run_mcp_sync(
    handler: _AsyncHandler,
    arguments: Dict[str, Any],
    *,
    text_fallback: Optional[Callable[[str], Optional[Dict[str, Any]]]] = None,
) -> Dict[str, Any]:
    """Run one async MCP handler and normalize its response for the CLI."""
    try:
        result = asyncio.run(handler(arguments))
    except Exception as exc:
        return {"success": False, "error": redact_sensitive_text(exc)}

    if not result:
        return {"success": False, "error": "No response"}

    response_text = getattr(result[0], "text", None)
    if not isinstance(response_text, str) or not response_text.strip():
        return {"success": False, "error": "No response"}

    payload = _parse_json_object(response_text)
    if payload is not None:
        return payload

    if text_fallback is not None:
        fallback = text_fallback(response_text)
        if fallback is not None:
            return fallback

    return {"success": False, "error": "Failed to parse response"}


def handle_db_connect_test(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Synchronous wrapper for ``db_connect_test``."""
    return _run_mcp_sync(
        async_handle_db_connect_test,
        arguments,
        text_fallback=_parse_connection_text,
    )


def handle_db_query_databases(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Synchronous wrapper for ``db_query_databases``."""
    return _run_mcp_sync(async_handle_db_query_databases, arguments)


def handle_db_query_tables(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Synchronous wrapper for ``db_query_tables``."""
    return _run_mcp_sync(async_handle_db_query_tables, arguments)


def handle_db_codegen_analyze(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Synchronous wrapper for ``db_codegen_analyze``."""
    return _run_mcp_sync(async_handle_db_codegen_analyze, arguments)


def handle_db_codegen_generate(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Synchronous wrapper for ``db_codegen_generate``."""
    return _run_mcp_sync(async_handle_db_codegen_generate, arguments)


def handle_springboot_read_config(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Synchronous wrapper for ``springboot_read_config``."""
    return _run_mcp_sync(async_handle_springboot_read_config, arguments)
