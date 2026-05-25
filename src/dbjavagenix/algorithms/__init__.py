"""Schema-graph algorithms (topological sort, clustering, cycle detection).

These are pure-algorithm modules — no I/O, no DB connection. They take plain
table + FK data and return structured results.

The MCP tool wrappers live in `dbjavagenix.database.schema_algorithms_tools`.
"""

from .schema_topo import TopoResult, topological_sort

__all__ = [
    "TopoResult",
    "topological_sort",
]
