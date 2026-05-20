"""CLI 模块烟雾测试 (导入 + 关键符号检查)

旧版本是脚本式写法 (print + return True/False), pytest 视为 silent fail。
重写为正确 pytest 风格。
"""

import importlib


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
