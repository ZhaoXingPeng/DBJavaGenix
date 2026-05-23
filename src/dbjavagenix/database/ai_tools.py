"""
P4: AI 语义工具 - 用 Claude API + 规则推断增强代码生成。

工具:
  - ai_infer_business_names (P4.1) : 表名/列名 → 业务 Java 命名
  - ai_recommend_template   (P4.2) : 整库 schema → 推荐模板分类
  - ai_summarize_schema     (P4.3) : 整库 schema → 自然语言概述

设计:
  - 默认走规则引擎 (无 ANTHROPIC_API_KEY 也能工作)
  - 设 prefer_llm=true 时优先 LLM,失败再降级
  - 所有响应附带 metrics (源/token 使用),便于 P4.4 监控
"""

import json
import logging
from typing import Any, Dict, List

from mcp.types import TextContent, Tool

from ..ai.llm_client import (
    GLOBAL_LLM_STATS,
    LLMMetrics,
    LLMResult,
    infer_names_via_llm,
    is_llm_available,
)
from ..ai.naming_rules import (
    NamingInference,
    infer_business_names_batch,
)

logger = logging.getLogger(__name__)


def get_ai_tools() -> List[Tool]:
    """返回 P4 AI 工具列表"""
    return [
        Tool(
            name="ai_infer_business_names",
            description=(
                "从数据库表/列推断 Spring Boot 项目中**业务上合理的 Java 命名**。"
                "默认基于 15 条命名规则; 设 prefer_llm=true 且 ANTHROPIC_API_KEY 可用时,优先调用 Claude "
                "(启用 prompt caching 节省 token)。"
                "返回每张表的 class_name + reason + table_kind (entity/association/log/dict/config)。"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "tables": {
                        "type": "array",
                        "description": "待推断的表列表",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string", "description": "表名"},
                                "columns": {
                                    "type": "array",
                                    "items": {"type": "object"},
                                    "description": "[{name, primary_key, ...}]",
                                },
                                "foreign_keys": {
                                    "type": "array",
                                    "items": {"type": "object"},
                                    "description": "[{column, references_table, ...}]",
                                },
                            },
                            "required": ["name"],
                        },
                        "minItems": 1,
                    },
                    "prefer_llm": {
                        "type": "boolean",
                        "description": "是否优先调用 Claude API (需要 ANTHROPIC_API_KEY)",
                        "default": False,
                    },
                    "model": {
                        "type": "string",
                        "description": "Anthropic 模型 ID",
                        "default": "claude-sonnet-4-6",
                    },
                },
                "required": ["tables"],
            },
        ),
    ]


async def handle_ai_infer_business_names(arguments: Dict[str, Any]) -> List[TextContent]:
    """处理业务命名推断请求"""
    tables = arguments.get("tables", [])
    prefer_llm = bool(arguments.get("prefer_llm", False))
    model = arguments.get("model", "claude-sonnet-4-6")

    if not tables:
        return [TextContent(
            type="text",
            text=json.dumps({"error": "tables is required and non-empty"}, ensure_ascii=False),
        )]

    inferences_out: List[Dict[str, Any]] = []
    source_used = "rule"
    llm_metrics: Dict[str, Any] = {}

    # 先跑规则,作为兜底 + LLM 失败时回退
    rule_inferences = infer_business_names_batch(tables)
    rule_map = {ri.table: ri for ri in rule_inferences}

    if prefer_llm and is_llm_available():
        llm_result: LLMResult = infer_names_via_llm(tables, model=model) or LLMResult()
        GLOBAL_LLM_STATS.record(llm_result.metrics)
        llm_metrics = _metrics_to_dict(llm_result.metrics)
        if llm_result.inferences:
            source_used = "llm"
            # 把 LLM 输出标记 source=llm,缺失字段从 rule 补
            for item in llm_result.inferences:
                table_name = item.get("table", "")
                fallback = rule_map.get(table_name)
                inferences_out.append(_merge_inference(item, fallback))
        else:
            # LLM 失败 → 回退规则
            source_used = "rule_after_llm_failure"
            inferences_out = [_rule_to_dict(ri) for ri in rule_inferences]
    else:
        inferences_out = [_rule_to_dict(ri) for ri in rule_inferences]
        if prefer_llm and not is_llm_available():
            source_used = "rule_llm_unavailable"

    response = {
        "inferences": inferences_out,
        "source": source_used,
        "table_count": len(tables),
        "llm_metrics": llm_metrics,
        "llm_available": is_llm_available(),
    }
    return [TextContent(
        type="text",
        text=json.dumps(response, ensure_ascii=False, indent=2),
    )]


def _rule_to_dict(ri: NamingInference) -> Dict[str, Any]:
    return {
        "table": ri.table,
        "class_name": ri.class_name,
        "field_naming": ri.field_naming,
        "reason": ri.reason,
        "table_kind": ri.table_kind,
        "source": ri.source,
        "confidence": ri.confidence,
    }


def _metrics_to_dict(m: LLMMetrics) -> Dict[str, Any]:
    return {
        "model": m.model,
        "input_tokens": m.input_tokens,
        "output_tokens": m.output_tokens,
        "cache_read_input_tokens": m.cache_read_input_tokens,
        "cache_creation_input_tokens": m.cache_creation_input_tokens,
        "error": m.error,
    }


def _merge_inference(
    llm_item: Dict[str, Any], rule_fallback: NamingInference
) -> Dict[str, Any]:
    """LLM 输出补全缺失字段 (从规则推断里取)"""
    merged: Dict[str, Any] = {
        "table": llm_item.get("table", ""),
        "class_name": llm_item.get("class_name") or (rule_fallback.class_name if rule_fallback else ""),
        "field_naming": llm_item.get("field_naming") or {},
        "reason": llm_item.get("reason") or (rule_fallback.reason if rule_fallback else ""),
        "table_kind": llm_item.get("table_kind") or (rule_fallback.table_kind if rule_fallback else "unknown"),
        "source": "llm",
        "confidence": 0.9,
    }
    return merged
