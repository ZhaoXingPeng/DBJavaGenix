"""
三种模板分类的真实数据库代码生成测试
详细测试 Default、MybatisPlus、MybatisPlus-Mixed 三种模板分类的代码生成效果
"""
import asyncio
import sys
import os
import logging

# Add src path to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
sys.path.insert(0, os.path.dirname(__file__))

from _db_config import get_test_db_config_or_exit  # noqa: E402

# Configure test logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# Loaded from env vars — see tests/_db_config.py for required variables.
TEST_DATABASE_CONFIG = get_test_db_config_or_exit()


async def test_default_template_generation():
    """测试 Default 模板分类的代码生成"""
    logger.info("🎯 测试 Default 模板分类")
    
    try:
        # Import required modules
        from dbjavagenix.core.models import DatabaseConfig, DatabaseType
        from dbjavagenix.database.connection_manager import ConnectionManager
        from dbjavagenix.database.codegen_tools import CodegenAnalyzer, CodegenGenerator
        
        # Setup connection
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
        
        # Get test table
        result = manager.execute_query(connection_id, f"SHOW TABLES FROM `{TEST_DATABASE_CONFIG['database']}` LIMIT 1")
        if not result:
            logger.error("❌ 数据库中无表")
            return False
        
        table_key = list(result[0].keys())[0]
        test_table = result[0][table_key]
        logger.info(f"📋 测试表: {test_table}")
        
        # Initialize tools
        analyzer = CodegenAnalyzer(manager)
        generator = CodegenGenerator()
        
        # Analyze table
        analysis_result = await analyzer.analyze_table_for_codegen(connection_id, test_table)
        logger.info(f"✅ 表分析完成: {analysis_result['table_name']}")
        
        # Generate Default template code
        generation_config = {
            "author": "DefaultTestUser",
            "package_name": "com.test.default",
            "include_swagger": True,
            "include_lombok": True,
            "include_mapstruct": True,
            "include_dto_vo": True
        }
        
        generation_result = await generator.generate_code(
            analysis_result,
            "Default",
            generation_config
        )
        
        # Validate Default template characteristics
        assert generation_result['template_category'] == "Default"
        generated_code = generation_result["generated_code"]
        
        # Expected files for Default template (traditional MyBatis)
        expected_files = [
            "entity.mustache",      # Entity class
            "dao.mustache",         # DAO interface
            "service.mustache",     # Service interface
            "serviceImpl.mustache", # Service implementation
            "controller.mustache",  # REST Controller
            "mapper.mustache",      # MyBatis XML mapper
        ]
        
        logger.info("📁 Default 模板文件验证:")
        for file_name in expected_files:
            if file_name in generated_code:
                file_info = generated_code[file_name]
                if "error" not in file_info:
                    logger.info(f"   ✅ {file_name}: 生成成功")
                    # Validate some content exists
                    if "code" in file_info and len(file_info["code"]) > 0:
                        logger.info(f"      📄 代码长度: {len(file_info['code'])} 字符")
                    else:
                        logger.warning(f"      ⚠️ {file_name}: 代码内容为空")
                else:
                    logger.error(f"   ❌ {file_name}: {file_info['error']}")
            else:
                logger.error(f"   ❌ 缺少文件: {file_name}")
        
        # Check additional files (DTO/VO if enabled)
        additional_files = ["dto.mustache", "vo.mustache", "mapstruct_mapper.mustache"]
        logger.info("📁 Default 附加文件验证:")
        for file_name in additional_files:
            if file_name in generated_code:
                logger.info(f"   ✅ {file_name}: 生成成功")
            else:
                logger.info(f"   ℹ️ {file_name}: 未生成（可选）")
        
        # Validate statistics
        stats = generation_result["generation_statistics"]
        logger.info("📊 Default 生成统计:")
        logger.info(f"   总文件: {stats['total_files']}")
        logger.info(f"   成功: {stats['success_files']}")
        logger.info(f"   失败: {stats['error_files']}")
        
        # Clean up
        manager.close_connection(connection_id)
        
        # Success if main files generated
        main_files_success = all(f in generated_code for f in expected_files[:4])  # Entity, DAO, Service, ServiceImpl
        
        logger.info(f"✅ Default 模板测试{'成功' if main_files_success else '失败'}")
        return main_files_success
        
    except Exception as e:
        logger.error(f"❌ Default 模板测试失败: {e}")
        logger.exception("完整错误信息:")
        return False


