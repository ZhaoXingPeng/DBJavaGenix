# v0.3 后续路线图

- **状态**: Active
- **日期**: 2026-09-08
- **关联 Issue**: #116
- **适用范围**: 功能冻结后的架构、集成、质量和发布工作

这份路线图是后续工作的唯一收尾入口。它把已经交付的能力、需要真实实验验证的候选项和每项工作的验收证据分开记录；候选项在完成对应 Issue 和 PR 前，不视为项目能力，也不应写成性能收益。

## 当前基线

基线随 `main` 更新；本次证据快照以 `f3b7741`（PR #142 合并）为准，运行时代码
仍包含 `f885f57` 的 PostgreSQL schema 存在性修复：

- 已支持 MySQL、PostgreSQL 和 SQLite 的连接、只读查询和统一元数据契约。
- 已提供原子代码生成、schema 图算法、MCP Apps、AI 语义增强和基础可观测性。
- `uv run --python 3.12 --extra dev python -m pytest tests/unit/ --no-cov -q`：680 passed
  （Windows、Python 3.12.12、uv 0.9.17）。该数字是本快照的本地基线，不替代 CI 的
  Python 3.11 / 3.12 / 3.13 矩阵。
- SQLite 元数据基准已固定输入和查询次数；`describe_table` 当前每次包含 7 次 SQL 往返，其中第 7 次用于识别 `AUTOINCREMENT`。
- CI 已用 Testcontainers 启动 MySQL 8.0 和 PostgreSQL 16-alpine。PR #133 通过真实
  `ConnectionManager -> DatabaseIntrospector.describe_table` 覆盖两方言的主键、外键、复合
  索引、NOT NULL 和自增语义；PostgreSQL 另以非 public schema 与 public 同名表验证显式
  schema 隔离。PR #136 继续在两个容器方言上执行
  `ConnectionManager -> DatabaseIntrospector -> CodegenAnalyzer -> CodegenGenerator`，验证
  `MybatisPlus-Mixed` 的 7 个内存文件均无 error；其最终 integration job 为 9 passed。
  PR #138 补充了无需 Docker 的临时 SQLite 文件 fixture，覆盖同一 metadata 与 7 文件生成链路；
  当前 #142 integration job 收集 10 项并为 10 passed、24 warnings、60.26s。上述结果不代表
  生产权限/版本组合、SQLite 并发锁或所有真实驱动值类型已验证。
- PR #140 使公共 `db_query_execute` 在执行前拒绝 `FOR SHARE`、`FOR KEY SHARE`、
  `FOR [NO KEY] UPDATE` 与 `LOCK IN SHARE MODE` 等带锁 SELECT，并保留可 JSON 解析的错误
  envelope。PR #142 使该工具的成功 Raw Response 可序列化 Decimal、日期时间、UUID、二进制
  和 timedelta；其余 MCP handler 的历史 JSON 路径不因此视为已统一。
- 当前没有可比较的真实 PostgreSQL/MySQL 延迟、吞吐或内存基准；任何后续 PR 必须先记录实验数据，再讨论优化结果。

### P0 进展记录

- **真实数据库集成矩阵（进行中）**：#133 完成 MySQL 8.0 / PostgreSQL 16-alpine 最小
  metadata contract 和 PostgreSQL schema 隔离；#136 完成两容器方言到 7 文件内存生成；#138
  完成 SQLite 文件 fixture 的等价路径。剩余验收项是生产权限/版本组合、SQLite 并发/文件锁边界，
  以及与固定 Java fixture 分开的真实数据库生成项目编译证据。
- **查询与元数据契约收口（进行中）**：#133 已修复 psycopg2 中
  `LIKE 'nextval(%%'` 的 literal-percent 转义；#140 收紧无副作用 SELECT，#142 修复常见驱动
  返回值的 Raw Response JSON 序列化。特殊标识符、空结果和表达式/复合键的更多真实跨方言组合、
  未记录的锁语法、查询资源限制与其他 MCP handler 仍未形成完整合同。

  当前分支补充 PostgreSQL dollar-quoted literal 的 tokenizer 支持，并将 PostgreSQL/SQLite
  的 `FETCH FIRST/NEXT ... ONLY` 纳入结果上限重写；`WITH TIES` 在无法证明不超限时明确拒绝。
  该项仍需真实方言实例验证，当前只计入本地回归证据。

## 优先级路线

优先级只表示依赖关系，不代表预先承诺实现结果。每项工作开始前都要创建独立 Issue。

### P0：功能冻结前必须完成

