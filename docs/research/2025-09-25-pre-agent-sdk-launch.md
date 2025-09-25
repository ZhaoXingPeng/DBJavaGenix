# 2025-09-25: 关注 Claude Agent SDK 发布

距离 Anthropic 9.29 发布会还有 4 天。从 changelog / Twitter 看到的信号:
- "Claude Agent SDK"(可能是 Claude Code SDK 改名 + 通用化)
- 关键词:hooks、subagents、MCP integration、Skills 前奏

对本项目意味着什么:
- 我们 v0.1 是单步生成,LLM 中间没法介入。Agent SDK 似乎专门解决这个
- "subagent" 概念很有意思:把"分析 schema" 和 "生成代码" 拆成两个 agent?
- 但 v0.1 重构成本很大,要权衡是否值得

**先观望,看 9.29 发了什么再决定。**

打算关注的几个点:
1. Agent SDK 是否要求 ANTHROPIC_API_KEY?CI 环境怎么办
2. subagent 和 MCP server 的边界
3. 是否标准化 "skill" 概念
4. 和 OpenAI Agents SDK / Google ADK 的差异
