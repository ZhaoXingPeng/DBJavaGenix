# DBJavaGenix 项目工程规范

本文件是项目协作、提交、合并、测试和发布的唯一规范入口。规则适用于维护者和贡献者；自动化检查逐步落实本文件中的门禁。

## 1. 工作流：Issue -> Branch -> Commit -> PR -> Merge

除紧急安全修复外，所有变更按以下顺序进行：

1. 先创建或补充 Issue，说明背景、目标、非目标、验收标准和风险。
2. 从 `main` 创建短生命周期分支：`feat/<issue>-<name>`、`fix/<issue>-<name>`、`docs/<issue>-<name>`、`test/<issue>-<name>` 或 `chore/<issue>-<name>`。
3. 以小步提交实现一个可验证的行为；一个提交应能独立理解、检查和回滚。
4. 提交 Pull Request，关联 Issue（使用 `Closes #123` 或 `Refs #123`），等待 CI 通过和代码审查。
5. 只通过 PR 合并到 `main`。合并前必须解决阻塞性评论，并确认测试、文档和兼容性影响。

紧急安全修复可以先提交最小修复，再在 24 小时内补建 Issue、测试和复盘记录。

## 2. 统一标题和正文规范

提交和 PR 使用完全相同的标题格式：先写 Gitmoji，再写 [Conventional Commits 1.0.0](https://www.conventionalcommits.org/en/v1.0.0/) 类型和范围。

### 中文优先

Issue 和 PR 的标题、正文描述默认优先使用中文，确保背景、验收标准、实验结果和风险对中文协作者清晰可读。Gitmoji、Conventional Commits 类型、代码标识、命令、API 名称、错误信息和数据库专有名词保留原文；涉及跨团队协作时可以补充英文摘要。

```text
<gitmoji> <type>(<scope>): <简短动作>

[正文：背景、变更、验证、实验、风险]

[脚注：Closes #123 / Refs #123 / BREAKING CHANGE: ...]
```

Gitmoji 使用短代码，保证终端、GitHub 和自动化工具中的显示一致。常用映射如下：

| Gitmoji | 类型 | 用途 |
| --- | --- | --- |
| `:sparkles:` | `feat` | 新增用户可见能力 |
| `:bug:` | `fix` | 修复错误行为 |
| `:test_tube:` | `test` | 新增或调整测试 |
| `:books:` | `docs` | 文档、规范或 ADR |
| `:recycle:` | `refactor` | 不改变外部行为的重构 |
| `:zap:` | `perf` | 性能改进 |
| `:construction_worker:` | `ci` / `build` | CI、构建或依赖 |
| `:lock:` | `security` | 安全修复或加固 |
| `:wrench:` | `chore` | 其他维护工作 |
| `:rocket:` | `release` | 发布和版本变更 |

类型必须与 Gitmoji 映射一致；范围使用受影响模块名，例如 `dialect`、`generator`、`ci`。

提交要求：

- 提交和 PR 标题使用祈使语气，必须包含受影响模块 scope，首行不超过 72 个字符，不以句号结尾，并以 Gitmoji 短代码开头。
- Gitmoji 必须使用短代码（例如 `:bug:`），禁止使用原生 Unicode Emoji；标题或评论出现连续问号时，优先按 UTF-8 编码损坏处理并修复后再提交。
- 每次提交只解决一个主题；不要把格式化、重命名和功能混在同一提交中。
- 提交前运行与改动相关的最小测试集；跨模块变更运行完整单元测试。
- 不提交密钥、数据库密码、个人配置、生成目录、覆盖率产物或构建缓存。
- 发现错误时优先修正提交历史，再创建 PR；不要依赖合并后再补救。

正文统一使用以下顺序，提交和 PR 都适用：

1. `背景`：为什么需要这次变更。
2. `变更`：做了什么，以及明确没有做什么。
3. `验证`：执行的命令和结果。
4. `实验`：输入、方法和可复现结果；没有实验时写“无”。
5. `风险`：兼容性、回滚方式和后续 Issue。

## 3. PR 要求

PR 标题必须与提交使用同一套 Gitmoji + Conventional Commits 格式。正文按上述顺序填写，并必须回答：

- 关联哪个 Issue，问题和验收标准是什么？
- 做了什么，哪些内容明确没有做？
- 架构边界或公共 API 是否变化？兼容性如何？
- 运行了哪些测试和静态检查，结果是什么？
- 做了哪些实验（基准、真实数据库、模板渲染等），得到什么证据？
- 风险、回滚方式和后续工作是什么？

合并门槛：

- CI 必须通过；失败的检查只能通过修复或有记录的维护者豁免处理。
- 至少一次维护者审查；涉及安全、数据访问或公共 API 时需要额外审查。
- 新功能必须有测试；缺陷修复必须有能复现并防止回归的测试。
- 行为变化必须同步更新 README、API 文档、ADR 或迁移说明。
- 优先使用 Squash merge，合并后的提交仍应保留清晰的 Conventional Commit 标题。

## 4. 测试和质量门禁

本地最小检查：

```bash
PYTHONPATH=src python -m pytest tests/unit/ -q
python -m ruff check src/ tests/
python -m ruff format --check src/ tests/
```

涉及数据库适配器或 SQL 行为时，额外运行：

```bash
PYTHONPATH=src python -m pytest tests/integration/ -q
```

测试应优先使用确定性 fixture；真实数据库测试通过 `DBJAVAGENIX_TEST_*` 环境变量显式启用。测试不得依赖个人机器上的凭据或服务。

## 5. 架构变更

- 先写 ADR，再实现跨模块架构决策；ADR 说明上下文、候选方案、决策、后果和迁移计划。
- 保持 Skills（流程编排）、MCP tools（能力接口）、Apps（展示层）边界，不让展示层直接访问数据库。
- 新增公共工具必须定义输入输出模型、错误语义、日志/指标和测试策略。
- 依赖升级必须说明安全、兼容性和运行时影响；锁定或记录可复现的版本范围。

## 6. 版本和发布

版本遵循 [Semantic Versioning 2.0.0](https://semver.org/)；变更记录遵循 [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)。发布前确认：

- CI、单元测试、必要的集成测试和模板渲染检查通过；
- README、迁移说明和公开 API 文档已更新；
- 依赖和安全扫描无未处理的高危问题；
- 发布说明包含用户影响、升级步骤、已知限制和验证结果。

## 7. 安全

不要在 Issue、PR、日志或测试报告中粘贴令牌、密码、连接串或完整数据库输出。安全漏洞请按 [`SECURITY.md`](../SECURITY.md) 私下报告。

## 8. 规范来源

本规范结合并适配以下公开指南（访问日期：2026-09-06）：

- [GitHub Flow](https://docs.github.com/en/get-started/using-github/github-flow)
- [GitHub 关于 Pull Request 的最佳实践](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests)
- [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/)
- [Semantic Versioning](https://semver.org/)
- [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
