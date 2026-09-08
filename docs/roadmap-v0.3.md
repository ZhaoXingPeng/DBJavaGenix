# v0.3 后续路线图

- **状态**: Active
- **日期**: 2026-09-08
- **关联 Issue**: #116
- **适用范围**: 功能冻结后的架构、集成、质量和发布工作

这份路线图是后续工作的唯一收尾入口。它把已经交付的能力、需要真实实验验证的候选项和每项工作的验收证据分开记录；候选项在完成对应 Issue 和 PR 前，不视为项目能力，也不应写成性能收益。

## 当前基线

基线以 `main` 的 `2803b40` 为准；该提交包含最近的治理和仓库元数据维护，运行时代码
基线仍包含 `f885f57` 的 PostgreSQL schema 存在性修复：

- 已支持 MySQL、PostgreSQL 和 SQLite 的连接、只读查询和统一元数据契约。
- 已提供原子代码生成、schema 图算法、MCP Apps、AI 语义增强和基础可观测性。
- `PYTHONPATH=src python -m pytest -q tests/unit`：660 passed。
- SQLite 元数据基准已固定输入和查询次数；`describe_table` 当前每次包含 7 次 SQL 往返，其中第 7 次用于识别 `AUTOINCREMENT`。
- CI 已用 Testcontainers 启动 MySQL 8.0 和 PostgreSQL 16，并覆盖 MySQL fixture 连通性及
  PostgreSQL 类型映射；尚未覆盖两个真实数据库上的完整 introspection、schema 隔离和生成链路。
- 当前没有可比较的真实 PostgreSQL/MySQL 延迟、吞吐或内存基准；任何后续 PR 必须先记录实验数据，再讨论优化结果。

## 优先级路线

优先级只表示依赖关系，不代表预先承诺实现结果。每项工作开始前都要创建独立 Issue。

### P0：功能冻结前必须完成

| 顺序 | 工作项 | 问题假设 | 验收证据 | 主要风险 |
| --- | --- | --- | --- | --- |
| 1 | 真实数据库集成矩阵 | 现有容器测试只证明 MySQL 连通性和 PostgreSQL 类型映射，无法发现完整工具链的驱动、权限和 catalog 差异 | 固定版本的 PostgreSQL、MySQL 容器和 SQLite fixture 均通过元数据契约、schema 隔离和代码生成 smoke test；记录镜像版本与命令 | Docker 不可用时只能运行明确标记的本地子集 |
| 2 | 查询与元数据契约收口 | MCP 查询、存在性检查、描述和生成路径仍可能出现边界语义漂移 | 对 schema、复合键、表达式索引、特殊标识符、空结果和只读限制建立跨方言契约测试；Raw Response 全部可解析 | 厂商 SQL 差异需要限制在 introspector 或 dialect 边界 |
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
