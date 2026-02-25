# 2026-02-25: 1h prompt caching 实测

## 设置
- anthropic SDK 0.45
- `cache_control: {"type": "ephemeral", "ttl": "1h"}`
- beta header 自动添加 (SDK 0.45+ 默认开)

## 实测脚本

```python
client = anthropic.Anthropic()
sys_prompt = open("naming_rules.txt").read()  # ~2.5k tokens

# 调用 1
r1 = client.messages.create(
    model="claude-sonnet-4-6",
    system=[{"type": "text", "text": sys_prompt,
             "cache_control": {"type": "ephemeral", "ttl": "1h"}}],
    messages=[{"role": "user", "content": "infer sys_user"}],
)
print(r1.usage.cache_creation_input_tokens, r1.usage.cache_read_input_tokens)
# 2480, 0  (创建缓存)

# 30 分钟后 call 2
r2 = client.messages.create(...)
print(r2.usage)
# cache_read 2480, cache_creation 0 (命中!)
```

## 数据
- 5 min TTL: 短会话内命中 (典型 LLM 会话 1-5 min,基本命中)
- 1h TTL: 跨会话命中 (用户 30 min 后再来,仍命中)
- 1h TTL 价格:cache write +25%(只算一次),cache read 0.1x

## 对本项目
ai_infer / ai_recommend / ai_summarize 共用相同 system prompt(规则文档),用 1h TTL 适合"用户一天内多次生成代码"的场景。

## 决策
v0.2 ai/llm_client.py:
- 默认 5 min TTL (省 cache write 成本)
- prefer_long_ttl=true 开 1h TTL (重度用户场景)
