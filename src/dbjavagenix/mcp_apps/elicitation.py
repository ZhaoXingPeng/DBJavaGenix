"""MCP v3 (2025-06-18 spec) elicitation helper.

`elicitation` lets the server ask the client to collect structured input from
the user (typically a form). Useful when a tool needs additional info that the
caller (LLM) couldn't infer.

The MCP wire format is:
```
{
  "method": "elicitation/create",
  "params": {
    "message": "请输入数据库连接信息",
    "requestedSchema": { ...JSON Schema... }
  }
}
```

This module:
1. Builds the request payload (`build_elicitation_request`)
2. Builds a graceful "missing params -> elicitation hint" response that works
   across clients (supporting and non-supporting):
   - If the client declared `elicitation` capability, the server should send
     `elicitation/create` (caller's responsibility)
   - Otherwise the response embeds a `_meta.elicitation` hint so the LLM /
     client can fall back to asking the user via text

Compatibility:
- Claude Desktop 4.x: native elicitation support → renders modal form
- Cherry Studio 1.5+: native support → inline form
- Cursor: no support → falls back to text-based question
- Continue.dev: partial → may render as JSON prompt
"""

from __future__ import annotations

from typing import Any


def build_elicitation_request(
    message: str,
    requested_schema: dict[str, Any],
) -> dict[str, Any]:
    """Build an MCP elicitation/create request payload.

    Args:
        message: human-readable prompt shown to the user
        requested_schema: JSON Schema for the data the server wants back

    Returns:
        Dict ready to be sent as the `params` of `elicitation/create`.
    """
    if not isinstance(message, str) or not message:
        raise ValueError("message must be a non-empty string")
    if not isinstance(requested_schema, dict):
        raise ValueError("requested_schema must be a dict (JSON Schema)")
    if requested_schema.get("type") != "object":
        raise ValueError("requested_schema must have type=object at the top level")
    return {
        "message": message,
        "requestedSchema": requested_schema,
    }


def missing_params_to_elicitation(
    tool_name: str,
    received: dict[str, Any],
    schema: dict[str, Any],
) -> dict[str, Any] | None:
    """Return an elicitation request for missing required params, or None.

    Args:
        tool_name: name of the tool that was called (for the prompt message)
        received: arguments the tool actually received
        schema: the tool's `inputSchema` (must be a JSON Schema with `required`)

    Returns:
        Dict suitable for `build_elicitation_request`, or None if all required
        params are present.
    """
    required: list[str] = schema.get("required", []) or []
    properties: dict[str, Any] = schema.get("properties", {}) or {}

    missing = [k for k in required if k not in received or received[k] in (None, "")]
    if not missing:
        return None

    sub_properties = {k: properties[k] for k in missing if k in properties}
    sub_schema = {
        "type": "object",
        "required": missing,
        "properties": sub_properties,
    }
    return build_elicitation_request(
        message=f"{tool_name} 需要补充以下信息: {', '.join(missing)}",
        requested_schema=sub_schema,
    )


def to_meta_hint(elicitation_request: dict[str, Any]) -> dict[str, Any]:
    """Wrap an elicitation request as an `_meta` payload.

    For clients that don't natively support `elicitation/create`, server can
    include this in tool error response's `_meta` field so the LLM can read
    and ask the user via text.
    """
    return {
        "mcp-apps/elicitation": elicitation_request,
    }
