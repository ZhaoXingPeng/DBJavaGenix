"""Unit tests for schema_cycle_check (DFS cycle detection)."""

import pytest

from dbjavagenix.algorithms.schema_cycle_check import CycleResult, find_cycles


class TestFindCycles:
    def test_empty(self):
        r = find_cycles([], [])
        assert r.cycles == []
        assert r.safe

    def test_no_fks(self):
        r = find_cycles(["a", "b", "c"], [])
        assert r.safe

    def test_chain_no_cycle(self):
        # a -> b -> c (no loop)
        r = find_cycles(["a", "b", "c"], [("b", "a"), ("c", "b")])
        assert r.safe

    def test_simple_2cycle(self):
        # a -> b -> a (mutual reference)
        r = find_cycles(["a", "b"], [("a", "b"), ("b", "a")])
        assert not r.safe
        assert len(r.cycles) == 1
        assert set(r.cycles[0]) == {"a", "b"}

    def test_3cycle(self):
        # a -> b -> c -> a
        r = find_cycles(["a", "b", "c"], [("a", "b"), ("b", "c"), ("c", "a")])
        assert not r.safe
        assert len(r.cycles) == 1
        assert set(r.cycles[0]) == {"a", "b", "c"}

    def test_self_reference_not_a_cycle(self):
        # employee.manager_id -> employee.id is OK (with NULL initial)
        r = find_cycles(["employee"], [("employee", "employee")])
        assert r.safe

    def test_chain_then_cycle(self):
        # x (alone) ; a -> b -> a
        r = find_cycles(["x", "a", "b"], [("a", "b"), ("b", "a")])
        assert not r.safe
        assert len(r.cycles) == 1
        assert set(r.cycles[0]) == {"a", "b"}

    def test_dedup_cycles(self):
        # Same cycle reachable from multiple starts shouldn't be double-counted
        # a -> b -> c -> a, plus extra x -> a (x is acyclic prefix)
        r = find_cycles(
            ["x", "a", "b", "c"],
            [("x", "a"), ("a", "b"), ("b", "c"), ("c", "a")],
        )
        assert len(r.cycles) == 1
        assert set(r.cycles[0]) == {"a", "b", "c"}

    def test_two_independent_cycles(self):
        # Cycle 1: a <-> b ; Cycle 2: c <-> d
        r = find_cycles(
            ["a", "b", "c", "d"],
            [("a", "b"), ("b", "a"), ("c", "d"), ("d", "c")],
        )
        assert not r.safe
        assert len(r.cycles) == 2

    def test_external_fk_ignored(self):
        # FK to table not in our list
        r = find_cycles(["a"], [("a", "external")])
        assert r.safe

    def test_safe_property(self):
        r1 = find_cycles(["a"], [])
        assert r1.safe is True
        r2 = find_cycles(["a", "b"], [("a", "b"), ("b", "a")])
        assert r2.safe is False

    def test_duplicate_tables_and_edges_are_normalized(self):
        r = find_cycles(
            ["a", "a", "b"],
            [("a", "b"), ("b", "a"), ("a", "b"), ("", "a")],
        )
        assert r.cycles == [["a", "b"]]

    def test_malformed_graph_values_are_ignored(self):
        r = find_cycles(["a", "b"], "not-an-edge-list")
        assert r.safe
