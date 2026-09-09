"""Regression tests for shared JSON serialization at MCP response boundaries."""

import asyncio
import json
from decimal import Decimal
from types import SimpleNamespace

from dbjavagenix.database import ai_tools, discovery_tools, observability_tools
from dbjavagenix.database.ai_tools import handle_ai_recommend_template
from dbjavagenix.database.discovery_tools import handle_search_tools
from dbjavagenix.database.observability_tools import handle_server_metrics


def test_ai_response_serializes_nested_driver_values(monkeypatch):
    monkeypatch.setattr(
        ai_tools,
        "recommend_template",
        lambda **_: SimpleNamespace(
            template="MybatisPlus",
            options={"sample": Decimal("1.25")},
            pattern="Custom",
            confidence="medium",
            score=Decimal("0.875"),
            reasons=[],
            matched_tables=[],
        ),
    )

    result = asyncio.run(handle_ai_recommend_template({"table_names": ["orders"]}))
    payload = json.loads(result[0].text)

    assert payload["score"] == "0.875"
    assert payload["options"]["sample"] == "1.25"


def test_discovery_response_serializes_driver_values(monkeypatch):
    monkeypatch.setattr(
        discovery_tools,
        "search_tools_by_query",
        lambda *_args, **_kwargs: [{"name": "custom", "score": Decimal("2.5")}],
    )

    result = asyncio.run(handle_search_tools({"query": "custom"}))
    payload = json.loads(result[0].text)

    assert payload["results"][0]["score"] == "2.5"


def test_observability_response_serializes_driver_values(monkeypatch):
    monkeypatch.setattr(
        observability_tools.GLOBAL_TOOL_METRICS,
        "snapshot",
        lambda: {"latency": Decimal("3.75")},
    )

    result = asyncio.run(handle_server_metrics({}))
    payload = json.loads(result[0].text)

    assert payload["metrics"]["latency"] == "3.75"
