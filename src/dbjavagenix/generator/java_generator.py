"""
Java 代码生成器
整合 EasyCode 模板移植功能，支持三种模板分类
"""

import os
from pathlib import Path
from typing import Dict, List, Optional
import logging

from .mustache_engine import MustacheTemplateEngine
from .template_context import TemplateContextBuilder, TemplateConfigManager
from ..core.models import TableInfo, GenerationConfig


logger = logging.getLogger(__name__)


class JavaCodeGenerator:
    """Java 代码生成器"""
    
    def __init__(self, config: GenerationConfig):
        self.config = config
        self.template_engine = MustacheTemplateEngine()  # 无参数初始化
        self.context_builder = TemplateContextBuilder(
            author=config.author,
            package_name=config.package_name
        )
        self.template_config = TemplateConfigManager()
        
        # 模板路径
        self.template_base_path = Path(__file__).parent.parent / "templates" / "java"
        
    def generate_from_table(self, table_info: TableInfo, output_dir: str, 
                          template_category: str = "Default",
                          include_dto_vo: bool = True) -> Dict[str, str]:
        """
        根据表信息生成 Java 代码
        
        Args:
            table_info: 表信息
            output_dir: 输出目录
            template_category: 模板分类 (Default, MybatisPlus, MybatisPlus-Mixed)
            include_dto_vo: 是否包含 DTO/VO
            
        Returns:
            生成的文件路径字典
        """
        logger.info(f"开始生成表 {table_info.name} 的 Java 代码，模板分类: {template_category}")
        
        # 构建模板上下文
        context = self.context_builder.build_context(table_info, template_category)
        
        # 生成文件
        generated_files = {}
        
        # 1. 生成主要模板文件
        template_files = self.template_config.get_template_files(template_category)
        for template_file in template_files:
            try:
                file_path = self._generate_file(
                    template_file, context, output_dir, template_category
                )
                generated_files[template_file] = file_path
                logger.debug(f"生成文件: {file_path}")
            except Exception as e:
                logger.error(f"生成文件 {template_file} 失败: {e}")
                raise
        
        # 2. 生成 DTO/VO/Mapper（如果需要）
        if include_dto_vo:
            additional_templates = self.template_config.get_additional_templates()
            for template_file in additional_templates:
                try:
                    file_path = self._generate_file(
                        template_file, context, output_dir, "common"
                    )
                    generated_files[template_file] = file_path
                    logger.debug(f"生成附加文件: {file_path}")
                except Exception as e:
                    logger.error(f"生成附加文件 {template_file} 失败: {e}")
                    # 附加文件生成失败不影响主流程
                    continue
        
        logger.info(f"成功生成 {len(generated_files)} 个文件")
        return generated_files
    
    def generate_from_database(self, database_url: str, output_dir: str,
                             template_category: str = "Default",
                             table_filter: Optional[List[str]] = None,
                             include_dto_vo: bool = True) -> Dict[str, Dict[str, str]]:
        """
        从数据库生成 Java 代码
        
        Args:
            database_url: 数据库连接 URL
            output_dir: 输出目录
            template_category: 模板分类
            table_filter: 表名过滤器
            include_dto_vo: 是否包含 DTO/VO
            
        Returns:
            按表名分组的生成文件路径字典
        """
        # TODO: 实现数据库直接分析功能
        # 当前版本使用 CodegenAnalyzer 和 CodegenGenerator 来实现此功能
        raise NotImplementedError("请使用 CodegenAnalyzer 和 CodegenGenerator 进行数据库分析和代码生成")
    
    def _generate_file(self, template_file: str, context: Dict, 
                      output_dir: str, category: str) -> str:
        """
        生成单个文件
        
        Args:
            template_file: 模板文件名
            context: 模板上下文
            output_dir: 输出目录
            category: 模板分类
            
        Returns:
            生成的文件路径
        """
        # 确定模板路径
        if category == "common":
            template_path = self.template_base_path / template_file
        else:
            template_path = self.template_base_path / category / template_file
        
        if not template_path.exists():
            raise FileNotFoundError(f"模板文件不存在: {template_path}")
        
        # 生成代码
        code = self.template_engine.render_file(str(template_path), context)
        
        # 确定输出路径
        output_path = self._get_output_path(template_file, context, output_dir)
        
        # 确保输出目录存在
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # 写入文件
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(code)
        
        return output_path
    
    def _get_output_path(self, template_file: str, context: Dict, output_dir: str) -> str:
        """
        获取输出文件路径
        
        Args:
            template_file: 模板文件名
            context: 模板上下文
            output_dir: 输出目录
            
        Returns:
            输出文件路径
        """
        path_mapping = self.template_config.get_output_path_mapping()
        
        if template_file not in path_mapping:
            # 默认路径
            file_name = template_file.replace('.mustache', '.java')
            relative_path = f"generated/{file_name}"
        else:
            relative_path = path_mapping[template_file]
        
        # 替换路径中的占位符
        relative_path = relative_path.format(**context)
        
        return os.path.join(output_dir, relative_path)
    
    def get_supported_categories(self) -> List[str]:
        """获取支持的模板分类"""
        return ["Default", "MybatisPlus", "MybatisPlus-Mixed"]
    
    def validate_template_category(self, category: str) -> bool:
        """验证模板分类是否支持"""
        return category in self.get_supported_categories()
    
    def list_template_files(self, category: str) -> List[str]:
        """列出指定分类的模板文件"""
        if not self.validate_template_category(category):
            raise ValueError(f"不支持的模板分类: {category}")
        
        return self.template_config.get_template_files(category)


