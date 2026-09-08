"""Regression tests for the public read-only SQL query tool."""

import json

import pytest

from dbjavagenix.database import mcp_tools


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "query",
    [
        "/* hidden */ SELECT 1",
        "SELECT 1; DROP TABLE users",
        "SELECT 1; SELECT 2",
        "WITH changed AS (DELETE FROM users RETURNING id) SELECT * FROM changed",
        "SELECT id FROM users -- hide a second statement\n",
        "UPDATE users SET name = 'changed'",
        "SELECT id INTO new_users FROM users",
    ],
)
async def test_db_query_execute_rejects_non_read_only_sql(monkeypatch, query):
    called = False

    def execute_query(*args, **kwargs):
        nonlocal called
        called = True
        return []

    monkeypatch.setattr(mcp_tools.connection_manager, "execute_query", execute_query)

    response = await mcp_tools.handle_db_query_execute({"connection_id": "test", "query": query})

    assert "Only" in response[0].text or "comments" in response[0].text
    assert called is False


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "query",
    [
        "SELECT id FROM users FOR UPDATE",
        "SELECT id FROM users FOR SHARE",
        "SELECT id FROM users FOR KEY SHARE",
        "SELECT id FROM users FOR NO KEY UPDATE",
        "SELECT id FROM users LOCK IN SHARE MODE",
        "WITH locked_rows AS (SELECT id FROM users FOR SHARE) SELECT id FROM locked_rows",
    ],
)
async def test_db_query_execute_rejects_locking_read_clauses(monkeypatch, query):
    called = False

    def execute_query(*_args, **_kwargs):
        nonlocal called
        called = True
        return []

    monkeypatch.setattr(mcp_tools.connection_manager, "execute_query", execute_query)

    response = await mcp_tools.handle_db_query_execute({"connection_id": "test", "query": query})

    payload = json.loads(response[0].text.split("Raw Response:", 1)[1].strip())
    assert "non-locking" in response[0].text
    assert payload["success"] is False
    assert payload["error"] == "query_failed"
    assert called is False


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "query",
    [
        "SELECT 1 AS share",
        "SELECT 1 AS lock",
        "SELECT 'LOCK IN SHARE MODE' AS note",
    ],
)
async def test_db_query_execute_preserves_lock_words_in_aliases_and_literals(monkeypatch, query):
    received = []

    monkeypatch.setattr(
        mcp_tools.connection_manager,
        "execute_query",
        lambda _connection_id, executed_query: received.append(executed_query) or [],
    )

    response = await mcp_tools.handle_db_query_execute(
        {"connection_id": "test", "query": query, "limit": 3}
    )

    assert "Query executed successfully" in response[0].text
    assert received == [f"{query} LIMIT 3"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "query",
    [
        "SELECT $$LIMIT 99; UPDATE users SET name = 'x'$$ AS body",
        "SELECT $tag$FOR SHARE; (nested)$tag$ AS body",
    ],
)
async def test_db_query_execute_ignores_keywords_inside_dollar_quoted_literals(monkeypatch, query):
    received = []

    monkeypatch.setattr(
        mcp_tools.connection_manager,
        "execute_query",
        lambda _connection_id, executed_query: received.append(executed_query) or [],
    )

    response = await mcp_tools.handle_db_query_execute(
        {"connection_id": "test", "query": query, "limit": 3}
    )

    assert "Query executed successfully" in response[0].text
    assert received == [f"{query} LIMIT 3"]


@pytest.mark.asyncio
async def test_db_query_execute_rejects_unterminated_dollar_quoted_literal(monkeypatch):
    called = False

    def execute_query(*_args, **_kwargs):
        nonlocal called
        called = True
        return []

    monkeypatch.setattr(mcp_tools.connection_manager, "execute_query", execute_query)

    response = await mcp_tools.handle_db_query_execute(
        {"connection_id": "test", "query": "SELECT $tag$missing", "limit": 3}
    )

    assert "Unterminated dollar-quoted" in response[0].text
    assert called is False


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("query", "expected"),
    [
        (
            "SELECT id FROM users FETCH FIRST 100 ROWS ONLY",
            "SELECT id FROM users FETCH FIRST 3 ROWS ONLY",
        ),
        (
            "SELECT id FROM users FETCH NEXT 2 ROW ONLY",
            "SELECT id FROM users FETCH NEXT 2 ROW ONLY",
        ),
        (
            "SELECT * FROM (SELECT id FROM users FETCH FIRST 100 ROWS ONLY) AS rows",
            "SELECT * FROM (SELECT id FROM users FETCH FIRST 100 ROWS ONLY) AS rows LIMIT 3",
        ),
    ],
)
async def test_db_query_execute_applies_limit_to_top_level_fetch(monkeypatch, query, expected):
    received = []

    monkeypatch.setattr(
        mcp_tools.connection_manager,
        "execute_query",
        lambda _connection_id, executed_query: received.append(executed_query) or [],
    )

    response = await mcp_tools.handle_db_query_execute(
        {"connection_id": "test", "query": query, "limit": 3}
    )

    assert "Query executed successfully" in response[0].text
    assert received == [expected]


