"""Schema topological sort (Kahn's algorithm).

Given a list of tables and their foreign-key relationships, produce a
deterministic ordering such that no table appears before any table it depends
on (via foreign key).

Use cases:
- Generating DDL in dependency order (CREATE table A before table B that
  references A).
- Generating @Autowired Service injection order in Spring Boot scaffolding.
- Detecting circular dependencies — unresolvable nodes are returned separately.

Complexity: O(V + E) where V = |tables|, E = |fks|.
"""

from collections import defaultdict, deque
from dataclasses import dataclass, field

from .graph_input import normalize_graph_input


@dataclass
class TopoResult:
    """Result of a topological sort.

    Attributes:
        order: tables in dependency-safe order (parents before children)
        unresolved: tables involved in cycles (no valid topo position)
        levels: depth of each table (tables with no dependencies = level 0)
    """

    order: list[str]
    unresolved: list[str] = field(default_factory=list)
    levels: dict[str, int] = field(default_factory=dict)

    @property
    def has_cycle(self) -> bool:
        return bool(self.unresolved)


def topological_sort(tables: list[str], fks: list[tuple[str, str]]) -> TopoResult:
    """Topologically sort tables by FK dependencies using Kahn's algorithm.

    Args:
        tables: list of table names (deduplicated)
        fks: list of (child, parent) tuples — child has a FK referencing parent

    Returns:
        TopoResult with order, unresolved (cycle members), and depth levels.

    Notes:
        - Self-references (child == parent) are silently ignored — they do not
          block topology because a self-referential row can always be inserted
          with NULL on the FK first.
        - FKs pointing to tables outside the `tables` list are ignored (the
          dependency is treated as already satisfied / external).
    """
    tables, fks = normalize_graph_input(tables, fks)
    table_set = set(tables)
    in_degree = {t: 0 for t in tables}
    children: dict[str, list[str]] = defaultdict(list)

    for child, parent in fks:
        if child not in table_set or parent not in table_set:
            continue
        if child == parent:
            continue
        children[parent].append(child)
        in_degree[child] += 1

    # Initial queue: tables with no dependencies (sorted for determinism)
    queue = deque(sorted(t for t, deg in in_degree.items() if deg == 0))
    levels: dict[str, int] = {t: 0 for t in queue}
    order: list[str] = []

    while queue:
        node = queue.popleft()
        order.append(node)
        for child in sorted(children[node]):
            in_degree[child] -= 1
            if in_degree[child] == 0:
                # Child's level = max(parent levels) + 1
                levels[child] = levels[node] + 1
                queue.append(child)

    unresolved = sorted(t for t, deg in in_degree.items() if deg > 0)
    return TopoResult(order=order, unresolved=unresolved, levels=levels)
