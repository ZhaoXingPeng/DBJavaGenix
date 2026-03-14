# 2026-03-14: 1M context GA 无 premium 加价

## 关键事实
- Sonnet 4.6 和 Opus 4.6 都 GA 1M context
- 无价格 tier 区分 (之前 beta 阶段 >200k tokens 翻倍计费,GA 后取消)
- beta header 仍需要:`anthropic-beta: extended-context-200k-2024-10-29` (向后兼容)

## 对本项目验证

测试 ai_summarize_schema 在 800 表大库(约 240k tokens schema):
- 之前 200k 限制:需要分批喂 → 4 次调用
- 1M GA:一次喂完 → 1 次调用,准确度更高

## 决策
v0.2 ai_summarize_schema:
- 默认全量喂(信任 1M 上下文)
- >800 表时给警告但仍喂
- >1500 表时降级到分批

## 这进一步强化 ADR-005
RAG 在 ≤1000 表场景毫无必要。
