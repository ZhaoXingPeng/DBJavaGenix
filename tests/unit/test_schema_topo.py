"""Unit tests for schema_topo (Kahn's topological sort)."""
import pytest

from dbjavagenix.algorithms.schema_topo import TopoResult, topological_sort


class TestTopologicalSort:
    def test_empty_input(self):
        r = topological_sort([], [])
        assert r.order == []
        assert r.unresolved == []
        assert not r.has_cycle

    def test_no_dependencies(self):
        r = topological_sort(["a", "b", "c"], [])
        assert r.order == ["a", "b", "c"]  # alphabetical (deterministic)
        assert all(r.levels[t] == 0 for t in r.order)

    def test_simple_chain(self):
        # a -> b -> c  (b depends on a; c depends on b)
        r = topological_sort(["a", "b", "c"], [("b", "a"), ("c", "b")])
        assert r.order == ["a", "b", "c"]
        assert r.levels == {"a": 0, "b": 1, "c": 2}
        assert not r.has_cycle

    def test_rbac_pattern(self):
        # sys_user_role references sys_user AND sys_role
        tables = ["sys_user", "sys_role", "sys_user_role"]
        fks = [("sys_user_role", "sys_user"), ("sys_user_role", "sys_role")]
        r = topological_sort(tables, fks)
        # Both parents at level 0, child at level 1
        assert set(r.order[:2]) == {"sys_user", "sys_role"}
        assert r.order[2] == "sys_user_role"
        assert r.levels["sys_user_role"] == 1

    def test_cycle_detection(self):
        # a -> b -> c -> a  (cycle)
        r = topological_sort(
            ["a", "b", "c"], [("b", "a"), ("c", "b"), ("a", "c")]
        )
        assert r.has_cycle
        assert set(r.unresolved) == {"a", "b", "c"}
        assert r.order == []

    def test_partial_cycle(self):
        # a (alone, no deps), b <-> c (cycle)
        r = topological_sort(["a", "b", "c"], [("b", "c"), ("c", "b")])
        assert r.order == ["a"]
        assert set(r.unresolved) == {"b", "c"}

    def test_self_reference_ignored(self):
        # a references itself (employee.manager_id -> employee.id)
        r = topological_sort(["a", "b"], [("a", "a"), ("b", "a")])
        assert r.order == ["a", "b"]  # self-ref doesn't block
        assert not r.has_cycle

    def test_external_fk_ignored(self):
        # `a` references `external` which is not in our tables list
        r = topological_sort(["a", "b"], [("a", "external"), ("b", "a")])
        assert r.order == ["a", "b"]
        assert not r.has_cycle

    def test_deterministic_order(self):
        # Multiple level-0 tables -> alphabetical
        r = topological_sort(["z", "y", "x"], [])
        assert r.order == ["x", "y", "z"]

    def test_levels_computed(self):
        # diamond: a -> b, a -> c, b -> d, c -> d
        r = topological_sort(
            ["a", "b", "c", "d"],
            [("b", "a"), ("c", "a"), ("d", "b"), ("d", "c")],
        )
        assert r.levels["a"] == 0
        assert r.levels["b"] == 1
        assert r.levels["c"] == 1
        assert r.levels["d"] == 2
