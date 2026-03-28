# ADR-005 草稿: 不引入的依赖

5 个明确 NO:

## 1. 不引入向量数据库 (Faiss / Annoy / hnswlib / Chroma)
依据:[v0.1-vector-tool-search] 实测

## 2. 不引入 LangChain / LlamaIndex
依据:[v0.1-langchain-orchestrator] 实测

## 3. 不引入 prometheus_client / opentelemetry-sdk
依据:MCP 是 stdio 进程,没 HTTP endpoint 给 Prometheus pull

## 4. 不引入 structlog
依据:stdlib logging + 自定义 JsonFormatter 够用

## 5. 不引入 RAG / 图数据库
依据:schema 已结构化,LLM 直接读

## 反思
这五个"不"本身就是面试加分项。
