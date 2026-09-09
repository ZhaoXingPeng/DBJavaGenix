"""Contract tests for canonical MCP tool listing and dispatch."""

import json

from mcp.types import TextContent, Tool
import pytest

from dbjavagenix.server import mcp_server


@pytest.mark.asyncio
async def test_every_listed_tool_has_a_handler():
    tools = await mcp_server.handle_list_tools()
    names = [tool.name for tool in tools]
    handlers = mcp_server._tool_handlers()

    assert len(names) == len(set(names))
    assert set(names) == set(handlers)
    assert all(callable(handler) for handler in handlers.values())


@pytest.mark.asyncio
async def test_schema_algorithm_tools_are_listed_and_dispatchable():
    tools = await mcp_server.handle_list_tools()
    names = {tool.name for tool in tools}

    assert {
        "schema_topo_order",
        "schema_cluster_tables",
        "schema_check_cycles",
    } <= names

    result = await mcp_server.handle_call_tool(
        "schema_topo_order",
        {"tables": ["parent", "child"], "fks": [["child", "parent"]]},
    )
    payload = json.loads(result[0].text)
    assert payload["order"] == ["parent", "child"]


@pytest.mark.asyncio
async def test_dispatch_resolves_handler_from_canonical_name(monkeypatch):
    calls = []

    async def fake_health(arguments):
        calls.append(arguments)
        return [TextContent(type="text", text="ok")]

    monkeypatch.setattr(mcp_server, "handle_server_health", fake_health)

    result = await mcp_server.handle_call_tool("server_health", {"verbose": True})

    assert result[0].text == "ok"
    assert calls == [{"verbose": True}]


@pytest.mark.asyncio
async def test_disconnect_is_dispatchable_from_canonical_name(monkeypatch):
    calls = []

    async def fake_disconnect(arguments):
        calls.append(arguments)
        return [TextContent(type="text", text="closed")]

    monkeypatch.setattr(mcp_server, "handle_db_disconnect", fake_disconnect)

    result = await mcp_server.handle_call_tool("db_disconnect", {"connection_id": "conn-1"})

    assert result[0].text == "closed"
    assert calls == [{"connection_id": "conn-1"}]


@pytest.mark.asyncio
async def test_unknown_tool_returns_structured_error(monkeypatch):
    monkeypatch.setattr(mcp_server, "_tool_handlers", lambda: {})

    result = await mcp_server.handle_call_tool("missing_tool", {})
    payload = json.loads(result[0].text)

    assert payload == {
        "success": False,
        "error": "unknown_tool",
        "tool": "missing_tool",
        "message": "Unknown tool: missing_tool",
    }


@pytest.mark.asyncio
async def test_handler_exception_returns_redacted_structured_error(monkeypatch):
    async def fail(_arguments):
        raise RuntimeError("failed for jdbc:mysql://reader:db-secret@db/app")

    monkeypatch.setattr(mcp_server, "_tool_handlers", lambda: {"failing_tool": fail})

    result = await mcp_server.handle_call_tool("failing_tool", {})
    payload = json.loads(result[0].text)

    assert payload["success"] is False
    assert payload["error"] == "tool_execution_failed"
    assert payload["tool"] == "failing_tool"
    assert payload["message"] == "failed for jdbc:mysql://reader:***@db/app"
    assert "db-secret" not in result[0].text


@pytest.mark.asyncio
async def test_structured_failure_response_is_counted_as_error(monkeypatch):
    async def fail_without_raise(_arguments):
        return [
            TextContent(
                type="text",
                text='Database query failed\n\nRaw Response: {"success": false, "error": "query_failed"}',
            )
        ]

    monkeypatch.setattr(
        mcp_server, "_tool_handlers", lambda: {"reported_failure": fail_without_raise}
    )
    mcp_server.GLOBAL_TOOL_METRICS.reset()

    result = await mcp_server.handle_call_tool("reported_failure", {})

    assert json.loads(result[0].text.split("Raw Response:", 1)[1].strip())["success"] is False
    stats = mcp_server.GLOBAL_TOOL_METRICS.get_stats("reported_failure")
    assert stats.calls == 1
    assert stats.errors == 1


@pytest.mark.asyncio
async def test_structured_success_response_is_not_counted_as_error(monkeypatch):
    async def success(_arguments):
        return [TextContent(type="text", text='{"success": true, "value": 1}')]

    monkeypatch.setattr(mcp_server, "_tool_handlers", lambda: {"reported_success": success})
    mcp_server.GLOBAL_TOOL_METRICS.reset()

    await mcp_server.handle_call_tool("reported_success", {})

    stats = mcp_server.GLOBAL_TOOL_METRICS.get_stats("reported_success")
    assert stats.calls == 1
    assert stats.errors == 0


def test_handler_registry_rejects_duplicate_tool_names(monkeypatch):
    duplicate = Tool(name="duplicate", description="test", inputSchema={"type": "object"})
    monkeypatch.setattr(mcp_server, "_TOOL_FACTORIES", (lambda: [duplicate, duplicate],))

    with pytest.raises(RuntimeError, match="Duplicate MCP tool name"):
        mcp_server._tool_handlers()
