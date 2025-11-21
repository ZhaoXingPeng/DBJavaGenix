# 2025-11-21: MCP 2025-11-25 anniversary spec - RC 速读

11.11 放出 RC,14 天 RC 窗口。11.25 正式发。预读关键点:

## 大改

1. **async ops**:工具可以返回 `pending` 状态,客户端轮询
2. **server identity**:server 可以声明自己的 identity / capability
3. **sampling with tools**:server 反向调 LLM 时可以带工具集
4. **官方 MCP Registry**:已经在用了,这次写进 spec

## 对本项目

**最有用**: async ops。我们的 codegen_render_* 同步返回字符串,但生成大库 (>200 表) 可能慢。
async 让客户端先看到 "正在生成中",server 后台跑。

**也有用**: server identity。可以在 metrics 工具里返回我们的 build_version / commit_hash。

**暂不急**: sampling with tools (v3 已经有 sampling 基础),Registry (后期再注册)。

## 行动
- [ ] 11.25 当晚再仔细看正式版本 changelog,看 RC 到 GA 有无变化
