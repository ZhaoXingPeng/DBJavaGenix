# ADR-005: 不引入的依赖 (划清边界)

**状态**: Accepted (各阶段持续应用, 2026-05)

## 背景

每加一个依赖都有隐性成本: 启动时间、安装大小、CVE 维护负担、API breaking change 风险。每个 Phase 都有"看起来应该用"的库,但加之前必须问: 这库带来的复杂度是否换得 actual user value?

## 决定 (5 个明确"不引入")

### 1. 不引入向量数据库 (Faiss / Annoy / hnswlib / Chroma)

**为什么诱人**: search_tools (P2.3) 看起来像"工具检索",可以用 embedding。  
**为什么不要**: 29 个工具规模下,关键词 + tag 已经精准 (实测 "render dao" 第一名就是 codegen_render_dao)。向量库引入 ~ 50MB 安装大小 + 1-2 秒冷启动延迟。`utils/tool_registry.py` 33 行实现搞定。

### 2. 不引入 LangChain / LlamaIndex

**为什么诱人**: 多步 LLM 工作流听起来像 "chain"。  
**为什么不要**: 我们的工作流已经被 **Skill 文件显式编排** (ADR-001),链条结构由 Skill markdown 写死,LLM 按部就班,不需要 framework 抽象。LangChain 的 callback/memory/agent 等概念对单进程 stdio MCP 是 overkill。

### 3. 不引入 prometheus_client / opentelemetry-sdk

**为什么诱人**: Phase 5 谈"可观测性"自然想到 Prometheus + OTel。  
**为什么不要**:
- MCP server 是 **stdio 进程**,生命周期跟随 client。没有 HTTP endpoint 让 Prometheus pull。
- OTel 完整栈含 OTLP exporter + context propagation + span processor,启动开销 ~ 200 ms,对单进程过度设计。
- 改用 in-process counter (`utils/metrics.py` 154 行) + MCP 工具暴露查询 (`server_metrics` / `ai_metrics`)。运维方接入 MCP 客户端即可读。

### 4. 不引入 structlog

**为什么诱人**: 结构化日志 (P5.2) 听起来像 structlog 的菜。  
**为什么不要**: stdlib `logging` + 自定义 `JsonFormatter` (122 行) 已够用。structlog 增加新概念 (BoundLogger / processor chain),团队学习成本不值。

### 5. 不引入 RAG / 图数据库

**为什么诱人**: 多表关系听起来像图,schema 概述听起来像 RAG。  
**为什么不要**:
- Schema 是结构化的 (information_schema),LLM 直接读列表更准
- 表关系用普通 SQL 外键就够,杀鸡用牛刀
- 大库 (1000+ 表) 才有 RAG 价值,DBJavaGenix 当前定位单库 ≤ 100 张表

## 替代方案 (为什么不预留接口)

```python
# 反例: "未来可扩展" 的接口
class ToolSearchBackend(ABC):
    @abstractmethod
    def search(self, query): ...

class KeywordBackend(ToolSearchBackend): ...
class EmbeddingBackend(ToolSearchBackend): ...  # 未实现
```

**否决**: YAGNI (You Aren't Gonna Need It)。当前没有 vector 后端的需求,先写 keyword 实现,真到了需要时再抽象。

## 后果

**好**:
- 依赖树短 (`pyproject.toml` 仅 6 个 runtime deps)
- Docker 镜像 ~ 200 MB (Python:3.11-slim base)
- CI 安装 + 测试 < 60 秒
- 心智负担低,新人 onboarding 一天能上手

**坏**:
- 未来需要 vector search / 完整 OTel 时,要做一次"引入新依赖"的 RFC 决策
- 受限场景 (例如必须接 Prometheus 监控的运维方) 需要写 sidecar / adapter

**反思 (划清边界本身就是面试加分项)**:
- 面试官问"为什么不用 X 库" → 答得出来才是真的懂工程克制
- 引一个库要权衡: 这库节省的代码量 vs 引入的复杂度,大多数情况下 "less is more"
