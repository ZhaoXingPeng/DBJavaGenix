# 2025-10-20: Skills 的 progressive disclosure 设计

## 观察

Anthropic 官方 examples 仓库的 skills/*/SKILL.md 都有相似结构:
1. **YAML frontmatter**: name + description + when_to_use,**总是可见**
2. **正文 H1+ 摘要**: 简介性内容,LLM 决策"是否使用本 skill" 时读
3. **detail sections**: H2 章节,按需 (LLM 决定加载本 skill 后) 才进上下文

LLM 看 description 的 token cost ~50 tokens / skill。
LLM 加载 skill 全文的 token cost ~ 1500-3000 tokens。

## 对本项目的延伸

我们的 MCP server 也可以借这个思路:**Tool description**(总可见) vs **Tool detail/example**(按需通过 search_tools 查)。

这就是 progressive tool discovery!29 个工具的 description schema 启动时全暴露 = ~3300 tokens。
如果只暴露 6 个 always-visible 工具的简短描述 + 一个 search_tools meta-tool,可以省 70% 启动 token。

## 验证 idea

需要实测:6 工具 description JSON 多少 tokens?29 工具全暴露多少?
等 v0.2 实现完做 token benchmark。
