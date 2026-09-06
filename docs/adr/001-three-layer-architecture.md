# ADR-001: 三层架构 (Skills + MCP + Apps)

**状态**: Accepted (Phase 2 落地, 2026-05)
**关联**: [iteration-plan/01-target-architecture.md](../../iteration-plan/01-target-architecture.md)

## 背景

DBJavaGenix v0.1 把所有逻辑塞进 `db_codegen_generate` 单个 MCP 工具:

```
[ LLM client ]  →  call_tool db_codegen_generate  →  内部黑盒:
                                                    - 项目验证
                                                    - 依赖分析
                                                    - schema 收集
                                                    - 模板渲染 5 层
                                                    - 写盘 + 备份
                                                    - 报告组装
```

**问题**:
- LLM 无法在中途介入 (例如让用户预览代码再决定是否写盘)
- 单工具 schema 描述膨胀,启动 token 高
- 工作流不可见,LLM 不知道步骤之间的顺序
- 加新能力 (ER 图 / AI 命名) 没有合适的插入点

## 决定

把"代码生成"工作流拆为 **三层**,各层职责单一:

```
[ Skills 层 ]   .claude/skills/*.md
                  - 定义"做什么 / 按什么顺序 / 何时停"
                  - 显式 5 阶段工作流
                  - LLM 加载后照做,不自由发挥

[ MCP 层 ]      原子工具 (32 个)
                  - 每个工具职责单一 (build_context / render_entity / ...)
                  - context 显式参数传递,无 server 内部状态
                  - 每个工具单元可测

[ Apps 层 ]     工具返回值 + _meta 字段
                  - 客户端按 mcp-apps/component 渲染 UI
                  - mermaid / dashboard / code-diff / tree
                  - 不支持的客户端降级看 text 内容
```

## 替代方案

### A. 继续单工具 + 选项扩展

不拆分,通过 `db_codegen_generate` 的参数 (如 `preview_mode=true`)控制中途暂停。
**否决**: 选项膨胀,且 LLM 无法在 server 内部 pause/resume — MCP 协议是 request/response。

### B. 全部交给 LLM 自由编排

不写 Skill,只暴露 atomic 工具,让 LLM 自己决定调用顺序。
**否决**: 实测 LLM 经常跳步 (省略依赖检查 / 跳过用户确认),代码生成出来不能用。Skill 充当"剧本"。

### C. Skills 单独服务化 (HTTP)

把 Skill 内容存在远端服务,客户端按需拉。
**否决**: 增加部署复杂度,且 Skills 本身是 markdown 文件,放进项目 `.claude/` 目录 client 直接读已经够轻量。

## 后果

**好**:
- LLM 工作流可见 → 用户可读 Skill 文件
- 工具粒度精细 → 单元测试覆盖率高 (atomic_codegen 64%, mcp_apps 100%)
- MCP Apps 让结果可视化 (4 个 UI 组件)

**坏**:
- 注册工具数从 15 涨到 32 → 默认模式 token 反而增加 (具体 token 数随工具 schema 变化)
- 通过 progressive mode (ADR-003) 缓解

**待办**:
- Skill 文件需要随 MCP 工具更新同步维护 (有漂移风险)
- 多个 Skill 之间的 transitions 没有正式 spec (例如 codegen → migration)
