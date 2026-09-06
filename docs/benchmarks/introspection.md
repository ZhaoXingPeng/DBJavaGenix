# 元数据描述基线

该基准用于比较 `DatabaseIntrospector.describe_table()` 的真实变化，不预设优化目标，也不把单机延迟当作跨环境结论。

## 复现

基准只使用 SQLite 内存数据库，不需要 Docker 或外部数据库：

```powershell
$env:PYTHONPATH = "src"
python scripts/benchmark_introspection.py --iterations 30 --warmup 5
```

输出为 JSON，包含中位数、P95、最小/最大延迟，以及每次描述调用的 SQL 查询次数。固定 schema 包含 `users`、`orders`、复合索引和外键，确保不同提交使用相同输入。

## 解释结果

- `queries_per_call` 用于识别 SQL 往返次数变化；它比单次延迟更适合作为代码优化的稳定信号。
- 延迟受操作系统、Python 版本和当前负载影响。提交 PR 时应附上命令、环境和原始 JSON，不将本地数字写成普遍性能保证。
- 当前基准只覆盖 SQLite；PostgreSQL/MySQL 对比需要可用的真实实例或 CI 服务后再扩展。

## 当前范围

本次只建立可重放基线，没有改变元数据查询实现，也没有声称性能提升。后续优化必须先用该基准记录前后结果，并同时确认元数据契约测试仍通过。
