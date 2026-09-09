# ADR-016: 将同步数据库调用移出 MCP 事件循环

- **状态**: Accepted
- **日期**: 2026-09-09
- **关联 Issue**: #211
- **关联实现**: `src/dbjavagenix/database/connection_manager.py`

## 背景

MCP handler 使用 `async def`，但数据库驱动和元数据 introspector 仍是同步实现。
网络等待或大型 SQLite 查询会占住事件循环，使同一会话的健康检查、取消和其他连接请求
延迟。SQLite 默认还会拒绝跨线程使用连接；多个 worker 直接共享一个连接也可能交叉使用
cursor。

## 决定

1. 在 MCP 数据库边界统一使用 `asyncio.to_thread`；保留同步 `ConnectionManager` API，
   供 CLI、测试和外部调用方继续使用。
2. `ConnectionManager` 为每个 connection ID 建立可重入锁，锁覆盖健康探测、cursor
   生命周期、SQL 执行和关闭；不同连接不共享这把锁。
3. SQLite 连接启用 `check_same_thread=False`，但只有在上述连接锁保护下交给 worker。
4. 异步 analyzer 通过 worker 中的短生命周期 event loop 执行，输入输出合同保持不变。
5. 取消异步 handler 不强杀底层驱动调用；worker 返回后由 context manager 关闭 cursor，
   连接仍可被显式 `db_disconnect` 释放。

## 备选方案

- 替换原生异步 MySQL/PostgreSQL 驱动：迁移成本高且会改变方言、事务和依赖边界，暂不采用。
- 只在 handler 外包线程、不加连接锁：会留下 SQLite thread-affinity 和 cursor 交叉风险，
  不采用。
- 为每个请求建立新连接：增加连接开销并破坏现有 connection ID 生命周期，不采用。

## 影响

- 同步公共 API、SQL、事务提交/回滚、权限和 MCP 文本/Raw Response 保持不变。
- 同一连接的数据库阶段串行，不同连接可以并行等待；不宣称生产吞吐提升。
- worker 调度带来少量开销；驱动额外的线程绑定限制需要在真实 MySQL/PostgreSQL 环境
  单独验证。

## 验证

- 受控 60ms 阻塞 driver + heartbeat 证明事件循环仍获调度。
- fake cursor 实验覆盖同连接最大并发为 1、跨连接同时进入和 close 等待 SQL body 完成。
- SQLite in-memory worker 查询和现有 SQLite MCP/codegen 合同继续通过；真实网络数据库
  线程模型不在本地实验范围内。
