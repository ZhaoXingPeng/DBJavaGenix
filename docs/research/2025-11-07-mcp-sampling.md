# 2025-11-07: MCP sampling 让 server 借用 client 的 LLM

## 是什么
sampling/createMessage 让 MCP server 反向调用客户端的 LLM:
```json
{
  "method": "sampling/createMessage",
  "params": {
    "messages": [{"role": "user", "content": "推断 sys_user 表的业务命名"}],
    "modelPreferences": {"intelligencePriority": 0.8}
  }
}
```
client 拿到请求,问用户是否允许,然后用它自己的 LLM (Claude / GPT) 跑,把结果返回给 server。

## 对本项目的应用

**ai_infer_business_names 当前**:
- 默认走规则
- prefer_llm=true 且 ANTHROPIC_API_KEY 存在 → 调用 Anthropic API
- ANTHROPIC_API_KEY 不存在 → 只走规则

**用 sampling 改造**:
- 默认走规则
- prefer_llm=true → 通过 client sampling 调用 (不需要 ANTHROPIC_API_KEY)
- 客户端没 sampling 支持 → 降级规则

## 好处
1. CI / 离线环境不用 API key 也能用 LLM 增强
2. 客户端控制成本(它自己的 LLM 配额)
3. 客户端可以管控请求(批准 / 拒绝)

## 顾虑
1. sampling 是 server 主动调 client,改了请求 / 响应方向
2. 客户端兼容性:Claude Desktop 4.5+ 支持,其他大多未支持
3. 比直接调 Anthropic API 多一跳

## 决策
v0.2 实现:
- 主路径仍是直调 Anthropic API
- sampling 作为可选路径(开关 USE_CLIENT_SAMPLING=1)
- ADR 里讲清楚 "为什么不默认 sampling"
