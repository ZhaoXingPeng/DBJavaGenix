#!/usr/bin/env python3
"""
Run all tests in the tests directory
"""
import os
import sys
import subprocess
from pathlib import Path

def run_test(test_file):
    """Run a single test file"""
    try:
        result = subprocess.run([sys.executable, test_file], 
                              capture_output=True, text=True, encoding='utf-8')
        return result.returncode == 0, result.stdout, result.stderr
    except UnicodeDecodeError:
        # Fallback for Windows encoding issues
        try:
            result = subprocess.run([sys.executable, test_file], 
                                  capture_output=True, text=True, encoding='gbk')
            return result.returncode == 0, result.stdout, result.stderr
        except:
            return False, "", "Encoding error"

def main():
    """Run all tests"""
    tests_dir = Path(__file__).parent
    test_files = [
        'test_cli.py',
        'test_server.py', 
        'test_utils_dependency.py',
        'test_utils_prefix.py',
        'unit/test_config.py',
        'unit/test_models.py'
    ]
    
    print("=== Running DBJavaGenix Test Suite ===\n")
    
    passed = 0
    failed = 0
    
    for test_file in test_files:
        test_path = tests_dir / test_file
        if test_path.exists():
            print(f"Running {test_file}...")
            success, stdout, stderr = run_test(str(test_path))
            
            if success:
                print(f"[PASS] {test_file}")
                passed += 1
            else:
                print(f"[FAIL] {test_file}")
                if stderr:
                    print(f"  Error: {stderr[:200]}...")
                failed += 1
            print()
        else:
            print(f"[SKIP] {test_file} not found")
            print()
    
    print("=== Test Summary ===")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print(f"Total: {passed + failed}")
    
    if failed == 0:
        print("\n[SUCCESS] All tests passed!")
        return True
    else:
        print(f"\n[ERROR] {failed} tests failed!")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)