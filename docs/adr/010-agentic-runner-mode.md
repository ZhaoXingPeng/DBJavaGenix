# ADR-010: agentic-runner 作为可选启动模式

**状态**: Accepted (v0.2.2 落地, 2026-06)
**关联**: `src/dbjavagenix/server/agentic_runner.py`
**前置**: [ADR-008](008-mcp-v3-elicitation-sampling.md) (sampling 解耦 LLM)

## 背景

DBJavaGenix 自始 (v0.1, 2025-09) 只有一种启动模式 — **MCP server**:
被动等待 Claude Desktop / Cursor / Continue.dev 等客户端发起 tool 调用。

实际有些使用场景需要 "主动" agent:

1. **批处理 / 一次性任务**:
   "扫描 host=X 数据库,生成代码到 ./out,然后退出"
   走 MCP server 需要打开客户端、连接、手动一个个调 tool,8-10 步操作。

2. **CI / 自动化**:
   流水线里夜间任务,根据线上 schema diff 重新生成 entity。
   无人值守环境没有 Claude Desktop UI。

3. **教学 / demo**:
   面试或介绍项目时,想 1 行命令展示 "同样的 tools 既能服务客户端,也能服务 agent"。

Claude Agent SDK (2025-09-29 发布,2026-Q1 GA) 提供了
"agent loop + hooks + subagents + MCP tools 注入" 的标准框架,正好填这个空。

## 决定

新增 `src/dbjavagenix/server/agentic_runner.py` 作为 **第二种启动模式**:

| 维度 | mcp_server | agentic_runner |
|------|-----------|----------------|
| 触发 | 客户端连接 | CLI 单次启动 |
| 控制权 | 客户端 LLM | runner 内嵌 Claude Opus 4.7 |
| 工具来源 | mcp_tools 注册表 | **同一个注册表 (zero duplication)** |
| 用户交互 | 实时 | 启动时给 goal,跑完返回结果 |
| 依赖 | 无额外 | `claude-agent-sdk` + `ANTHROPIC_API_KEY` |

关键设计:
1. **同一 tools 注册表** — `_default_tool_registry()` lazy import `database.mcp_tools`,
   两种模式行为完全一致
2. **优雅降级** — `is_agentic_available()` 探测 SDK + API key,缺任一即返回结构化
   错误而不是抛异常
3. **dry_run 模式** — 不调 LLM 只打印 plan,CI 验证配置正确性时用
4. **lazy import claude_agent_sdk** — 没装 SDK 的开发者 import 此模块不报错

## 替代方案

### A. 不做,让用户自己写脚本调 MCP tools

**否决**:
- DBJavaGenix 自己的 MCP server 只对接 stdio / SSE,直接调要重新搞 transport
- "写一个 agent loop" 是 ~150 行模板代码,我们提供省得每个用户重写
- 失去 "我们也会用 Agent SDK" 的叙事点

### B. 用 LangChain Agent / AutoGen

**否决**:
- v0.1 LangChain 试过(见 `docs/experiments/v0.1-langchain-orchestrator.md`)— 重、慢、抽象漏出
- AutoGen 适合多 agent 协作,我们只需要单 agent
- Claude Agent SDK 是官方一手 SDK,跟 Claude 模型更新节奏同步

### C. 把 agentic 做成默认模式,弃用 mcp_server

**否决**:
- MCP server 模式不依赖 ANTHROPIC_API_KEY,门槛低
- 客户端模式有 UI / 多轮交互优势,适合探索性工作
- 两种模式互补,各擅胜场

### D. 复用 mcp_server 进程,加 "agentic" 子命令

**否决**:
- 启动路径耦合,debug 困难
- 两种模式的 lifecycle 差异大(server 长驻 vs runner 一次性)
- 拆开 ~200 行换来清晰边界,值得

## 后果

**好**:
- 1 行命令完成 "schema 分析 → 代码生成" 全流程
- CI 友好 (dry_run 校验 + 真实模式跑批)
- Tools 零重复,任何 mcp_server 的新工具自动出现在 agentic 模式
- 13 个 unit test 验证启动路径(无需真实 API key)
- 为未来 "subagent" 留接口 (Agent SDK 支持 subagents)

**坏**:
- 多一个可选依赖 `claude-agent-sdk` (放 optional-deps,不是必需)
- 文档要解释 "两种模式怎么选" (README 加了对比表)
- agent 失控成本高 — `max_iterations` 默认 20 是软上限,真实场景仍要监控

**实测** (2026-06 dry_run + 真实 schema):
- dry_run: `dbjavagenix agentic --goal "..." --dry-run` 200ms 内返回 plan
- 真实跑: 一个 12 表的项目从 goal 到代码落地 ~90s,18 次 tool call

## 叙事意义

2025-2026 LLM 工程演进的关键节奏:
1. **2024**: 单次 prompt / 简单 RAG
2. **2025 H1**: tool use + MCP 协议
3. **2025 H2 - 2026 H1**: **Agent SDK / Skills** — 标准化 agent 框架

DBJavaGenix 从 v0.1 (RAG 实验) → v0.2 (MCP tools) → v0.2.2 (agentic 模式)
踩了完整三个节奏。这个 ADR 是第三节奏的落地证据。

更深的含义:**工具应该既能被 LLM 用,也能被 agent 用,还能被人用**。
agentic_runner 把 "同一组 MCP tools" 的复用边界推到极致 — 这是 v0.2.2 想表达的
"工程师视角下的 AI 集成"。
