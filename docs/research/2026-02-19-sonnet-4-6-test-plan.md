# 2026-02-19: Sonnet 4.6 vs 4.5 vs Opus 4.5 测试 plan

## 场景
- 10 个真实数据库 sample (RBAC / 电商 / 字典 / 日志 / 模糊业务)
- 每个跑 ai_infer / ai_recommend / ai_summarize

## 测试维度
1. 准确度 (人工评判 / 1-5 评分)
2. 延迟 (p50, p95)
3. Token 消耗 (in / out)
4. Cost (per 1k tools)

## 预期
- 4.6 准确度 ≈ Opus 4.5 (vs 4.5 提升明显)
- 4.6 延迟和 4.5 相当 (无 premium 价格 = 同 tier)
- Opus 4.5 在最难的"模糊业务"场景可能仍领先

## 不在 plan 里
- 不测 1M context 极限(到 v0.2 后期再说)
- 不测客户端 sampling (各 client 兼容性问题先放放)

## 执行时间
本周末抽 1 小时跑完,2/22 出报告。
