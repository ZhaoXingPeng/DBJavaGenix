"""Schema clustering by foreign-key connectivity (Union-Find).

Group tables into business clusters using the connected-components principle
on the FK relationship graph (treated as undirected).

Use cases:
- Identify "business modules" — e.g. all tables related to orders form one
  cluster, tables related to users form another.
- Generate Spring Boot package structure suggestions (one package per cluster).
- Surface "orphan" tables (clusters of size 1) for review.

Algorithm: Union-Find (disjoint-set) with union-by-rank + path compression.
Complexity: near O((V + E) * α(V)) where α is inverse Ackermann (practically
constant).

Cluster naming heuristic (in order of preference):
1. Longest common prefix of all member names (e.g. "sys_" → "sys_*")
2. Most-central table (highest in-cluster in-degree)
3. First member alphabetically
"""

from collections import defaultdict
from dataclasses import dataclass, field

from .graph_input import normalize_graph_input


@dataclass
class ClusterResult:
    """Result of schema clustering.

    Attributes:
        clusters: list of clusters; each cluster is a sorted list of member
                  table names. Clusters themselves are ordered by size desc
                  then alphabetically by first member.
        naming: cluster_index -> suggested human-readable name
    """

    clusters: list[list[str]]
    naming: dict[int, str] = field(default_factory=dict)

    @property
    def num_clusters(self) -> int:
        return len(self.clusters)


class _UnionFind:
    """Union-Find with union-by-rank + path compression."""

    def __init__(self, items: list[str]) -> None:
        self._parent = {x: x for x in items}
        self._rank = {x: 0 for x in items}

    def find(self, x: str) -> str:
        if self._parent[x] != x:
            self._parent[x] = self.find(self._parent[x])
        return self._parent[x]

    def union(self, x: str, y: str) -> None:
        px, py = self.find(x), self.find(y)
        if px == py:
            return
        if self._rank[px] < self._rank[py]:
            self._parent[px] = py
        elif self._rank[px] > self._rank[py]:
            self._parent[py] = px
        else:
            self._parent[py] = px
            self._rank[px] += 1


def cluster_tables(tables: list[str], fks: list[tuple[str, str]]) -> ClusterResult:
    """Cluster tables by FK connectivity (FK graph treated as undirected)."""
    tables, fks = normalize_graph_input(tables, fks)
    uf = _UnionFind(tables)
    table_set = set(tables)
    for child, parent in fks:
        if child in table_set and parent in table_set:
            uf.union(child, parent)

    groups: dict[str, list[str]] = defaultdict(list)
    for t in tables:
        groups[uf.find(t)].append(t)

    clusters = sorted(
        (sorted(members) for members in groups.values()),
        key=lambda m: (-len(m), m[0]),
    )
    naming = {i: _name_cluster(members, fks) for i, members in enumerate(clusters)}
    return ClusterResult(clusters=clusters, naming=naming)


def _name_cluster(members: list[str], fks: list[tuple[str, str]]) -> str:
    """Suggest a cluster name."""
    if not members:
        return "<empty>"
    if len(members) == 1:
        return members[0]  # solo cluster keeps its own name

    prefix = _common_prefix(members).rstrip("_-")
    if len(prefix) >= 3:
        return f"{prefix}_*"

    # Fallback: table with highest in-cluster in-degree
    member_set = set(members)
    degrees: dict[str, int] = {t: 0 for t in members}
    for child, parent in fks:
        if parent in member_set and child in member_set:
            degrees[parent] += 1
    central = max(degrees, key=lambda t: (degrees[t], -ord(t[0])))
    return f"around:{central}" if degrees[central] > 0 else members[0]


def _common_prefix(names: list[str]) -> str:
    """Longest common prefix of a list of strings."""
    if not names:
        return ""
    prefix = names[0]
    for name in names[1:]:
        i = 0
        while i < min(len(prefix), len(name)) and prefix[i] == name[i]:
            i += 1
        prefix = prefix[:i]
        if not prefix:
            return ""
    return prefix
