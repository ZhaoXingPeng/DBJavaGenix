"""Pytest harness for integration tests against ephemeral DB containers.

Uses `testcontainers` (https://testcontainers-python.readthedocs.io/) to spin
up real MySQL / PostgreSQL via Docker for each test session. This replaces
the previous workflow of pointing at a fixed shared dev DB (which leaked
credentials and required network access from CI).

If `testcontainers` is not installed, or Docker is not available, the
fixtures `skip()` instead of erroring so unit tests can still run.

Usage:

    pytest tests/integration/                # auto-spins MySQL container
    pytest tests/integration/ --no-docker    # skips all integration tests

The legacy env-var path (DBJAVAGENIX_TEST_DB_HOST) is still respected via
`existing_db_config` for runs against a real shared DB.
"""

from __future__ import annotations

import os
import socket
from typing import Optional

import pytest


# ---------------------------------------------------------------------------
# CLI flag: --no-docker disables container-based fixtures entirely
# ---------------------------------------------------------------------------


def pytest_addoption(parser):
    parser.addoption(
        "--no-docker",
        action="store_true",
        default=False,
        help="Skip integration tests that need Docker / testcontainers.",
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _docker_available() -> bool:
    """Best-effort check: probe `docker` socket / pipe without subprocess."""
    if os.name == "nt":
        # Windows: Docker Desktop pipe at \\.\pipe\docker_engine — hard to probe
        # without ctypes. Defer to import-time error from testcontainers.
        return True
    return os.path.exists("/var/run/docker.sock")


def _testcontainers_available() -> bool:
    try:
        import testcontainers  # noqa: F401
        return True
    except ImportError:
        return False


def _port_open(host: str, port: int, timeout: float = 1.0) -> bool:
    """Quick TCP probe — used to verify container is ready."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def existing_db_config() -> Optional[dict]:
    """If user exported DBJAVAGENIX_TEST_DB_HOST, use that instead of a container."""
    from tests._db_config import get_test_db_config
    return get_test_db_config()


@pytest.fixture(scope="session")
def mysql_container(request, existing_db_config):
    """Yields a dict { host, port, user, password, database, database_type }.

    Resolution order:
      1. If --no-docker flag set: skip
      2. If existing_db_config exists (env vars): use it
      3. If testcontainers + docker available: spin up MySQL container
      4. Otherwise: skip with reason
    """
    if request.config.getoption("--no-docker"):
        pytest.skip("--no-docker passed")

    if existing_db_config and existing_db_config["database_type"] == "mysql":
        # Trust env-var DB. Verify reachable before yielding.
        if not _port_open(existing_db_config["host"], existing_db_config["port"]):
            pytest.skip(
                f"DBJAVAGENIX_TEST_DB_HOST={existing_db_config['host']}:"
                f"{existing_db_config['port']} not reachable"
            )
        yield existing_db_config
        return

    if not _testcontainers_available():
        pytest.skip(
            "testcontainers not installed (pip install dbjavagenix[integration])"
        )
    if not _docker_available():
        pytest.skip("Docker not available")

    from testcontainers.mysql import MySqlContainer  # type: ignore

    with MySqlContainer("mysql:8.0") as container:
        config = {
            "host": container.get_container_host_ip(),
            "port": int(container.get_exposed_port(3306)),
            "username": container.username,
            "password": container.password,
            "database": container.dbname,
            "database_type": "mysql",
        }
        yield config
