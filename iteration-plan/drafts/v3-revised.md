# DBJavaGenix v0.2 重构方案 - 草稿 v3 (修订)

> 2026-02-22。整合 Sonnet 4.6 实测结果。

## 修订点

1. **LLM 默认 model**: claude-sonnet-4-6 (原 v3 是 4.5)
   - 准确度提升 (4.5 → 4.6 实测 +9% on ambiguous names)
   - 价格不变
   - 1M context GA

2. **大库支持**(新增章节)
   - 单库 ≤ 200 表:正常喂
   - 200-1000 表:开启 1M context beta header
   - >1000 表:警告 + 建议按业务簇分批

3. **prompt caching 1h TTL**
   - ai_* 工具的 system prompt(规则文档 ~2.5k tokens)用 1h TTL
   - 命中场景:用户在同一会话连续 generate 多张表

## Phase 1-6 子任务无变化
保持 v3 的拆分。

## 还缺
- [ ] ai 工具系列具体设计(P4.1-P4.4 内容)
- [ ] Phase 启动准备 checklist
