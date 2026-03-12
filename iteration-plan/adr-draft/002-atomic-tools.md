# ADR-002 草稿: 拆分原子工具

## 背景
v0.1 的 db_codegen_generate 是 "一把生成全套"。LLM 调一次拿 50 个文件。

## 问题
1. LLM 中途没法介入("先看 entity 再决定")
2. context 修改后只能 retry 整个流程
3. 失败时回滚困难

## 提案
拆 6 原子工具:
- codegen_build_context
- codegen_render_entity
- codegen_render_dao
- codegen_render_service
- codegen_render_controller
- codegen_render_mapper

## 优势
- LLM 可逐层渲染,中途调整 context
- 每层失败可单独 retry
- 每层返回都可带 _meta 让 client 显示 diff

## 待完善
正式 ADR 时补 "为什么这样切而不是其他" 论证。
