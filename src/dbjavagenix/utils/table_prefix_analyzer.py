#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
表名前缀分析器
用于分析表名前缀并生成相应的包结构
"""

import re
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass


@dataclass
class PrefixGroup:
    """前缀分组信息"""
    prefix: str              # 原始前缀 (如: sys)
    full_name: str           # 完整名称 (如: system)
    package_name: str        # 包名 (如: system)
    tables: List[str]        # 属于该前缀的表名列表
    

class TablePrefixAnalyzer:
    """表名前缀分析器"""
    
    # 预定义的前缀映射表 (可扩展)
    COMMON_PREFIX_MAPPINGS = {
        'sys': 'system',
        'auth': 'authentication', 
        'user': 'user',
        'admin': 'administration',
        'log': 'logging',
        'config': 'configuration',
        'dict': 'dictionary',
        'file': 'file',
        'msg': 'message',
        'pay': 'payment',
        'order': 'order',
        'product': 'product',
        'shop': 'shop',
        'cart': 'cart',
        'member': 'member',
        'org': 'organization',
        'dept': 'department',
        'role': 'role',
        'perm': 'permission',
        'menu': 'menu',
        'api': 'api',
        'data': 'data',
        'report': 'report',
        'workflow': 'workflow',
        'task': 'task',
        'job': 'job',
        'notice': 'notice',
        'news': 'news',
        'article': 'article',
        'content': 'content',
        'media': 'media',
        'attachment': 'attachment'
    }
    
    def __init__(self, min_tables_per_prefix: int = 2, min_prefix_length: int = 2):
        """
        初始化前缀分析器
        
        Args:
            min_tables_per_prefix: 最少多少个表才算有效前缀 (默认2个)
            min_prefix_length: 前缀最短长度 (默认2个字符)
        """
        self.min_tables_per_prefix = min_tables_per_prefix
        self.min_prefix_length = min_prefix_length
        
    def extract_prefix(self, table_name: str) -> Optional[str]:
        """
        从表名中提取前缀
        
        Args:
            table_name: 表名
            
        Returns:
            提取的前缀，如果没有则返回None
        """
        # 移除常见的表前缀符号
        cleaned_name = table_name.lower()
        
        # 通过下划线分割提取前缀
        if '_' in cleaned_name:
            parts = cleaned_name.split('_')
            if len(parts) >= 2:
                prefix = parts[0]
                # 检查前缀长度
                if len(prefix) >= self.min_prefix_length:
                    return prefix
        
        return None
    
    def analyze_table_prefixes(self, table_names: List[str]) -> Dict[str, PrefixGroup]:
        """
        分析表名列表的前缀分组
        
        Args:
            table_names: 表名列表
            
        Returns:
            前缀分组字典，key为前缀，value为PrefixGroup对象
        """
        # Step 1: 提取所有表的前缀
        prefix_tables: Dict[str, List[str]] = {}
        no_prefix_tables: List[str] = []
        
        for table_name in table_names:
            prefix = self.extract_prefix(table_name)
            if prefix:
                if prefix not in prefix_tables:
                    prefix_tables[prefix] = []
                prefix_tables[prefix].append(table_name)
            else:
                no_prefix_tables.append(table_name)
        
        # Step 2: 过滤出有效的前缀组 (表数量 >= min_tables_per_prefix)
        valid_prefixes = {
            prefix: tables 
            for prefix, tables in prefix_tables.items() 
            if len(tables) >= self.min_tables_per_prefix
        }
        
        # Step 3: 构建前缀分组
        prefix_groups = {}
        
        for prefix, tables in valid_prefixes.items():
            full_name = self._get_full_name(prefix, tables)
            package_name = self._generate_package_name(full_name)
            
            prefix_groups[prefix] = PrefixGroup(
                prefix=prefix,
                full_name=full_name,
                package_name=package_name,
                tables=sorted(tables)
            )
        
        # Step 4: 处理无前缀的表 (如果有的话，归入common分组)
        invalid_prefix_tables = []
        for prefix, tables in prefix_tables.items():
            if len(tables) < self.min_tables_per_prefix:
                invalid_prefix_tables.extend(tables)
        
        all_ungrouped = no_prefix_tables + invalid_prefix_tables
        if all_ungrouped:
            prefix_groups['common'] = PrefixGroup(
                prefix='common',
                full_name='common',
                package_name='common',
                tables=sorted(all_ungrouped)
            )
        
        return prefix_groups
    
    def _get_full_name(self, prefix: str, tables: List[str]) -> str:
        """
        获取前缀的完整名称
        
        Args:
            prefix: 前缀
            tables: 属于该前缀的表列表
            
        Returns:
            完整名称
        """
        # 首先检查预定义映射
        if prefix in self.COMMON_PREFIX_MAPPINGS:
            return self.COMMON_PREFIX_MAPPINGS[prefix]
        
        # TODO: 未来可以通过表注释分析得到更准确的名称
        # 这里暂时返回前缀本身
        return prefix
    
    def _generate_package_name(self, full_name: str) -> str:
        """
        生成包名
        
        Args:
            full_name: 完整名称
            
        Returns:
            包名 (小写，符合Java包命名规范)
        """
        # 将名称转换为合法的Java包名
        package_name = re.sub(r'[^a-zA-Z0-9]', '', full_name.lower())
        
        # 确保包名不以数字开头
        if package_name and package_name[0].isdigit():
            package_name = 'pkg' + package_name
            
        return package_name or 'common'
    
    def should_use_prefix_grouping(self, table_names: List[str]) -> bool:
        """
        判断是否应该使用前缀分组
        
        Args:
            table_names: 表名列表
            
        Returns:
            True如果应该使用前缀分组，False否则
        """
        prefix_groups = self.analyze_table_prefixes(table_names)
        
        # 如果有有效的前缀组(除了common)，则使用前缀分组
        valid_groups = [group for prefix, group in prefix_groups.items() if prefix != 'common']
        
        return len(valid_groups) > 0
    
    def get_table_package_suffix(self, table_name: str, table_names: List[str]) -> str:
        """
        获取表对应的包后缀
        
        Args:
            table_name: 表名
            table_names: 所有表名列表
            
        Returns:
            包后缀，如果不使用前缀分组则返回空字符串
        """
        if not self.should_use_prefix_grouping(table_names):
            return ""
        
        prefix_groups = self.analyze_table_prefixes(table_names)
        
        # 查找表所属的分组
        for prefix, group in prefix_groups.items():
            if table_name in group.tables:
                return group.package_name
        
        return "common"
    
    def generate_analysis_report(self, table_names: List[str]) -> str:
        """
        生成前缀分析报告
        
        Args:
            table_names: 表名列表
            
        Returns:
            分析报告文本
        """
        prefix_groups = self.analyze_table_prefixes(table_names)
        
        report = []
        report.append("# 表名前缀分析报告")
        report.append("")
        report.append(f"## 基本信息")
        report.append(f"- **总表数**: {len(table_names)}")
        report.append(f"- **前缀组数**: {len(prefix_groups)}")
        report.append(f"- **使用前缀分组**: {'是' if self.should_use_prefix_grouping(table_names) else '否'}")
        report.append("")
        
        if prefix_groups:
            report.append("## 前缀分组详情")
            report.append("")
            
            for prefix, group in sorted(prefix_groups.items()):
                report.append(f"### {group.full_name} ({prefix})")
                report.append(f"- **包名**: `{group.package_name}`")
                report.append(f"- **表数量**: {len(group.tables)}")
                report.append(f"- **表列表**:")
                for table in group.tables:
                    report.append(f"  - {table}")
                report.append("")
        
        return "\n".join(report)


if __name__ == "__main__":
    # 测试代码
    analyzer = TablePrefixAnalyzer()
    
    test_tables = [
        'sys_permissions',
        'sys_role_permissions', 
        'sys_user_organizations',
        'sys_user_roles',
        'sys_user_special_permissions',
        'user_profile',
        'product_category',
        'product_item',
        'order_info',
        'standalone_table'
    ]
    
    print("=== 前缀分析测试 ===")
    print(analyzer.generate_analysis_report(test_tables))
    
    print("\n=== 包后缀测试 ===")
    for table in test_tables:
        suffix = analyzer.get_table_package_suffix(table, test_tables)
        print(f"{table} -> {suffix}")