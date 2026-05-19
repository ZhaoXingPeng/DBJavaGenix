#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
测试前缀分析器的功能
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from dbjavagenix.utils.table_prefix_analyzer import TablePrefixAnalyzer

def test_sys_tables():
    """测试sys前缀表的分析"""
    analyzer = TablePrefixAnalyzer()
    
    # 当前数据库中的5张表
    test_tables = [
        'sys_permissions',
        'sys_role_permissions',
        'sys_user_organizations',
        'sys_user_roles',
        'sys_user_special_permissions'
    ]
    
    print("=== DBJavaGenix 前缀分析测试 ===\n")
    print(f"测试表名: {test_tables}\n")
    
    # 生成分析报告
    report = analyzer.generate_analysis_report(test_tables)
    print(report)
    
    print("\n=== 包路径测试 ===")
    for table in test_tables:
        suffix = analyzer.get_table_package_suffix(table, test_tables)
        print(f"{table} -> 包后缀: '{suffix}'")
        
        if suffix:
            full_package = f"com.example.default.{suffix}.controller"
            print(f"                    -> 完整包路径: {full_package}")
        else:
            full_package = "com.example.default.controller"
            print(f"                    -> 完整包路径: {full_package}")
        print()

if __name__ == "__main__":
    test_sys_tables()