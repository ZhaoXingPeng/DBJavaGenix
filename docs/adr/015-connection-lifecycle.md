# ADR-015: MCP 连接生命周期与显式释放

- **状态**: Accepted
- **日期**: 2026-09-09
- **关联 Issue**: #209
- **关联实现**: `src/dbjavagenix/database/mcp_tools.py`

## 背景

`ConnectionManager` 已经能够按 connection ID 关闭连接，但公共 MCP 合同只
暴露 `db_connect_test`。长生命周期客户端无法在探索完成、重试失败或切换数据库
时主动释放连接，连接对象和脱敏配置会一直保留到 server 进程退出。

## 决定

新增 `db_disconnect(connection_id)` 作为显式连接生命周期工具：

1. handler 只负责校验参数、调用 `ConnectionManager.close_connection()` 和序列化
   响应，不复制连接状态或驱动逻辑。
2. 成功关闭返回 `success=true`；未知、空值和重复关闭统一返回
   `success=false`、`error=connection_not_found`。
3. 关闭异常返回 `disconnect_failed`，异常文本经过现有凭据脱敏边界后再返回。
4. 工具加入 canonical MCP 列表和 progressive discovery 元数据；默认 progressive
   可见集合不变，客户端可通过 `search_tools("disconnect")` 发现它。
5. 客户端在会话结束时调用该工具；不引入连接池、TTL、后台回收或自动关闭策略。

## 备选方案

- 仅依赖进程退出时的 `__del__`：无法覆盖长会话中的提前释放和异常重试，已拒绝。
- 增加后台 TTL：可能误杀仍在使用的连接，并引入不可预测的时序，已拒绝。
- 在 handler 内直接操作驱动连接：会重复生命周期逻辑，绕过 `ConnectionManager`，已拒绝。

## 影响

- 连接建立和查询 API 保持兼容，旧客户端无需立即改造。
- 释放后的 connection ID 不可继续使用；后续查询收到既有的连接不存在错误。
- 显式释放降低长生命周期会话的资源占用，但不承诺性能收益或自动回收。

## 验证

- 单元测试覆盖工具 schema、成功关闭后的连接与配置清理、未知/空值/重复 ID、
  异常脱敏以及 canonical server dispatch。
- 使用 SQLite in-memory manager 和 monkeypatch 验证，不伪造真实 MySQL/PostgreSQL
  连接释放结果。
