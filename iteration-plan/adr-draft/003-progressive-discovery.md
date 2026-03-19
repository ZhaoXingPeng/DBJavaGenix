# ADR-003 草稿: Progressive Tool Discovery (keyword + tag)

## 背景
拆 6 原子工具后,工具总数从 15 涨到 22 → 29。每次 list_tools 全暴露 ~3300 tokens 启动开销。

## 提案
- always_visible 子集 (~6 工具) 默认暴露
- search_tools(query) meta-tool 按需发现其他工具
- 评分:exact name +10, tag +3, name substr +2, desc substr +1

## 为什么不用 embedding
见 v0.1 复盘 [v0.1-vector-tool-search]:实测 keyword 在 15 工具规模胜出。
29 工具规模仍在 keyword 占优区间。

## 优势
- 启动 token -70% (3304 → 985)
- 无新依赖
- 维护成本低 (tags 手工)

## 待完善
正式 ADR 时补 token 实测数据 + 客户端体感。
