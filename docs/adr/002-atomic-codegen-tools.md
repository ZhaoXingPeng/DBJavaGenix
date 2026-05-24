# ADR-002: 拆分大工具为原子工具

**状态**: Accepted (Phase 2.2 落地, 2026-05)
**关联**: [ADR-001](001-three-layer-architecture.md), `src/dbjavagenix/database/atomic_codegen_tools.py`

## 背景

旧 `db_codegen_generate(connection_id, table_name, ...)` 在 server 内部串行执行:
1. validate_project
2. analyze_dependencies
3. analyze table schema
4. build template context
5. render 5 个层 (entity/dao/service/controller/mapper)
6. compute output paths
7. write files to disk
8. format response text

**LLM 视角的痛点**:
- 不能"render 完后让用户改一下 className 再 render 一遍"
- 不能"先看 entity 长啥样,再决定要不要继续 dao/service"
- context 在 server 内部黑盒构建,LLM 不知道 templateContext 的结构

## 决定

把上述 8 步拆为 **6 个原子工具**:

```
codegen_build_context(connection_id, table, template_category, options...)
    → 返回 context dict (JSON), 不写盘

codegen_render_entity(context: dict)
    → 返回 {files: [{code, file_path, template_file}], language}
codegen_render_dao(context)        → 同上
codegen_render_service(context)    → 返回 2 files (interface + impl)
codegen_render_controller(context) → 同上
codegen_render_mapper(context)     → 根据 templateCategory 智能分发
    (Default → mapper.xml / Mixed → mapper.mustache / sb35-java21 → 空)
```

**约定**:
- 每个 render 工具 **不写盘** — 只返回代码字符串
- context dict 在工具间显式传递 (MCP 协议层友好)
- 容忍 LLM 把 context 序列化为 JSON 字符串后传入 (`_extract_context` 自动 parse)
- 返回值统一为 `{files: [...], language: "java"}` 结构,便于 UI 渲染

## 替代方案

### A. 把 db_codegen_generate 加 mode 参数

`db_codegen_generate(..., mode="preview")` 不写盘只返回内容。
**否决**: 仍是一个工具,LLM 一次拿到全部 5 层,无法选择性 render 一层。

### B. 服务端会话状态

server 维护一个 session dict,build_context 写入 session,render_* 从 session 取。
**否决**: 引入隐式状态,multi-client 隔离复杂,session 过期/回收策略复杂。当前显式参数虽冗长但清晰。

### C. 一次性返回所有层,LLM 选择展示哪些

`codegen_render_all(context) → {entity, dao, service, controller, mapper}`
**否决**: 单次调用 token 大 (一张 RBAC 表全 5 层约 8000 token),且无法只选择性重渲染某一层。

## 后果

**好**:
- LLM 可以走"render → 让用户看 → 改 className → 重 render"循环
- 单个工具 schema 小 (avg ~ 100 tok),启动总 token 仅微涨
- code-diff MCP App (P3.3) 完美适配 → 每个 render 返回一个 diff
- 单元测试更细 (atomic_codegen_tools 覆盖 64%)

**坏**:
- LLM 需要做 6 次 MCP 工具调用而不是 1 次 → 总耗时略增 (实测增加 200-300 ms)
- context 在 LLM 上下文中"传一手",会占额外 ~ 1000 token

**兜底**:
- 旧 `db_codegen_generate` 保留并标记 `[Legacy / single-shot]`,客户端不支持 conversation pause 时退路可用
