"""Contract tests for canonical MCP tool listing and dispatch."""

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
async def test_dispatch_resolves_handler_from_canonical_name(monkeypatch):
    calls = []

    async def fake_health(arguments):
        calls.append(arguments)
        return [TextContent(type="text", text="ok")]

    monkeypatch.setattr(mcp_server, "handle_server_health", fake_health)

    result = await mcp_server.handle_call_tool("server_health", {"verbose": True})

    assert result[0].text == "ok"
    assert calls == [{"verbose": True}]


def test_handler_registry_rejects_duplicate_tool_names(monkeypatch):
    duplicate = Tool(name="duplicate", description="test", inputSchema={"type": "object"})
    monkeypatch.setattr(mcp_server, "_TOOL_FACTORIES", (lambda: [duplicate, duplicate],))

    with pytest.raises(RuntimeError, match="Duplicate MCP tool name"):
        mcp_server._tool_handlers()
