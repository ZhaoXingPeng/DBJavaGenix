#!/usr/bin/env python3
"""
MCP Server functionality test
"""
import sys
import os

# Add src path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


def test_server_imports():
    """Test server module imports"""
    try:
        from dbjavagenix.server.mcp_server import server, handle_list_tools, handle_call_tool
        print("[PASS] Server imports test passed")
        return True
    except ImportError as e:
        print(f"[FAIL] Server imports test failed: {e}")
        return False


def test_mcp_tools_imports():
    """Test MCP tools imports"""
    try:
        from dbjavagenix.database.mcp_tools import (
            get_connection_tools,
            get_table_analysis_tools, 
            get_codegen_tools,
            get_dependency_check_tools
        )
        print("[PASS] MCP tools imports test passed")
        return True
    except ImportError as e:
        print(f"[FAIL] MCP tools imports test failed: {e}")
        return False


def test_tool_functions():
    """Test that tool functions are available"""
    try:
        from dbjavagenix.database.mcp_tools import (
            handle_db_connect_test,
            handle_db_query_databases,
            handle_db_query_tables,
            handle_db_codegen_analyze,
            handle_db_codegen_generate,
            handle_java_check_dependencies
        )
        print("[PASS] Tool functions test passed")
        return True
    except ImportError as e:
        print(f"[FAIL] Tool functions test failed: {e}")
        return False


def main():
    """Run server tests"""
    print("=== MCP Server Module Tests ===")
    
    tests = [
        test_server_imports,
        test_mcp_tools_imports,
        test_tool_functions
    ]
    
    passed = 0
    for test in tests:
        if test():
            passed += 1
    
    print(f"\nResults: {passed}/{len(tests)} tests passed")
    
    if passed == len(tests):
        print("[SUCCESS] All server tests passed!")
        return True
    else:
        print("[ERROR] Some server tests failed!")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)