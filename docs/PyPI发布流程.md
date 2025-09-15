# PyPI发布流程

## 概述
本文档详细说明如何将DBJavaGenix发布到PyPI (Python Package Index)，以便其他开发者可以通过pip安装和使用该工具。

## 发布前准备

### 1. 环境要求
- Python >= 3.9
- pip和setuptools
- twine (用于上传包到PyPI)
- PyPI账户并已验证邮箱

### 2. 安装必要工具
```bash
# 安装twine和build工具
pip install twine build
```

### 3. 检查项目配置
确保[pyproject.toml](file:///C:/project/ai/task/coder_prompt/DBJavaGenix/pyproject.toml)包含正确的项目信息：

```toml
[project]
name = "dbjavagenix"
version = "0.1.0"
description = "AI-enhanced Java code generator based on MCP service architecture"
authors = [
    {name = "ZXP", email = "2638265504@qq.com"}
]
readme = "README.md"
license = {text = "MIT"}
requires-python = ">=3.9"
keywords = ["mcp", "code-generation", "java", "database", "ai"]
classifiers = [
    "Development Status :: 3 - Alpha",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.9",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Topic :: Software Development :: Code Generators",
    "Topic :: Database",
]

dependencies = [
    "mcp>=1.0.0",
    "pydantic>=2.0.0",
    "sqlalchemy>=2.0.0",
    "pymysql>=1.0.0",
    "psycopg2-binary>=2.9.0",
    "pystache>=0.6.0",
    "aiofiles>=23.0.0",
    "typer>=0.9.0",
    "rich>=13.0.0",
    "openai>=1.0.0",
    "httpx>=0.24.0",
    "python-dotenv>=1.0.0",
]
```

## 发布步骤

### 1. 创建PyPI测试账户（可选但推荐）
访问 https://test.pypi.org/ 创建测试账户，用于测试发布流程。

### 2. 更新版本号
根据语义化版本控制规范更新版本号：

```bash
# 修改pyproject.toml中的version字段
# 格式：主版本号.次版本号.修订号 (如：0.1.0 -> 0.1.1)
```

### 3. 清理之前的构建
```bash
# 删除之前的构建文件
rm -rf dist/
rm -rf build/
rm -rf *.egg-info/
```

### 4. 构建发布包
```bash
# 使用build工具构建源码包和wheel包
python -m build

# 检查构建结果
ls -la dist/
# 应该看到类似以下文件：
# dbjavagenix-0.1.0-py3-none-any.whl
# dbjavagenix-0.1.0.tar.gz
```

### 5. 检查包内容
```bash
# 检查wheel包内容
tar -tzf dist/dbjavagenix-0.1.0.tar.gz

# 使用twine检查包
twine check dist/*
```

### 6. 测试安装（本地测试）
```bash
# 创建虚拟环境进行测试
python -m venv test_env
source test_env/bin/activate  # Linux/Mac
# 或 test_env\Scripts\activate  # Windows

# 本地安装测试
pip install dist/dbjavagenix-0.1.0-py3-none-any.whl

# 测试基本功能
dbjavagenix --help

# 退出虚拟环境
deactivate

# 删除测试环境
rm -rf test_env/
```

### 7. 注册PyPI账户
如果还没有PyPI账户：
1. 访问 https://pypi.org/account/register/
2. 注册账户并验证邮箱
3. 可选择启用两步验证提高安全性

### 8. 配置API令牌
1. 登录PyPI账户
2. 进入 Account Settings → API tokens
3. 点击"Add API token"
4. 设置令牌描述（如：dbjavagenix release）
5. 选择作用域（建议选择"Upload packages to specific projects"并指定项目名）
6. 保存生成的令牌

### 9. 配置认证信息
创建或编辑 `~/.pypirc` 文件：

```ini
[distutils]
index-servers =
    pypi
    testpypi

[pypi]
username = __token__
password = pypi-你的API令牌

[testpypi]
repository = https://test.pypi.org/legacy/
username = __token__
password = pypi-你的测试API令牌
```

### 10. 上传到Test PyPI（推荐）
```bash
# 先上传到Test PyPI进行测试
twine upload --repository testpypi dist/*

# 测试安装
pip install --index-url https://test.pypi.org/simple/ dbjavagenix
```

### 11. 上传到正式PyPI
```bash
# 上传到正式PyPI
twine upload dist/*

# 或者指定仓库
twine upload --repository pypi dist/*
```

## 发布后操作

### 1. 验证发布
```bash
# 创建新的虚拟环境进行验证
python -m venv verify_env
source verify_env/bin/activate  # Linux/Mac
# 或 verify_env\Scripts\activate  # Windows

# 从PyPI安装
pip install dbjavagenix

# 验证安装
dbjavagenix --version

# 测试基本命令
dbjavagenix --help

# 退出虚拟环境
deactivate
rm -rf verify_env/
```

### 2. 更新文档
- 更新[README.md](file:///C:/project/ai/task/coder_prompt/DBJavaGenix/README.md)中的安装说明
- 更新GitHub仓库的release notes
- 更新版本发布信息

### 3. 创建GitHub Release
在GitHub上创建对应的release，包含：
- 版本号
- 更新日志
- 发布到PyPI的链接

### 4. 通知社区
- 在相关论坛或社区发布更新通知
- 更新项目网站文档

## 常见问题和解决方案

### 1. 权限问题
如果遇到权限问题，确保：
- PyPI账户有发布该包名的权限
- 包名未被其他用户占用
- API令牌正确配置

### 2. 包名冲突
如果包名已被占用：
- 联系包的所有者协商
- 使用不同的包名
- 添加前缀或后缀区分

### 3. 依赖问题
确保所有依赖都正确声明：
- 运行时依赖在dependencies中声明
- 开发依赖在optional-dependencies中声明

### 4. 版本控制
- 遵循语义化版本控制规范
- 不要重复发布相同版本号的包
- 合理规划版本更新

## 最佳实践

### 1. 版本管理
- 遵循语义化版本控制 (SemVer)
- 使用git tag标记版本
- 保持CHANGELOG更新

### 2. 文档维护
- 每次发布前更新文档
- 提供清晰的安装和使用说明
- 维护CHANGELOG记录变更

### 3. 测试
- 发布前进行充分测试
- 在不同Python版本下验证兼容性
- 测试安装和基本功能

### 4. 安全
- 定期更新依赖
- 检查安全漏洞
- 不在代码中包含敏感信息
- 使用API令牌而非密码

## 自动化发布（可选）

可以使用GitHub Actions实现自动化发布：

```yaml
# .github/workflows/publish.yml
name: Publish to PyPI

on:
  release:
    types: [published]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v3
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.9'
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install build twine
    - name: Build package
      run: python -m build
    - name: Publish package
      uses: pypa/gh-action-pypi-publish@release/v1
      with:
        user: __token__
        password: ${{ secrets.PYPI_API_TOKEN }}
```

## 注意事项

1. 确保包名唯一且符合PyPI命名规范
2. 详细填写包描述和分类，便于搜索
3. 提供清晰的许可证信息
4. 确保README文档完整且易于理解
5. 测试不同Python版本的兼容性
6. 不要在包中包含敏感信息或本地配置文件
7. 遵循Python打包最佳实践