class BatchCodeGenerator:
    """批量代码生成器"""
    
    def __init__(self, config: GenerationConfig):
        self.config = config
        self.java_generator = JavaCodeGenerator(config)
    
    def generate_project_structure(self, database_url: str, output_dir: str,
                                 template_category: str = "MybatisPlus-Mixed",
                                 project_name: str = "generated-project") -> Dict[str, any]:
        """
        生成完整的项目结构
        
        Args:
            database_url: 数据库连接 URL
            output_dir: 输出目录
            template_category: 模板分类
            project_name: 项目名称
            
        Returns:
            生成结果统计
        """
        logger.info(f"开始生成完整项目结构: {project_name}")
        
        # 创建项目目录结构
        project_dir = os.path.join(output_dir, project_name)
        src_dir = os.path.join(project_dir, "src/main/java")
        resources_dir = os.path.join(project_dir, "src/main/resources")
        
        os.makedirs(src_dir, exist_ok=True)
        os.makedirs(resources_dir, exist_ok=True)
        
        # 生成 Java 代码
        generated_files = self.java_generator.generate_from_database(
            database_url, src_dir, template_category, include_dto_vo=True
        )
        
        # 生成项目配置文件
        self._generate_project_config(project_dir, project_name, template_category)
        
        # 统计生成结果
        total_files = sum(len(files) for files in generated_files.values())
        
        result = {
            "project_name": project_name,
            "project_dir": project_dir,
            "template_category": template_category,
            "tables_processed": len(generated_files),
            "total_files": total_files,
            "generated_files": generated_files
        }
        
        logger.info(f"项目生成完成: {total_files} 个文件，{len(generated_files)} 个表")
        return result
    
    def _generate_project_config(self, project_dir: str, project_name: str, 
                               template_category: str):
        """生成项目配置文件"""
        # 这里可以生成 pom.xml, application.yml 等配置文件
        # 暂时跳过，专注于 Java 代码生成
        pass


# 便捷函数
def quick_generate(database_url: str, output_dir: str, 
                  template_category: str = "MybatisPlus-Mixed",
                  table_filter: Optional[List[str]] = None) -> Dict[str, Dict[str, str]]:
    """
    快速生成代码的便捷函数
    
    Args:
        database_url: 数据库连接 URL
        output_dir: 输出目录
        template_category: 模板分类
        table_filter: 表名过滤器
        
    Returns:
        生成的文件路径字典
    """
    config = GenerationConfig(
        author="ZXP",
        package_name="com.example.generated"
    )
    
    generator = JavaCodeGenerator(config)
    return generator.generate_from_database(
        database_url, output_dir, template_category, table_filter
    )