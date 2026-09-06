# ADR-014: 统一数据库元数据描述契约

- **状态**: Accepted
- **日期**: 2026-09-07
- **关联 Issue**: #18
- **关联实现**: `src/dbjavagenix/database/introspection.py`

## 背景

代码生成、MCP 表工具和 ER 可视化都需要读取表、列、主键、外键和索引。早期实现把 MySQL、PostgreSQL 和 SQLite 查询分散在调用方，导致同一字段在不同数据库中的名称、空值和顺序不一致。PostgreSQL schema 同名表和 SQLite 特殊表名还会让“看似成功”的结果指向错误对象。

## 决策

以 `DatabaseIntrospector` 作为数据库元数据的唯一读取边界：

1. 对外返回统一字典结构：`name`、`schema`、`comment`、`columns`、`primary_keys`、`foreign_keys`、`indexes`。
2. 方言 SQL 只保留在 introspector 内部；调用方不再根据数据库类型拼接 catalog/PRAGMA 查询。
3. PostgreSQL 查询在提供 schema 时必须对所有 catalog 查询加同一 schema 条件；未提供 schema 且存在歧义时明确要求调用方指定 schema。
4. SQLite PRAGMA 标识符统一转义单引号，并保留复合索引的列顺序和表达式索引占位信息。
5. 新增字段必须先更新跨数据库契约测试，再被代码生成或 MCP 工具消费。

## 备选方案

- 让每个 MCP 工具维护自己的查询：实现重复、修复无法同步，已拒绝。
- 使用 SQLAlchemy Inspector 直接暴露厂商结果：无法稳定覆盖注释、原生类型和 SQLite PRAGMA 的项目契约，且会把方言差异泄漏给上层，已拒绝。
- 只返回最小的表/列列表：无法满足代码生成所需的约束、索引和注释信息，已拒绝。

## 影响

- 代码生成、MCP 表详情和 ER 图共享同一元数据语义，新增数据库方言只需扩展边界模块和契约测试。
- `describe_table` 会按表、列、主键、外键、索引读取多组元数据；查询往返次数由 `docs/benchmarks/introspection.md` 的可重放基准持续记录。
- 返回结构稳定优先于厂商字段一一映射；厂商独有字段可以保留在标准字段中，但不能改变必需字段的含义。

## 验证

- `tests/unit/test_metadata_contract.py` 验证 MySQL、PostgreSQL、SQLite 的共同字段和主键/索引语义。
- `tests/unit/test_database_introspection.py` 验证 PostgreSQL schema 隔离、歧义检测、SQLite 特殊标识符及复合索引顺序。
- PostgreSQL/SQLite 具体行为由相应集成测试和 MCP 工具回归测试覆盖。

## 后续

新增 Oracle 或 SQL Server 支持时，必须实现同一契约并补充真实数据库集成测试；在此之前不在 README 中宣称其元数据读取已完成。
