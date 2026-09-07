# Tool Schema Token Benchmark

> 测量 P2.2/P2.3 重构对 LLM 启动时 tool schema token 占用的影响。
> 数据采集时间: 2026-05-24,DBJavaGenix v0.2.0 (Phase 2 完成)

> 注：上方数据是 Phase 2 的历史快照。DTO 原子工具加入后，2026-09-07 本地复测为默认模式 33 个工具、19 817 chars（约 4 954 tokens），渐进模式 6 个工具、4 363 chars（约 1 090 tokens）。

## TL;DR

| 架构 | 启动暴露工具数 | Schema chars | ≈ tokens | 相对节省 |
|------|---------------|--------------|----------|---------|
| **Before** (Phase 1 单体工具) | 15 | ~9 800 | ~2 450 | 基线 |
| **After (default mode)** Phase 2 全部注册 | 22 | 13 215 | ~3 304 | -34% (升高,因为新增了原子工具) |
| **After (progressive mode)** Phase 2 + Tool Search | 6 | 3 942 | **~985** | **-60% vs Phase 1, -70% vs default** |

**结论**:
- 直接拆分大工具会增加总 schema(每个原子工具自带 schema),但**启动时不需要全部加载**。
- 通过 `DBJAVAGENIX_PROGRESSIVE=1` 环境变量启用渐进式发现后,启动 token 降到 985,远低于 iteration-plan 目标(< 2000)。
- LLM 通过 `search_tools(query)` 按需获取其余工具的完整 schema。

## 测量方法

每个工具的"schema 大小"按其完整 JSON 表示估算:

```python
json.dumps({
    "name": t.name,
    "description": t.description,
    "inputSchema": t.inputSchema,
}, ensure_ascii=False)
```

Token 估算用 `chars // 4`,这是 Claude / GPT-4 类英语-中文混合文本的经验近似。真实 token 由具体 tokenizer 决定,但相对比较意义不变。

复现命令:

```bash
PYTHONPATH=src python -c "
import json, asyncio
from dbjavagenix.server.mcp_server import handle_list_tools
tools = asyncio.run(handle_list_tools())
total = sum(len(json.dumps({'name':t.name,'description':t.description,'inputSchema':t.inputSchema}, ensure_ascii=False)) for t in tools)
print(f'{len(tools)} tools, {total} chars, ≈{total//4} tokens')
"
```

## 完整数据 (After / Default mode, 22 tools, historical snapshot)

| 工具 | Schema chars | ≈ tokens | always_visible |
|------|--------------|----------|----------------|
| `db_connect_test` | 832 | 208 | ✓ |
| `db_query_databases` | 261 | 65 |   |
| `db_query_tables` | 340 | 85 | ✓ |
| `db_query_table_exists` | 414 | 103 |   |
| `db_query_execute` | 457 | 114 |   |
| `db_table_describe` | 565 | 141 | ✓ |
| `db_table_columns` | 413 | 103 |   |
| `db_table_primary_keys` | 414 | 103 |   |
| `db_table_foreign_keys` | 416 | 104 |   |
| `db_table_indexes` | 403 | 100 |   |
| `db_codegen_analyze` (legacy) | 1041 | 260 |   |
| `db_codegen_generate` (legacy) | 1623 | 405 |   |
| `codegen_build_context` | 1069 | 267 | ✓ |
| `codegen_render_entity` | 404 | 101 |   |
| `codegen_render_dao` | 384 | 96 |   |
| `codegen_render_service` | 386 | 96 |   |
| `codegen_render_controller` | 397 | 99 |   |
| `codegen_render_mapper` | 469 | 117 |   |
| `springboot_validate_project` | 668 | 167 | ✓ |
| `springboot_analyze_dependencies` | 1088 | 272 |   |
| `springboot_read_config` | 703 | 175 |   |
| `search_tools` | 468 | 117 | ✓ |
| **TOTAL** | **13 215** | **~3 304** | 6 always-visible |

## Progressive Mode 暴露集合

启动时仅 6 个工具:

