# 2026-02-09: 客户端 Skill / _meta / elicitation 支持矩阵

| 客户端 | Skill 加载 | _meta 渲染 | elicitation | sampling | async ops |
|--------|-----------|-----------|-------------|----------|-----------|
| Claude Desktop 4.6 | ✅ | mermaid/diff/dashboard 全支持 | ✅ | ✅ | ✅ |
| Claude Code 2.0 | ✅ (原生 .claude/skills) | code-diff | ✅ | ✅ | ✅ |
| Cherry Studio 1.5 | ✅ | mermaid 支持,dashboard 降级 JSON | ✅ | ❌ | ❌ |
| Cursor 0.45 | ❌ | text 退化 | ❌ | ❌ | ❌ |
| Continue.dev 0.9 | 部分 | mermaid 支持 | 部分 | ❌ | ❌ |

## 设计含义
- 本项目走"渐进增强":_meta 携带 component,客户端识别就渲染,不识别就降级为纯文本
- elicitation / sampling 也走"先 detect capability,再决定路径"
- async ops 全部 client 都不普及,默认同步

## 行动
v0.2 设计要把"降级路径"画在 ADR 里。
