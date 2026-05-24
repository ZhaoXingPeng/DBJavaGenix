# ADR-004: 规则推断优先于 LLM

**状态**: Accepted (Phase 4 落地, 2026-05)
**关联**: `src/dbjavagenix/ai/naming_rules.py`, `src/dbjavagenix/ai/llm_client.py`

## 背景

Phase 4 引入 AI 语义工具 (`ai_infer_business_names` / `ai_recommend_template` / `ai_summarize_schema`)。理论上 Claude 等 LLM 在业务命名推断上比规则更强 (能识别 `loyalty_redemption` 是会员积分兑换,规则无法触达语义)。

**问题**: 完全依赖 LLM 调用有几个工程隐忧:
1. **CI / 离线开发** 没有 ANTHROPIC_API_KEY,工具直接挂掉不可用
2. **成本** 每次都打 API,简单场景 (sys_user → User) 大才小用
3. **延迟** API 调用 ~ 1.5-3 秒,影响 LLM 工作流流畅度
4. **可重复性** LLM 输出不稳定,同 input 不同时刻可能不同

## 决定

**默认走规则,LLM 是可选增强**:

1. 实现完整的 15 条规则推断引擎 (`naming_rules.py`):
   - 通用前缀剥离 (sys_/biz_/bd_/cms_...)
   - 不规则单数化 (categories → category)
   - PascalCase 转换
   - 关联表识别 (≥ 2 FK + 业务列 ≤ 1)
   - 日志/字典/配置表后缀识别
   - 重复后缀检查 (DictItem 不要变 DictItemDict)

2. LLM 路径作为可选增强 (`llm_client.py`):
   - 当 `prefer_llm=true` 且 `ANTHROPIC_API_KEY` 存在时优先调用 Claude
   - 系统 prompt 含完整规则文档,启用 prompt caching (5 分钟 TTL)
   - LLM 失败 → 自动回退规则,源标记 `source=rule_after_llm_failure`

3. 输出结构统一:
   - `{class_name, reason, table_kind, source, confidence}`
   - source: `rule` / `llm` / `rule_llm_unavailable` 等
   - LLM 比规则置信度高 (0.9 vs 0.7-0.85)

## 替代方案

### A. 全 LLM 化

所有命名推断直接打 Claude API。
**否决**: CI 跑不动,且 sys_user → User 不需要花 LLM 调用,规则就够了。

### B. 全规则化

不引入 LLM,只规则。
**否决**: 复杂业务表名 (loyalty_redemption / discount_campaign) 规则无法捕捉语义。

### C. 混合 (现行方案)

默认规则,可选 LLM。
**采纳**。

## 后果

**好**:
- 离线 / CI 环境直接跑,无外部依赖
- 简单场景 (RBAC / 常见命名) 零成本毫秒级响应
- LLM 路径作为增量价值,与规则结果一起返回让 LLM 评估
- prompt caching 5 分钟内连续调用 cache_read 命中 (省 ~ 2.7k token / 调用)

**坏**:
- 规则覆盖不全的边缘 case (复杂业务名词) 需要用户 prefer_llm=true 手动开启
- 规则和 LLM 输出结构需要保持一致 (`_merge_inference` 补齐字段)

**实测**:
- 规则推断 10 个真实样本全部正确 (单测 `test_ai_naming.py`)
- 同时把 LLM 输出与规则合并,LLM 不准时降级仍可用
