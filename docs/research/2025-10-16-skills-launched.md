# 2025-10-16 晚 22:55: Claude Skills 正式发布!

刚刚看到 Anthropic blog post。这玩意儿就是我等了一个月的东西。

## Skills 是什么 (官方定义)

> "Skills are folders that include instructions, scripts, and resources Claude loads when needed."

具体形态:
- `~/.claude/skills/<name>/SKILL.md` (user-scoped)
- `<project>/.claude/skills/<name>/SKILL.md` (project-scoped)
- SKILL.md 有 YAML frontmatter (name, description, when_to_use)
- 描述 LLM 何时该加载这个 skill
- progressive disclosure:metadata 总是可见,详细内容按需加载

## 为什么对本项目至关重要

**v0.1 痛点**: db_codegen_generate 是一个黑盒工具,LLM 调用完得到 50 个文件,中间无法介入。

**Skills 给的方案**: 写一份 java-codegen-from-db/SKILL.md,告诉 LLM "做代码生成时走 5 阶段流程"。LLM 按步骤跑,每一步可以暂停,可以让用户确认。

5 阶段:
1. 探查数据库 (db_connect_test, db_query_tables, db_table_describe)
2. 渲染 ER 图 + 推断业务命名 (db_render_er_diagram, ai_infer_business_names)
3. **用户确认点★** 让用户审推断
4. 分层渲染 (codegen_render_entity → dao → service → controller → mapper)
5. 后续步骤 (compile / test)

## 这意味着

v0.2 重构的核心拼图找齐了:
- **Skill 文件** 编排工作流
- **MCP 工具** 提供原子操作
- **MCP Apps**(下一步研究)做可视化

## 兴奋点

1. Skill 是 markdown,语言中立,客户端中立
2. 不绑 Claude Code(虽然首发支持的是它)
3. progressive disclosure 是关键 — 避免一次性把全部 schema 喂进上下文

## 今晚行动

- [x] 速读官方文档
- [ ] 明天梳理 Skill 和 MCP 的边界
- [ ] 起草 java-codegen-from-db SKILL.md 大纲
