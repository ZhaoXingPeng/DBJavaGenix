"""
P4.3: 数据库 schema 自然语言概述。

输入: 表名列表 + 外键关系 + (可选) 各表列数
输出: 多段文字描述,涵盖:
  - 总览: 表数、推断的模式
  - 模块划分: 按前缀 (sys_/biz_) 或主题词聚类
  - 核心实体: 命中模式的表
  - 关键关系: 描述 1-N / N-N 拓扑

设计:
  - 规则生成,无 LLM 依赖,可作为 LLM prompt 的种子描述
  - 输入与 ai_recommend_template 共享 (表名 + FK)
"""

from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .naming_rules import _strip_known_prefix
from .template_recommender import PATTERNS, recommend_template


@dataclass
class SchemaSummary:
    total_tables: int
    detected_pattern: str
    pattern_confidence: str
    modules: List[Dict[str, Any]]  # [{prefix, tables, description}]
    core_entities: List[str]
    relationships: List[Dict[str, str]]  # [{from_table, to_table, type}]
    narrative: str


def summarize_schema(
    table_names: List[str],
    foreign_keys: Optional[List[Dict[str, Any]]] = None,
    table_column_counts: Optional[Dict[str, int]] = None,
) -> SchemaSummary:
    """从整库 schema 生成自然语言概述。

    Args:
        table_names: 表名列表
        foreign_keys: [{from_table, from_column, to_table, to_column}] 或与 db_table_foreign_keys 一致
        table_column_counts: {表名: 列数}, 可选, 用于推断核心实体

    Returns:
        SchemaSummary 含结构化数据 + narrative 文本
    """
    foreign_keys = foreign_keys or []
    table_column_counts = table_column_counts or {}

    # 1. 模式检测
    rec = recommend_template(table_names, foreign_keys)

    # 2. 按前缀聚类
    modules = _group_by_prefix(table_names)

    # 3. 核心实体识别 (列数最多 + 在模式 matched_tables 中)
    core = _identify_core_entities(table_names, table_column_counts, rec.matched_tables)

    # 4. 关键关系
    relations = _summarize_relationships(foreign_keys)

    # 5. 拼装 narrative
    narrative = _build_narrative(
        total=len(table_names),
        pattern=rec.pattern,
        confidence=rec.confidence,
        modules=modules,
        core=core,
        relations=relations,
    )

    return SchemaSummary(
        total_tables=len(table_names),
        detected_pattern=rec.pattern,
        pattern_confidence=rec.confidence,
        modules=modules,
        core_entities=core,
        relationships=relations,
        narrative=narrative,
    )


def _group_by_prefix(table_names: List[str]) -> List[Dict[str, Any]]:
    """按前缀聚类"""
    groups: Dict[str, List[str]] = defaultdict(list)
    for t in table_names:
        lower = t.lower()
        prefix = _detect_module_prefix(lower)
        groups[prefix].append(t)

    # 排序: 表数多的在前
    sorted_groups = sorted(groups.items(), key=lambda kv: -len(kv[1]))
    return [
        {
            "prefix": prefix,
            "tables": tables,
            "table_count": len(tables),
            "description": _prefix_description(prefix),
        }
        for prefix, tables in sorted_groups
        if len(tables) >= 2 or prefix != "(other)"  # 只聚 ≥ 2 张表的前缀,杂表归 (other)
    ]


_MODULE_PREFIXES = ("sys_", "biz_", "bd_", "cms_", "ops_", "admin_", "core_", "t_", "tb_")


def _detect_module_prefix(lower_table: str) -> str:
    for prefix in _MODULE_PREFIXES:
        if lower_table.startswith(prefix):
            return prefix.rstrip("_")
    # 无识别前缀 → 用第一个 _ 前的词作为模块
    if "_" in lower_table:
        return lower_table.split("_", 1)[0]
    return "(other)"


def _prefix_description(prefix: str) -> str:
    descs = {
        "sys": "系统/权限模块 (用户、角色、菜单、字典)",
        "biz": "业务模块",
        "bd": "基础数据模块 (字典、配置)",
        "cms": "内容管理模块",
        "ops": "运维模块",
        "admin": "管理后台模块",
        "core": "核心领域模块",
        "t": "(通用建表前缀)",
        "tb": "(通用建表前缀)",
    }
    return descs.get(prefix, f"以 '{prefix}' 为前缀的表组")


def _identify_core_entities(
    table_names: List[str],
    column_counts: Dict[str, int],
    matched_tables: List[str],
) -> List[str]:
    """识别核心实体: 命中模式的 + 列数 top N"""
    # 命中模式的优先
    core = list(matched_tables)
    # 按列数补充
    if column_counts:
        ranked = sorted(
            column_counts.items(), key=lambda kv: -kv[1]
        )
        for t, _ in ranked[:5]:
            if t not in core:
                core.append(t)
    # 限制总数
    return core[:8]


def _summarize_relationships(
    foreign_keys: List[Dict[str, Any]]
) -> List[Dict[str, str]]:
    """收集独特的表-表关系 (去重)"""
    seen = set()
    relations: List[Dict[str, str]] = []
    for fk in foreign_keys:
        from_t = fk.get("from_table") or fk.get("table") or ""
        to_t = fk.get("to_table") or fk.get("references_table") or ""
        if not from_t or not to_t:
            continue
        key = (from_t, to_t)
        if key in seen:
            continue
        seen.add(key)
        relations.append({
            "from_table": from_t,
            "to_table": to_t,
            "type": "many-to-one",  # 默认假设 (FK 指向多对一)
        })
    return relations


def _build_narrative(
    total: int,
    pattern: str,
    confidence: str,
    modules: List[Dict[str, Any]],
    core: List[str],
    relations: List[Dict[str, str]],
) -> str:
    """拼装人类可读的 schema 描述"""
    lines: List[str] = []

    # 1. 总览
    lines.append(f"这个数据库包含 {total} 张表。")
    if pattern != "General":
        confidence_label = {"high": "强", "medium": "中等", "low": "弱"}.get(confidence, confidence)
        lines.append(f"检测到 **{pattern}** 业务模式 (匹配置信度: {confidence_label})。")
    else:
        lines.append("未识别到典型业务模式,可能是自定义领域。")
    lines.append("")

    # 2. 模块划分
    if len(modules) > 1:
        lines.append(f"按命名前缀可分为 {len(modules)} 个模块:")
        for m in modules[:5]:
            lines.append(
                f"  - **{m['prefix']}_*** ({m['table_count']} 张): {m['description']}"
            )
        if len(modules) > 5:
            lines.append(f"  - ... 还有 {len(modules) - 5} 个模块")
        lines.append("")

    # 3. 核心实体
    if core:
        lines.append("核心实体 (优先生成):")
        for t in core[:6]:
            lines.append(f"  - `{t}`")
        if len(core) > 6:
            lines.append(f"  - ... 还有 {len(core) - 6} 个")
        lines.append("")

    # 4. 关键关系
    if relations:
        lines.append(f"检测到 {len(relations)} 个外键关系,典型:")
        for rel in relations[:5]:
            lines.append(
                f"  - `{rel['from_table']}` → `{rel['to_table']}` ({rel['type']})"
            )
        if len(relations) > 5:
            lines.append(f"  - ... 还有 {len(relations) - 5} 个")
        lines.append("")

    if not lines[-1]:
        lines.pop()  # 去尾空行
    return "\n".join(lines)