async def test_mybatis_plus_template_generation():
    """测试 MybatisPlus 模板分类的代码生成"""
    logger.info("🎯 测试 MybatisPlus 模板分类")
    
    try:
        # Import required modules
        from dbjavagenix.core.models import DatabaseConfig, DatabaseType
        from dbjavagenix.database.connection_manager import ConnectionManager
        from dbjavagenix.database.codegen_tools import CodegenAnalyzer, CodegenGenerator
        
        # Setup connection
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
        
        # Get test table
        result = manager.execute_query(connection_id, f"SHOW TABLES FROM `{TEST_DATABASE_CONFIG['database']}` LIMIT 1")
        table_key = list(result[0].keys())[0]
        test_table = result[0][table_key]
        logger.info(f"📋 测试表: {test_table}")
        
        # Initialize tools
        analyzer = CodegenAnalyzer(manager)
        generator = CodegenGenerator()
        
        # Analyze table
        analysis_result = await analyzer.analyze_table_for_codegen(connection_id, test_table)
        logger.info(f"✅ 表分析完成: {analysis_result['table_name']}")
        
        # Generate MybatisPlus template code
        generation_config = {
            "author": "MybatisPlusTestUser",
            "package_name": "com.test.mybatisplus",
            "include_swagger": True,
            "include_lombok": True,
            "include_mapstruct": False,  # MybatisPlus typically doesn't need MapStruct
            "include_dto_vo": True
        }
        
        generation_result = await generator.generate_code(
            analysis_result,
            "MybatisPlus",
            generation_config
        )
        
        # Validate MybatisPlus template characteristics
        assert generation_result['template_category'] == "MybatisPlus"
        generated_code = generation_result["generated_code"]
        
        # Expected files for MybatisPlus template (no XML mapper, pure annotation)
        expected_files = [
            "entity.mustache",      # Entity class (extends Model)
            "dao.mustache",         # DAO interface (extends BaseMapper)
            "service.mustache",     # Service interface (extends IService)
            "serviceImpl.mustache", # Service implementation (extends ServiceImpl)
            "controller.mustache",  # REST Controller (extends ApiController)
        ]
        
        # Should NOT have XML mapper file
        should_not_have = ["mapper.mustache"]
        
        logger.info("📁 MybatisPlus 模板文件验证:")
        for file_name in expected_files:
            if file_name in generated_code:
                file_info = generated_code[file_name]
                if "error" not in file_info:
                    logger.info(f"   ✅ {file_name}: 生成成功")
                    # Check for MybatisPlus specific content patterns
                    if "code" in file_info:
                        code_content = file_info["code"]
                        if "BaseMapper" in code_content and file_name == "dao.mustache":
                            logger.info(f"      ✅ {file_name}: 包含 BaseMapper 继承")
                        if "ServiceImpl" in code_content and file_name == "serviceImpl.mustache":
                            logger.info(f"      ✅ {file_name}: 包含 ServiceImpl 继承")
                else:
                    logger.error(f"   ❌ {file_name}: {file_info['error']}")
            else:
                logger.error(f"   ❌ 缺少文件: {file_name}")
        
        # Verify XML mapper is NOT generated (MybatisPlus pure annotation mode)
        logger.info("📁 MybatisPlus 不应生成的文件验证:")
        for file_name in should_not_have:
            if file_name in generated_code:
                logger.warning(f"   ⚠️ {file_name}: 不应生成但存在")
            else:
                logger.info(f"   ✅ {file_name}: 正确未生成")
        
        # Validate statistics
        stats = generation_result["generation_statistics"]
        logger.info("📊 MybatisPlus 生成统计:")
        logger.info(f"   总文件: {stats['total_files']}")
        logger.info(f"   成功: {stats['success_files']}")
        logger.info(f"   失败: {stats['error_files']}")
        
        # Clean up
        manager.close_connection(connection_id)
        
        # Success if main files generated and no XML mapper
        main_files_success = all(f in generated_code for f in expected_files[:4])
        no_xml_mapper = "mapper.mustache" not in generated_code
        
        success = main_files_success and no_xml_mapper
        logger.info(f"✅ MybatisPlus 模板测试{'成功' if success else '失败'}")
        return success
        
    except Exception as e:
        logger.error(f"❌ MybatisPlus 模板测试失败: {e}")
        logger.exception("完整错误信息:")
        return False


