"""
P4.1: 基于规则的业务命名推断 (无需 LLM)。

提供 LLM 不可用 (无 ANTHROPIC_API_KEY / 网络受限) 时的降级路径,
以及为 LLM prompt 准备的"基础参考结果"。

核心规则 (15 条,与 iteration-plan 一致):
  1. 去前缀: sys_/sys/biz_/bd_/cms_/...
  2. 单数化: users → User, categories → Category
  3. PascalCase: user_role → UserRole
  4. 关联表识别: 含两个 *_id 外键且无业务列 → 加 'Assignment' 或 'Mapping' 后缀
  5. 日志表: *_log → *Log
  6. 字典表: sys_dict / *_dict → *Dict
  7. 配置表: *_config → *Config

输出与 LLM 模式格式一致, 便于上层无差别处理。
"""

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from ..core.java_identifiers import to_pascal_case


COMMON_PREFIXES = (
    "sys_",
    "biz_",
    "bd_",
    "cms_",
    "ops_",
    "admin_",
    "core_",
    "t_",
    "tb_",  # 通用建表习惯
)

# 不规则单数化(主要场景,不追求完全覆盖)
IRREGULAR_PLURALS = {
    "categories": "category",
    "histories": "history",
    "policies": "policy",
    "indices": "index",
    "matrices": "matrix",
    "people": "person",
    "children": "child",
    "men": "man",
    "women": "woman",
}

LOG_SUFFIXES = ("_log", "_logs", "_record", "_records", "_history", "_histories")
DICT_SUFFIXES = ("_dict", "_dictionary", "_dict_item", "_lookup")
CONFIG_SUFFIXES = ("_config", "_configs", "_setting", "_settings")


@dataclass
class NamingInference:
    table: str
    class_name: str
    field_naming: Dict[str, str]
    reason: str
    table_kind: str  # entity / association / log / dict / config / unknown
    source: str  # rule / llm
    confidence: float  # 0.0-1.0


def infer_business_name(
    table: str,
    columns: Optional[List[Dict[str, Any]]] = None,
    foreign_keys: Optional[List[Dict[str, Any]]] = None,
) -> NamingInference:
    """对单张表做规则推断。

    Args:
        table: 表名
        columns: [{name, primary_key, ...}] (用于关联表识别)
        foreign_keys: [{column, references_table, ...}] (用于关联表识别)

    Returns:
        NamingInference 对象
    """
    columns = columns or []
    foreign_keys = foreign_keys or []
    lower = table.lower()

    # 1. 检测特殊表类型
    kind, suffix_class = _detect_special_kind(lower)
    if kind != "unknown":
        stripped = _strip_known_prefix(lower)
        base_stripped = _strip_special_suffix(stripped, kind)
        base = _to_pascal_case(base_stripped) if base_stripped else _to_pascal_case(stripped)
        # 重复后缀检查: 把 base_stripped 按下划线/驼峰拆词,看是否含 suffix 关键字
        suffix_kw = suffix_class.lower()
        tokens = _tokenize(base_stripped or stripped)
        if suffix_kw in tokens:
            class_name = base
            reason = f"{kind} 表 (后缀匹配, base 已含 {suffix_class} 词)"
        else:
            class_name = f"{base}{suffix_class}"
            reason = f"{kind} 表 (后缀匹配) → +{suffix_class}"
        return NamingInference(
            table=table,
            class_name=class_name,
            field_naming={},
            reason=reason,
            table_kind=kind,
            source="rule",
            confidence=0.85,
        )

    # 2. 检测关联表: ≥ 2 个外键且其他列很少
    if _is_association_table(columns, foreign_keys):
        # 关联表命名: 用两个外键的 referenced_table 组合
        ref_tables = [
            _strip_known_prefix(fk.get("references_table", "")) for fk in foreign_keys[:2]
        ]
        ref_classes = [_to_pascal_case(_singularize(rt)) for rt in ref_tables if rt]
        if len(ref_classes) >= 2:
            class_name = f"{ref_classes[0]}{ref_classes[1]}Assignment"
        else:
            class_name = _to_pascal_case(_singularize(_strip_known_prefix(lower))) + "Mapping"
        return NamingInference(
            table=table,
            class_name=class_name,
            field_naming={},
            reason="关联表 (含 ≥ 2 个外键且业务列少) → Assignment 后缀",
            table_kind="association",
            source="rule",
            confidence=0.75,
        )

    # 3. 通用实体: 去前缀 + 单数 + PascalCase
    stripped = _strip_known_prefix(lower)
    singular = _singularize(stripped)
    class_name = _to_pascal_case(singular)
    return NamingInference(
        table=table,
        class_name=class_name,
        field_naming={},
        reason="实体表: 去前缀 + 单数化 + PascalCase",
        table_kind="entity",
        source="rule",
        confidence=0.7,
    )


