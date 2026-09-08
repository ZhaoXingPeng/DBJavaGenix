# Contributing to DBJavaGenix

感谢贡献。提交代码前请阅读 [`docs/engineering-standards.md`](docs/engineering-standards.md)，它是本项目的规范基线。

## 快速流程

1. 创建或更新 Issue，写清目标和验收标准。
2. 从 `main` 创建带 Issue 编号的短分支。
3. 小步提交，遵循统一的 Gitmoji + Conventional Commits 标题和正文格式。
4. 本地运行相关测试和 lint/format 检查。
5. 创建 PR，使用 `Closes #123` 或 `Refs #123` 关联 Issue，并填写 PR 模板的七个固定章节。
6. 在实现完成和验证完成两个里程碑发布事实回帖，记录输入、环境、命令、原始结果、设计取舍、边界、风险和回滚。
7. 等待 CI 和审查通过后合并；不要直接向 `main` 推送功能代码。

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

Issue 正文必须填写对应表单要求的环境/问题、方案、验收标准、测试计划和风险章节。PR 正文固定使用：
`关联 Issue`、`背景（Situation）`、`任务（Task）`、`行动（Action）`、`验证（Verification）`、
`实验与证据（Evidence）`、`兼容性、风险与回滚`。每个章节都要有实际内容；不要留下 `<...>`、`TODO`、
连续 `??`、U+FFFD、字面量 `\\n` 或 `\\r`。命令、原始结果和未执行检查必须如实记录，且先脱敏再粘贴。

校验器可在本地复用：

```bash
python scripts/validate_commit_title.py --title ":books: docs(governance): 更新协作规范"
python scripts/validate_commit_title.py --pr-event event.json
python scripts/validate_commit_title.py --issue-event event.json
```

提交后不需要轮询 CI；只有准备 squash merge 前，才检查最新提交的全部 required checks。