| 顺序 | 工作项 | 问题假设 | 验收证据 | 主要风险 |
| --- | --- | --- | --- | --- |
| 1 | 真实数据库集成矩阵 | 当前固定 MySQL/PostgreSQL 容器与 SQLite 文件 fixture 已覆盖 metadata、schema 隔离和内存生成，但仍可能在权限、版本、并发和真实生成项目编译处漂移 | 记录权限/版本组合；在 SQLite 文件锁和代表性真实数据库生成项目上补充可复现实验 | Docker 不可用时只能运行明确标记的本地子集；本地 SQLite 不能替代服务器方言 |
| 2 | 查询与元数据契约收口 | 锁定读和常见 driver 值已收口，但特殊标识符、空结果、表达式/复合键与未记录方言语法仍可能出现边界语义漂移 | 对 schema、复合键、表达式索引、特殊标识符、空结果和只读限制建立跨方言契约测试；按 handler 明确 Raw Response 序列化范围 | 厂商 SQL 差异需要限制在 introspector 或 dialect 边界 |
| 3 | 生成代码编译 smoke test | 模板渲染成功不等于 Java 工程可编译 | 用固定 fixture 生成 Entity/DAO/Service/Controller/DTO/Mapper，使用 Java 21 与 Spring Boot 3.5 依赖完成至少一次离线编译验证 | 构建网络和第三方依赖版本必须可复现 |
| 4 | 最终 CI 与发布门禁 | 当前质量检查分散，无法证明发布产物与源码一致 | 功能冻结后统一执行单测、集成测试、Ruff、模板检查、Java 编译、包构建、容器启动和安全扫描；产出可下载的版本工件 | CI 时长和外部服务失败需要缓存、重试和清晰降级 |

### P1：架构和性能验证

| 工作项 | 先决条件 | 验收证据 |
| --- | --- | --- |
| 元数据缓存生命周期 | P0 契约稳定，先取得缓存前基准 | 明确 connection-scoped key、失效时机和并发行为；以相同 fixture 对比 SQL 往返次数、P50/P95 和错误率；没有改善则不合入 |
| 同步数据库调用与 MCP 事件循环边界 | 记录并发请求下的阻塞现象 | 在真实或可控 stub 中比较直接调用、线程 offload 或异步驱动；以吞吐、尾延迟和资源占用决定方案，不凭直觉改造 |
| 方言扩展适配器 | P0 契约、驱动许可和测试基础设施完成 | Oracle/SQL Server 仅在驱动、连接、类型映射、元数据和集成测试全部具备后分别立项；不提前在能力列表中宣称支持 |
| 安全与可观测性收口 | P0 接口稳定 | 凭据脱敏、路径边界、只读 SQL、结构化错误和指标在端到端调用中有回归证据；记录已知限制和回滚方式 |

### P2：体验和长期演进

- 补齐 Claude Desktop、Cursor 等客户端的 MCP Apps 截图和兼容性记录。
- 评估 agentic runner 的 subagent 编排；先用基准任务证明收益，再决定是否引入额外并发和状态管理。
- 将迁移 Skill 的检查项与生成器输出建立可追踪的结果模型，避免只返回自然语言建议。
- 根据真实使用反馈决定是否增加模板分类、分页策略和增量生成，不以工具数量作为目标。

## Issue → PR 执行协议

1. 先创建 Issue，写明背景、目标、非目标、验收标准、实验输入和风险；Issue 与 PR 必须一一对应。
2. 从最新 `main` 创建 `feat/<issue>-<name>`、`fix/<issue>-<name>`、`test/<issue>-<name>` 或 `chore/<issue>-<name>` 分支。
3. 每个提交只包含一个可验证行为，标题使用 `:gitmoji: type(scope): 中文主题`；提交前运行与改动匹配的最小测试。
4. PR 正文使用 `关联 Issue`、Situation、Task、Action、Verification、Evidence、兼容性/风险/回滚七个章节，并用 `Closes #<issue>` 或 `Refs #<issue>` 关联；评论按事实拆分记录复现、取舍、实验、测试、兼容性和回滚，不限制为固定条数。
5. 性能没有可比数据时明确写“性能数据未测量”，不得从理论复杂度或单机一次运行推导收益；有数据时同时记录输入、环境、命令、原始结果和统计口径。
6. 只有测试、文档、兼容性和安全影响都核对后才 squash merge 到 `main`。路线图只定义范围和验收证据；后续实现按优先级另开 Issue 和 PR。

## 收尾定义

项目可以进入发布准备的条件是：

- P0 四项都有对应 Issue、PR、测试结果和可复现记录；
- 统一元数据契约在 SQLite、PostgreSQL、MySQL 集成环境和 fixture 中通过；
- 生成的代表性 Java 工程能够完成编译 smoke test；
- 最终 CI 门禁和发布工件在干净环境可复现；
- README、ADR、benchmark、部署说明和已知限制与实际行为一致。

在上述条件达成前，P1/P2 只作为排队计划，不应通过修改版本号或宣传文案假装完成。
