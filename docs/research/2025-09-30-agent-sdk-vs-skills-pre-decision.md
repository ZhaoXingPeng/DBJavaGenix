# 2025-09-30: Agent SDK 通读后的定位决定

## 结论:Agent SDK 暂时不引入

理由:

1. **场景错位**:Agent SDK 是"客户端"侧 (一个跑 agent loop 的 host 应用)。本项目 DBJavaGenix 是 **MCP server**(被 Claude Desktop / Cursor 等客户端调用)。
2. **重复 MCP 价值**:Agent SDK 内置 MCP 加载 = 客户端用它,可以调我们这种 MCP server。**他们用就够,我们不需要变成 Agent SDK 应用**。
3. **依赖膨胀**:`claude-agent-sdk` Python 包 + 它的依赖,对 stdio 模式 MCP server 是不必要的。

## 但 Skills 必须追

Skills 文件本质是 markdown,任何 MCP server / 任何 IDE / 任何 LLM 客户端都可以用(不限定 Claude Code)。

我们可以**自己**写 `.claude/skills/java-codegen-from-db/SKILL.md`,放在我们的 repo,Claude Desktop 加载 MCP 时同时加载 Skill。

## 行动

- [ ] 等 10 月 Skills 单独发布(传言)
- [ ] 那之前继续看 MCP v3 (2025-06-18) elicitation / sampling 怎么用
- [ ] 不引 claude-agent-sdk 包

## 备注

这是 "MCP server 项目应该怎么定位 Agent SDK" 的关键判断。后续 ADR 里要写清楚。
