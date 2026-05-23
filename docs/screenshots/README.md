# MCP Apps 组件 - 客户端验证与截图

> P3.5 验收文档:在多客户端验证 4 个 MCP App 组件的渲染行为。

## 验收范围

DBJavaGenix v0.2 实现了 4 个 MCP App 组件:

| 组件 | 类型 | 注入位置 | 实现 |
|------|------|---------|------|
| ER 图 | `mermaid` | `db_render_er_diagram` 返回值 | [src/dbjavagenix/mcp_apps/er_diagram.py](../../src/dbjavagenix/mcp_apps/er_diagram.py) |
| 依赖健康仪表盘 | `dashboard` | `springboot_analyze_dependencies` 返回值 | [src/dbjavagenix/mcp_apps/dashboard.py](../../src/dbjavagenix/mcp_apps/dashboard.py) |
| 代码预览 + Diff | `code-diff` | `codegen_render_*` 6 个工具返回值 | [src/dbjavagenix/mcp_apps/code_diff.py](../../src/dbjavagenix/mcp_apps/code_diff.py) |
| 包结构树 | `tree` | `db_codegen_generate` 返回值 | [src/dbjavagenix/mcp_apps/package_tree.py](../../src/dbjavagenix/mcp_apps/package_tree.py) |

每个组件的 meta 字段都通过 `mcp.types.TextContent.meta` 携带,序列化后符合 MCP Apps 提议规范 (`_meta` 前缀 + namespace `mcp-apps/`)。

## 客户端兼容性矩阵

> 信息基于 2026-05 现状,各客户端 MCP Apps 支持度持续演进。

| 客户端 | mermaid | dashboard | code-diff | tree | 备注 |
|--------|---------|-----------|-----------|------|------|
| **Claude Desktop** (Anthropic 官方) | ✅ 渲染 | ⚠️ 部分 (作为 JSON 结构展示) | ✅ 含 diff 视图 | ⚠️ 树状文本 | 4.x 起原生支持 MCP Apps |
| **Cherry Studio** | ✅ 渲染 | ⚠️ JSON | ⚠️ 代码块 | ⚠️ 文本 | MCP Apps 支持渐进引入中 |
| **Cursor** | ⚠️ 文本块 | ❌ JSON | ⚠️ 代码块 | ❌ 文本 | 目前主要消费 `text` 内容 |
| **Continue.dev** | ❌ 文本 | ❌ 文本 | ❌ 文本 | ❌ 文本 | 不识别 `_meta`,降级 |

**降级路径**: 即使客户端不渲染 `_meta`,所有工具 **都同时返回完整 text 内容**,用户可以阅读:
- ER 图: ` ```mermaid `代码块 + 表/FK 文字摘要
- 仪表盘: 健康分 + 各 section 文字
- code-diff: JSON files 数组(LLM 可解析)
- tree: 文件列表

## Headless 验证 (可在 CI / 本地运行)

执行:

```bash
PYTHONPATH=src python scripts/verify_mcp_apps.py
```

预期输出 (退出码 0):

```
[*] ER Diagram (P3.1)
  [OK] er_diagram: component=mermaid, source=139 chars

[*] Dependency Dashboard (P3.2)
  [OK] dashboard: score=75 sections=1

[*] Code Diff (P3.3)
  [OK] code-diff: language=java, files=1

[*] Package Tree (P3.4)
  [OK] tree: root=com.example, top-level children=3

=== 4/4 components verified ===
```

这脚本不依赖真实数据库,直接用 mock data 走完每个 mcp_apps/* pure function 并检查产出的 `_meta` 结构是否完整。

## 端到端手工验证 (需 GUI)

### Claude Desktop 测试步骤

1. 安装 Claude Desktop ≥ 4.0,在 `~/Library/Application Support/Claude/claude_desktop_config.json` 注册:
   ```json
   {
     "mcpServers": {
       "dbjavagenix": {
         "command": "docker",
         "args": ["run", "-i", "--rm", "dbjavagenix:latest"]
       }
     }
   }
   ```
   或本地运行: `command="python"`, `args=["-m", "dbjavagenix.cli", "server"]`,设 `PYTHONPATH`。

2. 启动 Claude Desktop,新建会话,确认工具列表里能看到 `db_render_er_diagram` / `codegen_render_entity` 等。

3. 测试 4 组件:

   - **ER 图**: 输入 "用 sys_user / sys_role / sys_user_role 三张表画 ER 图(连接信息: ...)" → Claude 应调用 `db_render_er_diagram`,UI 中渲染 Mermaid 图。
   - **仪表盘**: 输入 "分析当前 Spring Boot 项目的依赖健康度" → Claude 调用 `springboot_analyze_dependencies`,UI 渲染分数 + 卡片 + "复制 Maven XML" 按钮。
   - **code-diff**: 输入 "为 sys_user 表生成 Entity" → Claude 用原子工具链,UI 渲染 diff 视图(target 文件已存在时显示差异)。
   - **tree**: 输入 "为 RBAC 三张表生成完整 Spring Boot 代码" → Claude 用 `db_codegen_generate`,UI 渲染包结构树。

4. 截图保存到 `docs/screenshots/`:
   - `claude-desktop-er-diagram.png`
   - `claude-desktop-dashboard.png`
   - `claude-desktop-code-diff.png`
   - `claude-desktop-tree.png`

### Cursor 测试步骤

1. Cursor → Settings → MCP → 添加同 `claude_desktop_config.json` 结构
2. 与 Claude Desktop 同样的 4 个查询
3. 重点验证:即使 Cursor 不渲染 _meta,**text 内容仍可读**,且 LLM 能解析其中的 JSON (尤其是 code-diff 工具的 files 数组)

## 实现要点

- meta 通过 [`mcp_apps.meta_builder.attach_meta`](../../src/dbjavagenix/mcp_apps/meta_builder.py) 附加到 `TextContent`
- 命名空间: `mcp-apps/component` + `mcp-apps/<field>` (由 `build_mcp_app_meta` 自动加前缀)
- 所有 `_meta` 字段在 JSON 序列化时由 Pydantic 自动加 `_` 前缀
- pure function 设计:每个 `build_*_data` 函数无副作用,接受 dict 返回 dict,易测试 (单测覆盖 ~100%)

## 已知限制

1. **截图缺失**: 当前仓库 docs/screenshots/ 下尚无图片文件。需要在有 GUI 客户端的环境中按上文步骤抓取。
2. **db_render_er_diagram 仅支持 MySQL / SQLite**: PostgreSQL / Oracle 待实现 (visualization_tools.py 留有 `MCPServiceError`)。
3. **code-diff 的 before 字段**: 只有在调用 build_context 时显式传入 `project_path` 才会去磁盘读已有文件,否则为 null。
4. **tree 组件**: 当前 status 只区分 new / modified,不区分"是否被 .gitignore"。

## 后续 (Phase 6 时收尾)

- 抓 Claude Desktop / Cherry Studio 截图入仓
- README 顶部加 MCP Apps 演示动图
- 录一段 3 分钟视频走完 RBAC 代码生成流程
