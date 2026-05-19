#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
POM文件分析和智能建议生成器
分析现有pom.xml，与需求对比，生成详细的依赖管理建议
"""

import xml.etree.ElementTree as ET
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass
from pathlib import Path
import re

from .dependency_requirements import DependencyRequirements, DependencyInfo, DependencyStatus


@dataclass
class ExistingDependency:
    """现有依赖信息"""
    group_id: str
    artifact_id: str
    version: Optional[str] = None
    scope: str = "compile"
    source_line: Optional[int] = None  # 在pom.xml中的行号


@dataclass
class DependencyComparison:
    """依赖对比结果"""
    requirement: DependencyInfo
    existing: Optional[ExistingDependency] = None
    status: str = "missing"  # missing, exists, outdated, deprecated
    recommendation: str = ""
    maven_xml: str = ""  # 建议添加的Maven XML


@dataclass
class TechnologyStack:
    """技术栈信息"""
    has_javax: bool = False
    has_jakarta: bool = False
    has_spring_data: bool = False
    has_mybatis: bool = False
    has_swagger2: bool = False
    has_springdoc: bool = False
    is_modern_stack: bool = True  # 默认使用现代化技术栈


class PomAnalyzer:
    """POM文件分析器"""
    
    def __init__(self):
        self.requirements_analyzer = DependencyRequirements()
        
    def analyze_project_dependencies(self, 
                                   project_root: str,
                                   template_category: str,
                                   database_type: str,
                                   include_swagger: bool = True,
                                   include_lombok: bool = True,
                                   include_mapstruct: bool = True) -> Dict[str, any]:
        """
        分析项目依赖状况并生成建议
        
        Args:
            project_root: 项目根目录
            template_category: 模板类别
            database_type: 数据库类型
            include_swagger: 是否需要Swagger
            include_lombok: 是否需要Lombok
            include_mapstruct: 是否需要MapStruct
            
        Returns:
            完整的分析报告和建议
        """
        
        # 1. 解析现有依赖文件
        project_path = Path(project_root)
        build_tool = self._detect_build_tool(project_path)
        
        existing_deps = []
        if build_tool == "maven":
            pom_path = project_path / "pom.xml"
            existing_deps = self._parse_pom_file(pom_path)
            spring_boot_version = self._extract_spring_boot_version(pom_path)
        elif build_tool == "gradle":
            gradle_path = project_path / "build.gradle"
            if not gradle_path.exists():
                gradle_path = project_path / "build.gradle.kts"
            existing_deps = self._parse_gradle_file(gradle_path)
            spring_boot_version = self._extract_gradle_spring_boot_version(gradle_path)
        else:
            spring_boot_version = None
        
        # 2. 分析依赖需求
        requirements = self.requirements_analyzer.analyze_requirements(
            template_category=template_category,
            database_type=database_type,
            include_swagger=include_swagger,
            include_lombok=include_lombok,
            include_mapstruct=include_mapstruct,
            spring_boot_version=spring_boot_version
        )
        
        # 3. 对比分析
        comparison_results = self._compare_dependencies(requirements, existing_deps)

        # 3.1 模板适配过滤：在 MyBatis 系列模板下不强制引入 JPA，且避免建议裸 mybatis
        try:
            if template_category in ("Default", "MybatisPlus", "MybatisPlus-Mixed"):
                comparison_results = [
                    comp for comp in comparison_results
                    if f"{comp.requirement.group_id}:{comp.requirement.artifact_id}" not in {
                        "org.springframework.boot:spring-boot-starter-data-jpa",
                        "org.mybatis:mybatis"
                    }
                ]
        except Exception:
            pass
        
        # 4. 生成建议
        recommendations = self._generate_recommendations(comparison_results, spring_boot_version)
        
        # 5. 生成Maven XML代码块
        maven_xml_blocks = self._generate_maven_xml(comparison_results)
        
        # 6. 检测技术栈类型
        tech_stack = self._detect_technology_stack(existing_deps)
        
        return {
            "build_tool": build_tool,
            "config_file_exists": build_tool is not None,
            "config_file_path": str(project_path / ("pom.xml" if build_tool == "maven" else "build.gradle")) if build_tool else None,
            "spring_boot_version": spring_boot_version,
            "existing_dependencies": len(existing_deps),
            "requirements": requirements,
            "comparison_results": comparison_results,
            "recommendations": recommendations,
            "maven_xml": maven_xml_blocks,  # 注意：Gradle项目仍然提供Maven格式的参考
            "technology_stack": tech_stack,  # 新增技术栈信息
            "summary": self._generate_summary(comparison_results)
        }
    
    def _detect_technology_stack(self, existing_deps: List[ExistingDependency]) -> TechnologyStack:
        """
        检测项目使用的技术栈类型
        
        Args:
            existing_deps: 现有依赖列表
            
        Returns:
            TechnologyStack对象
        """
        tech_stack = TechnologyStack()
        
        for dep in existing_deps:
            # 检测注解API类型
            if dep.group_id == "javax.annotation" and dep.artifact_id == "javax.annotation-api":
                tech_stack.has_javax = True
                tech_stack.is_modern_stack = False
            elif dep.group_id == "jakarta.annotation" and dep.artifact_id == "jakarta.annotation-api":
                tech_stack.has_jakarta = True
                
            # 检测数据访问技术
            if dep.group_id == "org.springframework.data":
                tech_stack.has_spring_data = True
                tech_stack.is_modern_stack = False
            elif dep.group_id == "org.mybatis" or dep.group_id == "org.mybatis.spring.boot":
                tech_stack.has_mybatis = True
                
            # 检测API文档技术
            if dep.group_id == "io.swagger":
                tech_stack.has_swagger2 = True
                tech_stack.is_modern_stack = False
            elif dep.group_id == "org.springdoc":
                tech_stack.has_springdoc = True
        
        # 如果没有明确指定技术栈，默认使用现代化技术栈
        if not any([tech_stack.has_javax, tech_stack.has_jakarta, 
                   tech_stack.has_spring_data, tech_stack.has_mybatis,
                   tech_stack.has_swagger2, tech_stack.has_springdoc]):
            tech_stack.has_jakarta = True
            tech_stack.has_mybatis = True
            tech_stack.has_springdoc = True
            tech_stack.is_modern_stack = True
            
        return tech_stack
    
    def _parse_pom_file(self, pom_path: Path) -> List[ExistingDependency]:
        """解析pom.xml文件"""
        if not pom_path.exists():
            return []
        
        try:
            tree = ET.parse(pom_path)
            root = tree.getroot()
            
            # 处理命名空间
            namespace = {'maven': 'http://maven.apache.org/POM/4.0.0'}
            if root.tag.startswith('{'):
                namespace_uri = root.tag[1:root.tag.find('}')]
                namespace = {'maven': namespace_uri}
            
            dependencies = []
            
            # 查找所有dependency元素
            for dep in root.findall('.//maven:dependency', namespace):
                group_id = dep.find('maven:groupId', namespace)
                artifact_id = dep.find('maven:artifactId', namespace)
                version = dep.find('maven:version', namespace)
                scope = dep.find('maven:scope', namespace)
                
                if group_id is not None and artifact_id is not None:
                    dependencies.append(ExistingDependency(
                        group_id=group_id.text,
                        artifact_id=artifact_id.text,
                        version=version.text if version is not None else None,
                        scope=scope.text if scope is not None else "compile"
                    ))
            
            return dependencies
            
        except Exception as e:
            print(f"Warning: Failed to parse pom.xml: {e}")
            return []
    
    def _parse_gradle_file(self, gradle_path: Path) -> List[ExistingDependency]:
        """解析build.gradle文件 - 新增Gradle支持"""
        if not gradle_path.exists():
            return []
        
        try:
            with open(gradle_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            dependencies = []
            
            # 匹配Gradle依赖格式: implementation 'group:artifact:version'
            patterns = [
                r"(?:implementation|api|compile|testImplementation)\s+['\"]([^:]+):([^:]+):([^'\"]+)['\"]",
                r"(?:implementation|api|compile|testImplementation)\s+['\"]([^:]+):([^:]+)['\"]",  # 无版本号
                r"(?:implementation|api|compile|testImplementation)\s+group:\s*['\"]([^'\"]+)['\"],\s*name:\s*['\"]([^'\"]+)['\"],\s*version:\s*['\"]([^'\"]+)['\"]"
            ]
            
            for pattern in patterns:
                matches = re.findall(pattern, content)
                for match in matches:
                    if len(match) == 3:
                        group_id, artifact_id, version = match
                    elif len(match) == 2:
                        group_id, artifact_id = match
                        version = None
                    else:
                        continue
                        
                    dependencies.append(ExistingDependency(
                        group_id=group_id,
                        artifact_id=artifact_id,
                        version=version,
                        scope="compile"  # Gradle默认scope
                    ))
            
            return dependencies
            
        except Exception as e:
            print(f"Warning: Failed to parse build.gradle: {e}")
            return []
    
    def _detect_build_tool(self, project_root: Path) -> Optional[str]:
        """检测构建工具类型"""
        if (project_root / "pom.xml").exists():
            return "maven"
        elif (project_root / "build.gradle").exists() or (project_root / "build.gradle.kts").exists():
            return "gradle"
        else:
            return None
    
    def _extract_spring_boot_version(self, pom_path: Path) -> Optional[str]:
        """提取Spring Boot版本"""
        try:
            with open(pom_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 查找Spring Boot parent版本
            parent_pattern = r'<parent>.*?<groupId>org\.springframework\.boot</groupId>.*?<version>([^<]+)</version>.*?</parent>'
            match = re.search(parent_pattern, content, re.DOTALL)
            if match:
                return match.group(1)
            
            # 查找Spring Boot property版本
            property_pattern = r'<spring\.boot\.version>([^<]+)</spring\.boot\.version>'
            match = re.search(property_pattern, content)
            if match:
                return match.group(1)
            
            return None
            
        except Exception:
            return None
    
    def _extract_gradle_spring_boot_version(self, gradle_path: Path) -> Optional[str]:
        """提取Gradle中的Spring Boot版本"""
        try:
            with open(gradle_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 查找Spring Boot plugin版本
            patterns = [
                r'org\.springframework\.boot[\'\"]\s*version\s*[\'\"]([\d\.]+)',
                r'spring-boot[\'\"]\s*version\s*[\'\"]([\d\.]+)',
                r'springBootVersion\s*=\s*[\'\"]([\d\.]+)',
            ]
            
            for pattern in patterns:
                match = re.search(pattern, content)
                if match:
                    return match.group(1)
            
            return None
            
        except Exception:
            return None
    
    def _compare_dependencies(self, 
                            requirements: Dict[str, List[DependencyInfo]], 
                            existing_deps: List[ExistingDependency]) -> List[DependencyComparison]:
        """对比需求与现有依赖"""
        comparisons = []
        
        # 创建现有依赖的快速查找字典
        existing_dict = {}
        for dep in existing_deps:
            key = f"{dep.group_id}:{dep.artifact_id}"
            existing_dict[key] = dep
        
        # 检查所有需求类别
        for category, deps in requirements.items():
            for req_dep in deps:
                key = f"{req_dep.group_id}:{req_dep.artifact_id}"
                existing = existing_dict.get(key)
                
                comparison = DependencyComparison(requirement=req_dep, existing=existing)
                
                if existing is None:
                    comparison.status = "missing"
                    comparison.recommendation = f"添加{req_dep.description}"
                    comparison.maven_xml = self._format_maven_dependency(req_dep)
                else:
                    if req_dep.status == DependencyStatus.DEPRECATED:
                        comparison.status = "deprecated"
                        comparison.recommendation = f"建议迁移到新版本: {req_dep.migration_target.group_id}:{req_dep.migration_target.artifact_id}" if req_dep.migration_target else "依赖已过时"
                    elif existing.version and self._is_version_outdated(existing.version, req_dep.version):
                        comparison.status = "outdated"
                        comparison.recommendation = f"建议升级版本: {existing.version} -> {req_dep.version}"
                        comparison.maven_xml = self._format_maven_dependency(req_dep)
                    else:
                        comparison.status = "exists"
                        comparison.recommendation = "依赖已存在且版本合适"
                
                comparisons.append(comparison)
        
        return comparisons
    
    def _is_version_outdated(self, current: str, required: str) -> bool:
        """简单的版本比较（可以后续改进为更精确的语义版本比较）"""
        try:
            # 简单的数字版本比较
            current_parts = [int(x) for x in current.split('.') if x.isdigit()]
            required_parts = [int(x) for x in required.split('.') if x.isdigit()]
            
            # 补齐长度
            max_len = max(len(current_parts), len(required_parts))
            current_parts.extend([0] * (max_len - len(current_parts)))
            required_parts.extend([0] * (max_len - len(required_parts)))
            
            return current_parts < required_parts
        except:
            return False
    
    def _format_maven_dependency(self, dep: DependencyInfo) -> str:
        """格式化Maven依赖XML"""
        # 添加依赖描述注释
        comment = f"    <!-- {dep.description}: {dep.reason} -->"
        xml_lines = [
            comment,
            "    <dependency>",
            f"        <groupId>{dep.group_id}</groupId>",
            f"        <artifactId>{dep.artifact_id}</artifactId>",
            f"        <version>{dep.version}</version>"
        ]
        
        if dep.scope != "compile":
            xml_lines.append(f"        <scope>{dep.scope}</scope>")
        
        xml_lines.append("    </dependency>")
        
        return "\n".join(xml_lines)
    
    def _generate_recommendations(self, 
                                comparisons: List[DependencyComparison],
                                spring_boot_version: Optional[str]) -> Dict[str, List[str]]:
        """生成详细建议"""
        recommendations = {
            "critical": [],      # 关键问题
            "important": [],     # 重要建议  
            "optional": [],      # 可选优化
            "migration": []      # 迁移建议
        }
        
        for comp in comparisons:
            dep = comp.requirement
            
            if comp.status == "missing":
                if dep.status == DependencyStatus.REQUIRED:
                    recommendations["critical"].append(
                        f"❌ 缺少必需依赖: {dep.group_id}:{dep.artifact_id} - {dep.reason}"
                    )
                elif dep.status == DependencyStatus.RECOMMENDED:
                    recommendations["important"].append(
                        f"⚠️ 建议添加: {dep.group_id}:{dep.artifact_id} - {dep.reason}"
                    )
                else:
                    recommendations["optional"].append(
                        f"💡 可选依赖: {dep.group_id}:{dep.artifact_id} - {dep.reason}"
                    )
            
            elif comp.status == "deprecated":
                recommendations["migration"].append(
                    f"🔄 迁移建议: {dep.group_id}:{dep.artifact_id} 已过时，建议迁移到 {dep.migration_target.group_id}:{dep.migration_target.artifact_id}" if dep.migration_target else f"🔄 {dep.group_id}:{dep.artifact_id} 已过时"
                )
            
            elif comp.status == "outdated":
                recommendations["important"].append(
                    f"📦 版本升级: {dep.group_id}:{dep.artifact_id} 当前版本过旧，建议升级到 {dep.version}"
                )
        
        # 添加Spring Boot版本相关建议
        if spring_boot_version:
            if spring_boot_version.startswith("2."):
                recommendations["migration"].append(
                    "🚀 建议升级到Spring Boot 3.x以获得Jakarta EE支持和性能提升"
                )
            elif spring_boot_version.startswith("3."):
                recommendations["optional"].append(
                    f"✅ Spring Boot版本 {spring_boot_version} 符合现代化要求"
                )
        
        return recommendations
    
    def _generate_maven_xml(self, comparisons: List[DependencyComparison]) -> Dict[str, str]:
        """生成Maven XML代码块"""
        xml_blocks = {
            "missing_dependencies": [],
            "upgrade_dependencies": [],
            "migration_dependencies": []
        }
        
        for comp in comparisons:
            if comp.status == "missing" and comp.maven_xml:
                xml_blocks["missing_dependencies"].append({
                    "description": f"{comp.requirement.description} - {comp.requirement.reason}",
                    "xml": comp.maven_xml
                })
            elif comp.status == "outdated" and comp.maven_xml:
                xml_blocks["upgrade_dependencies"].append({
                    "description": f"升级 {comp.requirement.group_id}:{comp.requirement.artifact_id}",
                    "xml": comp.maven_xml
                })
            elif comp.status == "deprecated" and comp.requirement.migration_target:
                xml_blocks["migration_dependencies"].append({
                    "description": f"迁移 {comp.requirement.group_id}:{comp.requirement.artifact_id}",
                    "xml": self._format_maven_dependency(comp.requirement.migration_target)
                })
        
        return xml_blocks
    
    def _generate_summary(self, comparisons: List[DependencyComparison]) -> Dict[str, int]:
        """生成统计摘要"""
        summary = {
            "total_requirements": len(comparisons),
            "missing": len([c for c in comparisons if c.status == "missing"]),
            "exists": len([c for c in comparisons if c.status == "exists"]),
            "outdated": len([c for c in comparisons if c.status == "outdated"]),
            "deprecated": len([c for c in comparisons if c.status == "deprecated"])
        }
        
        summary["needs_attention"] = summary["missing"] + summary["outdated"] + summary["deprecated"]
        summary["health_score"] = max(0, 100 - (summary["needs_attention"] * 10))
        
        return summary
    
    def auto_add_missing_dependencies(self, project_root: str, comparison_results: List[DependencyComparison]) -> Dict[str, any]:
        """
        自动添加缺失的依赖到项目中
        
        Args:
            project_root: 项目根目录
            comparison_results: 依赖对比结果
            
        Returns:
            添加结果
        """
        project_path = Path(project_root)
        build_tool = self._detect_build_tool(project_path)
        
        if not build_tool:
            return {
                "success": False,
                "message": "未检测到构建工具"
            }
        
        # 收集需要添加的依赖
        missing_deps = []
        # Dynamically decide which missing deps to add based on the project's stack
        pom_path = Path(project_root) / "pom.xml"
        boot_version = None
        existing_coords = set()
        try:
            if pom_path.exists():
                boot_version = self._extract_spring_boot_version(pom_path)
                existing = self._parse_pom_file(pom_path)
                existing_coords = {f"{d.group_id}:{d.artifact_id}" for d in existing}
        except Exception:
            pass

        is_boot2 = bool(boot_version and str(boot_version).startswith("2."))
        uses_legacy_swagger = any(c.startswith("io.springfox:") or c == "io.swagger:swagger-annotations" for c in existing_coords)

        def is_allowed(comp) -> bool:
            coord = f"{comp.requirement.group_id}:{comp.requirement.artifact_id}"
            # Never add JPA for MyBatis/MyBatis-Plus based templates
            if coord == "org.springframework.boot:spring-boot-starter-data-jpa":
                return False
            # Never add bare MyBatis when using Spring Boot starters
            if coord == "org.mybatis:mybatis":
                return False
            # Prefer stack consistency for Swagger/OpenAPI
            if is_boot2 or uses_legacy_swagger:
                # On legacy projects, avoid adding springdoc unless user already uses it
                if coord.startswith("org.springdoc:"):
                    return False
            else:
                # On modern projects, avoid adding legacy swagger annotations
                if coord.startswith("io.swagger:") or coord.startswith("io.springfox:"):
                    return False
            # Jakarta/Javax base APIs are provided by Boot/starters; avoid explicit adds
            if comp.requirement.group_id.startswith("jakarta."):
                return False
            if comp.requirement.group_id.startswith("javax."):
                return False
            return True

        for comp in [c for c in comparison_results if is_allowed(c)]:
            if comp.status == "missing":
                missing_deps.append(comp.requirement)
        
        if not missing_deps:
            return {
                "success": True,
                "message": "没有需要添加的依赖",
                "added_count": 0
            }
        
        # 根据构建工具类型添加依赖
        try:
            if build_tool == "maven":
                added_count = self._add_maven_dependencies(project_path, missing_deps)
            elif build_tool == "gradle":
                added_count = self._add_gradle_dependencies(project_path, missing_deps)
            else:
                return {
                    "success": False,
                    "message": f"不支持的构建工具: {build_tool}"
                }
            
            return {
                "success": True,
                "message": f"成功添加 {added_count} 个依赖",
                "added_count": added_count
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"添加依赖失败: {str(e)}"
            }
    
    def _add_maven_dependencies(self, project_path: Path, dependencies: List[DependencyInfo]) -> int:
        """添加Maven依赖 - 修复版"""
        pom_file = project_path / "pom.xml"
        if not pom_file.exists():
            raise Exception("pom.xml文件不存在")
        
        # 读取pom.xml内容
        with open(pom_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 查找dependencies标签
        dependencies_pattern = r'(<dependencies>)(.*?)(</dependencies>)'
        dependencies_match = re.search(dependencies_pattern, content, re.DOTALL)
        
        added_count = 0
        
        if dependencies_match:
            # 在现有dependencies标签中添加依赖
            start_tag = dependencies_match.group(1)
            existing_content = dependencies_match.group(2)
            end_tag = dependencies_match.group(3)
            
            # 准备新依赖
            new_deps = []
            # 添加注释说明（只添加一次）
            if "DBJavaGenix 自动添加的依赖" not in content:  # 避免重复添加注释
                new_deps.append("    <!-- DBJavaGenix 自动添加的依赖 -->")
            
            for dep in dependencies:
                # 为每个依赖添加注释说明
                new_deps.append(f"    <!-- {dep.description}: {dep.reason} -->")
                new_deps.append("    <dependency>")
                new_deps.append(f"        <groupId>{dep.group_id}</groupId>")
                new_deps.append(f"        <artifactId>{dep.artifact_id}</artifactId>")
                new_deps.append(f"        <version>{dep.version}</version>")
                if dep.scope != "compile":
                    new_deps.append(f"        <scope>{dep.scope}</scope>")
                new_deps.append("    </dependency>")
                added_count += 1
            
            # 正确地重新组装dependencies块
            updated_deps_block = start_tag + existing_content
            if existing_content.strip():  # 如果已有内容，添加换行
                updated_deps_block += "\n" + "\n".join(new_deps) + "\n    "
            else:  # 如果没有内容，直接添加新依赖
                updated_deps_block += "\n".join(new_deps) + "\n    "
            updated_deps_block += end_tag
            
            # 替换原来的dependencies块
            content = content.replace(dependencies_match.group(0), updated_deps_block)
        else:
            # 创建新的dependencies标签
            new_deps_section = ["<dependencies>"]
            # 添加注释说明
            new_deps_section.append("    <!-- DBJavaGenix 自动添加的依赖 -->")
            for dep in dependencies:
                # 为每个依赖添加注释说明
                new_deps_section.append(f"    <!-- {dep.description}: {dep.reason} -->")
                new_deps_section.append("    <dependency>")
                new_deps_section.append(f"        <groupId>{dep.group_id}</groupId>")
                new_deps_section.append(f"        <artifactId>{dep.artifact_id}</artifactId>")
                new_deps_section.append(f"        <version>{dep.version}</version>")
                if dep.scope != "compile":
                    new_deps_section.append(f"        <scope>{dep.scope}</scope>")
                new_deps_section.append("    </dependency>")
                added_count += 1
            new_deps_section.append("</dependencies>")
            
            # 查找插入位置（在</project>标签前插入）
            insert_position = content.rfind("</project>")
            if insert_position != -1:
                # 在</project>标签前插入dependencies块
                content = content[:insert_position] + "    " + "\n    ".join(new_deps_section) + "\n\n" + content[insert_position:]
            else:
                # 如果找不到</project>标签，添加到文件末尾
                content = content.rstrip() + "\n\n" + "\n".join(new_deps_section) + "\n"
        
        # 写回文件
        with open(pom_file, 'w', encoding='utf-8') as f:
            f.write(content)
        
        return added_count
    
    def _add_gradle_dependencies(self, project_path: Path, dependencies: List[DependencyInfo]) -> int:
        """添加Gradle依赖"""
        gradle_file = project_path / "build.gradle"
        if not gradle_file.exists():
            gradle_file = project_path / "build.gradle.kts"
            if not gradle_file.exists():
                raise Exception("build.gradle文件不存在")
        
        # 读取build.gradle内容
        with open(gradle_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 查找dependencies块
        dependencies_pattern = r'(dependencies\s*\{.*?\})'
        dependencies_match = re.search(dependencies_pattern, content, re.DOTALL)
        
        added_count = 0
        
        if dependencies_match:
            # 在现有dependencies块中添加依赖
            existing_deps = dependencies_match.group(1)
            new_deps = []
            for dep in dependencies:
                scope = dep.scope if dep.scope in ["implementation", "api", "compileOnly", "runtimeOnly", "testImplementation"] else "implementation"
                new_deps.append(f"    // {dep.description}: {dep.reason}")
                new_deps.append(f"    {scope} '{dep.group_id}:{dep.artifact_id}:{dep.version}'")
                added_count += 1
            
            # 插入新依赖
            updated_deps = existing_deps[:-1] + "\n" + "\n".join(new_deps) + "\n}"
            content = content.replace(existing_deps, updated_deps)
        else:
            # 创建新的dependencies块
            new_deps_section = ["dependencies {"]
            for dep in dependencies:
                scope = dep.scope if dep.scope in ["implementation", "api", "compileOnly", "runtimeOnly", "testImplementation"] else "implementation"
                new_deps_section.append(f"    // {dep.description}: {dep.reason}")
                new_deps_section.append(f"    {scope} '{dep.group_id}:{dep.artifact_id}:{dep.version}'")
                added_count += 1
            new_deps_section.append("}")
            
            # 添加到文件末尾
            content = content.rstrip() + "\n\n" + "\n".join(new_deps_section) + "\n"
        
        # 写回文件
        with open(gradle_file, 'w', encoding='utf-8') as f:
            f.write(content)
        
        return added_count
