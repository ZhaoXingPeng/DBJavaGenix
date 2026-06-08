"""Smoke test: container fixture yields a usable DB config.

This is a meta-test of the harness itself — it doesn't depend on
DBJavaGenix application code. If this passes, downstream integration tests
for discovery / codegen can build on the same fixture.
"""

from __future__ import annotations


def test_mysql_container_yields_config(mysql_container):
    """The fixture returns a dict with all expected keys."""
    assert isinstance(mysql_container, dict)
    for key in ("host", "port", "username", "password", "database", "database_type"):
        assert key in mysql_container, f"missing key {key}"
    assert mysql_container["database_type"] == "mysql"
    assert isinstance(mysql_container["port"], int)
    assert mysql_container["port"] > 0


def test_mysql_container_reachable(mysql_container):
    """We can actually open a TCP connection to the yielded host:port."""
    from tests.integration.conftest import _port_open

    assert _port_open(mysql_container["host"], mysql_container["port"], timeout=5.0)
