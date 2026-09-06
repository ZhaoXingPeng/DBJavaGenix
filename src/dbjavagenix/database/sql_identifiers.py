"""Helpers for safely embedding database identifiers in dialect SQL."""

from typing import Any


def quote_mysql_identifier(identifier: Any) -> str:
    """Quote one MySQL identifier and reject control characters."""
    if not isinstance(identifier, str) or not identifier:
        raise ValueError("MySQL identifier must be a non-empty string")
    if any(ord(char) < 32 or ord(char) == 127 for char in identifier):
        raise ValueError("MySQL identifier must not contain control characters")
    return f"`{identifier.replace('`', '``')}`"
