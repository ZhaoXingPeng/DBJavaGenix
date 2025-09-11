#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
智能依赖需求分析器
根据代码生成选项和模板类型，分析项目所需的依赖
"""

from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass
from enum import Enum


class DependencyStatus(Enum):
    REQUIRED = "required"          # 必需依赖
    OPTIONAL = "optional"          # 可选依赖  
    DEPRECATED = "deprecated"      # 已过时依赖
    RECOMMENDED = "recommended"    # 推荐依赖


@dataclass
class DependencyInfo:
    """依赖信息"""
    group_id: str
    artifact_id: str
    version: str
    scope: str = "compile"
    status: DependencyStatus = DependencyStatus.REQUIRED
    description: str = ""
    migration_target: Optional['DependencyInfo'] = None  # 迁移目标
    reason: str = ""  # 需要此依赖的原因


class DependencyRequirements:
    """依赖需求分析器"""
    
    def __init__(self):
        self._initialize_dependency_catalog()
    
    def _initialize_dependency_catalog(self):
        """初始化依赖目录"""
        
        # Spring Boot 基础依赖 - 更新到最新稳定版本
        self.SPRING_BOOT_DEPENDENCIES = {
            # 核心依赖
            "spring-boot-starter": DependencyInfo(
                "org.springframework.boot", "spring-boot-starter", "3.5.5",
                description="Spring Boot核心启动器",
                reason="Spring Boot应用的基础依赖"
            ),
            "spring-boot-starter-web": DependencyInfo(
                "org.springframework.boot", "spring-boot-starter-web", "3.5.5", 
                description="Spring Boot Web启动器",
                reason="构建Web应用和REST API"
            ),
            "spring-boot-starter-data-jpa": DependencyInfo(
                "org.springframework.boot", "spring-boot-starter-data-jpa", "3.5.5",
                description="Spring Data JPA启动器", 
                reason="JPA数据访问支持"
            ),
            "spring-boot-starter-validation": DependencyInfo(
                "org.springframework.boot", "spring-boot-starter-validation", "3.5.5",
                description="Bean验证启动器",
                reason="支持@Valid注解和参数验证"
            )
        }
        
        # 数据库驱动依赖
        self.DATABASE_DEPENDENCIES = {
            "mysql": DependencyInfo(
                "com.mysql", "mysql-connector-j", "8.4.0",
                description="MySQL 8.0+ JDBC驱动",
                reason="连接MySQL数据库"
            ),
            "mysql-legacy": DependencyInfo(
                "mysql", "mysql-connector-java", "8.0.33",
                status=DependencyStatus.DEPRECATED,
                description="MySQL旧版JDBC驱动",
                reason="连接MySQL数据库（已过时）"
            ),
            "postgresql": DependencyInfo(
                "org.postgresql", "postgresql", "42.7.4",
                description="PostgreSQL JDBC驱动",
                reason="连接PostgreSQL数据库"
            ),
            "sqlite": DependencyInfo(
                "org.xerial", "sqlite-jdbc", "3.46.1.3", 
                description="SQLite JDBC驱动",
                reason="连接SQLite数据库"
            )
        }
        
        # MyBatis相关依赖 - 更新版本并添加核心MyBatis依赖
        self.MYBATIS_DEPENDENCIES = {
            "mybatis": DependencyInfo(
                "org.mybatis", "mybatis", "3.5.16",
                description="MyBatis核心持久层框架",
                reason="MyBatis ORM框架的核心依赖"
            ),
            "mybatis-spring-boot": DependencyInfo(
                "org.mybatis.spring.boot", "mybatis-spring-boot-starter", "3.0.4",
                description="MyBatis Spring Boot启动器",
                reason="MyBatis集成Spring Boot支持"
            ),
            "mybatis-plus": DependencyInfo(
                "com.baomidou", "mybatis-plus-spring-boot3-starter", "3.5.7",
                description="MyBatis-Plus Spring Boot 3启动器", 
                reason="MyBatis-Plus增强功能，包含MyBatis核心"
            ),
            "mybatis-plus-generator": DependencyInfo(
                "com.baomidou", "mybatis-plus-generator", "3.5.7",
                status=DependencyStatus.OPTIONAL,
                description="MyBatis-Plus代码生成器",
                reason="支持MyBatis-Plus代码生成"
            ),
            "velocity-engine": DependencyInfo(
                "org.apache.velocity", "velocity-engine-core", "2.4.1",
                status=DependencyStatus.OPTIONAL,
                description="Velocity模板引擎",
                reason="MyBatis-Plus代码生成器的模板引擎"
            ),
            "freemarker": DependencyInfo(
                "org.freemarker", "freemarker", "2.3.33",
                status=DependencyStatus.OPTIONAL,
                description="FreeMarker模板引擎",
                reason="MyBatis-Plus代码生成器的替代模板引擎"
            )
        }
        
        # 工具依赖 - 更新版本到最新稳定版
        self.TOOL_DEPENDENCIES = {
            # Lombok
            "lombok": DependencyInfo(
                "org.projectlombok", "lombok", "1.18.36",
                status=DependencyStatus.OPTIONAL,
                description="Lombok代码生成工具",
                reason="减少样板代码，支持@Data等注解"
            ),
            
            # MapStruct
            "mapstruct": DependencyInfo(
                "org.mapstruct", "mapstruct", "1.6.3",
                status=DependencyStatus.OPTIONAL,
                description="MapStruct对象映射框架",
                reason="自动生成对象映射代码"
            ),
            "mapstruct-processor": DependencyInfo(
                "org.mapstruct", "mapstruct-processor", "1.6.3",
                scope="provided",
                status=DependencyStatus.OPTIONAL,
                description="MapStruct注解处理器",
                reason="编译时生成映射实现"
            ),
            
            # Swagger/OpenAPI 3.0 (推荐)
            "springdoc-openapi": DependencyInfo(
                "org.springdoc", "springdoc-openapi-starter-webmvc-ui", "2.7.0",
                status=DependencyStatus.RECOMMENDED,
                description="SpringDoc OpenAPI 3.0支持",
                reason="生成现代化的API文档"
            ),
            
            # Swagger 2.x (已过时)
            "swagger-annotations-deprecated": DependencyInfo(
                "io.swagger", "swagger-annotations", "1.6.14",
                status=DependencyStatus.DEPRECATED,
                description="Swagger 2.x注解 (已过时)",
                reason="Swagger API文档注解 (建议迁移到OpenAPI 3.0)"
            ),
            
            # Jakarta EE 注解 (推荐)
            "jakarta-annotation": DependencyInfo(
                "jakarta.annotation", "jakarta.annotation-api", "2.1.1",
                status=DependencyStatus.RECOMMENDED,
                description="Jakarta EE注解API",
                reason="现代化的Java EE注解支持"
            ),
            "jakarta-validation": DependencyInfo(
                "jakarta.validation", "jakarta.validation-api", "3.0.2",
                status=DependencyStatus.RECOMMENDED,
                description="Jakarta Bean Validation API", 
                reason="现代化的Bean验证支持"
            ),
            
            # Javax 注解 (已过时)
            "javax-annotation-deprecated": DependencyInfo(
                "javax.annotation", "javax.annotation-api", "1.3.2",
                status=DependencyStatus.DEPRECATED,
                description="Javax注解API (已过时)",
                reason="Java EE注解支持 (建议迁移到jakarta)"
            ),
            "javax-validation-deprecated": DependencyInfo(
                "javax.validation", "validation-api", "2.0.1.Final",
                status=DependencyStatus.DEPRECATED,
                description="Javax Bean Validation API (已过时)",
                reason="Bean验证支持 (建议迁移到jakarta)"
            )
        }
        
        # 设置迁移关系
        self.TOOL_DEPENDENCIES["javax-annotation-deprecated"].migration_target = self.TOOL_DEPENDENCIES["jakarta-annotation"]
        self.TOOL_DEPENDENCIES["javax-validation-deprecated"].migration_target = self.TOOL_DEPENDENCIES["jakarta-validation"]
        self.TOOL_DEPENDENCIES["swagger-annotations-deprecated"].migration_target = self.TOOL_DEPENDENCIES["springdoc-openapi"]
    
    def analyze_requirements(self, 
                           template_category: str,
                           database_type: str,
                           include_swagger: bool = True,
                           include_lombok: bool = True, 
                           include_mapstruct: bool = True,
                           spring_boot_version: Optional[str] = None) -> Dict[str, List[DependencyInfo]]:
        """
        分析代码生成需求的依赖 - 增强版本兼容性检查
        
        Args:
            template_category: 模板类别 (Default/MybatisPlus/MybatisPlus-Mixed)
            database_type: 数据库类型 (mysql/postgresql/sqlite)
            include_swagger: 是否包含Swagger支持
            include_lombok: 是否包含Lombok支持
            include_mapstruct: 是否包含MapStruct支持
            spring_boot_version: Spring Boot版本
            
        Returns:
            按类别分组的依赖需求字典
        """
        
        # 根据Spring Boot版本调整依赖版本
        if spring_boot_version:
            self.adjust_versions_for_spring_boot(spring_boot_version)
        
        requirements = {
            "required": [],      # 必需依赖
            "optional": [],      # 可选依赖
            "recommended": [],   # 推荐依赖
            "deprecated": []     # 需要迁移的过时依赖
        }
        
        # 1. Spring Boot基础依赖 (必需)
        requirements["required"].extend([
            self.SPRING_BOOT_DEPENDENCIES["spring-boot-starter"],
            self.SPRING_BOOT_DEPENDENCIES["spring-boot-starter-web"],
            self.SPRING_BOOT_DEPENDENCIES["spring-boot-starter-validation"]
        ])
        
        # 2. 数据库驱动依赖 (必需)
        db_key = database_type.lower()
        if db_key in self.DATABASE_DEPENDENCIES:
            requirements["required"].append(self.DATABASE_DEPENDENCIES[db_key])
        
        # 3. MyBatis相关依赖
        if template_category == "Default":
            # 传统MyBatis - 需要核心MyBatis和Spring Boot集成
            requirements["required"].extend([
                # JPA not required for MyBatis-based Default template
                self.MYBATIS_DEPENDENCIES["mybatis"],
                self.MYBATIS_DEPENDENCIES["mybatis-spring-boot"]
            ])
        elif template_category in ["MybatisPlus", "MybatisPlus-Mixed"]:
            # MyBatis-Plus - 已包含MyBatis核心，不需要单独的MyBatis依赖
            requirements["required"].extend([
                # JPA not required for MyBatis-Plus templates
                self.MYBATIS_DEPENDENCIES["mybatis-plus"]
            ])
            # 注意：不添加代码生成器相关依赖，因为我们本身就是代码生成器
            # 不添加：mybatis-plus-generator, velocity-engine, freemarker
            # 也不添加单独的 mybatis 核心包，MyBatis-Plus starter 已包含
        
        # 4. 工具依赖
        if include_lombok:
            requirements["optional"].append(self.TOOL_DEPENDENCIES["lombok"])
        
        if include_mapstruct:
            requirements["optional"].extend([
                self.TOOL_DEPENDENCIES["mapstruct"],
                self.TOOL_DEPENDENCIES["mapstruct-processor"]
            ])
        
        if include_swagger:
            # 推荐现代化的OpenAPI 3.0
            requirements["recommended"].append(self.TOOL_DEPENDENCIES["springdoc-openapi"])
            # 标记过时的Swagger 2.x
            requirements["deprecated"].append(self.TOOL_DEPENDENCIES["swagger-annotations-deprecated"])
        
        # 5. Jakarta EE迁移 (推荐)
        requirements["recommended"].extend([
            self.TOOL_DEPENDENCIES["jakarta-annotation"],
            self.TOOL_DEPENDENCIES["jakarta-validation"]
        ])
        
        # 6. 标记过时的javax依赖
        requirements["deprecated"].extend([
            self.TOOL_DEPENDENCIES["javax-annotation-deprecated"],
            self.TOOL_DEPENDENCIES["javax-validation-deprecated"]
        ])
        
        return requirements
    
    def get_spring_boot_version_compatibility(self, version: str) -> Dict[str, str]:
        """获取Spring Boot版本兼容性信息 - 增强版"""
        compatibility = {
            "java_version": "17+",
            "jakarta_ee": True,
            "javax_ee": False,
            "recommended_dependencies": {},
            "mybatis_version": "3.5.16",
            "mybatis_plus_version": "3.5.7",
            "mysql_connector_version": "8.4.0"
        }
        
        if version.startswith("2."):
            compatibility.update({
                "java_version": "8+", 
                "jakarta_ee": False,
                "javax_ee": True,
                "mybatis_version": "3.4.6",  # 兼容Spring Boot 2.x
                "mybatis_plus_version": "3.4.3",
                "mysql_connector_version": "8.0.33"
            })
        elif version.startswith("3.0") or version.startswith("3.1"):
            compatibility.update({
                "java_version": "17+",
                "jakarta_ee": True, 
                "javax_ee": False,
                "mybatis_version": "3.5.10",
                "mybatis_plus_version": "3.5.3",
                "mysql_connector_version": "8.3.0"
            })
        elif version.startswith("3.2") or version.startswith("3.3"):
            compatibility.update({
                "java_version": "17+",
                "jakarta_ee": True, 
                "javax_ee": False,
                "mybatis_version": "3.5.14",
                "mybatis_plus_version": "3.5.5",
                "mysql_connector_version": "8.3.0"
            })
        elif version.startswith("3.4") or version.startswith("3.5"):
            # 最新版本，使用最新的兼容依赖
            compatibility.update({
                "java_version": "17+",
                "jakarta_ee": True, 
                "javax_ee": False,
                "mybatis_version": "3.5.16",
                "mybatis_plus_version": "3.5.7",
                "mysql_connector_version": "8.4.0"
            })
        
        return compatibility
    
    def adjust_versions_for_spring_boot(self, spring_boot_version: str) -> None:
        """根据Spring Boot版本调整依赖版本"""
        compat = self.get_spring_boot_version_compatibility(spring_boot_version)
        
        # 更新MyBatis依赖版本
        if "mybatis" in self.MYBATIS_DEPENDENCIES:
            self.MYBATIS_DEPENDENCIES["mybatis"].version = compat["mybatis_version"]
        
        if "mybatis-plus" in self.MYBATIS_DEPENDENCIES:
            # 版本
            self.MYBATIS_DEPENDENCIES["mybatis-plus"].version = compat["mybatis_plus_version"]
            # Spring Boot 2.x 使用 mybatis-plus-boot-starter；Boot 3.x 使用 mybatis-plus-spring-boot3-starter
            if spring_boot_version.startswith("2."):
                self.MYBATIS_DEPENDENCIES["mybatis-plus"].artifact_id = "mybatis-plus-boot-starter"
            else:
                self.MYBATIS_DEPENDENCIES["mybatis-plus"].artifact_id = "mybatis-plus-spring-boot3-starter"
        
        # 更新数据库驱动版本
        if "mysql" in self.DATABASE_DEPENDENCIES:
            if compat["mysql_connector_version"].startswith("8.4"):
                # 使用新版MySQL Connector/J
                self.DATABASE_DEPENDENCIES["mysql"].group_id = "com.mysql"
                self.DATABASE_DEPENDENCIES["mysql"].artifact_id = "mysql-connector-j"
            else:
                # 使用旧版MySQL Connector
                self.DATABASE_DEPENDENCIES["mysql"].group_id = "mysql"
                self.DATABASE_DEPENDENCIES["mysql"].artifact_id = "mysql-connector-java"
            
            self.DATABASE_DEPENDENCIES["mysql"].version = compat["mysql_connector_version"]
    
    def generate_migration_recommendations(self, current_dependencies: List[DependencyInfo]) -> List[Dict[str, any]]:
        """生成迁移建议"""
        recommendations = []
        
        for dep in current_dependencies:
            if dep.status == DependencyStatus.DEPRECATED and dep.migration_target:
                recommendations.append({
                    "type": "migration",
                    "from": f"{dep.group_id}:{dep.artifact_id}:{dep.version}",
                    "to": f"{dep.migration_target.group_id}:{dep.migration_target.artifact_id}:{dep.migration_target.version}",
                    "reason": f"迁移原因: {dep.description} -> {dep.migration_target.description}",
                    "impact": "需要更新import语句",
                    "priority": "high" if "javax" in dep.group_id else "medium"
                })
        
        return recommendations
