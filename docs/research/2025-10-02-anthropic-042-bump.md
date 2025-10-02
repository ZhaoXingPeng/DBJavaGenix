# 2025-10-02: anthropic SDK 0.34 → 0.42

## 变更
- 1h TTL beta header: `extended-cache-ttl-2025-04-11` 直接用 SDK 参数,不需要手填
- `messages.create()` 多了 `cache_control` 顶层参数
- thinking 字段更稳

## 我们的代码改动
- 暂未实际用 prompt caching,只是升级 SDK 待用

## 风险
- 已跑测试套件,无回归
