# ADR-009: 1h prompt caching TTL 作为可选项

**状态**: Accepted (v0.2.2 落地, 2026-06)
**关联**: `src/dbjavagenix/ai/llm_client.py` (P4.1, 增加 `cache_ttl` 参数)

## 背景

P4.1 (2026-04) 已经把 `NAMING_SYSTEM_PROMPT` (~2.5k tokens) 加上 `cache_control` 走 Anthropic 默认 5min ephemeral TTL。会话内连续调用 cache_read 命中率 ~95%,效果很好。

但有一类用户场景 5min TTL 兜不住:
- 早上 9 点用 DBJavaGenix 给项目 A 生成代码
- 中午 12 点切到项目 B 再用 — system prompt 完全一样,但 5min cache 早过期
- 下午 16 点又切回项目 A 微调 — 同上

实测一个"DBJavaGenix 重度用户"一天内调 `ai_infer_business_names` 平均 8-12 次,
间隔从 10 分钟到 4 小时不等。**5min cache 命中率掉到 ~30%**。

Anthropic 2026-01 GA 了 **1h cache TTL**(2025-08 beta,2026-01 转正):
- cache_write **+25% 成本**(只算 cache_creation 那一次)
- cache_read 价格不变(还是基础 input 的 10%)
- TTL 从 5min 拉到 1h,跨会话场景命中率显著回升

## 决定

`infer_names_via_llm(...)` 增加 `cache_ttl: str = "5m"` 参数:

```python
def infer_names_via_llm(tables, model="claude-sonnet-4-6", max_tokens=4096, cache_ttl: str = "5m"):
    if cache_ttl not in ("5m", "1h"):
        raise ValueError(...)
    ...
    cache_control_block = {"type": "ephemeral"}
    if cache_ttl == "1h":
        cache_control_block["ttl"] = "1h"
```

- **默认仍是 "5m"** — 单次/会话内调用最经济
- 显式传 `"1h"` 才走长 TTL
- 拒绝其他值(包括 `"30m"` / `"24h"` / `""` / `None`)— Anthropic 当前只这两档

参数从 MCP tool 层暴露给用户(下个迭代),用户根据自己使用模式选择。

## 替代方案

### A. 永远走 5m

**否决**:跨会话场景命中率 ~30%,而 1h 在重度场景能拉到 ~85%。
2.5k system prompt × 70% 命中 = 单次省 ~1750 input tokens × $3/M = ~$0.005/call,
重度用户一天省 ~$0.05,一个月省 ~$1.5。看起来不多但是有 "正确事情" 的信号价值。

### B. 永远走 1h

**否决**:轻度用户(一天调一两次)cache 没命中就过期了,cache_creation 还多付 25%。
对这部分用户是纯亏。**默认必须是 5m**。

### C. 自动检测(根据最近 N 次调用间隔决定)

**否决**:复杂度高,需要持久化最近调用记录。给用户一个开关更直接 — 用户最清楚自己用法。

### D. 缓存多个 TTL(5m + 1h 各一份)

**否决**:Anthropic 单 prompt 只允许一个 cache_control breakpoint(在系统 prompt 末尾)。
要同时享受两档需要拆 prompt,得不偿失。

## 后果

**好**:
- 重度用户(跨会话频繁调用)cache_read 命中率从 ~30% 跳到 ~85%
- 默认 "5m" 对轻度用户零影响、零额外成本
- 实现简单,7 行代码 + 7 个 unit test
- 全局指标 `GLOBAL_LLM_STATS.cache_hit_rate` 自然反映改善 (P4.4 已经在跟踪)

**坏**:
- 用户要主动选 `cache_ttl="1h"`,需要文档解释
- 1h beta 期 Anthropic 调整过价格 (2025-10 短暂涨过),GA 后稳定但需关注

**回归测试**:
- 7 个 unit test 覆盖 "5m / 1h 合法 + 4 种非法值抛 ValueError"
- 不需要真实 API key — validation 在 API 调用前

## 叙事意义

`prompt caching` 是 2025-2026 LLM 集成里**最被低估的工程优化**。
工程意义在于:
1. 把 "system prompt 即 system 设计文档" 这种长 prompt 的成本压到底
2. 让 "AI 集成" 从"贵 / 慢"变成 "贵但可缓存 / 慢但首 token 快"
3. 我们用 5m → 5m+1h 两档,展示**根据使用模式做成本/性能 trade-off** 的工程视角

这是 DBJavaGenix 在 v0.2.2 表达的 "AI 工程化" 一面 — 不止是 "调通 LLM",还要"经济地调"。
