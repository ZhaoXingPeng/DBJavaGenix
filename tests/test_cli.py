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
