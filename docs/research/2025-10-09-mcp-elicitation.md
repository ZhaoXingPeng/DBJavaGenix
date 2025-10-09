# 2025-10-09: MCP v3 (2025-06-18) elicitation

## 是什么
elicitation 允许 MCP server **主动**向用户/客户端发问 — 不是被动响应,而是 server 说"我需要更多信息"。

## 协议形态
```jsonrpc
{
  "method": "elicitation/create",
  "params": {
    "message": "请提供数据库连接信息",
    "requestedSchema": {
      "type": "object",
      "properties": {
        "host": {"type": "string"},
        "port": {"type": "integer"},
        "username": {"type": "string"},
        "password": {"type": "string", "format": "password"}
      }
    }
  }
}
```

客户端弹表单,用户填,server 拿到结构化结果。

## 对 DBJavaGenix 的应用

**场景**:用户说"从我的库生成代码",没提供 host/port/user/pwd。当前的 db_connect_test 工具会失败。

**用 elicitation 改造**:
- db_connect_test 拿到不完整参数时,server 触发 elicitation
- 客户端弹连接表单,用户填
- server 拿到完整参数,继续

## 客户端兼容性
- Claude Desktop 4.x:支持
- Cherry Studio:支持
- Cursor:不支持,降级走错误返回

## 列入 v0.2 候选
但 elicitation 本质是 UX 优化,不是关键路径。先用 plain error 返回,后续加。
