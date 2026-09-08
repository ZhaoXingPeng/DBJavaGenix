"""
代码生成集成工具
将数据库分析结果与模板系统集成，提供 MCP 工具接口
"""

from typing import Dict, List, Any, Optional
from ..database.connection_manager import ConnectionManager
from ..generator.template_context import TemplateContextBuilder
from ..core.models import TableInfo, ColumnInfo, DatabaseType
from .introspection import DatabaseIntrospector


class CodegenAnalyzer:
    """代码生成分析器 - 将数据库表结构转换为代码生成所需的格式"""

    def __init__(self, connection_manager: ConnectionManager):
        self.connection_manager = connection_manager
        self.introspector = DatabaseIntrospector(connection_manager)

    async def analyze_table_for_codegen(
        self,
        connection_id: str,
        table_name: str,
        all_table_names: Optional[List[str]] = None,
        template_category: str = "Default",
        project_root: Optional[str] = None,
        schema: Optional[str] = None,
    ) -> Dict[str, Any]:
        """分析单个表的结构，返回代码生成所需的完整信息"""

        # 获取表基本信息
        config = self.introspector.get_config(connection_id)
        table_info = self.introspector.get_table(connection_id, table_name, schema)

        # 获取列信息
        columns = self.introspector.get_columns(connection_id, table_name, schema)

        # 获取主键信息
        primary_keys = self.introspector.get_primary_keys(connection_id, table_name, schema)
        primary_key_set = set(primary_keys)
        for column in columns:
            column["primary_key"] = (
                column.get("primary_key", False) or column["name"] in primary_key_set
            )

        # 获取外键信息
        foreign_keys = self.introspector.get_foreign_keys(connection_id, table_name, schema)

        # 获取索引信息
        indexes = self.introspector.get_indexes(connection_id, table_name, schema)

        # 获取数据库名称
        database_name = table_info.get("schema") or config.database or "unknown"

        # 构建 TableInfo 对象
        table_obj = self._build_table_info(
            table_info,
            columns,
            primary_keys,
            foreign_keys,
            indexes,
            database_name,
            config.type,
        )

        # 构建代码生成上下文
        context_builder = TemplateContextBuilder(
            author="ZXP", package_name="com.example", database_type=config.type
        )
        context = context_builder.build_context(
            table_obj,
            template_category=template_category,
            all_table_names=all_table_names,
            project_root=project_root,
        )

        return {
            "table_name": table_name,
            "table_info": {
                "name": table_obj.name,
                "comment": table_obj.comment,
                "schema": table_obj.schema,
                "columns": [self._column_to_dict(col) for col in table_obj.columns],
            },
            "template_context": context,
            "java_types": self._extract_java_types(table_obj.columns, config.type),
            "imports_needed": self._calculate_imports_needed(table_obj.columns, config.type),
            "relationships": {
                "primary_keys": primary_keys,
                "foreign_keys": foreign_keys,
                "indexes": indexes,
            },
        }

    async def analyze_database_for_codegen(
        self, connection_id: str, table_filter: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """分析整个数据库，返回所有表的代码生成信息"""

        # PostgreSQL table names are scoped by schema. Keep that identity through
        # batch analysis so equally named tables cannot become ambiguous or overwrite
        # one another in the returned mapping.
        all_table_references = self.introspector.list_table_references(connection_id)
        # Prefix analysis operates on bare table names.  Deduplicate names so
        # PostgreSQL tables with the same name in different schemas do not
        # inflate a prefix group's table count.
        all_table_names = sorted(
            {str(reference["name"]) for reference in all_table_references if reference.get("name")}
        )

        def table_key(reference: Dict[str, str | None]) -> str:
            return (
                f"{reference['schema']}.{reference['name']}"
                if reference["schema"]
                else reference["name"]
            )

        tables_to_analyze = [
            reference
            for reference in all_table_references
            if not table_filter
            or reference["name"] in table_filter
            or table_key(reference) in table_filter
        ]
        analysis_results = {}
        for reference in tables_to_analyze:
            name = reference["name"]
            schema = reference["schema"]
            result_key = table_key(reference)
            try:
                analysis_results[result_key] = await self.analyze_table_for_codegen(
                    connection_id,
                    name,
                    all_table_names=all_table_names,
                    schema=schema,
                )
            except Exception as exc:
                analysis_results[result_key] = {"error": str(exc)}

        return {
            "database_info": {
                "total_tables": len(all_table_references),
                "analyzed_tables": len(tables_to_analyze),
                "success_count": sum("error" not in item for item in analysis_results.values()),
                "error_count": sum("error" in item for item in analysis_results.values()),
            },
            "tables": analysis_results,
        }

    def _build_table_info(
        self,
        table_info: Dict[str, Any],
        columns: List[Dict[str, Any]],
        primary_keys: List[str],
        foreign_keys: List[Dict[str, Any]],
        indexes: List[Dict[str, Any]],
        database_name: str = "unknown",
        database_type: DatabaseType = DatabaseType.MYSQL,
    ) -> TableInfo:
        """构建 TableInfo 对象"""

        column_objects = []
        for col in columns:
            column_obj = ColumnInfo(
                name=col["name"],
                data_type=col["type"],
                java_type=self._map_java_type(col["type"], database_type),
                nullable=col["nullable"],
                primary_key=col["primary_key"],
                default_value=col["default_value"],
                comment=col["comment"],
                auto_increment=col["auto_increment"],
                max_length=col["max_length"],
                precision=col.get("precision"),
                scale=col.get("scale"),
            )
            column_objects.append(column_obj)

        table_obj = TableInfo(
            name=table_info["name"],
            schema=database_name,
            comment=table_info["comment"],
            columns=column_objects,
            primary_keys=list(primary_keys),
            foreign_keys={
                item["column_name"]: (f"{item['referenced_table']}.{item['referenced_column']}")
                for item in foreign_keys
                if item.get("column_name")
            },
            indexes=[item["key_name"] for item in indexes if item.get("key_name")],
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
            "auto_increment": column.auto_increment,
            "max_length": column.max_length,
            "precision": column.precision,
            "scale": column.scale,
            "java_type": column.java_type,
        }

    def _extract_java_types(
        self, columns: List[ColumnInfo], database_type: DatabaseType = DatabaseType.MYSQL
    ) -> List[str]:
        """提取所需的 Java 类型列表"""
        context_builder = TemplateContextBuilder(database_type=database_type)
        java_types = set()

        for column in columns:
            java_type = context_builder._map_java_type(column.data_type)
            java_types.add(java_type)

        return sorted(list(java_types))

    def _calculate_imports_needed(
        self, columns: List[ColumnInfo], database_type: DatabaseType = DatabaseType.MYSQL
    ) -> List[str]:
        """计算需要导入的类列表"""
        context_builder = TemplateContextBuilder(database_type=database_type)
        # Use the same dialect-aware import table as generated template context.
        return context_builder._build_imports(columns, template_category="Default")

    def _map_java_type(
        self, database_type_name: str, database_type: DatabaseType = DatabaseType.MYSQL
    ) -> str:
        """将 MySQL 数据类型映射为 Java 类型"""
        from ..generator.template_context import TemplateContextBuilder

        context_builder = TemplateContextBuilder(database_type=database_type)
        return context_builder._map_java_type(database_type_name)


class CodegenGenerator:
    """代码生成器 - 根据分析结果生成 Java 代码"""

    def __init__(self):
        pass

    async def generate_code(
        self,
        analysis_result: Dict[str, Any],
        template_category: str = "MybatisPlus-Mixed",
        generation_config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """根据分析结果生成代码"""

        from ..generator.template_context import TemplateConfigManager

        supported_categories = TemplateConfigManager.get_supported_categories()
        if template_category not in supported_categories:
            supported = ", ".join(supported_categories)
            raise ValueError(f"不支持的模板分类: {template_category!r}；支持分类: {supported}")

        # 生成代码到内存中（不写入文件）
        generated_code = {}

        # 获取模板文件列表
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
            package_name = generation_config.get(
                "package_name", context.get("package", "com.example")
            )
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
            context.update(
                {
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
                    "author": author,
                }
            )

        # 更新上下文中的配置相关字段
        context.update(
            {
                "templateCategory": template_category,
                "isDefault": template_category == "Default",
                "isMybatisPlus": template_category == "MybatisPlus",
                "isMybatisPlusMixed": template_category == "MybatisPlus-Mixed",
            }
        )

        # 为每个模板生成代码
        for template_file in template_files:
            try:
                # 附加模板从 common 目录加载
                effective_category = (
                    template_category if template_file in base_templates else "common"
                )
                code = await self._render_template(template_file, context, effective_category)
                generated_code[template_file] = {
                    "filename": self._get_output_filename(template_file, context),
                    "code": code,
                    "template_file": template_file,
                }
            except Exception as e:
                generated_code[template_file] = {"error": str(e), "template_file": template_file}

        return {
            "table_name": analysis_result["table_name"],
            "template_category": template_category,
            "generated_code": generated_code,
            "generation_statistics": {
                "total_files": len(template_files),
                "success_files": len([f for f in generated_code.values() if "error" not in f]),
                "error_files": len([f for f in generated_code.values() if "error" in f]),
            },
        }

    async def _render_template(
        self, template_file: str, context: Dict[str, Any], category: str
    ) -> str:
        """渲染模板文件"""
        from pathlib import Path
        from ..generator.mustache_engine import MustacheTemplateEngine

        # 确定模板路径
        template_base_path = Path(__file__).parent.parent / "templates" / "java"

        if category == "common":
            template_path = template_base_path / "common" / template_file
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
            return template_file.replace(".mustache", ".java")
