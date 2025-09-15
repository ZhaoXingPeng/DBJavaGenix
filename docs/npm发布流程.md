# npm发布流程

## 概述
本文档详细说明如何将DBJavaGenix MCP服务器发布到npm.js仓库，以便其他开发者可以通过npm安装和使用该服务。

## 发布前准备

### 1. 环境要求
- Node.js >= 14.0.0
- npm账户并已登录
- Python >= 3.9（用于运行Python MCP服务器）
- Git

### 2. 检查package.json配置
确保[package.json](file:///C:/project/ai/task/coder_prompt/DBJavaGenix/package.json)包含以下必要字段：

```json
{
  "name": "dbjavagenix-mcp-server",
  "version": "0.1.0",
  "description": "DBJavaGenix MCP Server for Cherry Studio and other MCP clients",
  "main": "index.js",
  "bin": {
    "dbjavagenix-mcp": "./index.js"
  },
  "scripts": {
    "start": "node index.js",
    "test": "node index.js --help"
  },
  "keywords": ["mcp", "java", "code-generation", "database", "mysql", "spring-boot"],
  "author": "ZXP <2638265504@qq.com>",
  "license": "MIT",
  "engines": {
    "node": ">=14.0.0"
  }
}
```

### 3. 验证项目结构
确保以下文件和目录存在：
- [index.js](file:///C:/project/ai/task/coder_prompt/DBJavaGenix/index.js) - Node.js入口文件
- [src/](file:///C:/project/ai/task/coder_prompt/DBJavaGenix/src/) - Python源代码目录
- [pyproject.toml](file:///C:/project/ai/task/coder_prompt/DBJavaGenix/pyproject.toml) - Python项目配置
- [README.md](file:///C:/project/ai/task/coder_prompt/DBJavaGenix/README.md) - 项目说明文档

## 发布步骤

### 1. 测试本地安装
在发布之前，先测试本地安装是否正常工作：

```bash
# 克隆项目到临时目录
cd /tmp
git clone https://github.com/dbjavagenix/dbjavagenix.git
cd dbjavagenix

# 安装依赖
npm install

# 测试启动
npm start
```

### 2. 更新版本号
根据语义化版本控制规范更新版本号：

```bash
# 修改package.json中的version字段
# 或使用npm命令
npm version patch  # 补丁版本
npm version minor  # 次版本
npm version major  # 主版本
```

同时更新[pyproject.toml](file:///C:/project/ai/task/coder_prompt/DBJavaGenix/pyproject.toml)中的版本号以保持一致。

### 3. 构建发布包
```bash
# 清理之前的构建
rm -rf dist/

# 构建npm包
npm pack
```
更新版本号并重新发布
在项目根目录下运行以下命令：
```bash
npm version patch
```
### 4. 登录npm账户
```bash
npm login
# 输入用户名、密码和邮箱
```

### 5. 发布到npm
```bash
# 发布到公共npm仓库
npm publish

# 或者发布为测试版本
npm publish --tag beta
```

### 6. 验证发布
```bash
# 创建测试目录
mkdir test-install
cd test-install

# 安装发布的包
npm install dbjavagenix-mcp-server

# 测试运行
npx dbjavagenix-mcp
```

## 发布后操作

### 1. 更新文档
- 更新[README.md](file:///C:/project/ai/task/coder_prompt/DBJavaGenix/README.md)中的安装和使用说明
- 更新GitHub仓库的release notes

### 2. 创建GitHub Release
在GitHub上创建对应的release，包含：
- 版本号
- 更新日志
- 发布的npm包链接

### 3. 通知社区
- 在相关论坛或社区发布更新通知
- 更新项目网站文档

## 常见问题和解决方案

### 1. 权限问题
如果遇到权限问题，确保：
- npm账户有发布该包名的权限
- 包名未被其他用户占用

### 2. 依赖问题
确保所有依赖都正确声明：
- Python依赖在[pyproject.toml](file:///C:/project/ai/task/coder_prompt/DBJavaGenix/pyproject.toml)中声明
- Node.js依赖在[package.json](file:///C:/project/ai/task/coder_prompt/DBJavaGenix/package.json)中声明

### 3. 跨平台兼容性
确保：
- [index.js](file:///C:/project/ai/task/coder_prompt/DBJavaGenix/index.js)能在不同操作系统上运行
- Python代码兼容不同平台

## 最佳实践

### 1. 版本管理
- 遵循语义化版本控制
- 保持Python和Node.js版本号同步

### 2. 文档维护
- 每次发布前更新文档
- 提供清晰的安装和使用说明

### 3. 测试
- 发布前进行充分测试
- 在不同环境下验证功能

### 4. 安全
- 定期更新依赖
- 检查安全漏洞
- 不在代码中包含敏感信息

## 注意事项

1. 确保包名唯一且符合npm命名规范
2. 详细填写包描述和关键词，便于搜索
3. 提供清晰的许可证信息
4. 确保README文档完整且易于理解
5. 测试不同Node.js版本的兼容性
6. 确保Python环境依赖正确安装