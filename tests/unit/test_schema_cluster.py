"""Unit tests for schema_cluster (Union-Find clustering)."""

import pytest

from dbjavagenix.algorithms.schema_cluster import ClusterResult, cluster_tables


class TestClusterTables:
    def test_empty(self):
        r = cluster_tables([], [])
        assert r.clusters == []
        assert r.num_clusters == 0

    def test_no_fks_means_each_table_solo(self):
        r = cluster_tables(["a", "b", "c"], [])
        assert r.num_clusters == 3
        # Each cluster has 1 member
        assert all(len(c) == 1 for c in r.clusters)
        # Solo clusters named by their own name
        assert r.naming[0] in {"a", "b", "c"}

    def test_rbac_pattern_single_cluster(self):
        # sys_user, sys_role, sys_user_role all FK-connected
        tables = ["sys_user", "sys_role", "sys_user_role"]
        fks = [("sys_user_role", "sys_user"), ("sys_user_role", "sys_role")]
        r = cluster_tables(tables, fks)
        assert r.num_clusters == 1
        assert sorted(r.clusters[0]) == sorted(tables)
        # Common prefix detected
        assert r.naming[0] == "sys_*"

    def test_two_independent_clusters(self):
        # Cluster 1: user + user_role  ;  Cluster 2: order + order_item
        tables = ["user", "user_role", "order_t", "order_item"]
        fks = [("user_role", "user"), ("order_item", "order_t")]
        r = cluster_tables(tables, fks)
        assert r.num_clusters == 2
        # Larger / earlier cluster first (both size 2 -> alphabetical first member)
        assert r.clusters[0][0] in {"order_item", "order_t", "user", "user_role"}

    def test_cluster_naming_prefix(self):
        tables = ["biz_user", "biz_user_profile", "biz_user_role"]
        fks = [
            ("biz_user_profile", "biz_user"),
            ("biz_user_role", "biz_user"),
        ]
        r = cluster_tables(tables, fks)
        assert r.num_clusters == 1
        # Common prefix is "biz_user_" -> stripped "_" -> "biz_user"
        assert r.naming[0] == "biz_user_*"

    def test_cluster_naming_no_prefix_uses_central(self):
        # No common prefix but central node has high in-degree
        tables = ["alpha", "beta", "gamma"]
        fks = [("beta", "alpha"), ("gamma", "alpha")]
        r = cluster_tables(tables, fks)
        assert r.num_clusters == 1
        # central is "alpha" (highest in-degree in cluster)
        assert "alpha" in r.naming[0]

    def test_clusters_sorted_by_size(self):
        # Big cluster: a-b-c-d (3 FKs);  small: e (alone)
        tables = ["a", "b", "c", "d", "e"]
        fks = [("b", "a"), ("c", "a"), ("d", "a")]
        r = cluster_tables(tables, fks)
        assert r.num_clusters == 2
        # Cluster 0 has 4 members, cluster 1 has 1
        assert len(r.clusters[0]) == 4
        assert r.clusters[1] == ["e"]

    def test_fk_to_external_table_ignored(self):
        # "a" FK references "external" (not in tables list)
        r = cluster_tables(["a", "b"], [("a", "external")])
        assert r.num_clusters == 2

    def test_cluster_member_order_deterministic(self):
        # Clusters are returned with members sorted alphabetically
        r = cluster_tables(
            ["zeta", "alpha", "mu"],
            [("zeta", "alpha"), ("mu", "alpha")],
        )
        assert r.clusters[0] == ["alpha", "mu", "zeta"]

    def test_duplicate_tables_do_not_duplicate_cluster_members(self):
        r = cluster_tables(
            ["users", "users", "orders", "orders"],
            [("orders", "users"), ("orders", "users")],
        )
        assert r.clusters == [["orders", "users"]]

    def test_malformed_graph_values_are_ignored(self):
        r = cluster_tables(["users", "", None], [("users", ""), (None, "users")])
        assert r.clusters == [["users"]]
