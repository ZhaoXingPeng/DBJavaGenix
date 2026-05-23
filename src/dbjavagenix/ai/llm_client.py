"""
P4.1: Anthropic Claude API client with prompt caching.

设计:
  - 系统 prompt 含"命名规范规则"作为 cached prefix (~3000 tokens)
  - 输入只放当前表 schema (可变部分,不缓存)
  - 输出强制 JSON schema (Anthropic 的 tool_use 或者 prompt 约束)
  - 无 ANTHROPIC_API_KEY 时优雅降级,返回 None 让上层走规则

cache 控制:
  - cache_control: {"type": "ephemeral"} 标记 system prompt
  - 调用一次后,5 分钟内重复调用命中 cache_read_input_tokens
  - 暴露 metrics: tokens_used, cache_read, cache_creation
"""

import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ============================================================
# Cached system prompt (~ 2.5k tokens, 长度足以触发 prompt caching)
# ============================================================

NAMING_SYSTEM_PROMPT = """你是资深 Java 后端工程师,专长从数据库表名 / 列名推断 Spring Boot 项目里**业务上合理的 Java 类名 / 字段名**。

# 推断规则 (按优先级)

## 1. 通用前缀剥离

去掉这些常见前缀,聚焦核心业务名词:
- 模块前缀: `sys_`, `biz_`, `bd_` (基础数据), `cms_`, `ops_`, `admin_`, `core_`
- 通用建表习惯: `t_`, `tb_`
- 项目代号 (如 `myproject_`): 推断时也应去掉

例如:
- `sys_user` → `User` (不是 `SysUser`,因为 sys_ 是模块前缀)
- `biz_order` → `Order`
- `t_dept` → `Dept` (推荐 `Department` 更全)

## 2. 单数化

数据库表用复数 → Java 类用单数:
- `users` → `User`
- `orders` → `Order`
- `categories` → `Category` (不规则: ies → y)
- `boxes` → `Box` (es → 去)
- `policies` → `Policy`

不要单数化已经是单数的:
- `analysis` → `Analysis` (不要变 Analysi)
- `data` → `Data`

## 3. PascalCase 转换

snake_case → PascalCase:
- `user_role` → `UserRole`
- `order_item` → `OrderItem`

## 4. 关系表识别

含**两个 *_id 外键**且业务列很少 → 关系实体,加 `Assignment` 或 `Mapping` 后缀:
- `sys_user_role` (有 user_id + role_id) → `UserRoleAssignment` (不是 `UserRole`,因为它代表 "用户拥有角色" 这个关系)
- `order_product` → `OrderProductLine` 或 `OrderItem` (取决于上下文)

判断标准:
- ≥ 2 个外键
- 非主键非外键的"业务列" ≤ 1 (审计字段不算)

## 5. 特殊后缀表

按后缀加专属类名后缀:
- `*_log`, `*_history`, `*_record` → `*Log` (例: `login_log` → `LoginLog`)
- `*_dict`, `*_dictionary`, `*_dict_item` → `*Dict` (例: `sys_dict_item` → `DictItem`)
- `*_config`, `*_setting` → `*Config`

## 6. 列名映射

列名一般 snake_case → camelCase (Java 字段约定):
- `user_name` → `userName`
- `created_at` → `createdAt`
- `is_active` → `isActive` (保留 is 前缀)

但是有些保留原名:
- 单字 `id`, `name`, `age` → 不变
- 已经 camelCase 的 → 不动

## 7. 业务含义增强

如果列名含语义信息,在 reason 里说明:
- `status` (tinyint) → status 字段, 但建议在 Java 端用 enum
- `is_deleted`, `deleted_at` → 软删除模式
- `tenant_id` → 多租户字段
- `version` → 乐观锁字段

# 输出格式

对每张表,输出严格 JSON:
```json
{
  "table": "<原表名>",
  "class_name": "<推断的 Java 类名>",
  "field_naming": {"<原列名>": "<Java 字段名>"},
  "reason": "<一句话说明依据>",
  "table_kind": "entity | association | log | dict | config | unknown"
}
```

批量输入时返回数组。**只输出 JSON,不要任何解释/markdown 标记**。
"""


@dataclass
class LLMMetrics:
    """单次 LLM 调用的指标"""
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_input_tokens: int = 0
    cache_creation_input_tokens: int = 0
    model: str = ""
    error: Optional[str] = None


@dataclass
class LLMResult:
    """LLM 返回的解析结果"""
    inferences: List[Dict[str, Any]] = field(default_factory=list)
    metrics: LLMMetrics = field(default_factory=LLMMetrics)


