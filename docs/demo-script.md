# Demo 演示脚本

> 用 RBAC 三表场景 (sys_user / sys_role / sys_user_role) 演示 DBJavaGenix v0.2 的端到端工作流。
> 两个长度版本: **3 分钟快速版** (面试电梯演示) / **10 分钟深度版** (技术分享)。

## 准备

测试环境:
- MySQL 已建好 `myapp` 数据库,含 `sys_user / sys_role / sys_user_role` 三张表,有外键关系
- Spring Boot 3.5 + Java 21 空白项目 `test_project/` (有 `pom.xml` / `src/main/java`)
- Claude Desktop ≥ 4.0 (或 Cherry Studio / Cursor)
- 配置 `claude_desktop_config.json` 已注册 dbjavagenix MCP server

启动配置:
```json
{
  "mcpServers": {
    "dbjavagenix": {
      "command": "docker",
      "args": ["run", "-i", "--rm",
               "-e", "DBJAVAGENIX_PROGRESSIVE=1",
               "-e", "ANTHROPIC_API_KEY",
               "dbjavagenix:latest"]
    }
  }
}
```

## 3 分钟快速版 (面试电梯演示)

### [0:00] 开场 (15 秒)

**说**:
> "这是 DBJavaGenix,一个把数据库表反向工程为 Spring Boot 代码的 MCP 工具。8 个月前我做了第一版,3 周前重构成 Skills + Atomic Tools + MCP Apps 三层架构。我用一个 RBAC 三表场景演示。"

### [0:15] 启动 + 健康检查 (30 秒)

**做**: 在 Claude Desktop 新建对话,输入:
> "调用 server_health 看下状态"

**期望**: Claude 返回:
```json
{
  "status": "ok",
  "uptime_seconds": 3.2,
  "runtime": {"python_version": "3.11.x", "mcp_sdk_version": "1.6.0", ...},
  "modules": { ... 10/10 ok ... }
}
```

**说**:
> "33 个工具就绪,modules 全部 OK。注意 progressive 模式 — 初始只暴露 6 个 always-visible 工具,启动 token 从 3300 降到 985。"

### [0:45] 任务输入 (10 秒)

**输入**:
> "从我的 myapp 数据库的 sys_user, sys_role, sys_user_role 三张表生成完整 Spring Boot 代码。先画 ER 图给我看。"

### [0:55] 阶段 1+2: 连接 + ER 图 (40 秒)

**Claude 会**:
1. 调用 `search_tools("connect")` (因为 progressive 模式)
2. 调用 `db_connect_test(host=..., username=root, password=..., database=myapp)`
3. 调用 `db_table_describe` × 3
4. 调用 `db_table_foreign_keys` × 3
5. 调用 `db_render_er_diagram(database="myapp", tables=[...])`

**指**: Claude Desktop 中 mermaid ER 图渲染出来,显示三表 + FK 箭头。

**说**:
> "ER 图是 MCP App 渲染的,服务端用 `_meta.mcp-apps/component=mermaid` 携带源码,客户端识别后渲染。"

### [1:35] 阶段 3: AI 语义增强 (40 秒)

**Claude 会**:
- 调用 `ai_infer_business_names(tables=[...])`

**指**: 返回结果中 `sys_user_role` 被推断成 `UserRoleAssignment` (关联表),不是机械的 `SysUserRole`。

**说**:
> "这是规则引擎的输出,15 条规则覆盖了关联表识别。如果传 prefer_llm=true 还会调 Claude API 增强,带 prompt caching,5 分钟内重复调用只算 cache_read,省 70% input token。"

- Claude 接着调 `ai_recommend_template`,返回 `MybatisPlus-Mixed` + RBAC 模式 confidence=high。

### [2:15] 阶段 4: 分层渲染 + diff (30 秒)

**Claude 会**:
1. 调用 `codegen_build_context(connection_id, table_name="sys_user", template_category="MybatisPlus-Mixed", ...)`
2. 拿到 context dict
3. 依次调 `codegen_render_entity(context)` → `codegen_render_dao(context)` → ...

