# ADR-001 草稿: Skills + MCP + MCP Apps 三层架构

## 背景
v0.1 是单层 MCP server,工具是黑盒。LLM 没法中途介入。

## 提案
三层:
- **Skills** (markdown 工作流编排)
- **MCP Atomic Tools** (原子操作 + JSON Schema)
- **MCP Apps** (UI 组件 via _meta)

## 关键判断
- 三者都跨厂兼容(开放标准)
- 边界清晰:Skill 编排,MCP 执行,Apps 渲染

## 替代方案
- A. 单层 MCP big tool → 否决 (黑盒,LLM 失声)
- B. Agent SDK 内置 → 否决 (绑客户端,不是 server 应该做的)

## 待完善
等 Phase 6 实际写正式 ADR 时再扩。
