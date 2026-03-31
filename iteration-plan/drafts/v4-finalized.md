# DBJavaGenix v0.2 - drafts v4 finalized

> 2026-03-31。冻结方案。等 Opus 4.7 之后决定开发 model。

## 冻结的 Phase 拆分
v4 不再改 Phase 切分。

## 等 4 月
- Opus 4.7 是否发(预计 4.16 前后)
- 评估是否作为开发 model
- 如果发了,4.20-25 进入 Phase 1

## 关键决策
- model: Sonnet 4.6 (ai_* 工具默认) + Opus 4.7 (开发用,如果发了)
- LLM 路径:规则优先 + LLM 可选
- token caching: 5 min TTL 默认,1h TTL 可选
- 1M context: 默认开,无 premium 已 GA
