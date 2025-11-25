# 2025-11-25 晚: MCP anniversary spec 正式发布

## RC vs GA 对比
- 1 个 wire format 微调 (async ops 的 ID 字段从 token → operationId)
- 其他无变化

## async ops 详细 wire format
工具调用:
```json
{"method": "tools/call", "params": {"name": "codegen_render_dao", "arguments": {...}, "_meta": {"async": true}}}
```
server 返回:
```json
{"content": [], "isError": false, "_meta": {"async": {"status": "pending", "operationId": "op-abc123"}}}
```
client 轮询:
```json
{"method": "operations/get", "params": {"operationId": "op-abc123"}}
```

## 决策
- v0.2 主体不引 async ops(同步够用)
- 给 codegen_render_* 留 async 接口预留位 (但默认同步)
- v0.3 大库场景再开 async

## 11 月小结
MCP 这个月生态变化很大,我们的 v0.2 设计可以基于 anniversary 版做。
