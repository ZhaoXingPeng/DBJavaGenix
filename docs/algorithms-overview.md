# Schema 算法概览 — DBJavaGenix v0.2.1

> 三个图算法,纯 Python 实现,无外部依赖。
> 用于代码生成器对 schema 本身的分析:依赖排序、业务簇识别、循环检测。
> 详见 [ADR-006](adr/006-schema-algorithms.md)。

## 1. schema_topo — 拓扑排序 (Kahn 算法)

### 问题
有一组表和它们的外键依赖。给我一个"安全"的顺序,使得任何表都排在所有它依赖的表之后。

### 算法
```
1. 计算每个表的入度 (依赖了几个其他表)
2. 把入度为 0 的表入队列 (排序保证确定性)
3. 从队列出一个表,append 到结果
4. 这个表的所有"子表"(依赖它的)入度 -1
5. 入度变 0 的子表入队
6. 队列空时,如果还有表入度 > 0,这些表在环里 → unresolved
```

### 复杂度
O(V + E)。50 表库毫秒级。

### 输出
```python
TopoResult(
    order=["sys_role", "sys_user", "sys_user_role"],
    unresolved=[],
    levels={"sys_role": 0, "sys_user": 0, "sys_user_role": 1},
)
```

### 用途
- **DDL 顺序**: CREATE TABLE 时按 order 来,父表先建
- **Service 注入顺序**: Spring Boot 启动时,被依赖者先 instantiate
- **删除顺序**: 反向遍历 order,先删依赖少的

### 边界处理
- self-reference (employee.manager_id → employee.id):跳过,不阻塞
- FK 指向外部表(不在 tables 列表):跳过,视为外部依赖已满足

---

## 2. schema_cluster — 业务簇识别 (Union-Find)

### 问题
一个 100 表的库,哪些表关系紧密(用户簇 / 订单簇 / 字典簇)?

### 算法
```
1. 把 FK 关系图当无向图
2. Union-Find:每张表初始自成簇
3. 对每条 FK (a, b): union(a, b) — 它们属于同一簇
4. 最后用 find() 把表按根分组
5. 给每簇起名:
   - 最长公共前缀 (>=3 字符) → "biz_user_*"
   - 否则用中心表 (in-degree 最高的) → "around:central_table"
   - 单表簇用自身名
```

### 复杂度
近 O((V+E) * α(V)),α 是反 Ackermann 函数,几乎是常数。

### 输出
```python
ClusterResult(
    clusters=[["sys_user", "sys_user_role"], ["sys_role"], ["log_audit"]],
    naming={0: "sys_user_*", 1: "sys_role", 2: "log_audit"},
)
```

### 用途
- **包结构推荐**: 每个簇一个 Java package (`com.app.user`, `com.app.order`)
- **业务模块划分**: 簇就是天然的微服务候选边界
- **孤立表预警**: size=1 的簇可能是漏接的表 / 字典表

### 为什么用 Union-Find 而不是 BFS
- Union-Find 适合增量构图(每加一条 FK 就 union 一次)
- 路径压缩 + 按秩合并保证准线性
- 不需要显式遍历图

---

## 3. schema_cycle_check — FK 环检测 (DFS 三色)

### 问题
我的库里有没有 FK 环?例如 user → order → user_metadata → user?

### 算法
```
DFS,三种颜色:
- WHITE: 未访问
- GRAY: 当前在 DFS 栈上 (active path)
- BLACK: 完全探索完,离开栈

遇到 GRAY 节点 = 环!从该节点到当前位置就是环路径。

去重:同一个环可能从多个入口被发现,用 lexicographic canonical
rotation (字典序最小循环移位) 作为唯一 key。
```

### 复杂度
O(V + E)。

### 输出
```python
CycleResult(
    cycles=[["user", "order", "user_metadata"]],  # 含环上所有节点
    safe=False,  # 有环
)
```

### 用途
- **anti-pattern 提示**: 环几乎都是 schema 设计错误
- **生成代码前检查**: 有环就警告,避免生成出无法编译/插入的代码
- **可视化**: 客户端拿到 cycles 列表,可以在 ER 图里高亮

### 解决环的 3 种方式
1. 引入中间表打破环 (典型:user ↔ order 之间加 order_user_assoc)
2. 让某条 FK 可空 (允许 INSERT 时 NULL 起步)
3. 重新审视是否真的需要双向 FK

---

## 共同设计

### 输入统一
所有三个算法接收 `(tables: list[str], fks: list[tuple[str, str]])`,
其中 fks 是 `(child, parent)` 形式 —— child 表有 FK 指向 parent。

### 输出统一
都是 `@dataclass` 结构化结果,带 docstring 说明字段含义。

### 确定性
所有算法在等价输入下产生**相同输出**:
- queue / DFS 邻居遍历都先 sort
- 多解时按字典序选择
- 这让单测可以严格断言

### 无外部依赖
只用 `collections` 和 `dataclasses` (Python stdlib)。
对比:如果用 networkx,镜像大小 +10MB,启动延迟 +1-2 秒。
详见 [ADR-006](adr/006-schema-algorithms.md)。

---

## MCP 工具包装

三个算法各自对应一个 MCP 工具:
| 工具 | 算法 | 文件 |
|------|------|------|
| `schema_topo_order` | Kahn | algorithms/schema_topo.py |
| `schema_cluster_tables` | Union-Find | algorithms/schema_cluster.py |
| `schema_check_cycles` | DFS | algorithms/schema_cycle_check.py |

工具实现在 `database/schema_algorithms_tools.py`。

输入 schema 都是:
```json
{
  "tables": ["sys_user", "sys_role", "sys_user_role"],
  "fks": [["sys_user_role", "sys_user"], ["sys_user_role", "sys_role"]]
}
```

输出是 JSON 序列化的算法 result 对象。

---

## 测试覆盖

| 模块 | 单测数 | 覆盖率 |
|------|--------|--------|
| schema_topo | 10 | 100% |
| schema_cluster | 9 | 100% |
| schema_cycle_check | 11 | ~95% |
| schema_algorithms_tools | 10 | ~90% |

共 40 个 unit test 覆盖三个算法 + 工具包装。
