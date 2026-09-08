"""Tests for the reproducible local introspection benchmark."""

import runpy
from pathlib import Path

import pytest


_MODULE = runpy.run_path(str(Path(__file__).parents[2] / "scripts" / "benchmark_introspection.py"))
run_benchmark = _MODULE["run_benchmark"]


def test_benchmark_reports_contract_and_round_trip_baseline():
    result = run_benchmark(iterations=3, warmup=1)

    assert result["database"] == "sqlite"
    assert result["operation"] == "describe_table"
    assert result["columns"] == 4
    assert result["indexes"] == 2
    assert result["foreign_keys"] == 1
    assert result["queries_per_call"] == 7
    assert result["warm_queries_per_call"] == 0
    assert 0 < result["median_ms"] <= result["p95_ms"] <= result["max_ms"]
    assert result["cold_ms"] > 0


@pytest.mark.parametrize("iterations, warmup, message", [(0, 1, "at least 1"), (1, -1, "negative")])
def test_benchmark_rejects_invalid_parameters(iterations, warmup, message):
    with pytest.raises(ValueError, match=message):
        run_benchmark(iterations=iterations, warmup=warmup)