def is_llm_available() -> bool:
    """检查 ANTHROPIC_API_KEY + anthropic SDK 是否就绪"""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return False
    try:
        import anthropic  # noqa: F401
        return True
    except ImportError:
        return False


def infer_names_via_llm(
    tables: List[Dict[str, Any]],
    model: str = "claude-sonnet-4-6",
    max_tokens: int = 4096,
) -> Optional[LLMResult]:
    """用 Claude API 推断业务命名 (启用 prompt caching)。

    Args:
        tables: [{name, columns, foreign_keys}] 列表
        model: Anthropic 模型 ID
        max_tokens: 最大输出 token

    Returns:
        LLMResult 或 None (key 缺失 / 调用失败时)
    """
    if not is_llm_available():
        logger.info("LLM not available: ANTHROPIC_API_KEY missing or anthropic SDK not installed")
        return None

    try:
        import anthropic  # noqa: E402
    except ImportError:
        return None

    user_payload = json.dumps(
        {"tables": tables},
        ensure_ascii=False,
        indent=2,
    )

    try:
        client = anthropic.Anthropic()
        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=[
                {
                    "type": "text",
                    "text": NAMING_SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                "请对以下表批量推断业务命名,输出 JSON 数组。\n\n"
                                f"输入:\n{user_payload}"
                            ),
                        }
                    ],
                }
            ],
        )

        usage = response.usage
        metrics = LLMMetrics(
            input_tokens=getattr(usage, "input_tokens", 0),
            output_tokens=getattr(usage, "output_tokens", 0),
            cache_read_input_tokens=getattr(usage, "cache_read_input_tokens", 0) or 0,
            cache_creation_input_tokens=getattr(usage, "cache_creation_input_tokens", 0) or 0,
            model=model,
        )

        text_blocks = [b.text for b in response.content if hasattr(b, "text")]
        raw = "\n".join(text_blocks).strip()
        # 容忍 ```json fence
        if raw.startswith("```"):
            raw = raw.split("```", 2)[1] if "```" in raw[3:] else raw
            raw = raw.removeprefix("json").strip()

        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("LLM response not valid JSON, falling back. Raw: %s", raw[:200])
            metrics.error = "json_decode_failed"
            return LLMResult(inferences=[], metrics=metrics)

        # 容忍单对象 / 含 'inferences' 包装层
        if isinstance(parsed, dict) and "inferences" in parsed:
            inferences = parsed["inferences"]
        elif isinstance(parsed, list):
            inferences = parsed
        elif isinstance(parsed, dict):
            inferences = [parsed]
        else:
            inferences = []

        return LLMResult(inferences=inferences, metrics=metrics)

    except Exception as e:  # noqa: BLE001
        logger.error("LLM inference failed: %s", e)
        return LLMResult(inferences=[], metrics=LLMMetrics(error=str(e), model=model))


# ============================================================
# 全局指标累加器 (P4.4 暴露给 /metrics)
# ============================================================

@dataclass
class GlobalLLMStats:
    total_calls: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cache_read: int = 0
    total_cache_creation: int = 0
    total_errors: int = 0

    def record(self, metrics: LLMMetrics) -> None:
        self.total_calls += 1
        self.total_input_tokens += metrics.input_tokens
        self.total_output_tokens += metrics.output_tokens
        self.total_cache_read += metrics.cache_read_input_tokens
        self.total_cache_creation += metrics.cache_creation_input_tokens
        if metrics.error:
            self.total_errors += 1

    @property
    def cache_hit_rate(self) -> float:
        """cache_read / (cache_read + cache_creation + 普通 input)"""
        total_potentially_cached = (
            self.total_cache_read
            + self.total_cache_creation
            + self.total_input_tokens
        )
        if total_potentially_cached == 0:
            return 0.0
        return self.total_cache_read / total_potentially_cached

    @property
    def tokens_saved_via_cache(self) -> int:
        """cache_read 等价的"省下来的"token"""
        return self.total_cache_read

    def snapshot(self) -> Dict[str, Any]:
        return {
            "ai.calls_total": self.total_calls,
            "ai.errors_total": self.total_errors,
            "ai.tokens.input_total": self.total_input_tokens,
            "ai.tokens.output_total": self.total_output_tokens,
            "ai.tokens.cache_read_total": self.total_cache_read,
            "ai.tokens.cache_creation_total": self.total_cache_creation,
            "ai.cache_hit_rate": round(self.cache_hit_rate, 4),
            "ai.tokens_saved_via_cache": self.tokens_saved_via_cache,
        }


# 进程级单例
GLOBAL_LLM_STATS = GlobalLLMStats()
