# DBJavaGenix v0.2 重构方案 - FINAL

> 2026-04-22。冻结所有决策,准备进入 Phase 1。

## 开发 model
**Claude Opus 4.7 (1M context)** 通过 Claude Code 运行整个 v0.2 重构。

理由:
- SWE-bench 81.9%(代码任务 SOTA)
- 1M context 默认开,跨多文件改动一次性看清
- extended-thinking 帮助复杂判断
- 价格 $15/$75 高,但本次重构总成本可控(预估 $30-50)

## ai_* 工具默认 model
Sonnet 4.6(用户运行时)

## Phase 1 启动
2026-05-18 周一上午

## Phase 6 demo 时间
6 月初

## 这是 final draft
后续把 drafts/ 整理归档,iteration-plan/ 主文件正式产出。