**指**: 每次 render 在客户端 UI 显示一个 code-diff 视图,如果 test_project 中已有 User.java,会显示 before/after。

**说**:
> "这就是原子工具的好处 — LLM 可以让用户先看 entity 再决定要不要继续,中途修改 context 重新渲染。每个 render 的返回值都带 mcp-apps/component=code-diff。"

### [2:45] 收尾 (15 秒)

**做**: `server_metrics` 看一下累积调用。

**说**:
> "整个流程透明可观测,33 个工具,5 阶段 Skill 编排,4 个 MCP App 组件。代码在 [github.com/ZhaoXingPeng/DBJavaGenix](https://github.com/ZhaoXingPeng/DBJavaGenix),完整迭代方案在 iteration-plan/ 目录。"

---

## 10 分钟深度版 (技术分享)

### [0:00-1:00] 项目背景 (60 秒)

- "8 个月前我做了第一版,主要是 LLM 大工具一键生成"
- "面试准备时回看,发现几个问题: 启动 token 高,LLM 没法中途介入,返回值是死板文本"
- "用了 3 周做了 6 阶段重构,这是 v0.2 演示"
- 显示 iteration-plan/README.md 链接,提一句"完整方案在仓库里"

### [1:00-2:00] 架构总览 (60 秒)

打开 README.md 的 mermaid 架构图,讲三层:
- **Skills**: `.claude/skills/java-codegen-from-db/SKILL.md` — 看一眼"5 阶段工作流"
- **MCP 33 工具**: 强调 atomic 拆分 (db_codegen_generate → 7 个原子工具) 与 schema 图算法
- **Apps**: 4 个 UI 组件,客户端按 _meta 渲染

提一句:
> "划清边界很重要 — 我们明确不引向量数据库、不引 LangChain。ADR-005 写了 5 个 '不引入' 的理由。"

### [2:00-3:00] 启动 + 渐进发现 (60 秒)

启动 Claude Desktop,演示:

```jsonl
{"name": "server_health"}
{"name": "server_metrics"}
```

讲 progressive mode (ADR-003):
- Default: 22 工具 schema = 3304 tokens
- Progressive: 6 工具 = 985 tokens (-70%)
- LLM 通过 `search_tools(query)` 按需发现其他工具

演示一次 search:
```jsonl
{"name": "search_tools", "arguments": {"query": "render dao"}}
// 返回 [codegen_render_dao, codegen_render_controller, ...]
```

### [3:00-5:00] 端到端 RBAC 代码生成 (120 秒)

执行 3 分钟版的阶段 1-4,慢一些,每个阶段停下来讲:

#### 阶段 1: Skill 工作流编排

打开 `.claude/skills/java-codegen-from-db/SKILL.md`,指 "5 阶段" 章节:
> "Skill 把工作流写死,LLM 照着做不会乱调。例如阶段 3 强制 ★ 用户确认点 — LLM 必须 pause 让用户审推断结果,禁止默认接受。"

#### 阶段 2: 原子工具

演示 LLM 调用 `codegen_render_entity(context)` 后,把 context 改一下 className 再调:
> "这就是拆分的价值。旧 `db_codegen_generate` 是黑盒,改完再生成只能 retry 整个流程。"

#### 阶段 3: MCP App diff

代码 diff 渲染出来时:
> "服务端在 `_meta` 里写 mcp-apps/component=code-diff,客户端识别后用 Monaco editor 渲染。before 字段会读取目标位置已有文件,所以是真 diff 而不是单文件预览。"

### [5:00-6:30] AI 语义增强 (90 秒)

调 `ai_infer_business_names`,比较两种模式:

```jsonl
// 模式 1: 规则推断 (无 LLM)
{"name": "ai_infer_business_names", "arguments": {"tables": [...]}}
// 返回 source=rule, 0.05 ms 响应

// 模式 2: prefer_llm=true (LLM 增强)
{"name": "ai_infer_business_names", "arguments": {"tables": [...], "prefer_llm": true}}
// 返回 source=llm, 1.5 sec 响应
```

