"""Reproducible metadata introspection benchmark.

The benchmark intentionally uses only the local SQLite driver so it can run without
Docker or external services.  It measures the public ``describe_table`` contract,
including the number of SQL round trips made per call.
"""

from __future__ import annotations

import argparse
import json
import math
import platform
import statistics
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from dbjavagenix.core.models import DatabaseConfig, DatabaseType
from dbjavagenix.database.connection_manager import ConnectionManager
from dbjavagenix.database.introspection import DatabaseIntrospector


def _build_fixture() -> tuple[ConnectionManager, str]:
    manager = ConnectionManager()
    connection_id = manager.create_connection(
        DatabaseConfig(
            type=DatabaseType.SQLITE,
            host="",
            port=0,
            database=":memory:",
            username="",
            password="",
        )
    )
    manager.execute_query(
        connection_id,
        """
        PRAGMA foreign_keys = ON;
        """,
    )
    manager.execute_query(
        connection_id,
        """
        CREATE TABLE users (
            id INTEGER PRIMARY KEY,
            email TEXT NOT NULL,
            created_at TIMESTAMP NOT NULL
        )
        """,
    )
    manager.execute_query(
        connection_id,
        """
        CREATE TABLE orders (
            id INTEGER PRIMARY KEY,
            user_id INTEGER NOT NULL,
            total_cents INTEGER NOT NULL,
            created_at TIMESTAMP NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
        """,
    )
    manager.execute_query(
        connection_id,
        "CREATE UNIQUE INDEX orders_user_created_idx ON orders(user_id, created_at)",
    )
    return manager, connection_id


def _percentile(samples: list[float], percentile: float) -> float:
    ordered = sorted(samples)
    index = max(0, min(len(ordered) - 1, math.ceil(percentile * len(ordered)) - 1))
    return ordered[index]


def run_benchmark(iterations: int = 30, warmup: int = 5) -> dict[str, Any]:
    """Measure SQLite ``describe_table`` latency and SQL round trips."""
    if iterations < 1:
        raise ValueError("iterations must be at least 1")
    if warmup < 0:
        raise ValueError("warmup must not be negative")

    manager, connection_id = _build_fixture()
    query_count = 0
    original_execute = manager.execute_query

    def counted_execute(*args: Any, **kwargs: Any):
        nonlocal query_count
        query_count += 1
        return original_execute(*args, **kwargs)

    manager.execute_query = counted_execute  # type: ignore[method-assign]
    introspector = DatabaseIntrospector(manager)
    try:
        for _ in range(warmup):
            introspector.describe_table(connection_id, "orders")
        query_count = 0

        samples: list[float] = []
        metadata: dict[str, Any] = {}
        for _ in range(iterations):
            start = time.perf_counter()
            metadata = introspector.describe_table(connection_id, "orders")
            samples.append((time.perf_counter() - start) * 1000)

        return {
            "database": "sqlite",
            "operation": "describe_table",
            "table": "orders",
            "iterations": iterations,
            "warmup": warmup,
            "columns": len(metadata["columns"]),
            "indexes": len(metadata["indexes"]),
            "foreign_keys": len(metadata["foreign_keys"]),
            "queries_per_call": query_count / iterations,
            "min_ms": min(samples),
            "median_ms": statistics.median(samples),
            "p95_ms": _percentile(samples, 0.95),
            "max_ms": max(samples),
            "python": platform.python_version(),
            "platform": platform.platform(),
        }
    finally:
        manager.close_connection(connection_id)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iterations", type=int, default=30)
    parser.add_argument("--warmup", type=int, default=5)
    args = parser.parse_args()
    print(json.dumps(run_benchmark(args.iterations, args.warmup), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
