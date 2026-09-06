# ADR-012: Pin MCP SDK to the 1.x API Contract

- **Status**: Accepted
- **Date**: 2026-09-06
- **Related issue**: #5

## Context

DBJavaGenix registers handlers with the MCP Python SDK `Server.list_tools()` and `Server.call_tool()` APIs. The dependency declaration previously specified only `mcp>=1.6.0`. A fresh CI install resolved `mcp==2.1.1`, where the registration API is no longer compatible; test collection failed before any application test ran.

## Decision

Declare `mcp>=1.6.0,<2.0` consistently in `pyproject.toml`, `requirements.txt`, and `requirements-min.txt`. Upgrade to MCP 2.x is a separate migration with an explicit compatibility test, ADR update, and release note.

## Consequences

- Reproducible installs continue to use the API contract tested by this repository.
- Security and bug fixes within the 1.x line remain available through the lower-bound range.
- MCP 2.x features are deferred until the server registration, transport, and type models are migrated together.

## Verification

The CI quality matrix installs from `pyproject.toml` and runs the complete unit suite. A future MCP upgrade must first make this suite pass on the new major version.
