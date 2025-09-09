#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
智能依赖自动添加器
自动添加缺失的Maven/Gradle依赖到构建文件中
"""

import os
import re
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional, Tuple, Set
from pathlib import Path
from dataclasses import dataclass
from .dependency_requirements import DependencyInfo


@dataclass
class DependencyAddResult:
    """依赖添加结果"""
    success: bool
    added_dependencies: List[DependencyInfo]
    skipped_dependencies: List[Dict[str, str]]  # 已存在的依赖
    errors: List[str]
    backup_file: Optional[str] = None  # 备份文件路径


class AutoDependencyManager:
    """自动依赖管理器"""
    
    def __init__(self):
        self.maven_namespaces = {
            'maven': 'http://maven.apache.org/POM/4.0.0'
        }
    
    def add_dependencies_to_project(self, 
                                   project_path: str,
                                   dependencies: List[DependencyInfo],
                                   create_backup: bool = True,
                                   dry_run: bool = False) -> DependencyAddResult:
        """
        向项目中添加依赖
        
        Args:
            project_path: 项目路径
            dependencies: 要添加的依赖列表
            create_backup: 是否创建备份
            dry_run: 是否只是预演（不实际修改文件）
            
        Returns:
            依赖添加结果
        """
        project_path = Path(project_path)
        
        if not project_path.exists():
            return DependencyAddResult(
                success=False,
                added_dependencies=[],
                skipped_dependencies=[],
                errors=[f"项目路径不存在: {project_path}"]
            )
        
        # 检测构建工具
        build_tool = self._detect_build_tool(project_path)
        
        if not build_tool:
            return DependencyAddResult(
                success=False,
                added_dependencies=[],
                skipped_dependencies=[],
                errors=["未检测到Maven或Gradle构建工具"]
            )
        
        # 根据构建工具添加依赖
        if build_tool == "maven":
            return self._add_maven_dependencies(project_path, dependencies, create_backup, dry_run)
        elif build_tool == "gradle":
            return self._add_gradle_dependencies(project_path, dependencies, create_backup, dry_run)
        else:
            return DependencyAddResult(
                success=False,
                added_dependencies=[],
                skipped_dependencies=[],
                errors=[f"不支持的构建工具: {build_tool}"]
            )
    
    def _detect_build_tool(self, project_path: Path) -> Optional[str]:
        """检测构建工具类型"""
        if (project_path / "pom.xml").exists():
            return "maven"
        elif (project_path / "build.gradle").exists() or (project_path / "build.gradle.kts").exists():
            return "gradle"
        return None
    
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
                new_deps.append(f"    <dependency>")
                new_deps.append(f"        <groupId>{dep.group_id}</groupId>")
                new_deps.append(f"        <artifactId>{dep.artifact_id}</artifactId>")
                new_deps.append(f"        <version>{dep.version}</version>")
                if dep.scope != "compile":
                    new_deps.append(f"        <scope>{dep.scope}</scope>")
                new_deps.append(f"    </dependency>")
                added_count += 1
            
            # 正确地重新组装dependencies块
            updated_deps_block = start_tag
            if existing_content.strip():  # 如果已有内容，保留现有内容
                updated_deps_block += existing_content
                if not existing_content.endswith('\n'):
                    updated_deps_block += "\n"
                if new_deps:  # 如果有新依赖要添加
                    updated_deps_block += "\n".join(new_deps) + "\n    "
            else:  # 如果没有内容，直接添加新依赖
                if new_deps:
                    updated_deps_block += "\n" + "\n".join(new_deps) + "\n    "
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
                new_deps_section.append(f"    <dependency>")
                new_deps_section.append(f"        <groupId>{dep.group_id}</groupId>")
                new_deps_section.append(f"        <artifactId>{dep.artifact_id}</artifactId>")
                new_deps_section.append(f"        <version>{dep.version}</version>")
                if dep.scope != "compile":
                    new_deps_section.append(f"        <scope>{dep.scope}</scope>")
                new_deps_section.append(f"    </dependency>")
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
    
    def _add_maven_dependencies(self, 
                               project_path: Path, 
                               dependencies: List[DependencyInfo],
                               create_backup: bool,
                               dry_run: bool) -> DependencyAddResult:
        """向Maven项目添加依赖 - 使用字符串操作避免XML解析问题"""
        pom_file = project_path / "pom.xml"
        backup_file = None
        
        try:
            # 1. 读取现有pom.xml内容
            with open(pom_file, 'r', encoding='utf-8') as f:
                pom_content = f.read()
            
            # 2. 解析现有依赖（用于检查重复）
            existing_deps = self._parse_existing_dependencies_from_content(pom_content)
            added_dependencies = []
            skipped_dependencies = []
            
            # 3. 过滤需要添加的依赖
            for dep in dependencies:
                dep_key = f"{dep.group_id}:{dep.artifact_id}"
                
                if dep_key in existing_deps:
                    skipped_dependencies.append({
                        "dependency": dep_key,
                        "reason": f"已存在版本: {existing_deps[dep_key]}",
                        "current_version": existing_deps[dep_key],
                        "requested_version": dep.version
                    })
                else:
                    added_dependencies.append(dep)
            
            # 4. 如果没有需要添加的依赖
            if not added_dependencies:
                return DependencyAddResult(
                    success=True,
                    added_dependencies=[],
                    skipped_dependencies=skipped_dependencies,
                    errors=[]
                )
            
            # 5. 如果是dry run，直接返回结果
            if dry_run:
                return DependencyAddResult(
                    success=True,
                    added_dependencies=added_dependencies,
                    skipped_dependencies=skipped_dependencies,
                    errors=[]
                )
            
            # 6. 创建备份
            if create_backup:
                backup_file = self._create_backup(pom_file)
            
            # 7. 使用字符串操作添加依赖
            new_pom_content = self._insert_dependencies_string_based(pom_content, added_dependencies)
            
            # 8. 保存文件
            with open(pom_file, 'w', encoding='utf-8') as f:
                f.write(new_pom_content)
            
            return DependencyAddResult(
                success=True,
                added_dependencies=added_dependencies,
                skipped_dependencies=skipped_dependencies,
                errors=[],
                backup_file=str(backup_file) if backup_file else None
            )
            
        except Exception as e:
            return DependencyAddResult(
                success=False,
                added_dependencies=[],
                skipped_dependencies=[],
                errors=[f"Maven依赖添加失败: {e}"],
                backup_file=str(backup_file) if backup_file else None
            )
    
    def _add_gradle_dependencies(self, 
                                project_path: Path, 
                                dependencies: List[DependencyInfo],
                                create_backup: bool,
                                dry_run: bool) -> DependencyAddResult:
        """向Gradle项目添加依赖"""
        gradle_files = []
        
        # 查找Gradle构建文件
        if (project_path / "build.gradle").exists():
            gradle_files.append(project_path / "build.gradle")
        if (project_path / "build.gradle.kts").exists():
            gradle_files.append(project_path / "build.gradle.kts")
        
        if not gradle_files:
            return DependencyAddResult(
                success=False,
                added_dependencies=[],
                skipped_dependencies=[],
                errors=["未找到build.gradle文件"]
            )
        
        # 优先使用build.gradle
        gradle_file = gradle_files[0]
        backup_file = None
        
        try:
            # 1. 读取现有build.gradle
            with open(gradle_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 2. 检查现有依赖
            existing_deps = self._get_existing_gradle_dependencies(content)
            added_dependencies = []
            skipped_dependencies = []
            
            # 3. 过滤需要添加的依赖
            for dep in dependencies:
                dep_key = f"{dep.group_id}:{dep.artifact_id}"
                
                if dep_key in existing_deps:
                    skipped_dependencies.append({
                        "dependency": dep_key,
                        "reason": f"已存在版本: {existing_deps[dep_key]}",
                        "current_version": existing_deps[dep_key],
                        "requested_version": dep.version
                    })
                else:
                    added_dependencies.append(dep)
            
            # 4. 如果没有需要添加的依赖
            if not added_dependencies:
                return DependencyAddResult(
                    success=True,
                    added_dependencies=[],
                    skipped_dependencies=skipped_dependencies,
                    errors=[]
                )
            
            # 5. 如果是dry run，直接返回结果
            if dry_run:
                return DependencyAddResult(
                    success=True,
                    added_dependencies=added_dependencies,
                    skipped_dependencies=skipped_dependencies,
                    errors=[]
                )
            
            # 6. 创建备份
            if create_backup:
                backup_file = self._create_backup(gradle_file)
            
            # 7. 添加新依赖到build.gradle
            new_content = self._insert_gradle_dependencies(content, added_dependencies)
            
            # 8. 保存文件
            with open(gradle_file, 'w', encoding='utf-8') as f:
                f.write(new_content)
            
            return DependencyAddResult(
                success=True,
                added_dependencies=added_dependencies,
                skipped_dependencies=skipped_dependencies,
                errors=[],
                backup_file=str(backup_file) if backup_file else None
            )
            
        except Exception as e:
            return DependencyAddResult(
                success=False,
                added_dependencies=[],
                skipped_dependencies=[],
                errors=[f"Gradle依赖添加失败: {e}"],
                backup_file=str(backup_file) if backup_file else None
            )
    
    def _parse_existing_dependencies_from_content(self, pom_content: str) -> Dict[str, str]:
        """从POM内容字符串中解析现有依赖"""
        existing_deps = {}
        
        # 使用正则表达式匹配依赖块
        dependency_pattern = r'<dependency>\s*\n?\s*<groupId>([^<]+)</groupId>\s*\n?\s*<artifactId>([^<]+)</artifactId>(?:\s*\n?\s*<version>([^<]+)</version>)?'
        
        matches = re.findall(dependency_pattern, pom_content, re.MULTILINE | re.DOTALL)
        
        for group_id, artifact_id, version in matches:
            key = f"{group_id.strip()}:{artifact_id.strip()}"
            existing_deps[key] = version.strip() if version else "未指定"
        
        return existing_deps
    
    def _has_xml_syntax_errors(self, content: str) -> bool:
        """检查XML内容是否有语法错误"""
        
        # 检查常见的XML语法错误
        error_patterns = [
            r'<\s*$',           # 断开的开始标签，如 '<'
            r'</\s*$',          # 断开的结束标签，如 '</'
            r'<\s+[^>]*$',      # 不完整的标签
            r'</\s+$',          # 断开的结束标签，如 '</ '
        ]
        
        for pattern in error_patterns:
            if re.search(pattern, content, re.MULTILINE):
                return True
        
        # 尝试用ElementTree验证（更严格的检查）
        try:
            import xml.etree.ElementTree as ET
            ET.fromstring(content)
            return False
        except ET.ParseError:
            return True
        except Exception:
            # 如果有其他异常，也认为是有问题的
            return True
    
    def _fix_common_xml_errors(self, content: str) -> str:
        """自动修复常见的XML语法错误"""
        
        # 修复断开的标签，如 "</"
        # 更精确地查找这种情况并尝试修复
        patterns_fixes = [
            # 修复孤立的 "</  " 或 "</" 行，通常这应该是 "</dependencies>"
            (r'^\s*</\s*$', ''),  # 直接删除孤立的 "</" 行
            (r'^\s*</\s*\n', ''),  # 删除 "</" 后跟换行的情况
            
            # 修复在dependencies上下文中的断开标签
            (r'(\s+)</\s*(?=\s*<!--.*依赖)', r'\1</dependencies>\n\1<!-- 修复断开的dependencies标签 -->\n\1'),
            
            # 修复 "    < " 等断开的开始标签
            (r'^\s*<\s*$', ''),
            (r'^\s*<\s*\n', ''),
            
            # 清理重复的注释
            (r'(<!-- 下方是我们添加的依赖 -->\s*){2,}', r'\1'),
            (r'(<!-- DBJavaGenix 自动添加的依赖 -->\s*){2,}', r'\1'),
        ]
        
        for pattern, replacement in patterns_fixes:
            content = re.sub(pattern, replacement, content, flags=re.MULTILINE)
        
        # 清理重复的依赖块
        content = self._remove_duplicate_dependency_sections(content)
        
        return content
    
    def _remove_duplicate_dependency_sections(self, content: str) -> str:
        """移除重复的依赖块"""
        
        # 查找所有独立的依赖块（在</dependencies>之后还有依赖的情况）
        # 这种情况下，我们需要将这些依赖合并到主要的dependencies块中
        
        # 首先找到主要的dependencies块
        main_deps_pattern = r'(<dependencies>.*?</dependencies>)'
        main_deps_match = re.search(main_deps_pattern, content, re.DOTALL)
        
        if not main_deps_match:
            return content
        
        main_deps_block = main_deps_match.group(1)
        main_deps_end = main_deps_match.end()
        
        # 查找main dependencies块之后的依赖
        remaining_content = content[main_deps_end:]
        orphan_deps_pattern = r'<!-- [^>]+ -->\s*<dependency>.*?</dependency>'
        orphan_matches = re.findall(orphan_deps_pattern, remaining_content, re.DOTALL)
        
        if orphan_matches:
            # 将孤立的依赖合并到主要的dependencies块中
            orphan_deps_text = '\n        '.join(orphan_matches)
            
            # 在主要dependencies块的</dependencies>前插入孤立的依赖
            new_main_block = main_deps_block.replace(
                '</dependencies>',
                f'\n        {orphan_deps_text}\n    </dependencies>'
            )
            
            # 移除孤立的依赖
            for orphan in orphan_matches:
                remaining_content = remaining_content.replace(orphan, '', 1)
            
            # 重新组装内容
            content = content[:main_deps_match.start()] + new_main_block + remaining_content
        
        return content
    
    def _insert_dependencies_string_based(self, pom_content: str, dependencies: List[DependencyInfo]) -> str:
        """使用字符串操作插入依赖到POM内容中 - 修复版"""
        
        # 首先尝试修复常见的XML语法错误
        pom_content = self._fix_common_xml_errors(pom_content)
        
        # 再次检查是否还有语法错误
        if self._has_xml_syntax_errors(pom_content):
            raise Exception("POM文件存在复杂的XML语法错误，无法自动修复，请手动修复后再添加依赖")
        
        # 查找完整的 </dependencies> 标签
        dependencies_end_pattern = r'(\s*)</dependencies>\s*'
        dependencies_end_match = re.search(dependencies_end_pattern, pom_content, re.MULTILINE)
        
        if not dependencies_end_match:
            # 如果没有找到完整的 </dependencies>，这可能意味着：
            # 1. dependencies块没有正确关闭
            # 2. 完全没有dependencies块
            
            dependencies_start_pattern = r'<dependencies>\s*'
            dependencies_start_match = re.search(dependencies_start_pattern, pom_content)
            
            if dependencies_start_match:
                # 存在<dependencies>开始标签但没有</dependencies>结束标签
                # 我们需要在合适的位置插入依赖并添加结束标签
                
                # 查找最后一个</dependency>的位置
                last_dependency_pattern = r'</dependency>(\s*?)(?!.*</dependency>)'
                last_dependency_match = re.search(last_dependency_pattern, pom_content, re.DOTALL)
                
                if last_dependency_match:
                    # 在最后一个</dependency>后插入新依赖和</dependencies>
                    insert_pos = last_dependency_match.end()
                    new_dependencies_xml = self._generate_dependencies_xml(dependencies)
                    
                    return (pom_content[:insert_pos] + 
                            "\n\n        <!-- DBJavaGenix 自动添加的依赖 -->\n" +
                            new_dependencies_xml +
                            "\n    </dependencies>" +
                            pom_content[insert_pos:])
                else:
                    # <dependencies>后面没有任何dependency，直接在其后插入
                    insert_pos = dependencies_start_match.end()
                    new_dependencies_xml = self._generate_dependencies_xml(dependencies)
                    
                    return (pom_content[:insert_pos] + 
                            "\n        <!-- DBJavaGenix 自动添加的依赖 -->\n" +
                            new_dependencies_xml +
                            "\n    </dependencies>\n" +
                            pom_content[insert_pos:])
            else:
                # 完全没有dependencies块，创建新的
                project_end_pattern = r'(\s*)</project>'
                project_end_match = re.search(project_end_pattern, pom_content)
                
                if project_end_match:
                    dependencies_block = self._generate_dependencies_block(dependencies)
                    insert_pos = project_end_match.start()
                    return pom_content[:insert_pos] + dependencies_block + "\n\n" + pom_content[insert_pos:]
                else:
                    raise Exception("无法找到合适的位置插入依赖")
        
        # 在现有正确的dependencies块中添加新依赖
        new_dependencies_xml = self._generate_dependencies_xml(dependencies)
        
        # 在 </dependencies> 前插入新依赖
        insert_pos = dependencies_end_match.start()
        indent = dependencies_end_match.group(1)  # 保持相同的缩进
        
        return (pom_content[:insert_pos] + 
                "\n" + indent + "<!-- DBJavaGenix 自动添加的依赖 -->\n" +
                new_dependencies_xml +
                pom_content[insert_pos:])
    
    def _generate_dependencies_block(self, dependencies: List[DependencyInfo]) -> str:
        """生成完整的dependencies块"""
        lines = [
            "    <dependencies>",
            "        <!-- DBJavaGenix 自动添加的依赖 -->"
        ]
        
        for dep in dependencies:
            lines.extend(self._generate_single_dependency_lines(dep, "        "))
        
        lines.append("    </dependencies>")
        return "\n".join(lines)
    
    def _generate_dependencies_xml(self, dependencies: List[DependencyInfo]) -> str:
        """生成依赖XML字符串"""
        lines = []
        
        for dep in dependencies:
            lines.extend(self._generate_single_dependency_lines(dep, "        "))
        
        return "\n".join(lines)
    
    def _generate_single_dependency_lines(self, dep: DependencyInfo, indent: str) -> List[str]:
        """生成单个依赖的XML行"""
        lines = [
            f"{indent}<!-- {dep.description}: {dep.reason} -->",
            f"{indent}<dependency>",
            f"{indent}    <groupId>{dep.group_id}</groupId>",
            f"{indent}    <artifactId>{dep.artifact_id}</artifactId>",
            f"{indent}    <version>{dep.version}</version>"
        ]
        
        if dep.scope != "compile":
            lines.append(f"{indent}    <scope>{dep.scope}</scope>")
        
        lines.append(f"{indent}</dependency>")
        return lines
    
    def _get_existing_maven_dependencies(self, root: ET.Element) -> Dict[str, str]:
        """获取现有Maven依赖"""
        existing_deps = {}
        
        # 查找dependencies节点 - 修复命名空间问题
        deps_elem = None
        for elem in root.iter():
            if elem.tag.endswith('dependencies') or elem.tag == 'dependencies':
                deps_elem = elem
                break
        
        if deps_elem is not None:
            # 查找所有dependency子元素
            for dep_elem in deps_elem:
                if dep_elem.tag.endswith('dependency') or dep_elem.tag == 'dependency':
                    group_id = None
                    artifact_id = None
                    version = None
                    
                    # 查找groupId, artifactId, version子元素
                    for child in dep_elem:
                        if child.tag.endswith('groupId') or child.tag == 'groupId':
                            group_id = child.text
                        elif child.tag.endswith('artifactId') or child.tag == 'artifactId':
                            artifact_id = child.text
                        elif child.tag.endswith('version') or child.tag == 'version':
                            version = child.text
                    
                    if group_id and artifact_id:
                        key = f"{group_id}:{artifact_id}"
                        existing_deps[key] = version or "未指定"
        
        return existing_deps
    
    def _get_existing_gradle_dependencies(self, content: str) -> Dict[str, str]:
        """获取现有Gradle依赖"""
        existing_deps = {}
        
        # 匹配Gradle依赖声明
        dependency_pattern = r"(implementation|api|compileOnly|runtimeOnly|testImplementation)\s+['\"]([^:]+):([^:]+):?([^'\"]*)['\"]"
        matches = re.findall(dependency_pattern, content, re.MULTILINE)
        
        for scope, group_id, artifact_id, version in matches:
            key = f"{group_id.strip()}:{artifact_id.strip()}"
            existing_deps[key] = version.strip() if version else "未指定"
        
        return existing_deps
    
    def _insert_maven_dependencies(self, root: ET.Element, dependencies: List[DependencyInfo]):
        """插入Maven依赖到pom.xml"""
        
        # 查找现有dependencies节点 - 修复命名空间查找
        deps_elem = None
        
        # 尝试不同的方式查找dependencies节点
        for elem in root.iter():
            if elem.tag.endswith('dependencies') or elem.tag == 'dependencies':
                deps_elem = elem
                break
        
        if deps_elem is None:
            # 如果没有找到dependencies节点，创建一个新的
            deps_elem = ET.SubElement(root, 'dependencies')
        
        # 添加分隔注释说明这些是自动添加的依赖
        if dependencies:
            comment_text = " DBJavaGenix 自动添加的依赖 "
            try:
                comment = ET.Comment(comment_text)
                deps_elem.append(comment)
            except:
                # 如果添加注释失败，继续处理
                pass
        
        # 添加新依赖
        for dep in dependencies:
            # 为每个依赖添加注释
            try:
                dep_comment = ET.Comment(f" {dep.description} ")
                deps_elem.append(dep_comment)
            except:
                pass
            
            # 创建dependency元素
            dep_elem = ET.SubElement(deps_elem, 'dependency')
            
            # 添加依赖元素
            group_id_elem = ET.SubElement(dep_elem, 'groupId')
            group_id_elem.text = dep.group_id
            
            artifact_id_elem = ET.SubElement(dep_elem, 'artifactId')  
            artifact_id_elem.text = dep.artifact_id
            
            version_elem = ET.SubElement(dep_elem, 'version')
            version_elem.text = dep.version
            
            # 添加scope（如果不是compile）
            if dep.scope != "compile":
                scope_elem = ET.SubElement(dep_elem, 'scope')
                scope_elem.text = dep.scope
    
    def _insert_gradle_dependencies(self, content: str, dependencies: List[DependencyInfo]) -> str:
        """插入Gradle依赖到build.gradle"""
        
        # 找到dependencies块
        deps_pattern = r'(dependencies\s*\{[^}]*\})'
        deps_match = re.search(deps_pattern, content, re.DOTALL)
        
        if deps_match:
            # 在现有dependencies块中添加
            deps_block = deps_match.group(1)
            
            # 生成新依赖文本
            new_deps_lines = []
            for dep in dependencies:
                scope_mapping = {
                    "compile": "implementation",
                    "provided": "compileOnly",
                    "test": "testImplementation", 
                    "runtime": "runtimeOnly"
                }
                
                gradle_scope = scope_mapping.get(dep.scope, "implementation")
                new_deps_lines.extend([
                    f"    // {dep.description}",
                    f"    {gradle_scope} '{dep.group_id}:{dep.artifact_id}:{dep.version}'"
                ])
            
            # 在dependencies块末尾添加新依赖
            new_deps_text = "\n" + "\n".join(new_deps_lines)
            new_deps_block = deps_block[:-1] + new_deps_text + "\n}"
            
            content = content.replace(deps_block, new_deps_block)
        else:
            # 创建新的dependencies块
            new_deps_lines = ["dependencies {"]
            for dep in dependencies:
                scope_mapping = {
                    "compile": "implementation",
                    "provided": "compileOnly",
                    "test": "testImplementation",
                    "runtime": "runtimeOnly"
                }
                
                gradle_scope = scope_mapping.get(dep.scope, "implementation")
                new_deps_lines.extend([
                    f"    // {dep.description}",
                    f"    {gradle_scope} '{dep.group_id}:{dep.artifact_id}:{dep.version}'"
                ])
            new_deps_lines.append("}")
            
            # 在文件末尾添加dependencies块
            content += "\n\n" + "\n".join(new_deps_lines) + "\n"
        
        return content
    
    def _create_backup(self, file_path: Path) -> Path:
        """创建备份文件"""
        from datetime import datetime
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = file_path.parent / f"{file_path.stem}_backup_{timestamp}{file_path.suffix}"
        
        import shutil
        shutil.copy2(file_path, backup_file)
        
        return backup_file
    
    def _save_xml_with_formatting(self, tree: ET.ElementTree, file_path: Path):
        """保存格式化的XML文件"""
        # 简单的XML格式化
        self._indent_xml(tree.getroot())
        
        # 保存文件
        tree.write(file_path, encoding='utf-8', xml_declaration=True)
    
    def _indent_xml(self, elem: ET.Element, level: int = 0):
        """XML缩进格式化"""
        i = "\n" + level * "    "
        if len(elem):
            if not elem.text or not elem.text.strip():
                elem.text = i + "    "
            if not elem.tail or not elem.tail.strip():
                elem.tail = i
            for elem in elem:
                self._indent_xml(elem, level + 1)
            if not elem.tail or not elem.tail.strip():
                elem.tail = i
        else:
            if level and (not elem.tail or not elem.tail.strip()):
                elem.tail = i
    
    def validate_dependency_compatibility(self, 
                                        dependencies: List[DependencyInfo],
                                        project_spring_boot_version: Optional[str] = None) -> Dict[str, any]:
        """验证依赖兼容性"""
        
        warnings = []
        errors = []
        suggestions = []
        
        # 检查Spring Boot版本兼容性
        if project_spring_boot_version:
            for dep in dependencies:
                if dep.group_id.startswith("org.springframework.boot"):
                    if dep.version != project_spring_boot_version:
                        warnings.append({
                            "type": "version_mismatch",
                            "dependency": f"{dep.group_id}:{dep.artifact_id}",
                            "requested_version": dep.version,
                            "project_version": project_spring_boot_version,
                            "suggestion": f"建议使用项目的Spring Boot版本: {project_spring_boot_version}"
                        })
        
        # 检查过时依赖
        deprecated_patterns = ["javax.annotation", "javax.validation", "io.swagger"]
        for dep in dependencies:
            if any(pattern in dep.group_id for pattern in deprecated_patterns):
                warnings.append({
                    "type": "deprecated_dependency",
                    "dependency": f"{dep.group_id}:{dep.artifact_id}",
                    "reason": "此依赖已过时，建议迁移到Jakarta EE或现代替代方案"
                })
        
        return {
            "is_valid": len(errors) == 0,
            "warnings": warnings,
            "errors": errors,
            "suggestions": suggestions
        }