讲 prompt caching:
- 系统 prompt ~ 2.5k tokens 含 15 条规则文档
- `cache_control: {"type": "ephemeral"}` 标记
- 5 分钟内重复调用 cache_read_input_tokens 命中

调 `ai_metrics`:
```jsonl
{"name": "ai_metrics"}
// 显示 cache_hit_rate 0.6+
```

讲 ADR-004:
> "规则优先 + LLM 可选。CI 没有 ANTHROPIC_API_KEY 也能跑。简单场景 (sys_user → User) 不用打 API。"

### [6:30-7:30] MCP Apps 4 组件 (60 秒)

调一次 `db_render_er_diagram` 渲染 mermaid。
调 `springboot_analyze_dependencies` 看 dashboard 组件。
最后调 `db_codegen_generate` 看 tree 组件 (包结构树)。

提一句客户端兼容性:
> "Claude Desktop 4.x 全支持。Cherry Studio 支持 mermaid 但 dashboard 退化为 JSON。Cursor 主要看 text,_meta 忽略。我们的设计是 _meta 是渐进增强,降级路径完整。"

### [7:30-8:30] 可观测性 + 生产就绪 (60 秒)

调 `server_metrics`:
```jsonl
{"metrics": {
  "uptime_seconds": 432.5,
  "total_tool_calls": 23,
  "tools": [
    {"name": "codegen_render_entity", "calls": 3, "avg_duration_ms": 22.4, ...}
  ]
}}
```

打开 `docs/deployment.md`:
- 3 种部署模式 (Docker / uvx / dev)
- 6 个排障场景
- "不引入 prometheus_client 的理由" (ADR-005)

讲 JSON 日志:
```bash
DBJAVAGENIX_LOG_FORMAT=json docker run ... dbjavagenix
# stderr 输出单行 JSON, Loki/ELK 直接吃
```

### [8:30-9:30] 工程过程亮点 (60 秒)

- "Phase 1 一次发现 13 个真实 bug (例如 `_is_string_type` 处理 VARCHAR(64) 错误,index.js console.log 污染 stdout)"
- "Phase 2 拆分后单测覆盖率 0% → 64% (atomic_codegen_tools)"
- "提交规范: 每个子任务一个 commit,commit message 含 'Why' 而不只是 'What'"
- "CI 三 Job: lint + template-render + docker-build, 全绿"
- 显示 `git log --oneline` 的截图,30+ commits 每个都有清晰范围

### [9:30-10:00] 总结 + Q&A 引导 (30 秒)

> "这个项目想展示的不只是 '我会用 LLM 写代码',而是: 在已有项目上做架构重构,做工程上正确的取舍,把每一步都做到可测试、可观测、可部署。
> 完整方案在 `iteration-plan/`,5 个 ADR 在 `docs/adr/`,token benchmark 数据在 `docs/benchmarks/`。"
>
> "欢迎提问。"

---

## 演示前 checklist

- [ ] Claude Desktop 已配置且能看到 dbjavagenix 工具列表
- [ ] MySQL 已起,`myapp` 数据库 + 3 表 + FK 关系就绪
- [ ] `test_project/` 空白 Spring Boot 项目存在,有 pom.xml
- [ ] `ANTHROPIC_API_KEY` 已 export (演示 prefer_llm 路径)
- [ ] 显示器调字号 16+ (远程演示可读)
- [ ] 准备好 `server_health` / `server_metrics` 的预期截图作 fallback (万一现场掉链)

## 演示后跟进

- 仓库: https://github.com/ZhaoXingPeng/DBJavaGenix
- iteration-plan: 完整 6 阶段方案
- ADR: 5 个关键决策记录
- 简历可附: "DBJavaGenix v0.2 重构,3 周完成 6 阶段,620+ 单测,渐进发现 token -70%"
