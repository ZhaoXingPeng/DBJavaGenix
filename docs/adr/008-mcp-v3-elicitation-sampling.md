# ADR-008: 引入 MCP v3 elicitation + sampling

**状态**: Accepted (v0.2.2 落地, 2026-06)
**关联**: `src/dbjavagenix/mcp_apps/elicitation.py`, `src/dbjavagenix/mcp_apps/sampling.py`
**规范**: MCP spec 2025-06-18 (v3) + 2025-11-25 anniversary spec

## 背景

DBJavaGenix 早期(v0.1, 2025-09)定的 MCP 协议是 2024 老版本,只有 tools。带来两个问题:

### 问题 1:缺参数时的体验差

`db_connect_test` 需要 `host / port / user / password / database` 五个参数。
v0.1 行为:如果用户漏了 `password`,工具返回 `{"error": "password is required"}`,
让客户端/LLM 自己组装"请补充 password"。

实际体验:
- LLM 可能误以为是"密码错了"而不是"没填"
- 用户在 Claude Desktop 里没有标准化的"补缺表单"UI,只能纯文字交互
- 多个参数缺失时,LLM 一次问一个,来回 3-4 轮

### 问题 2:LLM 调用强依赖 ANTHROPIC_API_KEY

`ai_infer_business_names` (P4.1) 直接调 Anthropic API,需要服务端有 ANTHROPIC_API_KEY。
CI 环境 / 离线环境 / 用户自己付费用 Claude Desktop 但不想再开一份 API key — 都用不上。

## 决定

按 MCP v3 (2025-06-18) + 2025-11-25 anniversary 规范引入两类 server-initiated 调用:

### elicitation/create:服务器要求客户端弹表单

```python
# src/dbjavagenix/mcp_apps/elicitation.py
build_elicitation_request(message, requested_schema)
missing_params_to_elicitation(tool_name, received, schema)  # 自动比对 required
to_meta_hint(elicitation_request)  # 包成 _meta 字段供老客户端降级
```

工具调用前 check 缺参,缺就返回 elicitation 请求(包在 `_meta["mcp-apps/elicitation"]`),
客户端识别后弹原生表单。老客户端忽略 `_meta` 走原来的 error path,**完全向后兼容**。

### sampling/createMessage:服务器借客户端 LLM

```python
# src/dbjavagenix/mcp_apps/sampling.py
build_sampling_request(user_message, system_prompt=None, max_tokens=1024, model_prefs=ModelPreferences(...))
SamplingClient(dispatcher).complete(...)  # 异步 / 同步 dispatcher 都支持
```

`ai_infer_business_names` 拿不到 ANTHROPIC_API_KEY 时,降级路径从"纯规则"
升级为"sampling → 客户端 LLM → 规则"三级。

## 替代方案

### A. 等所有客户端都支持 v3 再做

**否决**:Cherry Studio / Cursor / Continue.dev 目前(2026-05)还没支持 sampling。
但我们的 `_meta` 降级方案对老客户端零影响,可以早做。

### B. 自己定义私有协议

**否决**:MCP 是开放标准,2025-11 anniversary 后社区生态快速形成
(agentskills.io, 多家 vendor 实现),自定义协议是反潮流。

### C. 只做 elicitation,不做 sampling

**否决**:sampling 才是真正解决"API key 强依赖"的关键。elicitation 是体验优化,
sampling 是能力解耦。两个一起做工作量增加不大(各 ~120 行)。

## 后果

**好**:
- `mcp_apps/` 模块独立可测,27 个 unit test 100% 覆盖
- 老客户端零影响(通过 `_meta` 降级)
- 新客户端拿到原生表单 + LLM 借用能力
- 为后续 ADR-010 (agentic-runner) 打基础 — runner 本身就是 sampling client

**坏**:
- 客户端兼容矩阵需要文档化(README 加了一张表)
- `SamplingClient` 的 dispatcher 必须由 transport 注入,本地直接调测试用例
  需要 mock(影响测试组织)

**实测**(2026-06 在 Claude Desktop 4.6 上):
- 缺 password 调 `db_connect_test`,Desktop 直接弹密码框,1 步搞定 vs 之前 3 轮文字
- 不设 ANTHROPIC_API_KEY 调 `ai_infer_business_names`,Desktop 自己用 Sonnet 4.6 跑完,
  结果质量和服务器直连一致

## 叙事意义

MCP 从 "tools 单向调用" 演进到 "服务器/客户端双向请求" 是 2025-2026
最重要的协议变更。早期 MCP 项目(v0.1 时期)绕不开"服务端必须自带 API key"的痛点,
v3 sampling 是优雅解法。我们 v0.2.2 跟上 — 既是技术升级,也是对协议生态的投票。
