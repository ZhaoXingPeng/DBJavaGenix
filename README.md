# DBJavaGenix

**智能Java代码生成器** - 基于MCP服务架构的数据库驱动代码生成工具

## 测试示例
<video width="630" height="300" src="https://github.com/user-attachments/assets/020dd55e-b3d9-4f3a-bd46-16ba2f19bae3" controls></video>
## 核心特性

### **我们提供的服务**
- **多数据库支持**: MySQL、PostgreSQL、SQLite分析
- **完整分层代码**: Entity、DAO、Service、Controller、Mapper
- **三套模板架构**: Default、MybatisPlus、MybatisPlus-Mixed
- **智能包结构**: 基于表前缀自动优化包组织
- **依赖管理**: 自动检查、修复和优化Maven依赖
- **项目验证**: SpringBoot项目结构检测和修复
- **现代注解**: Lombok、Swagger、MapStruct集成

### **暂未提供的服务**
- AI语义理解（计划中）
- 业务语义推断（计划中）
- 多语言支持（仅Java）

## 架构设计

```
用户连接数据库 → 表结构分析 → 模板渲染 → 完整Java项目代码
```

### 核心组件
- **MCP服务器**: 提供数据库分析和代码生成服务
- **数据库分析器**: 表结构、关系和元数据分析
- **代码生成器**: 基于Mustache模板的Java代码生成
- **依赖管理器**: 智能依赖检查、修复和迁移
- **项目验证器**: SpringBoot项目结构检测

## 快速开始

### 环境要求
- Node.js 16+
- Claude Desktop 或支持MCP的LLM客户端
- Java开发环境（用于生成的代码）

### 安装配置（推荐方式）

1. **通过npm安装**
```bash
npm install -g dbjavagenix-mcp-server
```

2. **配置MCP客户端**
在Claude Desktop或您的MCP客户端中添加以下配置：

```json
{
  "mcpServers": {
    "dbjavagenix": {
      "disabled": false,
      "timeout": 60,
      "type": "stdio",
      "command": "npx",
      "args": ["-y", "dbjavagenix-mcp-server"]
    }
  }
}
```

3. **启动服务**
```bash
npx dbjavagenix-mcp-server
```

### 开发者安装方式

1. **克隆项目**
```bash
git clone https://github.com/ZhaoXingPeng/DBJavaGenix.git
cd DBJavaGenix
```

2. **安装Python依赖**
```bash
# 使用uv（推荐）
uv sync

# 或使用pip
pip install -r requirements.txt
```

3. **启动开发环境**
```bash
# Windows
start-mcp.bat

# Linux/Mac
chmod +x start-mcp.sh && ./start-mcp.sh
```

### 使用方式

DBJavaGenix通过MCP工具与LLM交互，您需要向LLM提供以下信息：

#### 📝 **示例Prompt模板**

```
请帮我生成Java代码：

**数据库信息：**
- 类型：MySQL
- 主机：localhost:3306
- 数据库：test_db
- 用户名：root
- 密码：password

**生成选项：**
- 表名：user
- 模板分类：MybatisPlus-Mixed
- 包名：com.example.project
- 作者：YourName
- 包含：Swagger + Lombok + MapStruct

请先连接数据库，分析表结构，然后生成完整的Java代码。
```

#### **可用的MCP工具**

| 工具名称 | 功能描述 |
|---------|----------|
| `db_connect_test` | 测试数据库连接 |
| `db_query_databases` | 列出所有数据库 |
| `db_query_tables` | 列出数据库中的表 |
| `db_query_table_exists` | 检查表是否存在 |
| `db_query_execute` | 执行自定义SQL查询 |
| `db_table_describe` | 获取表结构详细信息 |
| `db_table_columns` | 获取表列信息 |
| `db_table_primary_keys` | 获取主键信息 |
| `db_table_foreign_keys` | 获取外键关系 |
| `db_table_indexes` | 获取索引信息 |
| `db_codegen_analyze` | 分析表结构用于代码生成 |
| `db_codegen_generate` | 生成完整Java代码 |
| `springboot_validate_project` | 验证SpringBoot项目结构 |
| `springboot_analyze_dependencies` | 智能分析项目依赖 |
| `springboot_read_config` | 读取Spring Boot配置（YAML/Properties/Bootstrap），推断基础包名与合并有效配置 |

### 模板分类说明

| 模板分类 | 特点 | 适用场景 |
|---------|------|----------|
| **Default** | 传统MyBatis + XML | 复杂SQL，手写优化 |
| **MybatisPlus** | 纯注解，无XML | 快速开发，简单CRUD |
| **MybatisPlus-Mixed** | 注解+XML混合 | 推荐选择，灵活性最佳 |

### 支持的数据库

- MySQL 5.7+ / 8.0+
- SQLite 3.x
- PostgreSQL (开发中)
- Oracle (计划中)

## 项目结构

```
DBJavaGenix/
├── src/dbjavagenix/           # 主要源码
│   ├── core/                  # 核心功能模块
│   ├── database/              # 数据库分析工具
│   ├── ai/                    # AI服务集成
│   ├── generator/             # 代码生成器
│   ├── templates/             # Java代码模板
│   ├── utils/                 # 工具类
│   └── server/                # MCP服务器
└──  config/                    # 配置文件
```

## 开发指南

### 开发环境搭建

```bash
# 克隆项目
git clone https://github.com/ZhaoXingPeng/DBJavaGenix.git
cd DBJavaGenix

# 创建虚拟环境
uv venv
source .venv/bin/activate  # Linux/Mac
# 或 .venv\Scripts\activate  # Windows

# 安装开发依赖
uv sync --extra dev
```

### 分支策略

- **main**: 稳定版本，用于发布
- **develop**: 开发分支，功能集成
- **feature/***: 功能分支，从develop分出
- **hotfix/***: 紧急修复，从main分出

### 开发流程

1. **创建功能分支**
```bash
git checkout develop
git pull origin develop
git checkout -b feature/your-feature-name
```

2. **开发和测试**
```bash
# 运行测试
python -m pytest tests/ -v

# 代码格式化
black src/ tests/
flake8 src/ tests/

# 类型检查
mypy src/
```

3. **提交代码**
```bash
git add .
git commit -m "feat: add your feature description"
git push origin feature/your-feature-name
```

### 代码规范

- **提交信息**: 遵循 [Conventional Commits](https://conventionalcommits.org/)
- **代码风格**: Black + Flake8
- **类型注解**: 使用 mypy 进行类型检查
- **文档**: 为新功能添加相应文档


### 调试技巧

```bash
# 启动MCP服务器调试模式
python -m dbjavagenix.server.mcp_server --debug

# 查看详细日志
export PYTHONPATH=src
python -m dbjavagenix.cli --verbose
```

## 贡献指南

欢迎贡献代码！请遵循以下流程：

1. Fork 项目到您的GitHub账户
2. 创建功能分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 创建Pull Request

## 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。

## 致谢

- [EasyCode](https://github.com/makejavas/EasyCode) - 模板设计灵感来源

## 联系方式

- 作者：ZXP
- 邮箱：2638265504@qq.com
- 项目地址：https://github.com/ZhaoXingPeng/DBJavaGenix
- 问题反馈：https://github.com/ZhaoXingPeng/DBJavaGenix/issues
