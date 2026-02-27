# 2026-02-27: ai_metrics 工具设计

## 暴露指标
1. 总调用数 (per ai_* tool)
2. cache_read_input_tokens 累计
3. cache_creation_input_tokens 累计
4. input_tokens (uncached)
5. output_tokens
6. cache_hit_rate = read / (read + uncached + create)

## TTL 区分
- 加 `ttl_breakdown: {"5min": {...}, "1h": {...}}`
- 5min 命中通常 80%+
- 1h 命中跨会话,通常 30-50%

## API 形态
```json
{
  "name": "ai_metrics",
  "result": {
    "calls": 23,
    "cache_hit_rate": 0.62,
    "total_input_tokens": 18400,
    "total_output_tokens": 4200,
    "ttl_breakdown": {...},
    "tools": {"ai_infer_business_names": {...}, ...}
  }
}
```

## 实现位置
- src/dbjavagenix/ai/llm_client.py 维护 GlobalLLMStats
- 在 ai_metrics 工具 (database/ai_tools.py) 暴露
