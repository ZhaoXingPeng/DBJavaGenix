# 部署与运维指南

> DBJavaGenix MCP Server 的生产部署 / 监控 / 排障手册。Phase 5 产出。

## 一、部署模式

DBJavaGenix 是 **stdio MCP Server**,不监听网络端口,生命周期跟随调用它的 client 进程。

```
LLM Client (Claude Desktop / Cursor / ...)
     │ stdin / stdout (JSON-RPC)
     ▼
[ dbjavagenix python -m dbjavagenix.cli server ]
     │
     ▼
MySQL / PostgreSQL / SQLite + 文件系统 (templates)
```

支持 3 种部署方式:

### A. Docker (推荐生产)

```bash
docker build -t dbjavagenix:latest .

# client 端配置 (claude_desktop_config.json):
{
  "mcpServers": {
    "dbjavagenix": {
      "command": "docker",
      "args": ["run", "-i", "--rm",
               "-e", "DBJAVAGENIX_LOG_FORMAT=json",
               "-e", "ANTHROPIC_API_KEY",
               "dbjavagenix:latest"]
    }
  }
}
```

优点: 隔离、可重现; 缺点: 启动 ≈ 1-2 秒延迟。

### B. uvx 直接拉

```bash
# 装一次到全局
uv tool install dbjavagenix

# client 配置:
{
  "mcpServers": {
    "dbjavagenix": {
      "command": "dbjavagenix-server"
    }
  }
}
```

### C. 本地 dev

```bash
# 从源码运行
PYTHONPATH=src python -m dbjavagenix.cli server
```

## 二、环境变量

| 变量 | 默认 | 说明 |
|------|------|------|
| `DBJAVAGENIX_LOG_FORMAT` | `plain` | `plain` (人类可读) 或 `json` (单行 JSON,便于日志聚合) |
| `DBJAVAGENIX_LOG_LEVEL` | `INFO` | `DEBUG` / `INFO` / `WARNING` / `ERROR` |
| `DBJAVAGENIX_PROGRESSIVE` | (off) | 设 `1` / `true` 启用渐进式工具发现 (启动 token < 1000) |
| `ANTHROPIC_API_KEY` | (none) | 启用 AI 工具的 LLM 路径; 缺失时降级规则推断 |
| `PYTHONPATH` | (auto) | Docker / Win 上有时需要显式指向 `src/` |

**关键限制**: MCP 协议走 stdio,**任何 print/console.log 到 stdout 都会污染 JSON-RPC**。我们的代码:
- Python: 所有 `logger.*` 输出到 stderr (通过 logging StreamHandler(stream=sys.stderr))
- Node wrapper (index.js): `console.log` 被替换为 `process.stderr.write`,启动信息走 stderr

## 三、健康检查

启动后第一次客户端连接,推荐调用 `server_health`:

```jsonl
// list_tools returns server_health among others (always_visible: false, 通过 search_tools 发现)
// call_tool:
{"name": "server_health", "arguments": {}}

// returns:
{
  "status": "ok",
  "uptime_seconds": 12.5,
  "server": {"name": "dbjavagenix", "version": "0.2.0"},
  "runtime": {
    "python_version": "3.11.x",
    "platform": "Linux-...",
    "mcp_sdk_version": "1.6.0",
    "anthropic_sdk_version": "0.40.x" | "not_installed"
  },
  "modules": {
    "dbjavagenix.database.mcp_tools": "ok",
    ...
  },
  "database": {"active_connections": 0},
  "ai": {"llm_available": true, "progressive_mode": false}
}
```

- `status: "ok"` ⇔ 所有核心模块 import 成功
- `status: "degraded"` ⇔ 某些模块加载失败 (查看 `modules.*` 找具体错误)

## 四、指标监控

### tool 调用指标 (server_metrics)

```jsonl
{"name": "server_metrics", "arguments": {}}

// returns:
{
  "metrics": {
    "uptime_seconds": 1832.4,
    "total_tool_calls": 47,
    "total_errors": 2,
    "overall_error_rate": 0.0425,
    "tools": [
      {"name": "codegen_render_entity",
       "calls": 12, "errors": 0, "error_rate": 0.0,
       "avg_duration_ms": 23.4, "last_duration_ms": 19.8,
       "min_duration_ms": 15.2, "max_duration_ms": 42.1,
       "last_call_at_epoch": ...},
      ...
    ]
  }
}
```

### AI prompt caching 指标 (ai_metrics)

