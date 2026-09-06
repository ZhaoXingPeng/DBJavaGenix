"""CLI 模块烟雾测试 (导入 + 关键符号检查)

旧版本是脚本式写法 (print + return True/False), pytest 视为 silent fail。
重写为正确 pytest 风格。
"""

import importlib
from types import SimpleNamespace

import pytest
from typer import Exit


def test_cli_module_imports():
    """cli 模块整体可导入"""
    mod = importlib.import_module("dbjavagenix.cli")
    assert hasattr(mod, "app"), "Typer app 未暴露"
    assert hasattr(mod, "console")


def test_cli_subcommands_present():
    """主要子命令函数存在"""
    mod = importlib.import_module("dbjavagenix.cli")
    for name in ("version", "init", "generate", "list_tables", "analyze", "server"):
        assert callable(getattr(mod, name, None)), f"subcommand {name} missing"


def test_show_ascii_icon_runs():
    """show_ascii_icon 应能在无参时无异常运行 (即使资源缺失也走降级)"""
    from dbjavagenix.cli import show_ascii_icon

    show_ascii_icon()


def test_dbjavagenix_error_format():
    """DBJavaGenixError 字符串化遵循 [CODE] message 模式"""
    from dbjavagenix.core.exceptions import DBJavaGenixError

    err = DBJavaGenixError("Test error", "TEST_ERROR")
    assert str(err) == "[TEST_ERROR] Test error"


def _fake_config():
    return SimpleNamespace(
        database=SimpleNamespace(
            type="sqlite",
            host="",
            port=0,
            username="",
            password="",
            database=":memory:",
            charset="utf8mb4",
        ),
        generation=SimpleNamespace(
            use_mybatis_plus=True,
            author="Test Author",
            package_name="com.example.generated",
            output_dir="generated_output",
        ),
    )


def test_analyze_runs_database_analysis_and_closes_connection(monkeypatch):
    mod = importlib.import_module("dbjavagenix.cli")
    calls = {}
    monkeypatch.setattr(mod, "show_ascii_icon", lambda: None)
    monkeypatch.setattr(
        mod, "ConfigManager", lambda *_args, **_kwargs: SimpleNamespace(load_config=_fake_config)
    )
    monkeypatch.setattr(
        mod,
        "handle_db_connect_test",
        lambda args: calls.update(connect=args) or {"success": True, "connection_id": "conn-1"},
    )
    monkeypatch.setattr(
        mod,
        "handle_db_codegen_analyze",
        lambda args: (
            calls.update(analyze=args)
            or {
                "success": True,
                "table_info": {
                    "columns": [{"name": "id", "type": "integer", "java_type": "Integer"}]
                },
                "java_types": ["Integer"],
                "relationships": {"primary_keys": ["id"], "foreign_keys": [], "indexes": []},
            }
        ),
    )
    monkeypatch.setattr(
        mod.connection_manager,
        "close_connection",
        lambda connection_id: calls.update(close=connection_id),
    )

    mod.analyze("users")

    assert calls["analyze"]["connection_id"] == "conn-1"
    assert calls["analyze"]["template_category"] == "MybatisPlus-Mixed"
    assert calls["close"] == "conn-1"


def test_analyze_connection_failure_exits_without_analysis(monkeypatch):
    mod = importlib.import_module("dbjavagenix.cli")
    monkeypatch.setattr(mod, "show_ascii_icon", lambda: None)
    monkeypatch.setattr(
        mod, "ConfigManager", lambda *_args, **_kwargs: SimpleNamespace(load_config=_fake_config)
    )
    monkeypatch.setattr(
        mod, "handle_db_connect_test", lambda _args: {"success": False, "error": "offline"}
    )
    with pytest.raises(Exit) as exc_info:
        mod.analyze("users")
    assert exc_info.value.exit_code == 1


