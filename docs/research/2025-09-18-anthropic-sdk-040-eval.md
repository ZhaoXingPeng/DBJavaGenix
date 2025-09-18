# 2025-09-18: anthropic Python SDK 0.40 升级评估

## 现状
本项目用的 anthropic SDK 0.34 (v0.1 时引入)。9 月 anthropic 已经发到 0.40 / 0.42。

## 0.34 → 0.40+ 变化
- `cache_control: {"type": "ephemeral"}` 字段从 beta 转为正式 GA(2025-08)
- `prompt_caching-2024-07-31` beta header 不再需要
- 新的 `extended-cache-ttl-2025-04-11` beta 头支持 1h TTL(beta)
- 流式 `text_delta` 字段更稳定

## 影响评估
- **本项目当前未用 prompt caching**(v0.1 单步生成,没多调)— 升级无功能性收益
- 0.34 仍然能跑,但 7 月之后的 1M context beta 需要 newer SDK + 特殊 beta header

## 决策
不急,先观望 9.29 Anthropic 发布会(Sonnet 4.5 + Agent SDK)。
如果新 SDK 强制新 anthropic 版本,再做整体升级。

## 行动
- [ ] 9.30 后回看,决定升级窗口
