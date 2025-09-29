# 2025-09-29 晚: Claude Agent SDK 发布 - 初读笔记

## 关键事实

- Sonnet 4.5 同时发布,SWE-bench 77.2% (上一代 Sonnet 4 是 72.7%)
- Agent SDK 是 "Claude Code 同款" 的开源化:hooks + subagents + MCP + skills
- Python + TypeScript SDK,API 围绕 `claude_agent_sdk.query(...)` async generator

## 关键原语

1. **Hooks**(`PreToolUse`, `PostToolUse`, `Stop`, `UserPromptSubmit` 等)
   - 用 shell 命令 / Python 函数拦截 / 修改 / 阻止工具调用
   - 对代码生成器:可以在 codegen_render_* 之前做项目预检
2. **Subagents**(`.claude/agents/*.md`)
   - YAML frontmatter + markdown 描述 + 可绑定工具子集
   - 用 Task tool 调用,fork 子上下文
3. **Skills**(`.claude/skills/*.md`)
   - 工作流编排,progressive disclosure (按需加载详细内容)
   - **这正是我们 v0.2 需要的!**
4. **MCP integration**:Agent SDK 内置 MCP server 加载,无缝调用

## 对 DBJavaGenix 的启示

- **Skills 是 v0.2 重构的关键拼图**:我们的 5 阶段工作流(连接 → ER 图 → AI 推断 → 渲染 → 部署)放进 Skill 文件,LLM 按部就班
- **Subagents 暂时不需要**:我们的子任务粒度小,Subagent 拆分会拖慢
- **Hooks 有可能用上**:`PreToolUse` 拦 db_connect_test 做凭据脱敏
- **Agent SDK 本身要不要引?** 倾向 **不要** — 我们是 MCP server,客户端是 Claude Desktop / Cursor 等。Agent SDK 是"客户端侧"的,跟我们错位

## 行动计划

- [ ] 通读 Skills 文档(明天)
- [ ] 评估 Skills 在 MCP server 项目里怎么"提供给 LLM"
- [ ] 写一份"v0.2 是否要重构成 Skills+MCP+Apps 三层"的提案

## 注意

不要盲目跟随。我们 v0.1 已经是 MCP server,Skills 是补充不是替代。
