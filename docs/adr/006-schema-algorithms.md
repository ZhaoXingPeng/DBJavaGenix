# ADR-006: 引入 schema 图算法作为分析底层

**状态**: Accepted (v0.2.1 落地, 2026-05)
**关联**: `src/dbjavagenix/algorithms/`, `src/dbjavagenix/database/schema_algorithms_tools.py`

## 背景

v0.2 (Phase 1-6) 把 LLM/MCP/Skills 这条线做完了。但作为"代码生成器"项目,只覆盖
"LLM 推断业务命名 + 模板渲染" 这一层是不够的。代码生成器还应该有**对 schema 本身的
分析能力** — 这是工程基础。

具体场景:
1. 生成 DDL 时,如果 A 表的外键引用 B 表,A 的 CREATE 必须在 B 之后
2. Spring Boot 工程的 Service 注入顺序也要按依赖图排
3. 表之间的业务簇识别(用户簇 / 订单簇 / 字典簇)可以作为包结构推荐
4. FK 循环(A→B→A)是典型 anti-pattern,应该在生成代码前提示

这些都是图算法,不是 LLM 范畴。

## 决定

新增 `src/dbjavagenix/algorithms/` 模块,纯算法,无 I/O,无 DB 依赖:

1. **schema_topo** (Kahn 拓扑排序)
   - 输入:tables + (child, parent) FK
   - 输出:order, unresolved (环), levels (深度)
   - 用途:DDL 顺序 / Service 注入顺序

2. **schema_cluster** (Union-Find)
   - 输入:tables + FK
   - 输出:clusters + 命名启发(common prefix / 中心表)
   - 用途:业务簇识别 / 包结构推荐

3. **schema_cycle_check** (DFS 三色标记)
   - 输入:tables + FK
   - 输出:cycles list + safe flag
   - 用途:FK 环检测(anti-pattern 提示)

通过 `src/dbjavagenix/database/schema_algorithms_tools.py` 包装为 3 个 MCP 工具:
- `schema_topo_order`
- `schema_cluster_tables`
- `schema_check_cycles`

## 替代方案

### A. 套用 networkx 库

`pip install networkx`,直接用 `networkx.topological_sort` / `networkx.connected_components`
/ `networkx.simple_cycles`。

**否决**:
- networkx 是大库 (~10MB,带 numpy 依赖),启动 +1-2 秒
- 我们的需求是三个 well-known 算法,自己实现 ~80 行 / 算法,比依赖外部包更可控
- 自己写的算法在测试 / 调试上更透明
- 跟 ADR-005 "不引入大库" 的精神一致

### B. 在 ai_summarize_schema 里隐式做

把拓扑排序等"埋"进 ai_summarize_schema 工具,作为副作用输出。

**否决**:
- 算法是确定性结果,不应该绑在概率性 LLM 工具上
- 让用户能单独调用算法(不打 API,毫秒级)有独立价值

### C. 不做,继续靠 LLM

让 LLM 在 system prompt 里"自己排个序"。

**否决**:
- LLM 排序在大库时会幻觉(漏表 / 顺序错)
- 确定性算法零成本,为什么不用

## 后果

**好**:
- 三个工具都是纯算法,零依赖外部库 (除 stdlib)
- 离线 / CI 可跑,无 API key 需求
- 总代码量约 280 行(三个算法)+ 250 行测试
- 复杂度都是 O(V+E),50 表库毫秒级
- 给"代码生成器"补完了"schema 分析"维度

**坏**:
- 多了 3 个 MCP 工具,工具总数 29 → 32(progressive discovery 仍然能处理)
- 算法自己实现,如果有 bug 要自己修(测试覆盖到位)

**实测**:
- 30 个 unit test 全部通过(topo 10 + cluster 9 + cycle 11)
- RBAC / 电商 / 字典 等真实样本验证正确

## 叙事意义

ADR-005 讲了 "不引入" 的克制,ADR-006 讲的是 "自己实现" 的能力。两者配合:
- 不引大库 (LangChain / 向量库 / networkx)
- 但需要的算法自己实现到位
- 测试覆盖到位

这是工程能力的体现。