```jsonl
{"name": "ai_metrics", "arguments": {}}

// returns:
{
  "metrics": {
    "ai.calls_total": 8,
    "ai.errors_total": 0,
    "ai.tokens.input_total": 1200,
    "ai.tokens.output_total": 950,
    "ai.tokens.cache_read_total": 6300,    // ← prompt cache 命中
    "ai.tokens.cache_creation_total": 2700, // 首次写入 cache
    "ai.cache_hit_rate": 0.612,
    "ai.tokens_saved_via_cache": 6300
  }
}
```

**典型期望值** (8 次 ai_infer_business_names 调用):
- 第 1 次: cache_creation_input_tokens ≈ 2700 (写入系统 prompt 到 cache)
- 第 2-8 次: cache_read_input_tokens ≈ 2700 each (5 分钟 TTL 命中)
- cache_hit_rate 应 > 0.5

## 五、生产 checklist

部署前确认:

- [ ] **核心**: `python -m dbjavagenix.cli server` 启动无 traceback
- [ ] **核心**: `server_health` 返回 `status: ok`
- [ ] **依赖**: `python -m pip check` 无冲突
- [ ] **日志**: `DBJAVAGENIX_LOG_FORMAT=json` 时 stderr 输出可被 JSON 解析
- [ ] **stdout 清洁**: 触发一次工具调用,stdout 内容必须**完全是** MCP JSON-RPC (无 print 噪声) → 这是 MCP 协议要求
- [ ] **数据库**: 提供给 `db_connect_test` 的凭据可读 (`db_query_tables` 返回非空)
- [ ] **模板**: `templates/java/sb35-java21/` 等目录存在 (Docker 镜像内已包含)
- [ ] **凭据**: `ANTHROPIC_API_KEY` 通过环境变量而非镜像内置 (避免泄露)
- [ ] **CI**: GitHub Actions 全绿 (lint + unit + docker build)

## 六、常见排障

### MCP 连接立即断开

最常见原因:**stdout 被污染**。
- 自检: 启动后 `echo '' | python -m dbjavagenix.cli server`,如果 stdout 出现非 JSON 行,说明有 `print` 漏到 stdout。
- 检查项: 任何新增的 logger 配置不要用 `sys.stdout`; 任何新增的 `print(...)` 必须显式 `file=sys.stderr`。

### `Unknown tool: xxx`

工具名拼写错误或 server 版本不匹配。`search_tools` 找一下确认完整工具名。

### `server_health` status=degraded

某个 `modules.*` 是 `FAIL: ...`,先 import 该模块手动复现:
```bash
PYTHONPATH=src python -c "import dbjavagenix.database.mcp_tools"
```
常见原因: 依赖缺失 (uv pip install -e ".[dev]") / 文件被误改。

### LLM 工具总是走规则推断

`server_health` 的 `ai.llm_available` 应是 `true`。如果 false,检查:
1. `ANTHROPIC_API_KEY` 是否设置 (Docker 用 `-e ANTHROPIC_API_KEY` 传入)
2. `pip list | grep anthropic` 应显示 ≥ 0.40

### cache_hit_rate 持续为 0

prompt caching 5 分钟 TTL,如果调用间隔 > 5 分钟会失效。也可能模型不支持 caching。
- 当前需要 `claude-sonnet-4-6` / `claude-opus-4-x` (含 4.5+) 才有 caching 支持。

## 七、Phase 5 实现的关键文件

- `src/dbjavagenix/utils/metrics.py` — 进程级 ToolCallMetrics + 装饰器
- `src/dbjavagenix/utils/logging_config.py` — JSON / plain formatter + trace_id
- `src/dbjavagenix/database/observability_tools.py` — `server_metrics` / `server_health` MCP 工具
- `src/dbjavagenix/server/mcp_server.py` — call_tool 已包裹 metrics 累加

## 八、不引入的依赖 (划清边界)

- **prometheus_client**: stdio 进程无 HTTP endpoint,Pull 模式不适用。改用 in-process 累加 + MCP 工具暴露。
- **opentelemetry-sdk**: 完整 OTel 栈包含 OTLP exporter / context 传播 / span processor,启动开销 ~ 200ms,且对 stdio 单进程过度设计。需要时可单独装 (extras),核心代码不依赖。
- **structlog**: stdlib logging + 自定义 JsonFormatter 已够用,无需引入第三方。

> 这些边界本身就是工程克制的体现 — 而不是漏掉。
