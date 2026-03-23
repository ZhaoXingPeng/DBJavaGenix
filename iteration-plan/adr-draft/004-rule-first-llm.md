# ADR-004 草稿: 规则推断优先, LLM 可选

## 背景
ai_infer_business_names 等工具理论上 LLM 比规则强(语义)。但全 LLM 化有问题:
- CI/离线无 ANTHROPIC_API_KEY 跑不了
- 每次都调 API 浪费
- API 调用延迟拖慢工作流

## 提案
默认规则(15 条 naming rules),prefer_llm=true 走 LLM,LLM 失败回退规则。

## 输出统一
- `source` 字段标 rule / llm / rule_llm_unavailable
- LLM 比规则置信度高 (0.9 vs 0.7-0.85)

## 待完善
正式 ADR 写实测对比数据。
