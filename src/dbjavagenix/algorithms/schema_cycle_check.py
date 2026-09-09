"""Detect foreign-key cycles in the schema graph (DFS with color marking).

A cycle in the FK graph is almost always a schema anti-pattern. Common shapes:
- user -> order -> user_metadata -> user (logical loop)
- A -> B -> A (mutual reference, often hides a missing intermediate table)

When a cycle is detected, the user should typically:
- Introduce a join table to break the loop
- Make one direction nullable so insertion can happen with NULL first
- Reconsider whether one of the FKs is actually needed

Algorithm: iterative DFS with three colors (WHITE / GRAY / BLACK).
- WHITE: not yet visited
- GRAY: currently on the DFS stack (active path)
- BLACK: fully explored, off the stack

When a GRAY node is re-encountered, the path from that node to the current
position is a cycle.

Complexity: O(V + E).
"""

from dataclasses import dataclass, field

from .graph_input import normalize_graph_input


_WHITE, _GRAY, _BLACK = 0, 1, 2


@dataclass
class CycleResult:
    """Result of FK cycle detection.

    Attributes:
        cycles: list of detected cycles; each cycle is a list of table names
                in dependency order (the last element implicitly references
                the first, closing the loop)
        safe: True if no cycles found
    """

    cycles: list[list[str]] = field(default_factory=list)

    @property
    def safe(self) -> bool:
        return len(self.cycles) == 0


def find_cycles(tables: list[str], fks: list[tuple[str, str]]) -> CycleResult:
    """Find FK cycles using iterative DFS.

    Args:
        tables: list of table names
        fks: (child, parent) tuples

    Returns:
        CycleResult with all detected elementary cycles.

    Notes:
        - We follow `child -> parent` edges (data-dependency direction).
        - Self-references (child == parent) are not reported as cycles;
          they are valid (e.g. employee.manager_id -> employee.id with NULL
          initial).
        - Duplicate cycle representations are deduplicated by canonical form
          (lexicographically smallest rotation).
    """
    tables, fks = normalize_graph_input(tables, fks)
    table_set = set(tables)
    adj: dict[str, list[str]] = {t: [] for t in tables}
    for child, parent in fks:
        if child in table_set and parent in table_set and child != parent:
            adj[child].append(parent)

    color = {t: _WHITE for t in tables}
    raw_cycles: list[list[str]] = []

    for start in sorted(tables):
        if color[start] != _WHITE:
            continue
        # Iterative DFS using a stack of (node, iterator over neighbors,
        # path-from-root)
        stack: list[tuple[str, list[str], int]] = [(start, sorted(adj[start]), 0)]
        path: list[str] = [start]
        color[start] = _GRAY

        while stack:
            node, neighbors, idx = stack[-1]
            if idx >= len(neighbors):
                color[node] = _BLACK
                path.pop()
                stack.pop()
                continue
            neighbor = neighbors[idx]
            stack[-1] = (node, neighbors, idx + 1)

            if color[neighbor] == _WHITE:
                color[neighbor] = _GRAY
                path.append(neighbor)
                stack.append((neighbor, sorted(adj[neighbor]), 0))
            elif color[neighbor] == _GRAY:
                # Cycle found — extract from `path` starting at `neighbor`
                try:
                    cycle_start = path.index(neighbor)
                except ValueError:
                    continue
                cycle = list(path[cycle_start:])
                raw_cycles.append(cycle)
            # else BLACK: already fully explored, no new cycle

    return CycleResult(cycles=_dedupe_cycles(raw_cycles))


def _dedupe_cycles(cycles: list[list[str]]) -> list[list[str]]:
    """Return unique cycles using canonical rotation as key."""
    seen: set[tuple[str, ...]] = set()
    result: list[list[str]] = []
    for cycle in cycles:
        canon = _canonical_rotation(cycle)
        if canon not in seen:
            seen.add(canon)
            result.append(list(canon))
    return result


def _canonical_rotation(cycle: list[str]) -> tuple[str, ...]:
    """Lexicographically smallest rotation of a cycle (for dedup)."""
    n = len(cycle)
    if n == 0:
        return ()
    rotations = [tuple(cycle[i:] + cycle[:i]) for i in range(n)]
    return min(rotations)
