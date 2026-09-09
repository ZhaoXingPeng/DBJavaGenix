# Contributing to DBJavaGenix

感谢贡献。提交代码前请阅读 [`docs/engineering-standards.md`](docs/engineering-standards.md)，它是本项目的规范基线。

## 快速流程

1. 创建或更新 Issue，写清目标和验收标准。
2. 从 `main` 创建带 Issue 编号的短分支。
3. 小步提交，遵循统一的 Gitmoji + Conventional Commits 标题和正文格式。
4. 本地运行相关测试和 lint/format 检查。
5. 创建 PR，关联 Issue，并填写 PR 模板中的测试、实验结果、风险和回滚信息。
6. 等待 CI 和审查通过后合并；不要直接向 `main` 推送功能代码。

Issue 和 PR 的标题、正文描述尽量使用中文，便于项目协作者审查和追踪。Gitmoji、commit 类型、代码标识、命令和 API 名称保留原文。

## 本地检查

```bash
uv venv
uv pip install -e ".[dev]"
PYTHONPATH=src uv run pytest tests/unit/ -q
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/

# 验证 sb35-java21 模板的代表性 Maven 编译路径（需要 Java 21 与 Maven）
PYTHONPATH=src uv run python scripts/verify_java_compile.py
```

数据库集成测试需要显式配置 `DBJAVAGENIX_TEST_*` 环境变量，详见 [`tests/README.md`](tests/README.md)。

## 标题和正文示例

```text
:sparkles: feat(dialect): 增加 PostgreSQL 数组类型映射
:bug: fix(connection): 脱敏诊断错误中的凭据
:test_tube: test(generator): 覆盖可空枚举字段
```

Bug Issue 依次写 `版本与环境`、`问题与预期行为`、`最小复现`、`验收标准`、`非目标、风险与安全`；
功能或架构 Issue 使用 `问题与用户价值`、`建议方案与替代方案`、`验收标准`、`架构、兼容性与测试计划`、
`非目标与风险`。PR 必须按模板中的七个固定章节填写，且每节有实际内容；实现完成和验证完成各发一条
包含结论、取舍、命令/结果、风险和下一步的回帖。Issue 编辑会触发轻量元数据检查，不能使用空章节、
连续 `??`、替代字符或字面量 `\\r\\n` 代替 Markdown 换行。
