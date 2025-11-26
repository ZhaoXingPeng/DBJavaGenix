# 2025-11-26: async ops 在 codegen_render_* 的评估

## 同步 vs 异步成本
代码渲染本身是模板填充,5ms / 表。一个 50 表库:
- 同步:50 个 tool calls × 5ms = 250ms,体感无感
- 异步:50 个 async ops × (5ms 渲染 + 100ms 轮询开销) = 5+ 秒

异步是负优化。

## async ops 何时有价值
- LLM 调用(2-5 秒)
- 大文件 IO
- 外部 API 调用

对应到本项目:
- ai_infer_business_names (调 Anthropic API ~ 1.5 sec) → 可考虑 async
- ai_summarize_schema → 同上
- codegen_render_* → 同步够

## 决策
v0.2:
- 全部同步
- 工具元数据里标 `_meta.expected_duration_ms` (annotations 扩展),让 client 知道
- v0.3 真的遇到大库瓶颈,再开 async
