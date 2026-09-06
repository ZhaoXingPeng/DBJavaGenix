# ADR-013: Canonical MCP Tool Contract

- **Status**: Accepted
- **Date**: 2026-09-06
- **Related issue**: #8

## Context

The MCP server kept tool listing and tool dispatch in separate hand-maintained
lists. A new tool could therefore appear in `list_tools` without a callable
handler, or remain callable but undiscoverable. Tool metadata in
`utils/tool_registry.py` was a third independent list.

## Decision

`server/mcp_server.py` owns one ordered tuple of tool factories. Both
`handle_list_tools` and `handle_call_tool` derive their behavior from that
canonical collection. A tool named `example_tool` must expose
`handle_example_tool`; startup/listing validation fails when a handler is
missing or a tool name is duplicated.

The progressive-discovery metadata registry remains responsible for search,
categories, and visibility policy. A separate change may replace its manual
metadata with generated metadata after the public search contract is specified.

## Consequences

- Adding a tool requires one factory entry and one conventionally named handler;
  list/dispatch drift is detected by tests and at runtime.
- Existing tool order and progressive filtering remain unchanged.
- The metadata registry is intentionally not coupled to execution so search
  descriptions can evolve without changing dispatch behavior.

## Verification

`tests/unit/test_server_dispatch.py` verifies that every listed tool has a
handler, dispatch resolves the canonical name, and duplicate names fail fast.
