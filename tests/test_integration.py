#!/usr/bin/env python3
"""
真实代码生成测试脚本
从数据库读取表结构并生成实际的Java代码文件
"""

import asyncio
import sys
import os
import tempfile
import logging
from pathlib import Path

# Add src path to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
sys.path.insert(0, os.path.dirname(__file__))

from _db_config import get_test_db_config_or_exit  # noqa: E402

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# Loaded from env vars — see tests/_db_config.py for required variables.
TEST_DATABASE_CONFIG = get_test_db_config_or_exit()

async def test_real_code_generation():
    """测试真实的代码生成"""
    logger.info("🚀 开始真实代码生成测试")
    
    try:
        # Import required modules
        from dbjavagenix.core.models import DatabaseConfig, DatabaseType
        from dbjavagenix.database.connection_manager import ConnectionManager
        from dbjavagenix.database.codegen_tools import CodegenAnalyzer, CodegenGenerator
        
        # Create connection
        manager = ConnectionManager()
        config = DatabaseConfig(
            type=DatabaseType.MYSQL,
            host=TEST_DATABASE_CONFIG["host"],
            port=TEST_DATABASE_CONFIG["port"],
            username=TEST_DATABASE_CONFIG["username"],
            password=TEST_DATABASE_CONFIG["password"],
            database=TEST_DATABASE_CONFIG["database"]
        )
        
        connection_id = manager.create_connection(config)
        logger.info(f"✅ 数据库连接成功: {connection_id}")
        
        # Get all tables
        result = manager.execute_query(connection_id, f"SHOW TABLES FROM `{TEST_DATABASE_CONFIG['database']}`")
        if not result:
            logger.error("❌ 数据库中无表")
            return False
        
        table_key = list(result[0].keys())[0]
        all_tables = [row[table_key] for row in result]
        logger.info(f"📋 发现数据库表: {len(all_tables)} 个")
        for i, table in enumerate(all_tables, 1):
            logger.info(f"   {i}. {table}")
        
        # Initialize tools
        analyzer = CodegenAnalyzer(manager)
        generator = CodegenGenerator()
        
        # Step 1: Generate code for all tables
        output_dir = Path("generated_output")
        output_dir.mkdir(exist_ok=True)
        
        templates = ["Default", "MybatisPlus", "MybatisPlus-Mixed"]
        all_results = {}
        
        total_success_files = 0
        total_error_files = 0
        
        for table_name in all_tables:
            logger.info("\\n" + "="*60)
            logger.info(f"🔍 处理表: {table_name}")
            logger.info("="*60)
            
            # Analyze table
            logger.info(f"📊 分析表结构: {table_name}")
            analysis_result = await analyzer.analyze_table_for_codegen(connection_id, table_name, all_tables)
            
            logger.info("✅ 表分析完成:")
            logger.info(f"   表名: {analysis_result['table_name']}")
            logger.info(f"   列数: {len(analysis_result['table_info']['columns'])}")
            logger.info(f"   Java类型: {', '.join(analysis_result['java_types'])}")
            
            table_results = {}
            
            for template in templates:
                logger.info(f"\\n🎯 生成 {template} 模板代码 for {table_name}")
                
                generation_config = {
                    "output_dir": str(output_dir / template),  # 移除表名子目录
                    "author": "ZXP", 
                    "package_name": f"com.example.{template.lower().replace('-', '')}",  # 统一包名，不包含表名
                    "include_swagger": True,
                    "include_lombok": True,
                    "include_mapstruct": True
                }
                
                # Generate code
                generation_result = await generator.generate_code(
                    analysis_result,
                    template,
                    generation_config
                )
                
                table_results[f"{table_name}_{template}"] = generation_result
                
                # Save generated code to files
                template_dir = output_dir / template  # 移除表名子目录
                template_dir.mkdir(parents=True, exist_ok=True)
                
                generated_code = generation_result["generated_code"]
                stats = generation_result["generation_statistics"]
                
                logger.info("   📊 生成统计:")
                logger.info(f"      总文件: {stats['total_files']}")
                logger.info(f"      成功: {stats['success_files']}")
                logger.info(f"      失败: {stats['error_files']}")
                
                total_success_files += stats['success_files']
                total_error_files += stats['error_files']
                
                # Save each generated file
                for template_file, file_info in generated_code.items():
                    if "error" not in file_info:
                        output_file = template_dir / file_info["filename"]
                        output_file.parent.mkdir(parents=True, exist_ok=True)
                        
                        with open(output_file, 'w', encoding='utf-8') as f:
                            f.write(file_info["code"])
                        
                        logger.info(f"      ✅ 保存文件: {output_file}")
                    else:
                        logger.error(f"      ❌ 生成失败: {template_file} - {file_info['error']}")
            
            all_results.update(table_results)
        
        # Step 2: Generate summary report
        logger.info("\\n" + "="*80)
        logger.info("📊 生成完成总结:")
        logger.info("="*80)
        logger.info(f"   📋 处理表数量: {len(all_tables)}")
        logger.info(f"   🎯 模板数量: {len(templates)}")
        logger.info(f"   ✅ 成功生成文件: {total_success_files}")
        logger.info(f"   ❌ 生成失败文件: {total_error_files}")
        logger.info(f"   📁 输出目录: {output_dir.absolute()}")
        
        # List all generated tables
        logger.info("\\n📝 生成的表:")
        for table in all_tables:
            logger.info(f"   ✅ {table}")
            for template in templates:
                template_dir = output_dir / template / table
                if template_dir.exists():
                    java_files = list(template_dir.rglob("*.java"))
                    xml_files = list(template_dir.rglob("*.xml"))
                    logger.info(f"      📦 {template}: {len(java_files)} Java文件, {len(xml_files)} XML文件")
        
        # Create summary file
        summary_file = output_dir / "GENERATION_SUMMARY.md"
        with open(summary_file, 'w', encoding='utf-8') as f:
            f.write("# 代码生成总结\\n\\n")
            f.write("## 基本信息\\n")
            f.write(f"- **处理表数量**: {len(all_tables)}\\n")
            f.write(f"- **数据库**: {TEST_DATABASE_CONFIG['database']}\\n")
            f.write(f"- **生成时间**: {__import__('datetime').datetime.now()}\\n\\n")
            
            f.write("## 处理的表\\n")
            for i, table in enumerate(all_tables, 1):
                f.write(f"{i}. **{table}**\\n")
            f.write("\\n")
            
            f.write("## 生成统计\\n")
            f.write(f"- **总成功文件**: {total_success_files}\\n")
            f.write(f"- **总失败文件**: {total_error_files}\\n")
            f.write(f"- **模板类型**: {len(templates)} 种 ({', '.join(templates)})\\n\\n")
            
            # 按表统计
            for table in all_tables:
                f.write(f"### {table}\\n")
                for template in templates:
                    template_dir = output_dir / template / table
                    if template_dir.exists():
                        java_files = list(template_dir.rglob("*.java"))
                        xml_files = list(template_dir.rglob("*.xml"))
                        f.write(f"- **{template}**: {len(java_files)} Java文件, {len(xml_files)} XML文件\\n")
                        
                        # 列出文件
                        for java_file in java_files:
                            rel_path = java_file.relative_to(template_dir)
                            f.write(f"  - ✅ {rel_path}\\n")
                        for xml_file in xml_files:
                            rel_path = xml_file.relative_to(template_dir)
                            f.write(f"  - 📋 {rel_path}\\n")
                f.write("\\n")
            
            f.write("## 目录结构\\n")
            f.write("```\\n")
            f.write("generated_output/\\n")
            for template in templates:
                f.write(f"├── {template}/\\n")
                for table in all_tables:
                    f.write(f"│   └── {table}/\\n")
            f.write("```\\n")
        
        logger.info(f"✅ 生成总结报告: {summary_file}")
        
        # Clean up
        manager.close_connection(connection_id)
        
        return total_success_files > 0
        
    except Exception as e:
        logger.error(f"❌ 真实代码生成测试失败: {e}")
        logger.exception("完整错误信息:")
        return False

async def main():
    """主函数"""
    logger.info("=" * 80)
    logger.info("🔬 DBJavaGenix 真实代码生成测试")
    logger.info("=" * 80)
    
    success = await test_real_code_generation()
    
    logger.info("\\n" + "=" * 80)
    if success:
        logger.info("✅ 真实代码生成测试成功！")
        logger.info("📁 请查看 generated_output 目录下的生成文件")
    else:
        logger.error("❌ 真实代码生成测试失败！")
    logger.info("=" * 80)

if __name__ == "__main__":
    asyncio.run(main())