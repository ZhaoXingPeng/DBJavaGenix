# 2025-10-28: 可借鉴的 Skill 设计模式

## 模式 1: "★ 用户确认点"

很多 Skills 在关键决策处显式标 `★ User confirmation required`。
LLM 看到这个会暂停,等用户响应。

**借鉴**: 我们的 5 阶段流程中,阶段 3 (AI 推断业务命名) 必须有用户确认 — 否则 LLM 默认接受会出错。

## 模式 2: "退路明示"

Skill 里写"如果 X 失败,fall back 到 Y"。例如:
> If `prefer_llm=true` and no ANTHROPIC_API_KEY, fall back to rule-based inference.

**借鉴**: ai_infer_business_names 当 LLM 不可用时自动走规则。

## 模式 3: 工具使用顺序固化

例如:
> 1. First call db_connect_test
> 2. Then call db_query_tables
> 3. Then for each table, call db_table_describe

**借鉴**: 写死调用顺序,避免 LLM 跳步 / 漏调。

## 模式 4: 拒绝模式

> Do NOT generate code without first showing the ER diagram for user confirmation.

**借鉴**: 强制 ER 图先于生成代码,防止 LLM "急于完成"。

## 模式 5: 中文 vs 英文

观察: 官方 examples 全英文。考虑到本项目目标用户主要中文,我们的 SKILL.md 可以中文为主,关键术语英文。

## 行动

- [ ] 起草 java-codegen-from-db/SKILL.md, 套用以上 5 个模式
- [ ] 阶段 3 的★ 用户确认点不要省
