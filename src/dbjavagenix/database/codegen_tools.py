"""
代码生成集成工具
将数据库分析结果与模板系统集成，提供 MCP 工具接口
"""

import json
from typing import Dict, List, Any, Optional
from ..database.connection_manager import ConnectionManager
from ..generator.java_generator import JavaCodeGenerator
from ..generator.template_context import TemplateContextBuilder
from ..core.models import TableInfo, ColumnInfo, GenerationConfig


class CodegenAnalyzer:
    """代码生成分析器 - 将数据库表结构转换为代码生成所需的格式"""
    
    def __init__(self, connection_manager: ConnectionManager):
        self.connection_manager = connection_manager
    
    async def analyze_table_for_codegen(self, connection_id: str, table_name: str,
                                       all_table_names: Optional[List[str]] = None,
                                       template_category: str = "Default",
                                       project_root: Optional[str] = None) -> Dict[str, Any]:
        """分析单个表的结构，返回代码生成所需的完整信息"""
        
        # 获取表基本信息
        table_info = await self._get_table_info(connection_id, table_name)
        
        # 获取列信息
        columns = await self._get_columns_info(connection_id, table_name)
        
        # 获取主键信息
        primary_keys = await self._get_primary_keys(connection_id, table_name)
        
        # 获取外键信息
        foreign_keys = await self._get_foreign_keys(connection_id, table_name)
        
        # 获取索引信息
        indexes = await self._get_indexes(connection_id, table_name)
        
        # 获取数据库名称
        connection = self.connection_manager.get_connection(connection_id)
        database_name = connection.db.decode('utf-8') if hasattr(connection, 'db') and connection.db else "unknown"
        
        # 构建 TableInfo 对象
        table_obj = self._build_table_info(table_info, columns, primary_keys, foreign_keys, indexes, database_name)
        
        # 构建代码生成上下文
        context_builder = TemplateContextBuilder(author="ZXP", package_name="com.example")
        context = context_builder.build_context(
            table_obj,
            template_category=template_category,
            all_table_names=all_table_names,
            project_root=project_root
        )
        
        return {
            "table_name": table_name,
            "table_info": {
                "name": table_obj.name,
                "comment": table_obj.comment,
                "columns": [self._column_to_dict(col) for col in table_obj.columns]
            },
            "template_context": context,
            "java_types": self._extract_java_types(table_obj.columns),
            "imports_needed": self._calculate_imports_needed(table_obj.columns),
            "relationships": {
                "primary_keys": primary_keys,
                "foreign_keys": foreign_keys,
                "indexes": indexes
            }
        }
    
    async def analyze_database_for_codegen(self, connection_id: str, table_filter: Optional[List[str]] = None) -> Dict[str, Any]:
        """分析整个数据库，返回所有表的代码生成信息"""
        
        # 获取所有表
        connection = self.connection_manager.get_connection(connection_id)
        cursor = connection.cursor()
        
        try:
            cursor.execute("SHOW TABLES")
            all_tables = [row[0] for row in cursor.fetchall()]
            
            # 应用表过滤器
            if table_filter:
                tables_to_analyze = [t for t in all_tables if t in table_filter]
            else:
                tables_to_analyze = all_tables
            
            # 分析每个表
            analysis_results = {}
            for table_name in tables_to_analyze:
                try:
                    table_analysis = await self.analyze_table_for_codegen(connection_id, table_name)
                    analysis_results[table_name] = table_analysis
                except Exception as e:
                    analysis_results[table_name] = {"error": str(e)}
            
            return {
                "database_info": {
                    "total_tables": len(all_tables),
                    "analyzed_tables": len(tables_to_analyze),
                    "success_count": len([r for r in analysis_results.values() if "error" not in r]),
                    "error_count": len([r for r in analysis_results.values() if "error" in r])
                },
                "tables": analysis_results
            }
            
        finally:
            cursor.close()
    
    async def _get_table_info(self, connection_id: str, table_name: str) -> Dict[str, Any]:
        """获取表基本信息"""
        connection = self.connection_manager.get_connection(connection_id)
        cursor = connection.cursor()
        
        try:
            query = """
            SELECT TABLE_NAME, TABLE_COMMENT, ENGINE, TABLE_COLLATION
            FROM information_schema.TABLES 
            WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s
            """
            cursor.execute(query, (table_name,))
            result = cursor.fetchone()
            
            if result:
                return {
                    "name": result[0],
                    "comment": result[1] or "",
                    "engine": result[2],
                    "collation": result[3]
                }
            else:
                raise ValueError(f"Table {table_name} not found")
                
        finally:
            cursor.close()
    
    async def _get_columns_info(self, connection_id: str, table_name: str) -> List[Dict[str, Any]]:
        """获取列信息"""
        connection = self.connection_manager.get_connection(connection_id)
        cursor = connection.cursor()
        
        try:
            query = """
            SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE, COLUMN_DEFAULT, 
                   COLUMN_COMMENT, COLUMN_TYPE, NUMERIC_PRECISION, NUMERIC_SCALE,
                   CHARACTER_MAXIMUM_LENGTH, COLUMN_KEY, EXTRA
            FROM information_schema.COLUMNS 
            WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s
            ORDER BY ORDINAL_POSITION
            """
            cursor.execute(query, (table_name,))
            columns = []
            
            for row in cursor.fetchall():
                columns.append({
                    "name": row[0],
                    "type": row[1],
                    "nullable": row[2] == "YES",
                    "default_value": row[3],
                    "comment": row[4] or "",
                    "column_type": row[5],
                    "precision": row[6],
                    "scale": row[7],
                    "max_length": row[8],
                    "column_key": row[9],
                    "extra": row[10],
                    "primary_key": row[9] == "PRI",
                    "auto_increment": "auto_increment" in (row[10] or "").lower()
                })
            
            return columns
            
        finally:
            cursor.close()
    
    async def _get_primary_keys(self, connection_id: str, table_name: str) -> List[str]:
        """获取主键信息"""
        connection = self.connection_manager.get_connection(connection_id)
        cursor = connection.cursor()
        
        try:
            query = """
            SELECT COLUMN_NAME
            FROM information_schema.KEY_COLUMN_USAGE 
            WHERE TABLE_SCHEMA = DATABASE() 
            AND TABLE_NAME = %s 
            AND CONSTRAINT_NAME = 'PRIMARY'
            ORDER BY ORDINAL_POSITION
            """
            cursor.execute(query, (table_name,))
            return [row[0] for row in cursor.fetchall()]
            
        finally:
            cursor.close()
    
    async def _get_foreign_keys(self, connection_id: str, table_name: str) -> List[Dict[str, Any]]:
        """获取外键信息"""
        connection = self.connection_manager.get_connection(connection_id)
        cursor = connection.cursor()
        
        try:
            query = """
            SELECT 
                CONSTRAINT_NAME,
                COLUMN_NAME,
                REFERENCED_TABLE_NAME,
                REFERENCED_COLUMN_NAME
            FROM information_schema.KEY_COLUMN_USAGE 
            WHERE TABLE_SCHEMA = DATABASE() 
            AND TABLE_NAME = %s 
            AND REFERENCED_TABLE_NAME IS NOT NULL
            ORDER BY CONSTRAINT_NAME, ORDINAL_POSITION
            """
            cursor.execute(query, (table_name,))
            
            foreign_keys = []
            for row in cursor.fetchall():
                foreign_keys.append({
                    "constraint_name": row[0],
                    "column_name": row[1],
                    "referenced_table": row[2],
                    "referenced_column": row[3]
                })
            
            return foreign_keys
            
        finally:
            cursor.close()
    
    async def _get_indexes(self, connection_id: str, table_name: str) -> List[Dict[str, Any]]:
        """获取索引信息"""
        connection = self.connection_manager.get_connection(connection_id)
        cursor = connection.cursor()
        
        try:
            query = f"SHOW INDEX FROM `{table_name}`"
            cursor.execute(query)
            
            indexes = []
            for row in cursor.fetchall():
                indexes.append({
                    "key_name": row[2],
                    "column_name": row[4],
                    "unique": not row[1],  # Non_unique = 0 means unique
                    "seq_in_index": row[3],
                    "index_type": row[10] if len(row) > 10 else "BTREE"
                })
            
            return indexes
            
        finally:
            cursor.close()
    
    def _build_table_info(self, table_info: Dict[str, Any], columns: List[Dict[str, Any]], 
                         primary_keys: List[str], foreign_keys: List[Dict[str, Any]], 
                         indexes: List[Dict[str, Any]], database_name: str = "unknown") -> TableInfo:
        """构建 TableInfo 对象"""
        
        column_objects = []
        for col in columns:
            column_obj = ColumnInfo(
                name=col["name"],
                data_type=col["type"],
                java_type=self._map_java_type(col["type"]),
                nullable=col["nullable"],
                primary_key=col["primary_key"],
                default_value=col["default_value"],
                comment=col["comment"]
            )
            # 添加额外属性
            column_obj.auto_increment = col["auto_increment"]
            column_obj.max_length = col["max_length"]
            column_objects.append(column_obj)
        
        table_obj = TableInfo(
            name=table_info["name"],
            schema=database_name,
            comment=table_info["comment"],
            columns=column_objects
        )
        
        return table_obj
    
    def _column_to_dict(self, column: ColumnInfo) -> Dict[str, Any]:
        """将 ColumnInfo 对象转换为字典"""
        return {
            "name": column.name,
            "type": column.data_type,
            "nullable": column.nullable,
            "primary_key": column.primary_key,
            "default_value": column.default_value,
            "comment": column.comment,
            "auto_increment": getattr(column, 'auto_increment', False),
            "max_length": getattr(column, 'max_length', None)
        }
    
    def _extract_java_types(self, columns: List[ColumnInfo]) -> List[str]:
        """提取所需的 Java 类型列表"""
        context_builder = TemplateContextBuilder()
        java_types = set()
        
        for column in columns:
            java_type = context_builder._map_java_type(column.data_type)
            java_types.add(java_type)
        
        return sorted(list(java_types))
    
    def _calculate_imports_needed(self, columns: List[ColumnInfo]) -> List[str]:
        """计算需要导入的类列表"""
        context_builder = TemplateContextBuilder()
        imports = set()
        
        for column in columns:
            java_type = context_builder._map_java_type(column.data_type)
            
            # 添加需要导入的类型
            if java_type == "BigDecimal":
                imports.add("java.math.BigDecimal")
            elif java_type == "LocalDate":
                imports.add("java.time.LocalDate")
            elif java_type == "LocalTime":
                imports.add("java.time.LocalTime")
            elif java_type == "LocalDateTime":
                imports.add("java.time.LocalDateTime")
        
        return sorted(list(imports))
    
    def _map_java_type(self, mysql_type: str) -> str:
        """将 MySQL 数据类型映射为 Java 类型"""
        from ..generator.template_context import TemplateContextBuilder
        context_builder = TemplateContextBuilder()
        return context_builder._map_java_type(mysql_type)


