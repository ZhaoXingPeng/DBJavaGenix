"""Test database configuration loaded from environment variables.

These tests (test_database.py / test_generator.py / test_integration.py) hit
a real MySQL instance. To run them, export:

    DBJAVAGENIX_TEST_DB_HOST=<host>
    DBJAVAGENIX_TEST_DB_PORT=<port>          # default 3306
    DBJAVAGENIX_TEST_DB_USER=<user>          # default root
    DBJAVAGENIX_TEST_DB_PASSWORD=<password>  # default empty
    DBJAVAGENIX_TEST_DB_NAME=<database>      # default test

If DBJAVAGENIX_TEST_DB_HOST is unset, get_test_db_config() returns None and
the caller should skip / exit gracefully.
"""

from __future__ import annotations

import os
import sys
from typing import Optional


def get_test_db_config() -> Optional[dict]:
    """Return a config dict, or None if DBJAVAGENIX_TEST_DB_HOST not set."""
    host = os.environ.get("DBJAVAGENIX_TEST_DB_HOST")
    if not host:
        return None
    return {
        "host": host,
        "port": int(os.environ.get("DBJAVAGENIX_TEST_DB_PORT", "3306")),
        "username": os.environ.get("DBJAVAGENIX_TEST_DB_USER", "root"),
        "password": os.environ.get("DBJAVAGENIX_TEST_DB_PASSWORD", ""),
        "database": os.environ.get("DBJAVAGENIX_TEST_DB_NAME", "test"),
        "database_type": "mysql",
    }


def get_test_db_config_or_exit() -> dict:
    """Return config, or print an error and exit if not configured.

    Use this in the standalone scripts (test_database.py / test_generator.py /
    test_integration.py) — they run via `python -m`, not pytest.
    """
    config = get_test_db_config()
    if config is None:
        print(
            "ERROR: integration test requires a real MySQL instance.\n"
            "  Set DBJAVAGENIX_TEST_DB_HOST (and optionally _PORT / _USER /\n"
            "  _PASSWORD / _NAME) and re-run.",
            file=sys.stderr,
        )
        sys.exit(1)
    return config
