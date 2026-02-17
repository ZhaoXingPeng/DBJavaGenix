# 2026-02-17 晚: Sonnet 4.6 发布!

## 关键事实
- Sonnet 4.6 SWE-bench Verified: 81.5% (Opus 4.5 是 80.9%)
- **1M context 转 GA**,无 premium 加价
- 价格不变 ($3 / $15 per Mtoken)
- coding 反超上一代 Opus

## 对本项目意义

### 1M context GA
- 大库 schema 直接喂(单库 ≤ 1000 表都够装)
- ADR-005 "不引 RAG" 的证据进一步强化

### coding 能力
- ai_infer_business_names 走 Sonnet 4.6 性价比最高
- 不需要 Opus 4.5(贵 5x,边际收益小)

### 与 v0.2 plan 对齐
- 当前 plan 里 LLM 默认 Sonnet 4.5,升级为 4.6 几乎零工作量(SDK 兼容)

## 立刻做
- [ ] 简单实测 4.6 vs 4.5 在 ai_infer 上的表现
- [ ] 更新 drafts/v3 → v3-revised:LLM 模型默认 4.6
- [ ] 实测 1M context 喂大库的可行性(用 200 表测试库)

## 后续 model 默认
v0.2 ai_* 工具默认 Sonnet 4.6,留 model 参数可切。