@pytest.mark.asyncio
async def test_db_query_execute_rejects_fetch_with_ties_before_execution(monkeypatch):
    called = False

    def execute_query(*_args, **_kwargs):
        nonlocal called
        called = True
        return []

    monkeypatch.setattr(mcp_tools.connection_manager, "execute_query", execute_query)

    response = await mcp_tools.handle_db_query_execute(
        {
            "connection_id": "test",
            "query": "SELECT id FROM users FETCH FIRST 10 ROWS WITH TIES",
            "limit": 3,
        }
    )

    assert "FETCH WITH TIES" in response[0].text
    assert called is False


def test_has_top_level_limit_clause_matches_supported_fetch_forms():
    assert mcp_tools._has_top_level_limit_clause("SELECT 1 FETCH FIRST 2 ROWS ONLY") is True
    assert (
        mcp_tools._has_top_level_limit_clause(
            "SELECT * FROM (SELECT 1 FETCH FIRST 2 ROWS ONLY) AS rows"
        )
        is False
    )


@pytest.mark.asyncio
async def test_db_query_execute_accepts_cte_and_trailing_semicolon(monkeypatch):
    received = []

    def execute_query(connection_id, query):
        received.append((connection_id, query))
        return [{"id": 1}]

    monkeypatch.setattr(mcp_tools.connection_manager, "execute_query", execute_query)

    response = await mcp_tools.handle_db_query_execute(
        {
            "connection_id": "test",
            "query": "WITH rows AS (SELECT 1 AS id) SELECT id FROM rows;",
            "limit": 5,
        }
    )

    assert "Query executed successfully" in response[0].text
    assert received == [("test", "WITH rows AS (SELECT 1 AS id) SELECT id FROM rows LIMIT 5")]


@pytest.mark.asyncio
async def test_db_query_execute_detects_limit_keyword_outside_literals(monkeypatch):
    received = []

    def execute_query(connection_id, query):
        received.append(query)
        return []

    monkeypatch.setattr(mcp_tools.connection_manager, "execute_query", execute_query)

    await mcp_tools.handle_db_query_execute(
        {"connection_id": "test", "query": "SELECT 'LIMIT is data' AS value", "limit": 3}
    )

    assert received == ["SELECT 'LIMIT is data' AS value LIMIT 3"]


@pytest.mark.asyncio
async def test_db_query_execute_does_not_treat_limit_alias_as_clause(monkeypatch):
    received = []

    def execute_query(connection_id, query):
        received.append(query)
        return []

    monkeypatch.setattr(mcp_tools.connection_manager, "execute_query", execute_query)

    await mcp_tools.handle_db_query_execute(
        {"connection_id": "test", "query": "SELECT 1 AS limit FROM users", "limit": 3}
    )

    assert received == ["SELECT 1 AS limit FROM users LIMIT 3"]


@pytest.mark.asyncio
async def test_db_query_execute_caps_existing_larger_limit(monkeypatch):
    received = []

    def execute_query(connection_id, query):
        received.append(query)
        return []

    monkeypatch.setattr(mcp_tools.connection_manager, "execute_query", execute_query)

    await mcp_tools.handle_db_query_execute(
        {"connection_id": "test", "query": "SELECT id FROM users LIMIT 1000", "limit": 10}
    )

    assert received == ["SELECT id FROM users LIMIT 10"]


@pytest.mark.asyncio
async def test_db_query_execute_preserves_existing_smaller_limit(monkeypatch):
    received = []

    monkeypatch.setattr(
        mcp_tools.connection_manager,
        "execute_query",
        lambda _connection_id, query: received.append(query) or [],
    )

    await mcp_tools.handle_db_query_execute(
        {"connection_id": "test", "query": "SELECT id FROM users LIMIT 3", "limit": 10}
    )

    assert received == ["SELECT id FROM users LIMIT 3"]


@pytest.mark.asyncio
async def test_db_query_execute_caps_limit_all_and_offset_form(monkeypatch):
    received = []

    monkeypatch.setattr(
        mcp_tools.connection_manager,
        "execute_query",
        lambda _connection_id, query: received.append(query) or [],
    )

    await mcp_tools.handle_db_query_execute(
        {"connection_id": "test", "query": "SELECT id FROM users LIMIT ALL", "limit": 10}
    )
    await mcp_tools.handle_db_query_execute(
        {"connection_id": "test", "query": "SELECT id FROM users LIMIT 20, 100", "limit": 10}
    )

    assert received == [
        "SELECT id FROM users LIMIT 10",
        "SELECT id FROM users LIMIT 20, 10",
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize("limit", [-1, 10_001, True, "10"])
async def test_db_query_execute_rejects_invalid_limits(monkeypatch, limit):
    called = False

    def execute_query(*args, **kwargs):
        nonlocal called
        called = True
        return []

    monkeypatch.setattr(mcp_tools.connection_manager, "execute_query", execute_query)

    response = await mcp_tools.handle_db_query_execute(
        {"connection_id": "test", "query": "SELECT 1", "limit": limit}
    )

    assert "limit" in response[0].text.lower()
    assert called is False
