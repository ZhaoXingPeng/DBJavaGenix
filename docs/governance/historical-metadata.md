# 历史元数据审计记录

本页记录 2026-09-09 治理工作中发现的编码和展示问题。它是审计说明，不代表已经重写 Git 历史；合并后的 commit object 保持原样，通过后续提交和 GitHub 可编辑字段修复可见信息。

## 不可变 commit object

以下提交的 subject 或展示文本曾包含连续问号、乱码或无上下文标题。它们已经进入历史，不能安全地改写 hash；后续审查应以对应提交的 diff、测试和本页说明为准。

| Commit | 历史展示问题 |
| --- | --- |
| `cf03c4b` | `:recycle: refactor(model): ??????????` |
| `603c598` | `:books: docs(governance): ?????????????` |
| `b60c4da` | `:bug: fix(codegen): ?? PostgreSQL ?????` |
| `c482fc1` | `:bug: fix(metadata): ?? PostgreSQL ??????` |
| `0ccbd15` | `:lock: security(codegen): ??????????` |
| `cc45e02` | `:recycle: refactor(codegen): ???????????? (#34)` |
| `a60bba6` | `:recycle: refactor(visualization): ??????????` |
| `ae79e66` | `:recycle: refactor(codegen): ????????????` |
| `a994e8c` | 旧英文/问号治理正文 |
| `46d1b2b` | 旧英文/问号 CI 正文 |
| `fd39727` | `init` |
| `18f7deb` | `Initial commit` |
| `06e0f8a` | 主页曾显示的 `feat(algorithms): schema_topo - Kahn 拓扑排序` |

## 已修复的 GitHub 展示元数据

以下对象的 title/body 可编辑，因此已通过 GitHub API 修复字面量伪换行、乱码和章节格式。修复不改变对应 commit hash 或 diff：

- PR body：`#78`、`#90`、`#92`、`#94`、`#96`、`#98`、`#100`、`#102`、`#104`、`#106`、`#109`、`#110`、`#112`、`#113`、`#115`、`#126`、`#131`、`#148`。
- Issue body：`#77`、`#125`、`#127`、`#135`。
- Title：PR/Issue `#3`、`#4`、`#112`。
- 主页仓库路径元数据：由提交 `2803b403` 统一。

修复后的正文仍需通过本地 `validate_pr_body()` 或 `validate_issue_body()` 检查；缺少实验输入、原始输出、边界或回滚信息的历史内容不能追溯补造，只能在后续回帖中补充真实证据。

## 审计边界

- 不在本页粘贴 token、密码、连接串、生产数据或完整数据库输出。
- 不把未运行的 CI、性能实验或真实数据库验证写成“通过”。
- 新 Issue/PR 使用模板并在合并前完成一次 required checks 核对；单次提交后不轮询 CI。
