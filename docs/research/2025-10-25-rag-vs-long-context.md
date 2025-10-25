# 2025-10-25: RAG vs 1M 长上下文 - 谁该用?

## 背景

5 月 Sonnet 4 beta 出 1M context,9 月看到 4.5 也支持。GA 估计明年初。
本项目从来没用 RAG (规则优先 + 可选 LLM),但要不要趁势加?

## 场景分析

DBJavaGenix 的 LLM 调用主要在:
- **ai_infer_business_names**: 输入 = 表名 + 列名 (~ 200 tokens / 表)
- **ai_recommend_template**: 输入 = schema 概览 (~ 500 tokens / 库)
- **ai_summarize_schema**: 输入 = 完整 schema 列表 (~ 100 tokens / 表)

典型库 (50 表) schema 总 size ~ 5k tokens。**完全装得进 200k 标准窗口**,1M 窗口更绰绰有余。

## RAG 在我们的场景

如果用 RAG:
- 把每张表的 metadata embedding,query 时检索 top-k
- 节省的 token: 5k * (1 - k/50) = ~3k (假设 k=20)
- 但**信息丢失**:被截断的表如果是关联表,LLM 推断错

## 结论

**不用 RAG**:
- 1M context 容得下 ≤ 1000 表
- 大库场景 (>1000 表) 才有必要,但本项目当前不针对这个场景
- 加 RAG 增加 ~500MB 依赖 (embedding model + vector store) + 启动延迟

## 但要做什么

1. v0.2 ai_summarize_schema 直接全量喂 schema (不限制 top-k)
2. 给大库 (>200 表) 准备一个 fallback:按业务簇分批喂

## 关联

- 验证了 v0.1 时期 [vector-tool-search] 的判断 — 工具数小时 keyword 胜,这里是 schema 量小时 long-context 胜
- 写进 ADR-005 "不引向量库" 的延伸理由
