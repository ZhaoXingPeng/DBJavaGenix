"""JSON encoding for values returned by database drivers."""

from __future__ import annotations

from base64 import b64encode
from datetime import date, datetime, time, timedelta
from decimal import Decimal
import json
from typing import Any
from uuid import UUID


def default(value: object) -> object:
    """Encode common driver values without losing precision or binary identity."""
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, (bytes, bytearray, memoryview)):
        return {
            "encoding": "base64",
            "data": b64encode(bytes(value)).decode("ascii"),
        }
    if isinstance(value, timedelta):
        return str(value)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def dumps(value: Any, *, ensure_ascii: bool = False, indent: int | str | None = None) -> str:
    """Serialize a payload using the shared MCP driver-value contract."""
    return json.dumps(value, ensure_ascii=ensure_ascii, indent=indent, default=default)
