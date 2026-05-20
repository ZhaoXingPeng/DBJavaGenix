"""MCP Server 模块导入烟雾测试

旧版本用 print + return False 写法, 导致 import 错误被 pytest 视为通过
(silent fail)。改写为正确的 pytest 风格, 让任何遗留的不存在符号引用直接
报错。

历史遗留: 旧 test 引用过 `handle_java_check_dependencies` 与
`get_dependency_check_tools`, 这两个函数从未实际实现 (见
mcp_server.py 内对应注释), P1.6 阶段移除。
"""

import importlib


def test_server_module_imports():
    """mcp_server 主模块及关键符号可被 import"""
    mod = importlib.import_module("dbjavagenix.server.mcp_server")
    assert hasattr(mod, "server")
    assert hasattr(mod, "handle_list_tools")
    assert hasattr(mod, "handle_call_tool")


def test_mcp_tools_factory_functions_present():
    """工具注册工厂函数全部存在 (Tool list 提供方)"""
    mod = importlib.import_module("dbjavagenix.database.mcp_tools")
    for name in (
        "get_connection_tools",
        "get_table_analysis_tools",
        "get_codegen_tools",
        "get_springboot_project_tools",
    ):
        assert callable(getattr(mod, name, None)), f"{name} not callable"


def test_core_handlers_present():
    """核心工具 handler 函数可被 import"""
    mod = importlib.import_module("dbjavagenix.database.mcp_tools")
    for name in (
        "handle_db_connect_test",
        "handle_db_query_databases",
        "handle_db_query_tables",
        "handle_db_codegen_analyze",
        "handle_db_codegen_generate",
        "handle_springboot_validate_project",
        "handle_springboot_analyze_dependencies",
    ):
        assert callable(getattr(mod, name, None)), f"{name} missing or not callable"


def test_get_connection_tools_returns_tool_list():
    """get_connection_tools 应返回非空的 Tool 对象列表"""
    from dbjavagenix.database.mcp_tools import get_connection_tools

    tools = get_connection_tools()
    assert isinstance(tools, list)
    assert len(tools) > 0
    # 每个 Tool 至少有 name 与 description
    for t in tools:
        assert getattr(t, "name", None), "Tool missing name"
        assert getattr(t, "description", None), "Tool missing description"
