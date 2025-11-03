# 2025-11-03: elicitation 用在 db_connect_test

## 场景
用户:"从我数据库生成代码,host=192.168.1.5"
LLM 调 db_connect_test(host="192.168.1.5"),缺少 port/username/password。

## 当前行为 (v0.1)
返回错误 `{"error": "missing required params: port, username, password"}`。
LLM 抓到错,反过来问用户。**3 轮对话**,UX 不好。

## elicitation 改造
db_connect_test 检测到参数不足,server 直接发 elicitation/create:
```json
{
  "method": "elicitation/create",
  "params": {
    "message": "需要数据库连接信息",
    "requestedSchema": {
      "type": "object",
      "required": ["port", "username", "password"],
      "properties": {
        "port": {"type": "integer", "default": 3306},
        "username": {"type": "string"},
        "password": {"type": "string", "format": "password"}
      }
    }
  }
}
```
客户端弹原生表单,**1 轮交互完成**。

## 客户端支持矩阵 (2025-11 调研)
- Claude Desktop 4.x: ✅ 弹模态表单
- Cherry Studio: ✅ 弹 inline 表单
- Cursor: ❌ 当前不支持 elicitation,降级走错误返回
- Continue.dev: ✅ 但 UX 较粗糙

## 决策
v0.2 实现时:
- 默认走错误返回(老兼容)
- 如果客户端 declares elicitation capability,走 elicitation
- 在 SKILL.md 里告诉 LLM "如果第一次失败,通过 elicitation 收集补充信息"

## 复杂度
不复杂。MCP Python SDK 1.6 已经支持 elicitation/create。
