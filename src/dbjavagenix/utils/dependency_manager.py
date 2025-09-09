#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
整合依赖管理器
统一管理依赖检查、分析、自动添加和修复功能
"""

from typing import Dict, List, Optional, Any
from pathlib import Path
import xml.etree.ElementTree as ET

# 移除对dependency_checker的引用，因为我们已经删除了这个文件
# from .dependency_checker import JavaDependencyChecker
from .pom_analyzer import PomAnalyzer
from .auto_dependency_manager import AutoDependencyManager
from .dependency_requirements import DependencyRequirements


class DependencyManager:
    """整合依赖管理器"""
    
    def __init__(self):
        # 移除对checker的初始化
        # self.checker = JavaDependencyChecker()
        self.analyzer = PomAnalyzer()
        self.auto_manager = AutoDependencyManager()
        self.requirements = DependencyRequirements()
    
    def check_and_fix_dependencies(self, project_root: str, template_category: str, 
                                 database_type: str, **kwargs) -> Dict[str, Any]:
        """
        检查并自动修复项目依赖
        
        Args:
            project_root: 项目根目录
            template_category: 模板类别
            database_type: 数据库类型
            **kwargs: 其他参数 (include_swagger, include_lombok, include_mapstruct等)
            
        Returns:
            检查和修复结果
        """
        project_path = Path(project_root)
        
        # 1. 分析项目依赖状况
        analysis_result = self.analyzer.analyze_project_dependencies(
            project_root=project_root,
            template_category=template_category,
            database_type=database_type,
            include_swagger=kwargs.get("include_swagger", True),
            include_lombok=kwargs.get("include_lombok", True),
            include_mapstruct=kwargs.get("include_mapstruct", True)
        )
        
        # 2. 检查用户现有依赖
        build_tool = analysis_result["build_tool"]
        detected_deps = {}
        pom_content = None
        gradle_content = None
        
        if build_tool == "maven":
            pom_file = project_path / "pom.xml"
            if pom_file.exists():
                with open(pom_file, 'r', encoding='utf-8') as f:
                    pom_content = f.read()
                # 使用pom_analyzer来检测现有依赖
                existing_deps = self.analyzer._parse_pom_file(pom_file)
                # 转换为字典格式
                for dep in existing_deps:
                    key = f"{dep.group_id}:{dep.artifact_id}"
                    detected_deps[key] = {
                        "group_id": dep.group_id,
                        "artifact_id": dep.artifact_id,
                        "version": dep.version or "未指定",
                        "scope": dep.scope
                    }
            else:
                detected_deps = {}
        elif build_tool == "gradle":
            gradle_file = project_path / "build.gradle"
            if not gradle_file.exists():
                gradle_file = project_path / "build.gradle.kts"
            if gradle_file.exists():
                with open(gradle_file, 'r', encoding='utf-8') as f:
                    gradle_content = f.read()
                # 使用pom_analyzer来检测现有依赖
                existing_deps = self.analyzer._parse_gradle_file(gradle_file)
                # 转换为字典格式
                for dep in existing_deps:
                    key = f"{dep.group_id}:{dep.artifact_id}"
                    detected_deps[key] = {
                        "group_id": dep.group_id,
                        "artifact_id": dep.artifact_id,
                        "version": dep.version or "未指定",
                        "scope": dep.scope
                    }
            else:
                detected_deps = {}
        else:
            detected_deps = {}
        
        # 3. 验证用户依赖是否合适
        validation_result = self._validate_user_dependencies(detected_deps)
        
        # 4. 自动添加缺失的依赖
        auto_add_result = self.analyzer.auto_add_missing_dependencies(
            project_root=project_root,
            comparison_results=analysis_result["comparison_results"]
        )
        
        # 5. 自动修复过时依赖
        fix_result = {"success": True, "message": "无过时依赖需要修复"}
        if validation_result["deprecated"]:
            if build_tool == "maven" and pom_content:
                fix_result = self._auto_fix_deprecated_dependencies(
                    project_root=project_root,
                    pom_content=pom_content
                )
            elif build_tool == "gradle" and gradle_content:
                fix_result = self._auto_fix_deprecated_dependencies(
                    project_root=project_root,
                    gradle_content=gradle_content
                )
        
        return {
            "analysis_result": analysis_result,
            "validation_result": validation_result,
            "auto_add_result": auto_add_result,
            "fix_result": fix_result,
            "summary": {
                "build_tool": build_tool,
                "missing_dependencies_added": auto_add_result.get("added_count", 0),
                "deprecated_dependencies_fixed": 1 if fix_result["success"] and "修复" in fix_result["message"] else 0,
                "validation_warnings": len(validation_result["deprecated"]) + len(validation_result["incompatible"])
            }
        }
    
    def get_dependency_health_report(self, project_root: str) -> Dict[str, Any]:
        """
        获取依赖健康报告
        
        Args:
            project_root: 项目根目录
            
        Returns:
            依赖健康报告
        """
        # 使用PomAnalyzer来检查项目依赖
        analysis_result = self.analyzer.analyze_project_dependencies(
            project_root=project_root,
            template_category="MybatisPlus-Mixed",  # 使用默认模板类别
            database_type="mysql"  # 使用默认数据库类型
        )
        
        # 从分析结果中提取健康信息
        comparison_results = analysis_result["comparison_results"]
        
        # 统计信息
        total_requirements = len(comparison_results)
        missing_count = len([c for c in comparison_results if c.status == "missing"])
        outdated_count = len([c for c in comparison_results if c.status == "outdated"])
        deprecated_count = len([c for c in comparison_results if c.status == "deprecated"])
        exists_count = total_requirements - missing_count - outdated_count - deprecated_count
        
        # 计算健康分数
        health_score = max(0, 100 - (missing_count * 10 + outdated_count * 5 + deprecated_count * 5))
        
        report = {
            "project_path": project_root,
            "build_tool": analysis_result["build_tool"],
            "total_dependencies": total_requirements,
            "found_dependencies": exists_count,
            "missing_required": missing_count,
            "missing_optional": 0,  # 在新的分析中不区分必需和可选
            "health_score": health_score,
            "issues": []
        }
        
        # 添加问题列表
        if missing_count > 0:
            report["issues"].append({
                "type": "missing_required",
                "count": missing_count,
                "description": "缺少必需依赖"
            })
        
        if outdated_count > 0:
            report["issues"].append({
                "type": "version_warnings",
                "count": outdated_count,
                "description": "依赖版本过时"
            })
        
        if deprecated_count > 0:
            report["issues"].append({
                "type": "deprecated_warnings",
                "count": deprecated_count,
                "description": "使用了过时依赖"
            })
        
        return report
    
    def generate_migration_guide(self, project_root: str) -> Dict[str, Any]:
        """
        生成依赖迁移指南
        
        Args:
            project_root: 项目根目录
            
        Returns:
            迁移指南
        """
        project_path = Path(project_root)
        build_tool = self._detect_build_tool(project_path)
        
        if not build_tool:
            return {
                "success": False,
                "message": "未检测到构建工具"
            }
        
        # 获取现有依赖
        detected_deps = {}
        if build_tool == "maven":
            pom_file = project_path / "pom.xml"
            if pom_file.exists():
                existing_deps = self.analyzer._parse_pom_file(pom_file)
                # 转换为字典格式
                for dep in existing_deps:
                    key = f"{dep.group_id}:{dep.artifact_id}"
                    detected_deps[key] = {
                        "group_id": dep.group_id,
                        "artifact_id": dep.artifact_id,
                        "version": dep.version or "未指定",
                        "scope": dep.scope
                    }
            else:
                return {
                    "success": False,
                    "message": "pom.xml文件不存在"
                }
        elif build_tool == "gradle":
            gradle_file = project_path / "build.gradle"
            if not gradle_file.exists():
                gradle_file = project_path / "build.gradle.kts"
            if gradle_file.exists():
                existing_deps = self.analyzer._parse_gradle_file(gradle_file)
                # 转换为字典格式
                for dep in existing_deps:
                    key = f"{dep.group_id}:{dep.artifact_id}"
                    detected_deps[key] = {
                        "group_id": dep.group_id,
                        "artifact_id": dep.artifact_id,
                        "version": dep.version or "未指定",
                        "scope": dep.scope
                    }
            else:
                return {
                    "success": False,
                    "message": "build.gradle文件不存在"
                }
        else:
            return {
                "success": False,
                "message": f"不支持的构建工具: {build_tool}"
            }
        
        # 验证依赖并生成迁移建议
        validation_result = self._validate_user_dependencies(detected_deps)
        migration_suggestions = validation_result["deprecated"]
        
        return {
            "success": True,
            "build_tool": build_tool,
            "migration_suggestions": migration_suggestions,
            "total_suggestions": len(migration_suggestions)
        }
    
    def _detect_build_tool(self, project_root: Path) -> Optional[str]:
        """检测构建工具类型"""
        if (project_root / "pom.xml").exists():
            return "maven"
        elif (project_root / "build.gradle").exists() or (project_root / "build.gradle.kts").exists():
            return "gradle"
        return None
    
    def _validate_user_dependencies(self, detected_deps: Dict[str, Dict[str, str]]) -> Dict[str, List[str]]:
        """
        验证用户已定义的依赖是否合适
        
        Args:
            detected_deps: 用户已定义的依赖
            
        Returns:
            验证结果，包括过时依赖、版本不兼容等警告
        """
        validation_results = {
            "deprecated": [],      # 过时依赖
            "incompatible": [],    # 版本不兼容
            "conflicting": [],     # 冲突依赖
            "suggestions": []      # 建议
        }
        
        # 过时依赖映射
        DEPRECATED_MAPPINGS = {
            "javax.annotation:javax.annotation-api": "jakarta.annotation:jakarta.annotation-api",
            "javax.validation:validation-api": "jakarta.validation:jakarta.validation-api",
            "io.swagger:swagger-annotations": "org.springdoc:springdoc-openapi-starter-webmvc-ui"
        }
        
        for key, dep in detected_deps.items():
            # 检查是否为过时依赖
            if key in DEPRECATED_MAPPINGS:
                validation_results["deprecated"].append({
                    "dependency": f"{dep['group_id']}:{dep['artifact_id']}:{dep['version']}",
                    "recommendation": f"建议迁移到 {DEPRECATED_MAPPINGS[key]}"
                })
            
            # 检查javax到jakarta的迁移问题
            if "javax.annotation" in key:
                validation_results["deprecated"].append({
                    "dependency": f"{dep['group_id']}:{dep['artifact_id']}:{dep['version']}",
                    "recommendation": "建议迁移到 jakarta.annotation:jakarta.annotation-api"
                })
            
            if "javax.validation" in key:
                validation_results["deprecated"].append({
                    "dependency": f"{dep['group_id']}:{dep['artifact_id']}:{dep['version']}",
                    "recommendation": "建议迁移到 jakarta.validation:jakarta.validation-api"
                })
            
            # 检查Swagger 2.x到OpenAPI 3.0的迁移
            if "io.swagger" in key:
                validation_results["deprecated"].append({
                    "dependency": f"{dep['group_id']}:{dep['artifact_id']}:{dep['version']}",
                    "recommendation": "建议迁移到 org.springdoc:springdoc-openapi-starter-webmvc-ui"
                })
        
        return validation_results
    
    def _auto_fix_deprecated_dependencies(self, project_root: str, pom_content: str = None, 
                                       gradle_content: str = None) -> Dict[str, any]:
        """
        自动修复过时依赖
        
        Args:
            project_root: 项目路径
            pom_content: pom.xml内容
            gradle_content: build.gradle内容
            
        Returns:
            修复结果
        """
        try:
            if pom_content:
                return self._fix_maven_deprecated_deps(project_root, pom_content)
            elif gradle_content:
                return self._fix_gradle_deprecated_deps(project_root, gradle_content)
            else:
                return {
                    "success": False,
                    "message": "未提供构建文件内容"
                }
        except Exception as e:
            return {
                "success": False,
                "message": f"修复依赖失败: {str(e)}"
            }
    
    def _fix_maven_deprecated_deps(self, project_root: str, pom_content: str) -> Dict[str, any]:
        """修复Maven过时依赖"""
        updated_content = pom_content
        
        # 过时依赖映射
        DEPRECATED_MAPPINGS = {
            "javax.annotation:javax.annotation-api": "jakarta.annotation:jakarta.annotation-api",
            "javax.validation:validation-api": "jakarta.validation:jakarta.validation-api",
            "io.swagger:swagger-annotations": "org.springdoc:springdoc-openapi-starter-webmvc-ui"
        }
        
        # 替换过时依赖
        for old_dep, new_dep in DEPRECATED_MAPPINGS.items():
            old_group, old_artifact = old_dep.split(":")
            new_group, new_artifact = new_dep.split(":")
            
            # 查找并替换groupId和artifactId
            updated_content = re.sub(
                f'<groupId>{re.escape(old_group)}</groupId>\s*<artifactId>{re.escape(old_artifact)}</artifactId>',
                f'<groupId>{new_group}</groupId>\n            <artifactId>{new_artifact}</artifactId>',
                updated_content,
                flags=re.MULTILINE
            )
        
        # 特殊处理javax到jakarta的迁移
        updated_content = re.sub(
            r'<groupId>javax\.annotation</groupId>\s*<artifactId>javax\.annotation-api</artifactId>',
            '<groupId>jakarta.annotation</groupId>\n            <artifactId>jakarta.annotation-api</artifactId>',
            updated_content,
            flags=re.MULTILINE
        )
        
        updated_content = re.sub(
            r'<groupId>javax\.validation</groupId>\s*<artifactId>validation-api</artifactId>',
            '<groupId>jakarta.validation</groupId>\n            <artifactId>jakarta.validation-api</artifactId>',
            updated_content,
            flags=re.MULTILINE
        )
        
        # 写回文件
        pom_file = Path(project_root) / "pom.xml"
        with open(pom_file, 'w', encoding='utf-8') as f:
            f.write(updated_content)
        
        return {
            "success": True,
            "message": "成功修复过时依赖"
        }
    
    def _fix_gradle_deprecated_deps(self, project_root: str, gradle_content: str) -> Dict[str, any]:
        """修复Gradle过时依赖"""
        updated_content = gradle_content
        
        # 过时依赖映射
        DEPRECATED_MAPPINGS = {
            "javax.annotation:javax.annotation-api": "jakarta.annotation:jakarta.annotation-api",
            "javax.validation:validation-api": "jakarta.validation:jakarta.validation-api",
            "io.swagger:swagger-annotations": "org.springdoc:springdoc-openapi-starter-webmvc-ui"
        }
        
        # 替换过时依赖
        for old_dep, new_dep in DEPRECATED_MAPPINGS.items():
            old_group, old_artifact = old_dep.split(":")
            new_group, new_artifact = new_dep.split(":")
            
            # 查找并替换依赖声明
            updated_content = re.sub(
                f"['\"]{re.escape(old_group)}:{re.escape(old_artifact)}:",
                f"'{new_group}:{new_artifact}:",
                updated_content
            )
        
        # 特殊处理javax到jakarta的迁移
        updated_content = re.sub(
            r"['\"]javax\.annotation:javax\.annotation-api:",
            "'jakarta.annotation:jakarta.annotation-api:",
            updated_content
        )
        
        updated_content = re.sub(
            r"['\"]javax\.validation:validation-api:",
            "'jakarta.validation:jakarta.validation-api:",
            updated_content
        )
        
        # 写回文件
        gradle_file = Path(project_root) / "build.gradle"
        if not gradle_file.exists():
            gradle_file = Path(project_root) / "build.gradle.kts"
        
        with open(gradle_file, 'w', encoding='utf-8') as f:
            f.write(updated_content)
        
        return {
            "success": True,
            "message": "成功修复过时依赖"
        }


# 使用示例
if __name__ == "__main__":
    # 创建依赖管理器实例
    manager = DependencyManager()
    
    # 示例：检查并修复依赖
    # result = manager.check_and_fix_dependencies(
    #     project_root="./test-project",
    #     template_category="MybatisPlus",
    #     database_type="mysql"
    # )
    # print(result)
    pass