def _detect_special_kind(lower_table: str) -> Tuple[str, str]:
    """检测日志/字典/配置表,返回 (kind, suffix_class)"""
    for suffix in LOG_SUFFIXES:
        if lower_table.endswith(suffix):
            return "log", "Log"
    for suffix in DICT_SUFFIXES:
        if lower_table.endswith(suffix):
            return "dict", "Dict"
    for suffix in CONFIG_SUFFIXES:
        if lower_table.endswith(suffix):
            return "config", "Config"
    return "unknown", ""


def _strip_special_suffix(name: str, kind: str) -> str:
    """根据 kind 去掉对应的特殊后缀,容忍前导下划线"""
    suffix_groups = {
        "log": LOG_SUFFIXES,
        "dict": DICT_SUFFIXES,
        "config": CONFIG_SUFFIXES,
    }
    suffixes = suffix_groups.get(kind, ())
    # 先用带下划线的精确匹配 (例 'login_log' → 'login')
    for suffix in suffixes:
        if name.endswith(suffix):
            return name[: -len(suffix)]
    # 再尝试无下划线匹配 (例 stripped='dict_item' 没匹配上 '_dict_item' 时,
    #   退而求其次让 'dict' 这种短 case 也能去)
    bare_suffixes = [s.lstrip("_") for s in suffixes]
    for bare in bare_suffixes:
        if name.endswith(bare) and name != bare:
            return name[: -len(bare)].rstrip("_")
    return name


def _is_association_table(
    columns: List[Dict[str, Any]], foreign_keys: List[Dict[str, Any]]
) -> bool:
    """判断是否是关联表 (含 ≥ 2 个外键 + 业务列少)"""
    if len(foreign_keys) < 2:
        return False
    fk_cols = {fk.get("column", "") for fk in foreign_keys}
    pk_count = sum(1 for c in columns if c.get("primary_key"))
    # 业务列 = 非主键 + 非外键
    business_cols = [
        c for c in columns if not c.get("primary_key") and c.get("name") not in fk_cols
    ]
    # 时间戳/审计字段不算业务列
    business_cols = [c for c in business_cols if not _is_audit_column(c.get("name", ""))]
    # 业务列 ≤ 1 (例如 'remark') 视为关联表
    return len(business_cols) <= 1 and pk_count <= 1


_AUDIT_PATTERNS = (
    "created_at",
    "updated_at",
    "create_time",
    "update_time",
    "created_by",
    "updated_by",
    "deleted_at",
    "deleted",
    "version",
    "tenant_id",
    "remark",
)


def _is_audit_column(name: str) -> bool:
    return name.lower() in _AUDIT_PATTERNS


def _strip_known_prefix(name: str) -> str:
    for prefix in COMMON_PREFIXES:
        if name.startswith(prefix):
            return name[len(prefix) :]
    return name


def _singularize(name: str) -> str:
    """简单英文单数化"""
    if not name:
        return name
    lower = name.lower()
    if lower in IRREGULAR_PLURALS:
        return IRREGULAR_PLURALS[lower]
    # ies → y
    if lower.endswith("ies") and len(lower) > 3:
        return lower[:-3] + "y"
    # ses / xes / ches / shes
    for suf in ("ses", "xes", "ches", "shes"):
        if lower.endswith(suf):
            return lower[:-2]
    # 复数 s 去掉 (排除 ss / us / is 等不应该去的)
    if lower.endswith("s") and not lower.endswith(("ss", "us", "is", "as", "os")):
        return lower[:-1]
    return lower


_CAMEL_SPLIT_RE = re.compile(r"[_\-\s]+")


def _to_pascal_case(name: str) -> str:
    return to_pascal_case(name)


def _tokenize(name: str) -> List[str]:
    """把下划线/连字符分隔的名字拆为 lowercase 词列表"""
    return [p.lower() for p in _CAMEL_SPLIT_RE.split(name) if p]


def infer_business_names_batch(tables: List[Dict[str, Any]]) -> List[NamingInference]:
    """对一批表批量推断 (输入格式与 LLM 模式一致)"""
    return [
        infer_business_name(
            table=t.get("name", ""),
            columns=t.get("columns", []),
            foreign_keys=t.get("foreign_keys", []),
        )
        for t in tables
    ]
