# ADR-003: Progressive Discovery (Tool Search)

**状态**: Accepted (Phase 2.3 落地, 2026-05)
**关联**: `src/dbjavagenix/utils/tool_registry.py`, [docs/benchmarks/token-usage.md](../benchmarks/token-usage.md)

## 背景

拆分原子工具 (ADR-002) 后,server 注册的工具从 15 涨到 22 → 29。每个工具的 `inputSchema` 在 `list_tools` 响应里完整暴露给 LLM。

实测 29 个工具的 schema 在初始 `list_tools` 中合计 **~ 3300 tokens**,仅工具列表就占用每次 conversation 的初始上下文。

## 决定

引入 **Progressive Discovery** 机制:

1. 每个工具的 `ToolMetadata` 多一个 `always_visible: bool` 字段
2. 通过环境变量 `DBJAVAGENIX_PROGRESSIVE=1` 启用过滤模式
3. progressive 模式下 `list_tools` 只返回 `always_visible=True` 的工具
4. 新增 meta-tool `search_tools(query: str)` 按关键词搜索完整 tool registry
5. LLM 在 progressive 模式下,通过 `search_tools` 按需"发现"其他工具,再 call_tool 调用

**Always-visible 集合 (6 个,合计 ~985 tokens)**:
- `db_connect_test` (建立连接)
- `db_query_tables` (列出表)
- `db_table_describe` (看表结构)
- `codegen_build_context` (代码生成入口)
- `springboot_validate_project` (项目预检)
- `search_tools` (发现其他工具)

**搜索打分**:
- exact name match: +10
- tag 命中: +3
- name substring: +2
- description substring: +1

## 替代方案

### A. 按工具 category 分组,客户端切换

让客户端 UI 提供"显示/隐藏 ai_* 工具"开关。
**否决**: 把切换决策推给 UI 端,各客户端实现不一致。Server 端控制更可控。

### B. 向量检索 (embedding search)

工具描述用 embedding 模型 vectorize,query 时算余弦相似度。
**否决**: 29 个工具规模下关键词匹配已精准 (实测 query="render dao" 第一名就是 codegen_render_dao);引入 ANN 库 (Faiss / Annoy / hnswlib) 增加启动延迟与依赖复杂度,违背"工程克制"边界。

### C. 动态 MCP `tools/listChanged` 通知

MCP 1.6 支持工具列表变更通知,server 可在运行时动态加/减工具。
**部分采纳**: 我们没用 listChanged 主动推送,只通过 search_tools + call_tool 名称白名单实现。listChanged 留作 v0.3 优化项。

## 后果

**好**:
- 启动 token 减 70.2% (3304 → 985)
- 客户端不变 — 只是看到的工具列表更短
- 调用任何工具仍然走原通路,无路由分支

**坏**:
- LLM 第一次需要某工具时,先调一次 `search_tools` 再 call_tool → 多一轮 round-trip
- tool_registry 元数据 (tags) 是手工维护,新加工具要记得同步

**实测数据**:
| 模式 | 工具数 | tokens | 节省 |
|------|--------|--------|------|
| Default | 22 (现 29) | 3304 | 基线 |
| Progressive | 6 | 985 | -70.2% |
