"""Regression tests for the synchronous MCP-to-CLI response adapter."""

import pytest
from mcp.types import TextContent

from dbjavagenix import cli_helpers


def _text_response(text: str) -> list[TextContent]:
    return [TextContent(type="text", text=text)]


def test_connection_text_fallback_is_case_insensitive(monkeypatch):
    async def fake_connect(_arguments):
        return _text_response(
            "Database connection successful!\n- Connection ID: conn-1\n- Server: SQLite"
        )

    monkeypatch.setattr(cli_helpers, "async_handle_db_connect_test", fake_connect)

    assert cli_helpers.handle_db_connect_test({}) == {
        "success": True,
        "connection_id": "conn-1",
        "server_info": "SQLite",
    }


@pytest.mark.parametrize(
    ("wrapper_name", "handler_name"),
    [
        ("handle_db_connect_test", "async_handle_db_connect_test"),
        ("handle_db_query_databases", "async_handle_db_query_databases"),
        ("handle_db_query_tables", "async_handle_db_query_tables"),
        ("handle_db_codegen_analyze", "async_handle_db_codegen_analyze"),
        ("handle_db_codegen_generate", "async_handle_db_codegen_generate"),
        ("handle_springboot_read_config", "async_handle_springboot_read_config"),
    ],
)
def test_all_wrappers_accept_direct_json(monkeypatch, wrapper_name, handler_name):
    async def fake_handler(_arguments):
        return _text_response('{"success": true, "value": 1}')

    monkeypatch.setattr(cli_helpers, handler_name, fake_handler)

    wrapper = getattr(cli_helpers, wrapper_name)
    assert wrapper({}) == {"success": True, "value": 1}


def test_adapter_accepts_raw_response_before_human_text():
    async def fake_handler(_arguments):
        return _text_response('Report\n\nRaw Response: {"success": true, "value": 2}')

    assert cli_helpers._run_mcp_sync(fake_handler, {}) == {
        "success": True,
        "value": 2,
    }


@pytest.mark.parametrize(
    "result",
    [[], _text_response("not-json")],
)
def test_adapter_returns_stable_parse_errors(result):
    async def fake_handler(_arguments):
        return result

    payload = cli_helpers._run_mcp_sync(fake_handler, {})

    assert payload["success"] is False
    assert payload["error"] in {"No response", "Failed to parse response"}


def test_adapter_redacts_exception_text():
    async def fake_handler(_arguments):
        raise RuntimeError("failed for jdbc:mysql://reader:db-secret@db/app")

    payload = cli_helpers._run_mcp_sync(fake_handler, {})

    assert payload == {
        "success": False,
        "error": "failed for jdbc:mysql://reader:***@db/app",
    }
