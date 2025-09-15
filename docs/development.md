# DBJavaGenix 开发环境搭建指南

## 📅 概述

本文档为开发者提供DBJavaGenix项目的开发环境搭建指南，包括环境准备、依赖安装、测试运行和开发流程。

## 🚀 环境要求

### 基本要求
- **Python**: 3.9+
- **包管理**: uv (推荐) 或 pip
- **数据库**: MySQL/PostgreSQL/SQLite
- **编辑器**: VS Code, PyCharm 或其他 Python IDE

### 可选工具
- **Git**: 版本控制
- **Docker**: 容器化部署
- **Java 环境**: 用于验证生成的代码

## 快速开始

### 1. 克隆项目

```bash
git clone <repository-url>
cd DBJavaGenix
```

### 2. 创建虚拟环境

```bash
# 使用uv (推荐)
uv venv
source .venv/bin/activate  # Linux/Mac
# 或 .venv\Scripts\activate  # Windows

# 或使用Python venv
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# 或 .venv\Scripts\activate  # Windows
```

### 3. 安装依赖

```bash
# 使用uv
uv sync --extra dev

# 或使用pip
pip install -e ".[dev]"
```

### 4. 配置环境

```bash
# 复制配置文件模板
cp config/config.example.yaml config.yaml

# 编辑配置文件，设置数据库和AI服务信息
# 参考config.example.yaml中的配置说明
```

### 5. 运行测试

```bash
# 运行全部测试
pytest

# 运行指定测试
pytest tests/test_models.py

# 运行覆盖率测试
pytest --cov=src/dbjavagenix

# 运行集成测试
pytest tests/test_integration.py -v
```

### 6. 验证安装

```bash
# 检查CLI命令
set PYTHONPATH=src
python -m dbjavagenix.cli --help

# 测试MCP服务器
set PYTHONPATH=src
python -m dbjavagenix.cli server
```

## 🤖 测试和调试

### 单元测试

```bash
# 运行所有单元测试
pytest tests/unit/ -v

# 测试特定模块
pytest tests/test_config.py tests/test_models.py

# 生成测试报告
pytest --cov=src/dbjavagenix --cov-report=html
```

### 集成测试

```bash
# 测试数据库连接
pytest tests/test_database.py -v

# 测试代码生成流程
pytest tests/test_generator.py -v

# 测试MCP服务器
pytest tests/test_server.py -v
```

### 性能测试

```bash
# 测试数据库查询性能
pytest tests/test_performance.py -v

# 测试代码生成性能
pytest tests/test_codegen_performance.py -v
```

## 🛠️ 开发工具

### 代码格式化

```bash
# 格式化代码
black src/ tests/

# 检查代码风格
flake8 src/ tests/

# 类型检查
mypy src/dbjavagenix/

# 一键格式化
./scripts/format.sh  # 如果有的话
```

### Pre-commit 钩子

```bash
# 安装 pre-commit 钩子
pre-commit install

# 手动运行所有钩子
pre-commit run --all-files

# 更新 pre-commit 配置
pre-commit autoupdate
```

### IDE 配置

**VS Code 推荐插件：**
- Python
- Pylance  
- Black Formatter
- autoDocstring
- GitLens

**PyCharm 配置：**
- 启用 Black 作为代码格式化工具
- 配置 mypy 作为外部工具
- 设置项目解释器为虚拟环境

## 项目结构

```
DBJavaGenix/
├── src/dbjavagenix/           # 主要源码
│   ├── core/                  # 核心模块（模型、异常等）
│   ├── database/              # 数据库连接和分析
│   ├── ai/                    # AI服务集成
│   ├── generator/             # 代码生成器
│   ├── templates/             # Java代码模板
│   ├── server/                # MCP服务器
│   ├── config/                # 配置管理
│   └── utils/                 # 工具函数
├── tests/                     # 测试代码
│   ├── unit/                  # 单元测试
│   ├── integration/           # 集成测试
│   └── fixtures/              # 测试数据
├── docs/                      # 文档
├── config/                    # 配置文件
├── examples/                  # 使用示例
└── scripts/                   # 辅助脚本
```

## 开发流程

1. 创建新分支进行开发
2. 编写代码和测试
3. 运行测试确保通过
4. 提交代码（自动运行pre-commit钩子）
5. 创建Pull Request

## 调试技巧

### 启用调试模式

在配置文件中设置：
```yaml
debug: true
log_level: DEBUG
```

### 使用断点调试

```python
import pdb; pdb.set_trace()
```

### 查看SQL执行

设置环境变量：
```bash
export SQLALCHEMY_ECHO=true
```

### 性能分析

```bash
# 使用 cProfile 分析性能
python -m cProfile -o profile_output.prof -m dbjavagenix.cli generate

# 查看性能报告
python -c "import pstats; pstats.Stats('profile_output.prof').sort_stats('cumulative').print_stats(20)"
```

## 🚀 部署和发布

### 构建包

```bash
# 构建源码包和wheel包
python -m build

# 检查包的完整性
twine check dist/*
```

### 版本管理

```bash
# 查看当前版本
python -c "from src.dbjavagenix import __version__; print(__version__)"

# 更新版本号（在pyproject.toml中）
# 然后创建git标签
git tag -a v0.1.1 -m "Release version 0.1.1"
git push origin v0.1.1
```

## 📚 贡献指南

### 代码风格

- 遵循 PEP 8 代码风格
- 使用 Black 进行代码格式化
- 类型注解覆盖率 > 90%
- 函数和类必须有文档字符串

### 提交规范

```
feat: 新功能
fix: 修复bug
docs: 文档更新
style: 代码格式调整
refactor: 代码重构
test: 测试相关
chore: 构建过程或辅助工具的变动
```

### Pull Request 流程

1. Fork 项目到个人仓库
2. 创建功能分支 `git checkout -b feature/new-feature`
3. 提交更改 `git commit -m 'feat: add new feature'`
4. 推送分支 `git push origin feature/new-feature`
5. 创建 Pull Request

## 🔧 常见问题

### 导入错误

**问题**: `ModuleNotFoundError: No module named 'dbjavagenix'`

**解决**: 确保设置了 PYTHONPATH
```bash
set PYTHONPATH=src  # Windows
export PYTHONPATH=src  # Linux/Mac
```

### 数据库连接问题

**问题**: 连接超时或认证失败

**解决**: 
1. 检查数据库服务状态
2. 验证连接参数
3. 确认防火墙设置
4. 测试网络连通性

### 模板渲染错误

**问题**: `TemplateNotFoundError` 或 `TemplateRenderError`

**解决**:
1. 检查模板文件路径
2. 验证模板语法
3. 确认模板上下文数据完整性

### 依赖管理问题

**问题**: 生成的代码缺少依赖导致编译错误

**解决**:
1. 使用 `dbjavagenix check-dependencies` 检查项目依赖
2. 使用 `dbjavagenix fix-dependencies` 自动修复缺失依赖
3. 使用 `dbjavagenix migration-guide` 获取依赖迁移建议
4. 手动更新 pom.xml 或 build.gradle 文件

## 📞 获得帮助

- **邮箱**: 2638265504@qq.com
- **文档**: 查看 docs/ 目录下的其他文档
- **Issue**: 在项目仓库创建 Issue
- **讨论**: 参与项目讨论区

---

**维护者**: ZXP (2638265504@qq.com)  
**最后更新**: 2025-09-05