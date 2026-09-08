# 元数据描述基线

该基准用于比较 `DatabaseIntrospector.describe_table()` 的真实变化，不预设优化目标，也不把单机延迟当作跨环境结论。

## 复现

基准只使用 SQLite 内存数据库，不需要 Docker 或外部数据库：

```powershell
$env:PYTHONPATH = "src"
python scripts/benchmark_introspection.py --iterations 30 --warmup 5
```

输出为 JSON，包含冷调用与热调用的中位数、P95、最小/最大延迟，以及 SQL 查询次数。`queries_per_call`
表示清空缓存后的冷调用往返数，`warm_queries_per_call` 表示缓存命中时每次调用的平均往返数。
固定 schema 包含 `users`、`orders`、复合索引和外键，确保不同提交使用相同输入。

## 解释结果

- `queries_per_call` 用于识别冷路径 SQL 往返次数，`warm_queries_per_call` 应在缓存命中时为 0；
  它们比单次延迟更适合作为代码优化的稳定信号。
- 延迟受操作系统、Python 版本和当前负载影响。提交 PR 时应附上命令、环境和原始 JSON，不将本地数字写成普遍性能保证。
- 当前基准只覆盖 SQLite；PostgreSQL/MySQL 对比需要可用的真实实例或 CI 服务后再扩展。

## 当前范围

当前基准包含 SQLite 自增主键识别所需的 `sqlite_master` DDL 查询，因此固定 schema 的冷
`describe_table` 包含 7 次 SQL 往返；连接级缓存的热调用不产生 SQL 往返。延迟受操作系统、
Python 版本和当前负载影响，不代表性能提升或跨环境结论。后续优化必须同时记录冷/热结果和
元数据契约测试结果。
