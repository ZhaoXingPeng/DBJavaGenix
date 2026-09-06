"""MCP tools wrapping schema-graph algorithms.

Exposes three tools:
- schema_topo_order: tables in dependency-safe order
- schema_cluster_tables: tables grouped into business clusters
- schema_check_cycles: detect FK cycles (anti-patterns)

All three operate on the same input shape:
{
    "tables": ["sys_user", "sys_role", "sys_user_role"],
    "fks": [["sys_user_role", "sys_user"], ["sys_user_role", "sys_role"]]
}

The connection_id parameter is optional: when provided, the tool fetches tables
and FKs from the live DB. When omitted, the caller supplies them directly
(useful for analysis-only flows without a DB connection).
"""

from __future__ import annotations

from typing import Any

from mcp.types import TextContent, Tool

from ..algorithms import (
    cluster_tables,
    find_cycles,
    topological_sort,
)


SCHEMA_TOPO_TOOL = Tool(
    name="schema_topo_order",
    description=(
        "Topologically sort tables by FK dependencies. Returns order safe for "
        "DDL creation or Service injection. Detects cycles via unresolved list."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "tables": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of table names",
            },
            "fks": {
                "type": "array",
                "items": {
                    "type": "array",
                    "items": {"type": "string"},
                    "minItems": 2,
                    "maxItems": 2,
                },
                "description": "List of [child, parent] FK tuples",
            },
        },
        "required": ["tables", "fks"],
    },
)


SCHEMA_CLUSTER_TOOL = Tool(
    name="schema_cluster_tables",
    description=(
        "Group tables into business clusters via Union-Find on FK connectivity. "
        "Returns clusters with suggested names (common prefix or central table)."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "tables": {
                "type": "array",
                "items": {"type": "string"},
            },
            "fks": {
                "type": "array",
                "items": {
                    "type": "array",
                    "items": {"type": "string"},
                    "minItems": 2,
                    "maxItems": 2,
                },
            },
        },
        "required": ["tables", "fks"],
    },
)


SCHEMA_CYCLE_TOOL = Tool(
    name="schema_check_cycles",
    description=(
        "Detect FK cycles in schema (anti-pattern). Returns cycles list and "
        "safe boolean. Self-references not reported as cycles."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "tables": {"type": "array", "items": {"type": "string"}},
            "fks": {
                "type": "array",
                "items": {
                    "type": "array",
                    "items": {"type": "string"},
                    "minItems": 2,
                    "maxItems": 2,
                },
            },
        },
        "required": ["tables", "fks"],
    },
)


def _parse_input(arguments: dict[str, Any]) -> tuple[list[str], list[tuple[str, str]]]:
    tables = list(arguments.get("tables", []))
    raw_fks = arguments.get("fks", [])
    fks: list[tuple[str, str]] = []
    for fk in raw_fks:
        if isinstance(fk, (list, tuple)) and len(fk) == 2:
            fks.append((str(fk[0]), str(fk[1])))
    return tables, fks


async def handle_schema_topo_order(arguments: dict[str, Any]) -> list[TextContent]:
    tables, fks = _parse_input(arguments)
    result = topological_sort(tables, fks)
    payload = {
        "order": result.order,
        "unresolved": result.unresolved,
        "levels": result.levels,
        "has_cycle": result.has_cycle,
    }
    return [TextContent(type="text", text=_render(payload))]


async def handle_schema_cluster_tables(
    arguments: dict[str, Any],
) -> list[TextContent]:
    tables, fks = _parse_input(arguments)
    result = cluster_tables(tables, fks)
    payload = {
        "num_clusters": result.num_clusters,
        "clusters": [
            {"name": result.naming.get(i, ""), "members": members}
            for i, members in enumerate(result.clusters)
        ],
    }
    return [TextContent(type="text", text=_render(payload))]


async def handle_schema_check_cycles(
    arguments: dict[str, Any],
) -> list[TextContent]:
    tables, fks = _parse_input(arguments)
    result = find_cycles(tables, fks)
    payload = {
        "safe": result.safe,
        "cycle_count": len(result.cycles),
        "cycles": result.cycles,
    }
    return [TextContent(type="text", text=_render(payload))]


def _render(payload: dict[str, Any]) -> str:
    import json

    return json.dumps(payload, ensure_ascii=False, indent=2)


SCHEMA_ALGORITHM_TOOLS = [
    SCHEMA_TOPO_TOOL,
    SCHEMA_CLUSTER_TOOL,
    SCHEMA_CYCLE_TOOL,
]


def get_schema_algorithm_tools() -> list[Tool]:
    """Return the schema graph tools for canonical MCP registration."""
    return list(SCHEMA_ALGORITHM_TOOLS)


SCHEMA_ALGORITHM_HANDLERS = {
    "schema_topo_order": handle_schema_topo_order,
    "schema_cluster_tables": handle_schema_cluster_tables,
    "schema_check_cycles": handle_schema_check_cycles,
}
