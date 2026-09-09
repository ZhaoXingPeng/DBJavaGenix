"""Tests for the shared MCP JSON driver-value contract."""

from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
import json
from types import SimpleNamespace
from uuid import UUID

import pytest

from dbjavagenix.core.models import DatabaseType
from dbjavagenix.database import atomic_codegen_tools
from dbjavagenix.utils.json_serialization import default, dumps


def test_dumps_preserves_supported_driver_values():
    payload = {
        "amount": Decimal("12.30"),
        "created_at": datetime(2026, 9, 8, 10, 0, tzinfo=timezone.utc),
        "event_date": date(2026, 9, 8),
        "event_time": time(10, 0, 1, 234_000),
        "event_id": UUID("12345678-1234-5678-1234-567812345678"),
        "payload": b"\x00\xff",
        "mutable_payload": bytearray(b"ok"),
        "view_payload": memoryview(b"view"),
        "duration": timedelta(seconds=2),
    }

    encoded = json.loads(dumps(payload))

    assert encoded == {
        "amount": "12.30",
        "created_at": "2026-09-08T10:00:00+00:00",
        "event_date": "2026-09-08",
        "event_time": "10:00:01.234000",
        "event_id": "12345678-1234-5678-1234-567812345678",
        "payload": {"encoding": "base64", "data": "AP8="},
        "mutable_payload": {"encoding": "base64", "data": "b2s="},
        "view_payload": {"encoding": "base64", "data": "dmlldw=="},
        "duration": "0:00:02",
    }


def test_default_rejects_unknown_objects():
    class UnknownDriverValue:
        pass

    with pytest.raises(TypeError, match="UnknownDriverValue"):
        default(UnknownDriverValue())


@pytest.mark.asyncio
async def test_atomic_context_serializes_nested_driver_values(monkeypatch):
    class Analyzer:
        def __init__(self, _manager):
            pass

        async def analyze_table_for_codegen(self, *_args, **_kwargs):
            return {
                "template_context": {
                    "packageSuffix": "",
                    "columns": [
                        {
                            "defaultValue": Decimal("12.30"),
                            "observedAt": datetime(2026, 9, 8, tzinfo=timezone.utc),
                            "eventId": UUID("12345678-1234-5678-1234-567812345678"),
                            "payload": memoryview(b"view"),
                        }
                    ],
                }
            }

    monkeypatch.setattr(
        "dbjavagenix.database.codegen_tools.CodegenAnalyzer",
        Analyzer,
    )
    monkeypatch.setattr(
        atomic_codegen_tools.connection_manager,
        "get_connection_info",
        lambda _connection_id: SimpleNamespace(
            type=DatabaseType.SQLITE,
            database="app",
        ),
    )
    monkeypatch.setattr(atomic_codegen_tools, "_collect_all_table_names", lambda *_args: [])

    response = await atomic_codegen_tools.handle_codegen_build_context(
        {
            "connection_id": "sqlite-1",
            "table_name": "events",
            "template_category": "Default",
        }
    )

    payload = json.loads(response[0].text)
    column = payload["context"]["columns"][0]
    assert column["defaultValue"] == "12.30"
    assert column["observedAt"] == "2026-09-08T00:00:00+00:00"
    assert column["eventId"] == "12345678-1234-5678-1234-567812345678"
    assert column["payload"] == {"encoding": "base64", "data": "dmlldw=="}