class CodegenGenerator:
    """代码生成器 - 根据分析结果生成 Java 代码"""
    
    def __init__(self):
        pass
    
    async def generate_code(self, analysis_result: Dict[str, Any], 
                          template_category: str = "MybatisPlus-Mixed",
                          generation_config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """根据分析结果生成代码"""
        
        # 构建生成配置
        config = GenerationConfig(
            output_dir=generation_config.get("output_dir", "/tmp/generated") if generation_config else "/tmp/generated",
            author=generation_config.get("author", "ZXP") if generation_config else "ZXP",
            package_name=generation_config.get("package_name", "com.example.generated") if generation_config else "com.example.generated"
        )
        
        # 创建 Java 代码生成器
        java_generator = JavaCodeGenerator(config)
        
        # 构建 TableInfo 对象
        table_info_dict = analysis_result["table_info"]
        columns = []
        for col_dict in table_info_dict["columns"]:
            column = ColumnInfo(
                name=col_dict["name"],
                data_type=col_dict["type"],
                java_type=col_dict.get("java_type", "String"),
                nullable=col_dict["nullable"],
                primary_key=col_dict["primary_key"],
                default_value=col_dict["default_value"],
                comment=col_dict["comment"]
            )
            columns.append(column)
        
        table_info = TableInfo(
            name=table_info_dict["name"],
            schema="test1",  # 使用默认schema
            comment=table_info_dict["comment"],
            columns=columns
        )
        
        # 生成代码到内存中（不写入文件）
        generated_code = {}
        
        # 获取模板文件列表
        from ..generator.template_context import TemplateConfigManager
        template_config = TemplateConfigManager()
        base_templates = template_config.get_template_files(template_category)
        template_files = list(base_templates)
        # 动态附加DTO/VO/MapStruct模板 & MyBatis-Plus配置
        tc = analysis_result.get("template_context", {})
        use_mapstruct = bool(tc.get("useMapStruct"))
        include_dto_vo = bool(tc.get("includeDtoVo") or tc.get("include_dto_vo"))
        extras: list[str] = []
        if include_dto_vo:
            extras.extend(["dto.mustache", "vo.mustache"])
        if use_mapstruct:
            extras.append("mapstruct_mapper.mustache")
        # 为 MyBatis-Plus 路线附加配置类（分页拦截器）
        if template_category in ("MybatisPlus", "MybatisPlus-Mixed"):
            extras.append("mybatis_plus_config.mustache")
        if extras:
            template_files.extend(extras)
        
        # 使用分析结果中的模板上下文，但更新配置相关字段
        context = analysis_result["template_context"].copy()
        
        # 重新设置包名和作者信息
        if generation_config:
            package_name = generation_config.get("package_name", context.get("package", "com.example"))
            author = generation_config.get("author", context.get("author", "ZXP"))
            
            # 获取前缀后缀
            package_suffix = context.get("packageSuffix", "")
            
            # 重新构建组件包名
            if package_suffix:
                controller_package = f"{package_name}.controller.{package_suffix}"
                service_package = f"{package_name}.service.{package_suffix}"
                entity_package = f"{package_name}.entity.{package_suffix}"
                dao_package = f"{package_name}.dao.{package_suffix}"
                # 修复serviceImpl包路径问题
                service_impl_package = f"{package_name}.service.impl.{package_suffix}"
            else:
                controller_package = f"{package_name}.controller"
                service_package = f"{package_name}.service"
                entity_package = f"{package_name}.entity"
                dao_package = f"{package_name}.dao"
                # 修复serviceImpl包路径问题
                service_impl_package = f"{package_name}.service.impl"
            
            # 更新上下文中的包相关信息
            context.update({
                "package": package_name,
                "packageName": package_name,
                "hasPackageName": bool(package_name),
                "basePackage": package_name,
                "controllerPackage": controller_package,
                "servicePackage": service_package,
                "entityPackage": entity_package,
                "daoPackage": dao_package,
                # 添加serviceImpl包路径
                "serviceImplPackage": service_impl_package,
                "author": author
            })
        
        # 更新上下文中的配置相关字段
        context.update({
            "templateCategory": template_category,
            "isDefault": template_category == "Default",
            "isMybatisPlus": template_category == "MybatisPlus", 
            "isMybatisPlusMixed": template_category == "MybatisPlus-Mixed",
        })
        
        # 为每个模板生成代码
        for template_file in template_files:
            try:
                # 附加模板从 common 目录加载
                effective_category = template_category if template_file in base_templates else "common"
                code = await self._render_template(template_file, context, effective_category)
                generated_code[template_file] = {
                    "filename": self._get_output_filename(template_file, context),
                    "code": code,
                    "template_file": template_file
                }
            except Exception as e:
                generated_code[template_file] = {
                    "error": str(e),
                    "template_file": template_file
                }
        
        return {
            "table_name": analysis_result["table_name"],
            "template_category": template_category,
            "generated_code": generated_code,
            "generation_statistics": {
                "total_files": len(template_files),
                "success_files": len([f for f in generated_code.values() if "error" not in f]),
                "error_files": len([f for f in generated_code.values() if "error" in f])
            }
        }
    
    async def _render_template(self, template_file: str, context: Dict[str, Any], 
                             category: str) -> str:
        """渲染模板文件"""
        from pathlib import Path
        from ..generator.mustache_engine import MustacheTemplateEngine
        
        # 确定模板路径
        template_base_path = Path(__file__).parent.parent / "templates" / "java"
        
        if category == "common":
            template_path = template_base_path / template_file
        else:
            template_path = template_base_path / category / template_file
        
        if not template_path.exists():
            raise FileNotFoundError(f"模板文件不存在: {template_path}")
        
        # 渲染模板
        engine = MustacheTemplateEngine()
        return engine.render_file(str(template_path), context)
    
    def _get_output_filename(self, template_file: str, context: Dict[str, Any]) -> str:
        """获取输出文件名"""
        from ..generator.template_context import TemplateConfigManager
        
        template_config = TemplateConfigManager()
        path_mapping = template_config.get_output_path_mapping()
        
        if template_file in path_mapping:
            relative_path = path_mapping[template_file]
            # 替换路径中的占位符
            file_path = relative_path.format(**context)
            
            # 添加包路径结构
            package_name = context.get("package", "com.example")
            if package_name:
                # 将包名转换为路径
                package_path = package_name.replace(".", "/")
                # 对于Java源文件，添加包路径
                if file_path.endswith(".java"):
                    # 提取文件名和相对目录
                    path_parts = file_path.split("/")
                    if len(path_parts) > 1:
                        # 移除表名路径，让所有表共享同一个包结构
                        relative_dir = "/".join(path_parts[:-1])
                        filename = path_parts[-1]
                        # 构建带包路径的完整路径，不包含表名子包
                        return f"{package_path}/{relative_dir}/{filename}"
                    else:
                        return f"{package_path}/{file_path}"
                else:
                    # 对于XML等资源文件，不添加包路径，但添加resources前缀
                    return f"resources/{file_path}"
            
            return file_path
        else:
            # 默认文件名
            return template_file.replace('.mustache', '.java')
