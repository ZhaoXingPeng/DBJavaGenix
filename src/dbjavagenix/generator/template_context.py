"""
模板上下文构建器
用于构建 Mustache 模板渲染所需的上下文数据
"""

from typing import Dict, List, Any, Optional
from datetime import datetime
import re
from ..core.models import TableInfo, ColumnInfo, DatabaseType


class TemplateContextBuilder:
    """模板上下文构建器"""
    
    def __init__(self, author: str = "ZXP", package_name: str = "com.example"):
        self.author = author
        self.package_name = package_name
        self.date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    def build_context(self, table_info: TableInfo, template_category: str = "Default",
                     all_table_names: Optional[List[str]] = None, project_root: Optional[str] = None) -> Dict[str, Any]:
        """
        构建模板上下文
        
        Args:
            table_info: 表信息
            template_category: 模板分类 (Default, MybatisPlus, MybatisPlus-Mixed)
            all_table_names: 所有表名列表(用于前缀分析)
            project_root: 项目根目录，用于检测技术栈
            
        Returns:
            模板上下文字典
        """
        # 基础上下文 - 修复变量名映射
        class_name = self._to_pascal_case(table_info.name)
        entity_name_lower = self._to_camel_case(table_info.name)
        primary_key_info = self._build_primary_key_context(table_info.columns)
        columns_context = self._build_columns_context(table_info.columns)
        
        # 前缀分析 - 新增功能
        package_suffix = ""
        if all_table_names:
            from ..utils.table_prefix_analyzer import TablePrefixAnalyzer
            analyzer = TablePrefixAnalyzer()
            package_suffix = analyzer.get_table_package_suffix(table_info.name, all_table_names)
        
        # 构建包名 (支持前缀子包)
        base_package = self.package_name
        if package_suffix:
            # 为不同的组件类型构建包名
            controller_package = f"{base_package}.controller.{package_suffix}"
            service_package = f"{base_package}.service.{package_suffix}"
            entity_package = f"{base_package}.entity.{package_suffix}"
            dao_package = f"{base_package}.dao.{package_suffix}"
            dto_package = f"{base_package}.dto.{package_suffix}"
            vo_package = f"{base_package}.vo.{package_suffix}"
        else:
            # 无前缀时使用基础包
            controller_package = f"{base_package}.controller"
            service_package = f"{base_package}.service"
            entity_package = f"{base_package}.entity"
            dao_package = f"{base_package}.dao"
            dto_package = f"{base_package}.dto"
            vo_package = f"{base_package}.vo"
        
        # 修复serviceImpl包路径问题
        if package_suffix:
            service_impl_package = f"{base_package}.service.impl.{package_suffix}"
        else:
            service_impl_package = f"{base_package}.service.impl"
        
        # 检测技术栈信息
        tech_stack = self._detect_technology_stack(project_root, template_category)
        
        context = {
            # 类和包相关
            "className": class_name,
            "name": class_name,  # 添加 name 别名
            "entityName": class_name,  # 添加 entityName 别名
            "lowerCaseName": entity_name_lower,  # 添加小写变量名
            "entityNameLowerCase": entity_name_lower,  # 别名
            "package": base_package,  # 基础包名，用于向下兼容
            "packageName": base_package,  # 基础包名，用于向下兼容
            "hasPackageName": bool(base_package),
            "packageSuffix": package_suffix if package_suffix else "",  # 前缀子包名，空时为空字符串
            "basePackage": base_package,  # 基础包名
            
            # 不同组件的完整包名
            "controllerPackage": controller_package,
            "servicePackage": service_package, 
            "entityPackage": entity_package,
            "daoPackage": dao_package,
            # 添加serviceImpl包路径
            "serviceImplPackage": service_impl_package,
            # 添加dto和vo包路径
            "dtoPackage": dto_package,
            "voPackage": vo_package,
            
            # 表相关
            "tableName": table_info.name,
            "comment": table_info.comment or table_info.name,
            "entityNameLowerCase": entity_name_lower,
            
            # 作者和日期
            "author": self.author,
            "date": self.date,
            "serialVersionUID": "1",
            
            # 列相关
            "columns": columns_context,
            "primaryKey": primary_key_info,
            "nonPrimaryColumns": self._build_non_primary_columns_context(table_info.columns),
            "otherColumns": self._build_non_primary_columns_context(table_info.columns),  # 别名
            
            # 主键相关 - 添加缺失的主键字段
            "primaryKeyName": primary_key_info["name"] if primary_key_info else "id",
            "primaryKeyType": primary_key_info["javaType"] if primary_key_info else "Long",
            "primaryKeyColumn": primary_key_info["dbName"] if primary_key_info else "id",  # 数据库列名
            "capitalizedPrimaryKeyName": primary_key_info["javaName"].capitalize() if primary_key_info else "Id",
            
            # 导入相关
            "imports": self._build_imports(table_info.columns, template_category),
            
            # 特性标志
            "hasDateField": self._has_date_field(table_info.columns),
            "hasBigDecimalField": self._has_big_decimal_field(table_info.columns),
            "useLombok": template_category in ["Default", "MybatisPlus", "MybatisPlus-Mixed"],
            "useSwagger": True,
            "pagination": True,  # 启用分页
            "generateDto": False,  # 默认不生成DTO
            "generateVo": False,   # 默认不生成VO
            "hasDto": False,
            "hasVo": False,
            "hasMapStruct": True,
            
            # 技术栈相关标志
            "hasJavax": tech_stack.has_javax,
            "hasJakarta": tech_stack.has_jakarta,
            "hasSpringData": tech_stack.has_spring_data,
            "hasMyBatis": tech_stack.has_mybatis,
            "hasSwagger2": tech_stack.has_swagger2,
            "hasSpringDoc": tech_stack.has_springdoc,
            "useModernStack": tech_stack.is_modern_stack,
            
            # 模板分类相关
            "templateCategory": template_category,
            "isDefault": template_category == "Default",
            "isMybatisPlus": template_category == "MybatisPlus",
            "isMybatisPlusMixed": template_category == "MybatisPlus-Mixed",
            
            # 自定义映射规则
            "customMappings": self._build_custom_mappings(table_info.columns),
        }
        
        return context
    
    def _detect_technology_stack(self, project_root: Optional[str], template_category: str) -> Any:
        """
        检测项目使用的技术栈类型
        
        Args:
            project_root: 项目根目录
            template_category: 模板分类
            
        Returns:
            TechnologyStack对象
        """
        # 如果没有提供项目根目录，使用默认的现代化技术栈
        if not project_root:
            from ..utils.pom_analyzer import TechnologyStack
            tech_stack = TechnologyStack()
            tech_stack.has_jakarta = True
            tech_stack.has_mybatis = template_category in ["Default", "MybatisPlus", "MybatisPlus-Mixed"]
            tech_stack.has_springdoc = True
            tech_stack.is_modern_stack = True
            return tech_stack
        
        # 使用PomAnalyzer检测技术栈
        try:
            from ..utils.pom_analyzer import PomAnalyzer
            analyzer = PomAnalyzer()
            analysis_result = analyzer.analyze_project_dependencies(
                project_root=project_root,
                template_category=template_category,
                database_type="mysql"  # 默认数据库类型
            )
            return analysis_result.get("technology_stack", TechnologyStack())
        except Exception as e:
            # 如果检测失败，使用默认的现代化技术栈
            from ..utils.pom_analyzer import TechnologyStack
            tech_stack = TechnologyStack()
            tech_stack.has_jakarta = True
            tech_stack.has_mybatis = template_category in ["Default", "MybatisPlus", "MybatisPlus-Mixed"]
            tech_stack.has_springdoc = True
            tech_stack.is_modern_stack = True
            return tech_stack
    
    def _build_columns_context(self, columns: List[ColumnInfo]) -> List[Dict[str, Any]]:
        """构建列上下文"""
        column_contexts = []
        
        for i, column in enumerate(columns):
            java_name = self._to_camel_case(column.name)
            java_type = self._map_java_type(column.data_type)
            column_context = {
                # 基础字段信息
                "name": column.name,  # 数据库字段名
                "javaName": java_name,  # Java字段名
                "capitalizedJavaName": java_name.capitalize(),  # 首字母大写的Java字段名
                "dbName": column.name,
                "javaType": java_type,
                "jdbcType": self._map_jdbc_type(column.data_type),
                "comment": column.comment or column.name,
                
                # 字段属性
                "isPrimaryKey": column.primary_key,
                "primaryKey": column.primary_key,  # 兼容两种写法
                "isNullable": column.nullable,
                "nullable": column.nullable,
                "isAutoIncrement": getattr(column, 'auto_increment', False),
                "autoIncrement": getattr(column, 'auto_increment', False),
                "defaultValue": column.default_value,
                "maxLength": getattr(column, 'max_length', None),
                
                # 验证相关
                "required": not column.nullable and not column.primary_key,
                "isString": self._is_string_type(column.data_type),
                "stringType": self._is_string_type(column.data_type),  # 别名
                "isStringType": self._is_string_type(column.data_type),  # 另一个别名
                
                # 循环标志
                "hasNext": i < len(columns) - 1,
                "isFirst": i == 0,
                "isLast": i == len(columns) - 1,
                "last": i == len(columns) - 1,  # 添加 last 别名
            }
            column_contexts.append(column_context)
        
        return column_contexts
    
    def _build_primary_key_context(self, columns: List[ColumnInfo]) -> Optional[Dict[str, Any]]:
        """构建主键上下文"""
        pk_column = next((col for col in columns if col.primary_key), None)
        
        if pk_column:
            java_name = self._to_camel_case(pk_column.name)
            return {
                "name": java_name,  # Java字段名
                "dbName": pk_column.name,  # 数据库字段名
                "javaName": java_name,
                "javaType": self._map_java_type(pk_column.data_type),
                "jdbcType": self._map_jdbc_type(pk_column.data_type),
                "comment": pk_column.comment or pk_column.name,
            }
        
        return None
    
    def _build_non_primary_columns_context(self, columns: List[ColumnInfo]) -> List[Dict[str, Any]]:
        """构建非主键列上下文"""
        non_pk_columns = [col for col in columns if not col.primary_key]
        column_contexts = []
        
        for i, column in enumerate(non_pk_columns):
            java_name = self._to_camel_case(column.name)
            java_type = self._map_java_type(column.data_type)
            column_context = {
                # 基础字段信息
                "name": column.name,  # 数据库字段名
                "javaName": java_name,  # Java字段名
                "capitalizedJavaName": java_name.capitalize(),  # 首字母大写的Java字段名
                "dbName": column.name,
                "javaType": java_type,
                "jdbcType": self._map_jdbc_type(column.data_type),
                "comment": column.comment or column.name,
                
                # 字段属性
                "isPrimaryKey": column.primary_key,
                "primaryKey": column.primary_key,  # 兼容两种写法
                "isNullable": column.nullable,
                "nullable": column.nullable,
                "isAutoIncrement": getattr(column, 'auto_increment', False),
                "autoIncrement": getattr(column, 'auto_increment', False),
                "defaultValue": column.default_value,
                "maxLength": getattr(column, 'max_length', None),
                
                # 验证相关
                "required": not column.nullable and not column.primary_key,
                "isString": self._is_string_type(column.data_type),
                "stringType": self._is_string_type(column.data_type),  # 别名
                "isStringType": self._is_string_type(column.data_type),  # 另一个别名
                "isStringType": self._is_string_type(column.data_type),  # 别名
                
                # 循环标志
                "hasNext": i < len(non_pk_columns) - 1,
                "isFirst": i == 0,
                "isLast": i == len(non_pk_columns) - 1,
                "last": i == len(non_pk_columns) - 1,  # 添加 last 别名
            }
            column_contexts.append(column_context)
        
        return column_contexts
    
    def _build_custom_mappings(self, columns: List[ColumnInfo]) -> Dict[str, bool]:
        """构建自定义映射规则"""
        column_names = [self._to_camel_case(col.name) for col in columns]
        
        return {
            "hasCreateTimeMapping": "createTime" in column_names,
            "hasUpdateTimeMapping": "updateTime" in column_names,
            "hasIdMapping": "id" in column_names,
        }
    
    def _build_imports(self, columns: List[ColumnInfo], template_category: str) -> List[str]:
        """构建导入列表"""
        imports = []
        java_types = {self._map_java_type(col.data_type) for col in columns}
        
        # 时间类型导入
        if "LocalDateTime" in java_types:
            imports.append("java.time.LocalDateTime")
        if "LocalDate" in java_types:
            imports.append("java.time.LocalDate")
        if "LocalTime" in java_types:
            imports.append("java.time.LocalTime")
        if "BigDecimal" in java_types:
            imports.append("java.math.BigDecimal")
        
        return sorted(imports)
    
    def _has_date_field(self, columns: List[ColumnInfo]) -> bool:
        """检查是否包含日期字段"""
        date_types = ['DATETIME', 'TIMESTAMP', 'DATE', 'TIME']
        return any(col.data_type.upper() in date_types for col in columns)
    
    def _has_big_decimal_field(self, columns: List[ColumnInfo]) -> bool:
        """检查是否包含 BigDecimal 字段"""
        decimal_types = ['DECIMAL', 'NUMERIC', 'MONEY']
        return any(col.data_type.upper() in decimal_types for col in columns)
    
    def _is_string_type(self, db_type: str) -> bool:
        """检查是否为字符串类型"""
        string_types = ['VARCHAR', 'CHAR', 'TEXT', 'LONGTEXT', 'MEDIUMTEXT', 'TINYTEXT', 'NVARCHAR', 'NCHAR']
        return db_type.upper() in string_types
    
    def _to_pascal_case(self, name: str) -> str:
        """转换为 PascalCase"""
        # 移除下划线并转换为 PascalCase
        words = name.split('_')
        return ''.join(word.capitalize() for word in words)
    
    def _to_camel_case(self, name: str) -> str:
        """转换为 camelCase"""
        pascal_case = self._to_pascal_case(name)
        return pascal_case[0].lower() + pascal_case[1:] if pascal_case else ''
    
    def _map_java_type(self, db_type: str) -> str:
        """映射数据库类型到 Java 类型"""
        type_mapping = {
            # 整数类型
            'TINYINT': 'Byte',
            'SMALLINT': 'Short', 
            'MEDIUMINT': 'Integer',
            'INT': 'Integer',
            'INTEGER': 'Integer',
            'BIGINT': 'Long',
            
            # 浮点类型
            'FLOAT': 'Float',
            'DOUBLE': 'Double',
            'DECIMAL': 'BigDecimal',
            'NUMERIC': 'BigDecimal',
            
            # 字符串类型
            'CHAR': 'String',
            'VARCHAR': 'String',
            'TEXT': 'String',
            'LONGTEXT': 'String',
            'MEDIUMTEXT': 'String',
            'TINYTEXT': 'String',
            'NCHAR': 'String',
            'NVARCHAR': 'String',
            
            # 日期时间类型
            'DATE': 'LocalDate',
            'TIME': 'LocalTime',
            'DATETIME': 'LocalDateTime',
            'TIMESTAMP': 'LocalDateTime',
            'YEAR': 'Integer',
            
            # 布尔类型
            'BOOLEAN': 'Boolean',
            'TINYINT(1)': 'Boolean',
            
            # 二进制类型
            'BINARY': 'byte[]',
            'VARBINARY': 'byte[]',
            'BLOB': 'byte[]',
            'LONGBLOB': 'byte[]',
            'MEDIUMBLOB': 'byte[]',
            'TINYBLOB': 'byte[]',
            
            # JSON 类型
            'JSON': 'String',
        }
        
        # 处理带长度的类型，如 VARCHAR(255)
        base_type = re.sub(r'\([^)]*\)', '', db_type.upper())
        
        return type_mapping.get(base_type, 'String')
    
    def _map_jdbc_type(self, db_type: str) -> str:
        """映射数据库类型到 JDBC 类型"""
        jdbc_mapping = {
            # 整数类型
            'TINYINT': 'TINYINT',
            'SMALLINT': 'SMALLINT',
            'MEDIUMINT': 'INTEGER',
            'INT': 'INTEGER',
            'INTEGER': 'INTEGER',
            'BIGINT': 'BIGINT',
            
            # 浮点类型
            'FLOAT': 'FLOAT',
            'DOUBLE': 'DOUBLE',
            'DECIMAL': 'DECIMAL',
            'NUMERIC': 'NUMERIC',
            
            # 字符串类型
            'CHAR': 'CHAR',
            'VARCHAR': 'VARCHAR',
            'TEXT': 'LONGVARCHAR',
            'LONGTEXT': 'LONGVARCHAR',
            'MEDIUMTEXT': 'LONGVARCHAR',
            'TINYTEXT': 'VARCHAR',
            'NCHAR': 'NCHAR',
            'NVARCHAR': 'NVARCHAR',
            
            # 日期时间类型
            'DATE': 'DATE',
            'TIME': 'TIME',
            'DATETIME': 'TIMESTAMP',
            'TIMESTAMP': 'TIMESTAMP',
            'YEAR': 'INTEGER',
            
            # 布尔类型
            'BOOLEAN': 'BOOLEAN',
            'TINYINT(1)': 'BOOLEAN',
            
            # 二进制类型
            'BINARY': 'BINARY',
            'VARBINARY': 'VARBINARY',
            'BLOB': 'BLOB',
            'LONGBLOB': 'LONGVARBINARY',
            'MEDIUMBLOB': 'LONGVARBINARY',
            'TINYBLOB': 'VARBINARY',
            
            # JSON 类型
            'JSON': 'LONGVARCHAR',
        }
        
        # 处理带长度的类型
        base_type = re.sub(r'\([^)]*\)', '', db_type.upper())
        
        return jdbc_mapping.get(base_type, 'VARCHAR')


