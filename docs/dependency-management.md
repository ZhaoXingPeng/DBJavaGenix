# DBJavaGenix 依赖管理指南

## 📅 概述

DBJavaGenix 提供了强大的依赖管理功能，能够自动检查、修复和优化 Java 项目的依赖配置。这解决了用户在代码生成后遇到的依赖缺失问题，如 `javax.annotation.Resource`、`javax.validation.Valid`、`io.swagger.annotations` 等无法解析的问题。

## 🎯 核心功能

### 1. 智能依赖检查
- 自动检测项目中缺失的必需依赖
- 识别过时和不兼容的依赖
- 提供详细的健康度评分

### 2. 自动依赖修复
- 自动添加缺失的依赖到 pom.xml 或 build.gradle
- 自动修复过时依赖（如 javax 到 jakarta 的迁移）
- 保持用户现有配置风格

### 3. 依赖迁移建议
- 提供从旧版本到新版本的迁移路径
- 支持 Spring Boot 版本升级建议
- 生成详细的 Maven XML 代码块

## 🚀 使用方法

### CLI 命令

#### 检查依赖健康度
```bash
# 检查当前目录项目的依赖
dbjavagenix check-dependencies

# 检查指定项目的依赖
dbjavagenix check-dependencies /path/to/project

# 显示详细信息
dbjavagenix check-dependencies --verbose
```

#### 自动修复依赖
```bash
# 自动修复当前目录项目的依赖
dbjavagenix fix-dependencies

# 指定模板类别和数据库类型
dbjavagenix fix-dependencies --template MybatisPlus --database postgresql

# 修复指定项目
dbjavagenix fix-dependencies /path/to/project
```

#### 生成迁移指南
```bash
# 生成当前目录项目的迁移指南
dbjavagenix migration-guide

# 生成指定项目的迁移指南
dbjavagenix migration-guide /path/to/project
```

### MCP 工具

在 MCP 服务器模式下，可以通过以下工具进行依赖管理：

1. `springboot_validate_project` - 验证项目结构和依赖
2. `springboot_analyze_dependencies` - 分析依赖并生成修复建议

## 📦 支持的依赖类型

### 核心框架依赖
- Spring Boot (2.7.x, 3.0.x, 3.3.x, 3.5.x)
- MyBatis / MyBatis-Plus
- JPA/Hibernate

### 数据库驱动
- MySQL (mysql-connector-java, mysql-connector-j)
- PostgreSQL
- SQLite

### 开发工具
- Lombok
- MapStruct
- Swagger/OpenAPI (springdoc-openapi)

### Jakarta EE 迁移
- javax.annotation → jakarta.annotation
- javax.validation → jakarta.validation
- javax.servlet → jakarta.servlet

## 🛠️ 工作原理

### 1. 依赖检测流程
```
项目扫描 → 解析构建文件 → 对比需求清单 → 生成分析报告
```

### 2. 智能适配策略
- **用户优先**: 优先使用用户现有配置风格
- **版本兼容**: 确保依赖版本间的兼容性
- **最小干预**: 只在必要时添加或修改依赖
- **调用隔离**: 每次分析从默认依赖目录开始，Spring Boot 版本调整不会泄漏到后续项目

### 3. 自动修复机制
- Maven 项目: 自动修改 pom.xml 文件
- Gradle 项目: 自动修改 build.gradle 文件
- 保留用户原有格式和注释

## 📋 最佳实践

### 1. 生成代码前检查依赖
```bash
# 在生成代码前先检查依赖
dbjavagenix check-dependencies
dbjavagenix fix-dependencies
dbjavagenix generate --tables user,order
```

### 2. 定期更新依赖
```bash
# 定期检查并更新依赖
dbjavagenix check-dependencies
dbjavagenix migration-guide
```

### 3. 处理常见问题

#### javax 到 jakarta 迁移
```bash
# 自动修复 javax 到 jakarta 的迁移问题
dbjavagenix fix-dependencies
```

#### Swagger 2.x 到 OpenAPI 3.0 迁移
```bash
# 获取迁移建议
dbjavagenix migration-guide
```

## 🎯 解决的具体问题

### 1. 依赖缺失问题
```
Cannot resolve symbol 'Resource'
Cannot resolve symbol 'validation'  
Cannot resolve symbol 'swagger'
```
**解决方案**: 自动添加缺失的依赖

### 2. 版本不兼容问题
```
Method not found in jakarta.annotation
Validation not working with new Spring Boot
```
**解决方案**: 自动修复版本兼容性问题

### 3. 过时依赖问题
```
javax.annotation is deprecated
Swagger 2.x is outdated
```
**解决方案**: 提供迁移路径并自动修复

## 📊 依赖健康度评分

健康度评分基于以下因素计算：
- 必需依赖完整性 (权重 80%)
- 可选依赖完整性 (权重 20%)
- 过时依赖数量 (扣分项)

评分等级：
- 90-100: 优秀 - 项目依赖配置完整且现代化
- 70-89: 良好 - 项目依赖配置基本完整
- 50-69: 一般 - 建议补充缺失依赖
- 0-49: 较差 - 需要紧急处理依赖问题

## 🔧 高级配置

### 自定义依赖配置
在 `config.yaml` 中可以自定义依赖配置：

```yaml
dependencies:
  spring_boot_version: "3.5.5"
  mybatis_plus_version: "3.5.7"
  mysql_connector_version: "8.4.0"
  include_swagger: true
  include_lombok: true
  include_mapstruct: true
```

### 模板类别依赖映射
不同模板类别需要不同的依赖：

1. **Default (传统MyBatis)**
   - mybatis-spring-boot-starter
   - spring-boot-starter-data-jpa

2. **MybatisPlus (纯注解)**
   - mybatis-plus-boot-starter

3. **MybatisPlus-Mixed (混合模式)**
   - mybatis-plus-boot-starter
   - mybatis-spring-boot-starter

## 🤝 集成开发环境

### IDE 集成建议
1. 在生成代码前运行依赖检查
2. 生成代码后重新导入 Maven/Gradle 项目
3. 使用 IDE 的依赖分析工具进行二次验证

### CI/CD 集成
```yaml
# GitHub Actions 示例
- name: Check Dependencies
  run: |
    dbjavagenix check-dependencies
    dbjavagenix fix-dependencies
    
- name: Generate Code
  run: |
    dbjavagenix generate --tables user,order
```

## 📞 获得帮助

如果在使用依赖管理功能时遇到问题：

1. 查看详细错误日志
2. 运行 `dbjavagenix check-dependencies --verbose` 获取更多信息
3. 检查项目构建文件格式是否正确
4. 联系维护者: 2638265504@qq.com

---

**维护者**: ZXP (2638265504@qq.com)  
**最后更新**: 2025-09-07