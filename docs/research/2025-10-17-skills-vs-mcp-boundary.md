# 2025-10-17: Skills 与 MCP 的边界

## 核心结论

| 维度 | Skill | MCP Tool |
|------|-------|---------|
| 形态 | markdown 文档 | JSON-RPC endpoint |
| 内容 | 工作流编排 / 决策树 / when_to_use | 原子操作 + 输入/输出 schema |
| 谁加载 | 客户端 (Claude Code / Desktop) | 客户端启动时通过 MCP server 暴露 |
| 是否纯静态 | 是 (markdown) | 否 (有运行时逻辑) |
| 是否绑 Anthropic | 不绑 (markdown 通用) | 不绑 (协议标准) |

## 应用到 DBJavaGenix

**Skill 负责**:
- "5 阶段代码生成" 工作流定义
- "Spring Boot 2.7 → 3.x 迁移" 迁移步骤
- 哪些工具按什么顺序调,哪里需要用户确认

**MCP Tool 负责**:
- db_connect_test (建连接)
- db_table_describe (查表结构)
- codegen_render_entity (渲染 entity 模板)
- db_render_er_diagram (生成 mermaid)
- ...等 29 个原子操作

## 反例

错误的设计:把 "5 阶段流程" 写进 MCP server 内部 (做成一个大 tool)。
后果: 像 v0.1 db_codegen_generate 那样黑盒,LLM 没法中途介入。

正确:5 阶段写在 Skill 里,每阶段调对应 MCP tool。LLM 走每步都可以暂停。

## 这个区分要写进 ADR

后续 v0.2 设计 ADR-001 直接采用这个划分。
