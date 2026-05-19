"""
Java项目依赖检查工具测试脚本
"""
import os
import tempfile
from pathlib import Path
import sys

# 添加src到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from dbjavagenix.utils.dependency_manager import DependencyManager
# from dbjavagenix.utils.dependency_checker import JavaDependencyChecker


def create_sample_maven_project():
    """创建示例Maven项目用于测试"""
    temp_dir = tempfile.mkdtemp(prefix="test_maven_")
    pom_content = """<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 
         http://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>
    
    <groupId>com.example</groupId>
    <artifactId>test-project</artifactId>
    <version>1.0.0</version>
    
    <properties>
        <maven.compiler.source>11</maven.compiler.source>
        <maven.compiler.target>11</maven.compiler.target>
    </properties>
    
    <dependencies>
        <!-- Spring Boot基础 -->
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter</artifactId>
            <version>2.7.0</version>
        </dependency>
        
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-web</artifactId>
            <version>2.7.0</version>
        </dependency>
        
        <!-- MyBatis -->
        <dependency>
            <groupId>org.mybatis.spring.boot</groupId>
            <artifactId>mybatis-spring-boot-starter</artifactId>
            <version>2.2.2</version>
        </dependency>
        
        <!-- MySQL驱动 -->
        <dependency>
            <groupId>mysql</groupId>
            <artifactId>mysql-connector-java</artifactId>
            <version>8.0.29</version>
        </dependency>
        
        <!-- Lombok -->
        <dependency>
            <groupId>org.projectlombok</groupId>
            <artifactId>lombok</artifactId>
            <version>1.18.24</version>
            <scope>provided</scope>
        </dependency>
        
        <!-- Swagger -->
        <dependency>
            <groupId>io.springfox</groupId>
            <artifactId>springfox-swagger2</artifactId>
            <version>3.0.0</version>
        </dependency>
    </dependencies>
</project>
"""
    
    pom_path = Path(temp_dir) / "pom.xml"
    with open(pom_path, 'w', encoding='utf-8') as f:
        f.write(pom_content)
    
    return temp_dir


def create_sample_gradle_project():
    """创建示例Gradle项目用于测试"""
    temp_dir = tempfile.mkdtemp(prefix="test_gradle_")
    build_gradle_content = """plugins {
    id 'java'
    id 'org.springframework.boot' version '2.7.0'
    id 'io.spring.dependency-management' version '1.0.11.RELEASE'
}

group = 'com.example'
version = '1.0.0'
sourceCompatibility = '11'

repositories {
    mavenCentral()
}

dependencies {
    // Spring Boot基础
    implementation 'org.springframework.boot:spring-boot-starter'
    implementation 'org.springframework.boot:spring-boot-starter-web'
    
    // MyBatis Plus
    implementation 'com.baomidou:mybatis-plus-boot-starter:3.5.1'
    
    // MySQL驱动
    runtimeOnly 'mysql:mysql-connector-java'
    
    // Lombok
    compileOnly 'org.projectlombok:lombok'
    annotationProcessor 'org.projectlombok:lombok'
    
    // MapStruct
    implementation 'org.mapstruct:mapstruct:1.5.1.Final'
    annotationProcessor 'org.mapstruct:mapstruct-processor:1.5.1.Final'
    
    // 测试依赖
    testImplementation 'org.springframework.boot:spring-boot-starter-test'
}
"""
    
    gradle_path = Path(temp_dir) / "build.gradle"
    with open(gradle_path, 'w', encoding='utf-8') as f:
        f.write(build_gradle_content)
    
    return temp_dir


def test_dependency_checker():
    """测试依赖检查器"""
    print("=== Java项目依赖管理器测试 ===\n")
    
    # 使用DependencyManager替代JavaDependencyChecker
    manager = DependencyManager()
    
    # 测试1: Maven项目
    print("测试1: Maven项目依赖检查")
    print("-" * 50)
    maven_dir = create_sample_maven_project()
    try:
        # 使用DependencyManager的check_and_fix_dependencies方法
        result = manager.check_and_fix_dependencies(
            project_root=maven_dir,
            template_category="MybatisPlus-Mixed",
            database_type="mysql"
        )
        print(f"项目路径: {maven_dir}")
        print(f"检查结果: {result['analysis_result']['build_tool']}")
        
        # 显示分析结果
        analysis = result['analysis_result']
        summary = analysis['summary']
        print(f"健康度评分: {summary['health_score']}%")
        print(f"找到的依赖: {summary['found_dependencies']}")
        print(f"缺失必需依赖: {summary['missing_required']}")
        
        # 显示比较结果
        comparisons = analysis['comparison_results']
        missing_deps = [c for c in comparisons if c.status == "missing"]
        if missing_deps:
            print("\n缺失的依赖:")
            for dep in missing_deps:
                print(f"  • {dep.requirement.group_id}:{dep.requirement.artifact_id} - {dep.requirement.description}")
    
    except Exception as e:
        print(f"Maven测试失败: {e}")
    
    print("\n" + "=" * 60 + "\n")
    
    # 测试2: Gradle项目  
    print("测试2: Gradle项目依赖检查")
    print("-" * 50)
    gradle_dir = create_sample_gradle_project()
    try:
        # 使用DependencyManager的check_and_fix_dependencies方法
        result = manager.check_and_fix_dependencies(
            project_root=gradle_dir,
            template_category="MybatisPlus-Mixed", 
            database_type="mysql"
        )
        print(f"项目路径: {gradle_dir}")
        print(f"检查结果: {result['analysis_result']['build_tool']}")
        
        # 显示分析结果
        analysis = result['analysis_result']
        summary = analysis['summary']
        print(f"健康度评分: {summary['health_score']}%")
        print(f"找到的依赖: {summary['found_dependencies']}")
        print(f"缺失必需依赖: {summary['missing_required']}")
        
        # 显示比较结果
        comparisons = analysis['comparison_results']
        missing_deps = [c for c in comparisons if c.status == "missing"]
        if missing_deps:
            print("\n缺失的依赖:")
            for dep in missing_deps:
                print(f"  • {dep.requirement.group_id}:{dep.requirement.artifact_id} - {dep.requirement.description}")
    
    except Exception as e:
        print(f"Gradle测试失败: {e}")
    
    print("\n" + "=" * 60 + "\n")
    
    # 测试3: 不存在的项目
    print("测试3: 错误情况测试")
    print("-" * 50)
    try:
        result = manager.check_and_fix_dependencies(
            project_root="/nonexistent/path",
            template_category="MybatisPlus-Mixed",
            database_type="mysql"
        )
        print(f"不存在路径的检查结果: {result.get('success', False)}")
        print(f"错误信息: {result.get('error', 'N/A')}")
    except Exception as e:
        print(f"错误情况测试失败: {e}")
    
    # 清理临时文件
    import shutil
    try:
        shutil.rmtree(maven_dir)
        shutil.rmtree(gradle_dir)
        print("\n清理完成")
    except:
        pass
    
    print("\n依赖管理器测试完成!")


if __name__ == "__main__":
    test_dependency_checker()