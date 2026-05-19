#!/usr/bin/env python3
"""
CLI interface test
"""
import sys
import os
from unittest.mock import patch, MagicMock

# Add src path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from dbjavagenix.cli import show_ascii_icon
from dbjavagenix.core.exceptions import DBJavaGenixError


def test_ascii_icon_display():
    """Test ASCII icon display functionality"""
    try:
        # Test icon display without file (should not raise error)
        show_ascii_icon()
        print("[PASS] ASCII icon display test passed")
    except Exception as e:
        print(f"[FAIL] ASCII icon display test failed: {e}")
        return False
    return True


def test_cli_imports():
    """Test that CLI module can import all dependencies"""
    try:
        from dbjavagenix.cli import (
            app, console, version, init, generate, 
            list_tables, check_dependencies, analyze, server
        )
        print("[PASS] CLI imports test passed")
    except ImportError as e:
        print(f"[FAIL] CLI imports test failed: {e}")
        return False
    return True


def test_exception_handling():
    """Test CLI exception handling"""
    try:
        # Test that we can create and handle DBJavaGenix exceptions
        error = DBJavaGenixError("Test error", "TEST_ERROR")
        assert str(error) == "[TEST_ERROR] Test error"
        print("[PASS] Exception handling test passed")
    except Exception as e:
        print(f"[FAIL] Exception handling test failed: {e}")
        return False
    return True


def main():
    """Run CLI tests"""
    print("=== CLI Module Tests ===")
    
    tests = [
        test_cli_imports,
        test_ascii_icon_display,
        test_exception_handling
    ]
    
    passed = 0
    for test in tests:
        if test():
            passed += 1
    
    print(f"\nResults: {passed}/{len(tests)} tests passed")
    
    if passed == len(tests):
        print("[SUCCESS] All CLI tests passed!")
        return True
    else:
        print("[ERROR] Some CLI tests failed!")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)