```
db_connect_test               208 tok  (连接入口)
db_query_tables                85 tok  (列出表)
db_table_describe             141 tok  (查看结构)
codegen_build_context         267 tok  (代码生成入口)
springboot_validate_project   167 tok  (项目预检)
search_tools                  117 tok  (按需发现其他工具)
                            ──────
                              985 tok
```

LLM 工作流示例(progressive 模式):

1. 启动 → 看到 6 个工具,~985 tokens
2. 用户说"渲染 Entity" → LLM 调用 `search_tools("render entity")`
3. 返回 `codegen_render_entity` 的 brief 描述,LLM 直接以名字 call_tool
4. 服务端不限制 progressive 工具的 call,只限制 list

## 三阶段对比

| 维度 | Phase 1 (单体工具) | Phase 2 default | Phase 2 progressive |
|------|-------------------|-----------------|---------------------|
| 注册工具数 | 15 | 22 | 22 (其中 6 暴露) |
| 启动 tokens | ~2 450 | ~3 304 | **~985** |
| 单工具最大 schema | `db_codegen_generate` (405 tok) | 同 | 同 |
| LLM 工作流可拆 | ❌ (一步到位) | ✅ (7 个原子工具) | ✅ |
| 用户预览/修改时机 | ❌ | ✅ (build_context → render → 预览 → 写) | ✅ |

## 端到端对话 token 估算(粗略)

> 完整对话 token = list_tools + 用户问 + 工具 IO + LLM 回答。这里只看 list_tools 部分,因为这是渐进式发现的目标。

**场景**: 用户要从 sys_user / sys_role / sys_user_role 三张表生成 Spring Boot 代码(RBAC 场景)。

| 阶段 | Phase 1 | Phase 2 progressive |
|------|---------|---------------------|
| 启动 list_tools | 2 450 | 985 |
| 单次 codegen 调用输入 schema | ~405 (db_codegen_generate) | ~267 (build_context, 后续 render_* 平均 ~100) |
| 7 个原子工具调用合计 schema 暴露 | n/a (走 db_codegen_generate 一次) | ~800 (search_tools 拉出 6 个 render_* 工具) |
| **总 list_tools / schema 部分** | **~2 855** | **~1 685** |

Progressive 路径在节省启动 token 的同时,通过 search_tools 暴露完整工具能力,几乎不损失功能性。

## 设计取舍

**为什么不用向量检索?**
- 22 个工具规模下,关键词 + tag 已经精准(测试中 query="render dao" 第一名就是目标)。
- 引入向量数据库会增加启动依赖与冷启动延迟,不符合"工程克制"边界(见 `iteration-plan/01-target-architecture.md` 第五章)。

**为什么不直接删除 legacy 大工具?**
- `db_codegen_generate` 占用 405 tokens 但**默认不暴露**(非 always_visible)。
- 它仍有兼容性价值: 在受限客户端(不支持 MCP App 渲染、不支持 conversation pause)下,"一步到位"模式更友好。
- 删除会破坏现有 v0.1.x 用户的工作流。

**为什么把 `springboot_validate_project` 列为 always_visible 而不是 `springboot_analyze_dependencies`?**
- 工作流中 validate 在前(预检结构),analyze 在后(依赖健康)。
- 预检失败时不需要继续,所以 validate 是必经。
- analyze 通过 search_tools 一键找到。

## 后续可优化项

- **Phase 3**: MCP Apps 引入 `_meta` 字段后,部分工具 description 可缩减(交给 UI 表达)
- **Phase 4**: 新增的 `ai_*` 工具加入 progressive 集合,搜索覆盖范围扩大
- **Tag 增强**: 当前 tag 是手工维护,可考虑从工具 description 自动抽取
- **客户端协商**: MCP 1.6+ 支持 tools/listChanged,可让客户端动态获取已"发现"的工具集

---

**测量者**: DBJavaGenix Phase 2 (P2.4)
**数据**: 真实从 `handle_list_tools` 提取,见 `tests/unit/test_tool_registry.py` 验证