async def test_mybatis_plus_mixed_template_generation():
    """测试 MybatisPlus-Mixed 模板分类的代码生成"""
    logger.info("🎯 测试 MybatisPlus-Mixed 模板分类")
    
    try:
        # Import required modules
        from dbjavagenix.core.models import DatabaseConfig, DatabaseType
        from dbjavagenix.database.connection_manager import ConnectionManager
        from dbjavagenix.database.codegen_tools import CodegenAnalyzer, CodegenGenerator
        
        # Setup connection
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
        
        # Get test table
        result = manager.execute_query(connection_id, f"SHOW TABLES FROM `{TEST_DATABASE_CONFIG['database']}` LIMIT 1")
        table_key = list(result[0].keys())[0]
        test_table = result[0][table_key]
        logger.info(f"📋 测试表: {test_table}")
        
        # Initialize tools
        analyzer = CodegenAnalyzer(manager)
        generator = CodegenGenerator()
        
        # Analyze table
        analysis_result = await analyzer.analyze_table_for_codegen(connection_id, test_table)
        logger.info(f"✅ 表分析完成: {analysis_result['table_name']}")
        
        # Generate MybatisPlus-Mixed template code
        generation_config = {
            "author": "MixedTestUser",
            "package_name": "com.test.mixed",
            "include_swagger": True,
            "include_lombok": True,
            "include_mapstruct": True,   # Mixed mode can use MapStruct
            "include_dto_vo": True
        }
        
        generation_result = await generator.generate_code(
            analysis_result,
            "MybatisPlus-Mixed",
            generation_config
        )
        
        # Validate MybatisPlus-Mixed template characteristics
        assert generation_result['template_category'] == "MybatisPlus-Mixed"
        generated_code = generation_result["generated_code"]
        
        # Expected files for MybatisPlus-Mixed (combines MybatisPlus + XML for complex queries)
        expected_files = [
            "entity.mustache",      # Entity class (extends Model)
            "dao.mustache",         # DAO interface (extends BaseMapper + custom methods)
            "service.mustache",     # Service interface (extends IService + batch operations)
            "serviceImpl.mustache", # Service implementation (extends ServiceImpl + batch impl)
            "controller.mustache",  # REST Controller (extends ApiController + batch APIs)
            "mapper.mustache",      # MyBatis XML mapper (for batch operations)
        ]
        
        logger.info("📁 MybatisPlus-Mixed 模板文件验证:")
        for file_name in expected_files:
            if file_name in generated_code:
                file_info = generated_code[file_name]
                if "error" not in file_info:
                    logger.info(f"   ✅ {file_name}: 生成成功")
                    # Check for Mixed mode specific content
                    if "code" in file_info:
                        code_content = file_info["code"]
                        if "BaseMapper" in code_content and file_name == "dao.mustache":
                            logger.info(f"      ✅ {file_name}: 包含 BaseMapper 继承")
                        if "batch" in code_content.lower() and file_name == "dao.mustache":
                            logger.info(f"      ✅ {file_name}: 包含批量操作方法")
                        if file_name == "mapper.mustache" and "insertBatch" in code_content:
                            logger.info(f"      ✅ {file_name}: 包含批量操作 SQL")
                else:
                    logger.error(f"   ❌ {file_name}: {file_info['error']}")
            else:
                logger.error(f"   ❌ 缺少文件: {file_name}")
        
        # Check additional files (should include all for Mixed mode)
        additional_files = ["dto.mustache", "vo.mustache", "mapstruct_mapper.mustache"]
        logger.info("📁 MybatisPlus-Mixed 附加文件验证:")
        for file_name in additional_files:
            if file_name in generated_code:
                logger.info(f"   ✅ {file_name}: 生成成功")
            else:
                logger.info(f"   ℹ️ {file_name}: 未生成")
        
        # Validate statistics
        stats = generation_result["generation_statistics"]
        logger.info("📊 MybatisPlus-Mixed 生成统计:")
        logger.info(f"   总文件: {stats['total_files']}")
        logger.info(f"   成功: {stats['success_files']}")
        logger.info(f"   失败: {stats['error_files']}")
        
        # Clean up
        manager.close_connection(connection_id)
        
        # Success if all main files generated including XML mapper
        main_files_success = all(f in generated_code for f in expected_files)
        has_xml_mapper = "mapper.mustache" in generated_code
        
        success = main_files_success and has_xml_mapper
        logger.info(f"✅ MybatisPlus-Mixed 模板测试{'成功' if success else '失败'}")
        return success
        
    except Exception as e:
        logger.error(f"❌ MybatisPlus-Mixed 模板测试失败: {e}")
        logger.exception("完整错误信息:")
        return False


