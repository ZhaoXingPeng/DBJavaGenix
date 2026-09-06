# Contributing to DBJavaGenix

感谢贡献。提交代码前请阅读 [`docs/engineering-standards.md`](docs/engineering-standards.md)，它是本项目的规范基线。

## 快速流程

1. 创建或更新 Issue，写清目标和验收标准。
2. 从 `main` 创建带 Issue 编号的短分支。
3. 小步提交，遵循统一的 Gitmoji + Conventional Commits 标题和正文格式。
4. 本地运行相关测试和 lint/format 检查。
5. 创建 PR，关联 Issue，并填写 PR 模板中的测试、实验结果、风险和回滚信息。
6. 等待 CI 和审查通过后合并；不要直接向 `main` 推送功能代码。

## 本地检查

```bash
uv venv
uv pip install -e ".[dev]"
PYTHONPATH=src uv run pytest tests/unit/ -q
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/
```

数据库集成测试需要显式配置 `DBJAVAGENIX_TEST_*` 环境变量，详见 [`tests/README.md`](tests/README.md)。

## 标题和正文示例

```text
:sparkles: feat(dialect): add PostgreSQL array type mapping
:bug: fix(connection): redact credentials from diagnostic errors
:test_tube: test(generator): cover nullable enum columns
```

正文依次写 `背景`、`变更`、`验证`、`实验`、`风险`。PR 标题和首个提交标题必须相同风格；PR 额外关联 Issue 并填写审查清单。