def test_analyze_failure_closes_connection(monkeypatch):
    mod = importlib.import_module("dbjavagenix.cli")
    calls = []
    monkeypatch.setattr(mod, "show_ascii_icon", lambda: None)
    monkeypatch.setattr(
        mod, "ConfigManager", lambda *_args, **_kwargs: SimpleNamespace(load_config=_fake_config)
    )
    monkeypatch.setattr(
        mod, "handle_db_connect_test", lambda _args: {"success": True, "connection_id": "conn-2"}
    )
    monkeypatch.setattr(
        mod, "handle_db_codegen_analyze", lambda _args: {"success": False, "error": "bad table"}
    )
    monkeypatch.setattr(mod.connection_manager, "close_connection", calls.append)

    with pytest.raises(Exit) as exc_info:
        mod.analyze("users")
    assert exc_info.value.exit_code == 1
    assert calls == ["conn-2"]


def test_analyze_unexpected_failure_closes_connection(monkeypatch):
    mod = importlib.import_module("dbjavagenix.cli")
    calls = []
    monkeypatch.setattr(mod, "show_ascii_icon", lambda: None)
    monkeypatch.setattr(
        mod, "ConfigManager", lambda *_args, **_kwargs: SimpleNamespace(load_config=_fake_config)
    )
    monkeypatch.setattr(
        mod, "handle_db_connect_test", lambda _args: {"success": True, "connection_id": "conn-3"}
    )
    monkeypatch.setattr(
        mod,
        "handle_db_codegen_analyze",
        lambda _args: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    monkeypatch.setattr(mod.connection_manager, "close_connection", calls.append)

    with pytest.raises(RuntimeError, match="boom"):
        mod.analyze("users")
    assert calls == ["conn-3"]


def test_codegen_analysis_wrapper_parses_structured_response(monkeypatch):
    from dbjavagenix import cli_helpers
    from mcp.types import TextContent

    async def fake_analyze(_arguments):
        return [
            TextContent(
                type="text",
                text='Report\n\nRaw Response: {"success": true, "table_name": "users"}',
            )
        ]

    monkeypatch.setattr(cli_helpers, "async_handle_db_codegen_analyze", fake_analyze)

    result = cli_helpers.handle_db_codegen_analyze({"connection_id": "conn-1"})

    assert result == {"success": True, "table_name": "users"}


def test_list_tables_forwards_schema_filter(monkeypatch):
    mod = importlib.import_module("dbjavagenix.cli")
    calls = {}
    config = SimpleNamespace(
        database=SimpleNamespace(
            type="postgresql",
            host="db.example",
            port=5432,
            username="reader",
            password="secret",
            database="app",
            charset="utf8mb4",
        )
    )
    monkeypatch.setattr(mod, "show_ascii_icon", lambda: None)
    monkeypatch.setattr(
        mod, "ConfigManager", lambda *_args, **_kwargs: SimpleNamespace(load_config=lambda: config)
    )
    monkeypatch.setattr(
        mod,
        "handle_db_connect_test",
        lambda _args: {"success": True, "connection_id": "pg-1", "server_info": "PostgreSQL"},
    )
    monkeypatch.setattr(
        mod,
        "handle_db_query_tables",
        lambda args: calls.update(args=args) or {"success": True, "tables": ["users"]},
    )
    monkeypatch.setattr(
        mod.connection_manager, "close_connection", lambda cid: calls.update(close=cid)
    )

    mod.list_tables(schema="tenant_a")

    assert calls["args"] == {"connection_id": "pg-1", "database": "app", "schema": "tenant_a"}
    assert calls["close"] == "pg-1"


def test_extract_table_name_accepts_current_and_legacy_table_shapes():
    from dbjavagenix.cli import _extract_table_name

    assert _extract_table_name("users") == "users"
    assert _extract_table_name({"table_name": "orders"}) == "orders"
    assert _extract_table_name({"name": "audit_log"}) == "audit_log"
    assert _extract_table_name({"table_name": ""}) is None
    assert _extract_table_name(42) is None


def test_table_display_row_accepts_current_and_legacy_table_shapes():
    from dbjavagenix.cli import _table_display_row

    assert _table_display_row("users") == ("users", "", "")
    assert _table_display_row({"table_name": "orders", "engine": "InnoDB", "comment": "订单"}) == (
        "orders",
        "InnoDB",
        "订单",
    )
    assert _table_display_row(42) == ("", "", "")


def test_codegen_result_succeeded_accepts_success_report():
    from dbjavagenix.cli import _codegen_result_succeeded

    assert _codegen_result_succeeded({"success": True}) is True
    assert (
        _codegen_result_succeeded({"success": False, "error": "Code Generation Complete: users"})
        is True
    )
    assert _codegen_result_succeeded({"success": False, "error": "connection failed"}) is False
    assert _codegen_result_succeeded(None) is False


def test_generate_uses_current_codegen_contract(monkeypatch):
    mod = importlib.import_module("dbjavagenix.cli")
    calls = {"generate": [], "close": []}
    monkeypatch.setattr(mod, "show_ascii_icon", lambda: None)
    monkeypatch.setattr(
        mod, "ConfigManager", lambda *_args, **_kwargs: SimpleNamespace(load_config=_fake_config)
    )
    monkeypatch.setattr(
        mod,
        "handle_db_connect_test",
        lambda _args: {"success": True, "connection_id": "conn-1"},
    )
    monkeypatch.setattr(
        mod,
        "handle_db_query_tables",
        lambda _args: {"success": True, "tables": ["users", "orders"]},
    )

    def fake_generate(arguments):
        calls["generate"].append(arguments)
        return {"success": True, "report": "Code Generation Complete"}

    monkeypatch.setattr(mod, "handle_db_codegen_generate", fake_generate)
    monkeypatch.setattr(mod.connection_manager, "close_connection", calls["close"].append)

    mod.generate(
        tables=None,
        config_path=None,
        output_dir=None,
        package_name=None,
        dry_run=False,
    )

    assert [call["table_name"] for call in calls["generate"]] == ["users", "orders"]
    assert all(call["connection_id"] == "conn-1" for call in calls["generate"])
    assert all(call["template_category"] == "Default" for call in calls["generate"])
    assert all("table_analysis" not in call for call in calls["generate"])
    assert calls["close"] == ["conn-1"]


def test_generate_forwards_schema_to_listing_and_generation(monkeypatch):
    mod = importlib.import_module("dbjavagenix.cli")
    calls = {"query": [], "generate": [], "close": []}
    monkeypatch.setattr(mod, "show_ascii_icon", lambda: None)
    monkeypatch.setattr(
        mod, "ConfigManager", lambda *_args, **_kwargs: SimpleNamespace(load_config=_fake_config)
    )
    monkeypatch.setattr(
        mod,
        "handle_db_connect_test",
        lambda _args: {"success": True, "connection_id": "conn-1"},
    )

    def fake_query(arguments):
        calls["query"].append(arguments)
        return {"success": True, "tables": ["users"]}

    monkeypatch.setattr(mod, "handle_db_query_tables", fake_query)

    def fake_generate(arguments):
        calls["generate"].append(arguments)
        return {"success": True}

    monkeypatch.setattr(mod, "handle_db_codegen_generate", fake_generate)
    monkeypatch.setattr(mod.connection_manager, "close_connection", calls["close"].append)

    mod.generate(
        tables=None,
        config_path=None,
        schema="tenant_a",
        output_dir=None,
        package_name=None,
        dry_run=False,
    )

    assert calls["query"] == [
        {"connection_id": "conn-1", "database": ":memory:", "schema": "tenant_a"}
    ]
    assert calls["generate"][0]["schema"] == "tenant_a"
    assert calls["close"] == ["conn-1"]
