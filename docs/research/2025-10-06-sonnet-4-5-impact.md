# 2025-10-06: Sonnet 4.5 对 DBJavaGenix 的潜在帮助

## Sonnet 4.5 关键指标
- SWE-bench Verified: 77.2% (Sonnet 4 是 72.7%)
- 长上下文保真度比 Sonnet 4 更稳
- Tool use 的 JSON Schema 遵守性更强

## 对本项目影响
1. **ai_infer_business_names**(规划中):4.5 的命名推断更准
2. **MCP 工具 schema 解析**:工具 JSON Schema 严格性提升,Claude 更少胡乱填参
3. **5 阶段 Skill 工作流**:长上下文保真意味着多步对话不会"忘记前面"

## 不需要做的
- 不需要把现有代码升 4.5 特化 — Sonnet 4.5 默认对所有 client 可用
- 不需要换模型 minimum — 我们的 LLM client 是可选(规则优先)

## 备忘
- Sonnet 4 ($3 / Mtoken in) → 4.5 ($3 / Mtoken) — 价格未涨
