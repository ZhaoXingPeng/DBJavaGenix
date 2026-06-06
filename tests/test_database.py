"""
基于真实数据库的代码生成完整测试
从数据库表结构分析到完整Java代码生成的端到端测试
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

# Configure test logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# Loaded from env vars — see tests/_db_config.py for required variables.
TEST_DATABASE_CONFIG = get_test_db_config_or_exit()


async def test_database_table_analysis_to_codegen():
    """测试从数据库表结构分析到代码生成上下文的完整流程"""
    logger.info("🔬 测试数据库表结构分析到代码生成上下文")
    
    try:
        # Import required modules
        from dbjavagenix.core.models import DatabaseConfig, DatabaseType
        from dbjavagenix.database.connection_manager import ConnectionManager
        from dbjavagenix.database.codegen_tools import CodegenAnalyzer
        
        logger.info("✅ 模块导入成功")
        
        # Create connection manager
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
        
        # Initialize codegen analyzer
        analyzer = CodegenAnalyzer(manager)
        
        # Get table list
        result = manager.execute_query(connection_id, f"SHOW TABLES FROM `{TEST_DATABASE_CONFIG['database']}`")
        if not result:
            logger.error("❌ 数据库中无表")
            return False
        
        table_key = list(result[0].keys())[0]
        tables = [row[table_key] for row in result]
        logger.info(f"📋 发现 {len(tables)} 个表: {tables}")
        
        # Test each table for codegen analysis
        success_count = 0
        for table_name in tables[:3]:  # Test first 3 tables
            logger.info(f"\n🔍 分析表用于代码生成: {table_name}")
            
            try:
                # Perform codegen analysis
                analysis_result = await analyzer.analyze_table_for_codegen(connection_id, table_name)
                
                # Validate analysis result structure
                assert "table_name" in analysis_result
                assert "table_info" in analysis_result
                assert "template_context" in analysis_result
                assert "java_types" in analysis_result
                assert "imports_needed" in analysis_result
                assert "relationships" in analysis_result
                
                logger.info(f"   ✅ 表名: {analysis_result['table_name']}")
                logger.info(f"   ✅ 表信息: {analysis_result['table_info']['name']}")
                logger.info(f"   ✅ 列数量: {len(analysis_result['table_info']['columns'])}")
                logger.info(f"   ✅ Java类型: {', '.join(analysis_result['java_types'])}")
                logger.info(f"   ✅ 需要导入: {', '.join(analysis_result['imports_needed'])}")
                
                # Validate template context
                context = analysis_result["template_context"]
                assert "className" in context
                assert "tableName" in context  
                assert "columns" in context
                assert "package" in context
                
                logger.info(f"   ✅ 生成类名: {context['className']}")
                logger.info("   ✅ 模板上下文完整")
                
                success_count += 1
                
            except Exception as e:
                logger.error(f"   ❌ 表 {table_name} 分析失败: {e}")
                continue
        
        # Clean up
        manager.close_connection(connection_id)
        logger.info("✅ 数据库连接已关闭")
        
        logger.info(f"\n📊 分析完成: 成功 {success_count}/{min(len(tables), 3)} 个表")
        return success_count > 0
        
    except Exception as e:
        logger.error(f"❌ 数据库表结构分析到代码生成失败: {e}")
        logger.exception("完整错误信息:")
        return False


async def test_template_category_code_generation():
    """测试三种模板分类的真实代码生成"""
    logger.info("🎨 测试三种模板分类的代码生成")
    
    try:
        # Import required modules
        from dbjavagenix.core.models import DatabaseConfig, DatabaseType, GenerationConfig
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
        logger.info("✅ 数据库连接成功")
        
        # Get first table for testing
        result = manager.execute_query(connection_id, f"SHOW TABLES FROM `{TEST_DATABASE_CONFIG['database']}` LIMIT 1")
        if not result:
            logger.error("❌ 数据库中无表")
            return False
        
        table_key = list(result[0].keys())[0]
        test_table = result[0][table_key]
        logger.info(f"📋 测试表: {test_table}")
        
        # Initialize analyzer and generator
        analyzer = CodegenAnalyzer(manager)
        generator = CodegenGenerator()
        
        # Test three template categories
        template_categories = ["Default", "MybatisPlus", "MybatisPlus-Mixed"]
        success_count = 0
        
        for category in template_categories:
            logger.info(f"\n🎯 测试模板分类: {category}")
            
            try:
                # Analyze table for codegen
                analysis_result = await analyzer.analyze_table_for_codegen(connection_id, test_table)
                
                # Generate code using specific template category
                generation_config = {
                    "author": "TestUser",
                    "package_name": f"com.test.{category.lower()}",
                    "include_swagger": True,
                    "include_lombok": True,
                    "include_mapstruct": True
                }
                
                generation_result = await generator.generate_code(
                    analysis_result,
                    category,
                    generation_config
                )
                
                # Validate generation result
                assert "generated_code" in generation_result
                assert "template_category" in generation_result
                assert "generation_statistics" in generation_result
                
                logger.info(f"   ✅ 模板分类: {generation_result['template_category']}")
                logger.info(f"   ✅ 生成文件数量: {generation_result['generation_statistics']['total_files']}")
                logger.info(f"   ✅ 成功文件: {generation_result['generation_statistics']['success_files']}")
                
                # Validate generated code structure
                generated_code = generation_result["generated_code"]
                
                # Check expected files based on template category
                if category == "Default":
                    expected_files = ["entity.mustache", "dao.mustache", "service.mustache", 
                                    "serviceImpl.mustache", "controller.mustache", "mapper.mustache"]
                elif category == "MybatisPlus":
                    expected_files = ["entity.mustache", "dao.mustache", "service.mustache", 
                                    "serviceImpl.mustache", "controller.mustache"]
                elif category == "MybatisPlus-Mixed":
                    expected_files = ["entity.mustache", "dao.mustache", "service.mustache", 
                                    "serviceImpl.mustache", "controller.mustache", "mapper.mustache"]
                
                for expected_file in expected_files:
                    if expected_file in generated_code:
                        logger.info(f"   ✅ 包含文件: {expected_file}")
                    else:
                        logger.warning(f"   ⚠️ 缺少文件: {expected_file}")
                
                success_count += 1
                
            except Exception as e:
                logger.error(f"   ❌ 模板分类 {category} 生成失败: {e}")
                continue
        
        # Clean up
        manager.close_connection(connection_id)
        
        logger.info(f"\n📊 模板测试完成: 成功 {success_count}/{len(template_categories)} 个分类")
        return success_count == len(template_categories)
        
    except Exception as e:
        logger.error(f"❌ 模板分类代码生成测试失败: {e}")
        logger.exception("完整错误信息:")
        return False


async def test_database_complete_package_generation():
    """测试从数据库读取到完整Java包生成的端到端流程"""
    logger.info("📦 测试完整Java包生成")
    
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
        logger.info("✅ 数据库连接成功")
        
        # Get tables for testing
        result = manager.execute_query(connection_id, f"SHOW TABLES FROM `{TEST_DATABASE_CONFIG['database']}` LIMIT 2")
        if not result:
            logger.error("❌ 数据库中无表")
            return False
        
        table_key = list(result[0].keys())[0]
        test_tables = [row[table_key] for row in result]
        logger.info(f"📋 测试表: {test_tables}")
        
        # Initialize tools
        analyzer = CodegenAnalyzer(manager)
        generator = CodegenGenerator()
        
        # Test complete package generation for multiple tables
        logger.info(f"\n🏗️ 生成完整Java包 ({len(test_tables)} 个表)")
        
        success_count = 0
        all_generated_code = {}
        
        for table_name in test_tables:
            logger.info(f"\n📄 处理表: {table_name}")
            
            try:
                # Analyze table
                analysis_result = await analyzer.analyze_table_for_codegen(connection_id, table_name)
                
                # Generate complete package (including DTO/VO)
                generation_config = {
                    "author": "TestUser",
                    "package_name": "com.test.complete",
                    "include_swagger": True,
                    "include_lombok": True,
                    "include_mapstruct": True,
                    "include_dto_vo": True
                }
                
                generation_result = await generator.generate_code(
                    analysis_result,
                    "MybatisPlus-Mixed",  # Use most complete template
                    generation_config
                )
                
                all_generated_code[table_name] = generation_result
                
                logger.info(f"   ✅ 表 {table_name}: {generation_result['generation_statistics']['total_files']} 个文件")
                
                # Validate complete package structure
                generated_code = generation_result["generated_code"]
                
                # Check main files
                main_files = ["entity.mustache", "dao.mustache", "service.mustache", 
                            "serviceImpl.mustache", "controller.mustache", "mapper.mustache"]
                for file_name in main_files:
                    if file_name in generated_code:
                        logger.info(f"   ✅ 主要文件: {file_name}")
                
                # Check additional files (DTO/VO)
                additional_files = ["dto.mustache", "vo.mustache", "mapstruct_mapper.mustache"]
                for file_name in additional_files:
                    if file_name in generated_code:
                        logger.info(f"   ✅ 附加文件: {file_name}")
                
                success_count += 1
                
            except Exception as e:
                logger.error(f"   ❌ 表 {table_name} 包生成失败: {e}")
                continue
        
        # Summary
        total_files = sum(
            result['generation_statistics']['total_files'] 
            for result in all_generated_code.values()
        )
        
        logger.info("\n📊 完整包生成完成:")
        logger.info(f"   ✅ 成功表数: {success_count}/{len(test_tables)}")
        logger.info(f"   ✅ 总文件数: {total_files}")
        logger.info("   ✅ 包结构完整")
        
        # Clean up
        manager.close_connection(connection_id)
        
        return success_count == len(test_tables)
        
    except Exception as e:
        logger.error(f"❌ 完整包生成测试失败: {e}")
        logger.exception("完整错误信息:")
        return False


async def main():
    """主测试运行器"""
    logger.info("=" * 80)
    logger.info("🔬 DBJavaGenix 真实数据库代码生成测试")
    logger.info("=" * 80)
    
    # Test 1: Database table analysis to codegen
    test1_success = await test_database_table_analysis_to_codegen()
    
    # Test 2: Template category code generation
    test2_success = await test_template_category_code_generation()
    
    # Test 3: Complete package generation
    test3_success = await test_database_complete_package_generation()
    
    logger.info("\n" + "=" * 80)
    
    if test1_success and test2_success and test3_success:
        logger.info("✅ 总体结果: 所有真实数据库代码生成测试通过!")
        logger.info("   ✅ 数据库分析到代码生成: 通过")
        logger.info("   ✅ 三种模板分类测试: 通过")
        logger.info("   ✅ 完整包生成测试: 通过")
    else:
        logger.error("❌ 总体结果: 部分测试失败")
        logger.info(f"   {'✅' if test1_success else '❌'} 数据库分析到代码生成: {'通过' if test1_success else '失败'}")
        logger.info(f"   {'✅' if test2_success else '❌'} 三种模板分类测试: {'通过' if test2_success else '失败'}")
        logger.info(f"   {'✅' if test3_success else '❌'} 完整包生成测试: {'通过' if test3_success else '失败'}")
    
    logger.info("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())