class TemplateConfigManager:
    """模板配置管理器"""
    
    @staticmethod
    def get_template_files(category: str) -> List[str]:
        """获取指定分类的模板文件列表"""
        template_files = {
            "Default": [
                "entity.mustache",
                "dao.mustache", 
                "service.mustache",
                "serviceImpl.mustache",
                "controller.mustache",
                "mapper.xml.mustache"  # 使用 mapper.xml.mustache
            ],
            "MybatisPlus": [
                "entity.mustache",
                "dao.mustache",
                "service.mustache", 
                "serviceImpl.mustache",
                "controller.mustache"
            ],
            "MybatisPlus-Mixed": [
                "entity.mustache",
                "dao.mustache",
                "service.mustache",
                "serviceImpl.mustache", 
                "controller.mustache",
                "mapper.mustache"
            ]
        }
        
        return template_files.get(category, [])
    
    @staticmethod
    def get_additional_templates() -> List[str]:
        """获取通用附加模板列表"""
        return [
            "dto.mustache",
            "vo.mustache", 
            "mapstruct_mapper.mustache"
        ]
    
    @staticmethod
    def get_output_path_mapping() -> Dict[str, str]:
        """获取输出路径映射 - 支持前缀子包在组件类型之后"""
        return {
            "entity.mustache": "entity/{packageSuffix}/{className}.java",
            "dao.mustache": "dao/{packageSuffix}/{className}Dao.java", 
            "service.mustache": "service/{packageSuffix}/{className}Service.java",
            "serviceImpl.mustache": "service/impl/{packageSuffix}/{className}ServiceImpl.java",
            "controller.mustache": "controller/{packageSuffix}/{className}Controller.java",
            "mapper.xml.mustache": "mapper/{className}Dao.xml",  # XML文件不需要子包
            "mapper.mustache": "mapper/{className}Dao.xml",
            "dto.mustache": "dto/{packageSuffix}/{className}DTO.java",
            "vo.mustache": "vo/{packageSuffix}/{className}VO.java",
            "mapstruct_mapper.mustache": "mapper/{packageSuffix}/{className}Mapper.java"
            ,"mybatis_plus_config.mustache": "config/MybatisPlusConfig.java"
        }
