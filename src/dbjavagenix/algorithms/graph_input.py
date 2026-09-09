"""Normalize schema graph inputs shared by all graph algorithms."""

from __future__ import annotations

from typing import Any


def normalize_graph_input(tables: Any, fks: Any) -> tuple[list[str], list[tuple[str, str]]]:
    """Return a deterministic, duplicate-free graph input.

    The MCP schema describes both values as arrays of strings, but direct
    callers and LLM payloads can still provide malformed values.  Keep the
    existing tolerant contract by ignoring invalid entries while preventing
    duplicate nodes and edges from skewing algorithm results.
    """
    normalized_tables: list[str] = []
    seen_tables: set[str] = set()
    if isinstance(tables, (list, tuple)):
        for table in tables:
            if not isinstance(table, str) or not table.strip() or table in seen_tables:
                continue
            seen_tables.add(table)
            normalized_tables.append(table)

    normalized_fks: list[tuple[str, str]] = []
    seen_fks: set[tuple[str, str]] = set()
    if isinstance(fks, (list, tuple)):
        for fk in fks:
            if not isinstance(fk, (list, tuple)) or len(fk) != 2:
                continue
            child, parent = fk
            if (
                not isinstance(child, str)
                or not isinstance(parent, str)
                or not child.strip()
                or not parent.strip()
            ):
                continue
            edge = (child, parent)
            if edge in seen_fks:
                continue
            seen_fks.add(edge)
            normalized_fks.append(edge)

    return normalized_tables, normalized_fks