async def test_template_comparison():
    """测试三种模板分类的对比分析"""
    logger.info("🔍 测试三种模板分类对比")
    
    try:
        # Import required modules
        from dbjavagenix.core.models import DatabaseConfig, DatabaseType
        from dbjavagenix.database.connection_manager import ConnectionManager
        from dbjavagenix.database.codegen_tools import CodegenAnalyzer, CodegenGenerator
        
        # Setup connection
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
        
        # Get test table
        result = manager.execute_query(connection_id, f"SHOW TABLES FROM `{TEST_DATABASE_CONFIG['database']}` LIMIT 1")
        table_key = list(result[0].keys())[0]
        test_table = result[0][table_key]
        
        # Initialize tools
        analyzer = CodegenAnalyzer(manager)
        generator = CodegenGenerator()
        
        # Analyze table once
        analysis_result = await analyzer.analyze_table_for_codegen(connection_id, test_table)
        
        # Generate with all three templates
        templates = ["Default", "MybatisPlus", "MybatisPlus-Mixed"]
        results = {}
        
        for template in templates:
            generation_config = {
                "author": f"{template}User",
                "package_name": f"com.test.{template.lower()}",
                "include_swagger": True,
                "include_lombok": True,
                "include_mapstruct": True,
                "include_dto_vo": True
            }
            
            result = await generator.generate_code(
                analysis_result,
                template,
                generation_config
            )
            results[template] = result
        
        # Compare results
        logger.info("📊 三种模板分类对比:")
        
        for template, result in results.items():
            stats = result["generation_statistics"]
            generated_code = result["generated_code"]
            
            logger.info(f"\n🎯 {template} 模板:")
            logger.info(f"   总文件: {stats['total_files']}")
            logger.info(f"   成功文件: {stats['success_files']}")
            logger.info(f"   文件列表: {', '.join(generated_code.keys())}")
            
            # Check template-specific characteristics
            if template == "Default":
                has_xml = "mapper.mustache" in generated_code
                logger.info(f"   XML映射: {'是' if has_xml else '否'}")
            elif template == "MybatisPlus":
                has_xml = "mapper.mustache" in generated_code
                logger.info(f"   XML映射: {'否(纯注解)' if not has_xml else '是(异常)'}")
            elif template == "MybatisPlus-Mixed":
                has_xml = "mapper.mustache" in generated_code
                logger.info(f"   XML映射: {'是(混合模式)' if has_xml else '否(异常)'}")
        
        # Summary comparison
        logger.info("\n📈 模板对比总结:")
        logger.info("   Default: 传统MyBatis，完整XML映射")
        logger.info("   MybatisPlus: 纯注解模式，无XML")
        logger.info("   MybatisPlus-Mixed: 混合模式，注解+XML")
        
        # Clean up
        manager.close_connection(connection_id)
        
        # Success if all templates generated successfully
        all_success = all(
            result["generation_statistics"]["success_files"] > 0 
            for result in results.values()
        )
        
        logger.info(f"✅ 模板对比测试{'成功' if all_success else '失败'}")
        return all_success
        
    except Exception as e:
        logger.error(f"❌ 模板对比测试失败: {e}")
        logger.exception("完整错误信息:")
        return False


async def main():
    """主测试运行器"""
    logger.info("=" * 80)
    logger.info("🎨 DBJavaGenix 三种模板分类测试")
    logger.info("=" * 80)
    
    # Test each template category
    test1_success = await test_default_template_generation()
    test2_success = await test_mybatis_plus_template_generation()
    test3_success = await test_mybatis_plus_mixed_template_generation()
    test4_success = await test_template_comparison()
    
    logger.info("\n" + "=" * 80)
    
    if all([test1_success, test2_success, test3_success, test4_success]):
        logger.info("✅ 总体结果: 所有模板分类测试通过!")
        logger.info("   ✅ Default 模板: 通过")
        logger.info("   ✅ MybatisPlus 模板: 通过")
        logger.info("   ✅ MybatisPlus-Mixed 模板: 通过")
        logger.info("   ✅ 模板对比: 通过")
    else:
        logger.error("❌ 总体结果: 部分测试失败")
        logger.info(f"   {'✅' if test1_success else '❌'} Default 模板: {'通过' if test1_success else '失败'}")
        logger.info(f"   {'✅' if test2_success else '❌'} MybatisPlus 模板: {'通过' if test2_success else '失败'}")
        logger.info(f"   {'✅' if test3_success else '❌'} MybatisPlus-Mixed 模板: {'通过' if test3_success else '失败'}")
        logger.info(f"   {'✅' if test4_success else '❌'} 模板对比: {'通过' if test4_success else '失败'}")
    
    logger.info("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())