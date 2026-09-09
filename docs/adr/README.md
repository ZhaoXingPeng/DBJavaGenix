# Architecture Decision Records (ADR)

> 重构期间的关键决策。每个 ADR 包含: 背景 / 决定 / 替代方案 / 后果。

## 索引

### Phase 1-5 (v0.2 主线)
- [ADR-001: 三层架构 (Skills + MCP + Apps)](001-three-layer-architecture.md)
- [ADR-002: 拆分大工具为原子工具](002-atomic-codegen-tools.md)
- [ADR-003: Progressive Discovery (Tool Search)](003-progressive-tool-discovery.md)
- [ADR-004: 规则推断优先于 LLM](004-rule-first-then-llm.md)
- [ADR-005: 不引入的依赖 (划清边界)](005-non-dependencies.md)

### v0.2.1 (Java 工程补完)
- [ADR-006: schema 图算法自实现](006-schema-algorithms.md)
- [ADR-007: 自带工程规范配置生成](007-quality-config-generation.md)

### v0.2.2 (MCP v3 + AI 工程化)
- [ADR-008: 引入 MCP v3 elicitation + sampling](008-mcp-v3-elicitation-sampling.md)
- [ADR-009: 1h prompt caching TTL 作为可选项](009-prompt-caching-1h-ttl.md)
- [ADR-010: agentic-runner 作为可选启动模式](010-agentic-runner-mode.md)
- [ADR-011: Multi-dialect strategy](011-multi-dialect-strategy.md)
- [ADR-012: Pin MCP SDK to the 1.x API contract](012-mcp-sdk-compatibility.md)
- [ADR-013: Canonical MCP tool contract](013-canonical-mcp-tool-contract.md)

### v0.3 (数据库元数据契约)
- [ADR-014: 统一数据库元数据描述契约](014-metadata-introspection-contract.md)
- [ADR-015: MCP 连接生命周期与显式释放](015-connection-lifecycle.md)
- [ADR-016: 将同步数据库调用移出 MCP 事件循环](016-async-database-boundary.md)
