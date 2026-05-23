"""
P4.2: 模板推荐规则 - 检测数据库模式 (RBAC / 电商 / CMS / 工单 / 通用)。

输入: 整库表名列表 + 各表的外键关系
输出: 推荐的 template_category + useSwagger / useLombok / include_mapstruct 配置 + 推荐理由

设计:
  - 基于模式匹配 (表名 + 关系) 评分
  - 多模式可同时匹配,选最高分
  - 阈值 < 0.5 时给 "general" 通用建议
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


# ============================================================
# 模式特征定义
# ============================================================

@dataclass
class SchemaPattern:
    name: str
    description: str
    # 必须 (any-of) 包含的表名片段 (lowercase)
    required_table_fragments: List[List[str]]
    # 额外加分项
    bonus_table_fragments: List[str]
    # 推荐的模板分类
    recommended_template: str
    recommended_options: Dict[str, Any]
    notes: str


PATTERNS = [
    SchemaPattern(
        name="RBAC",
        description="基于角色的权限管理 (Role-Based Access Control)",
        required_table_fragments=[
            ["user"],
            ["role"],
        ],
        bonus_table_fragments=["permission", "menu", "resource", "user_role", "role_permission", "role_menu"],
        recommended_template="MybatisPlus-Mixed",
        recommended_options={
            "useSwagger": True,
            "useLombok": True,
            "include_mapstruct": True,
            "generate_dto": True,
            "generate_vo": True,
        },
        notes="RBAC 三/四表模型,建议生成 DTO + VO 区分网络模型与领域模型;含权限校验所以推荐 Swagger 暴露 API。",
    ),
    SchemaPattern(
        name="E-Commerce",
        description="电商订单系统 (Orders + Items + Products + Categories)",
        required_table_fragments=[
            ["order"],
            ["product"],
        ],
        bonus_table_fragments=["order_item", "order_detail", "category", "sku", "inventory", "payment", "shipping", "cart"],
        recommended_template="MybatisPlus-Mixed",
        recommended_options={
            "useSwagger": True,
            "useLombok": True,
            "include_mapstruct": True,
            "generate_dto": True,
            "generate_vo": True,
        },
        notes="电商系统通常多表关联 (订单/订单项/商品/SKU),建议 MybatisPlus-Mixed (XML 处理复杂查询) + DTO/VO 分层。",
    ),
    SchemaPattern(
        name="CMS",
        description="内容管理系统 (Articles + Categories + Tags + Comments)",
        required_table_fragments=[
            ["article", "content", "post"],
        ],
        bonus_table_fragments=["category", "tag", "comment", "attachment", "author", "media"],
        recommended_template="MybatisPlus",
        recommended_options={
            "useSwagger": True,
            "useLombok": True,
            "include_mapstruct": False,
            "generate_dto": True,
            "generate_vo": False,
        },
        notes="CMS 系统 CRUD 占主体,纯 MybatisPlus (BaseMapper) 已足够,无需 XML; DTO 用于前后端交互。",
    ),
    SchemaPattern(
        name="Ticketing",
        description="工单系统 (Tickets + Assignments + Status History)",
        required_table_fragments=[
            ["ticket", "issue", "case"],
        ],
        bonus_table_fragments=["assignment", "status_history", "ticket_log", "priority", "category"],
        recommended_template="MybatisPlus-Mixed",
        recommended_options={
            "useSwagger": True,
            "useLombok": True,
            "include_mapstruct": True,
            "generate_dto": True,
            "generate_vo": True,
        },
        notes="工单系统有状态机 + 历史记录,建议生成 DTO/VO,Mixed 模式便于审计查询。",
    ),
    SchemaPattern(
        name="Modern-Spring-Boot-3",
        description="现代 Spring Boot 3.x + Java 21 + JPA",
        required_table_fragments=[],  # 不靠表名,靠用户提示
        bonus_table_fragments=[],
        recommended_template="sb35-java21",
        recommended_options={
            "useSwagger": True,
            "useLombok": True,
            "include_mapstruct": False,
            "generate_dto": True,
            "generate_vo": False,
        },
        notes="Spring Boot 3.x + Java 21 + JPA/Hibernate 6 + record DTO + jakarta 命名空间。适合从零的新项目。",
    ),
]


# ============================================================
# 推荐引擎
# ============================================================

@dataclass
class TemplateRecommendation:
    template: str
    options: Dict[str, Any]
    pattern: str
    score: float
    reasons: List[str]
    matched_tables: List[str]
    confidence: str  # high / medium / low


def recommend_template(
    table_names: List[str],
    foreign_keys: Optional[List[Dict[str, Any]]] = None,
    hint_modern_stack: bool = False,
) -> TemplateRecommendation:
    """从整库表名 + 关系推荐模板分类。

    Args:
        table_names: 数据库中所有表名
        foreign_keys: 跨表 FK 列表 (可选,目前未用于评分)
        hint_modern_stack: 用户暗示偏好 Java 21/jakarta → 推 sb35-java21

    Returns:
        TemplateRecommendation
    """
    if hint_modern_stack:
        modern = next(p for p in PATTERNS if p.name == "Modern-Spring-Boot-3")
        return TemplateRecommendation(
            template=modern.recommended_template,
            options=modern.recommended_options,
            pattern=modern.name,
            score=1.0,
            reasons=[modern.notes],
            matched_tables=[],
            confidence="high",
        )

    lower_tables = [t.lower() for t in table_names]
    best: Optional[TemplateRecommendation] = None

    for pattern in PATTERNS:
        if pattern.name == "Modern-Spring-Boot-3":
            continue  # 仅在 hint=true 时触发

        score, reasons, matched = _score_pattern(pattern, lower_tables)
        if score == 0:
            continue
        confidence = _score_to_confidence(score)
        rec = TemplateRecommendation(
            template=pattern.recommended_template,
            options=pattern.recommended_options,
            pattern=pattern.name,
            score=score,
            reasons=reasons + [pattern.notes],
            matched_tables=matched,
            confidence=confidence,
        )
        if best is None or rec.score > best.score:
            best = rec

    if best is None or best.score < 0.5:
        # 通用建议
        return TemplateRecommendation(
            template="MybatisPlus-Mixed",
            options={
                "useSwagger": True,
                "useLombok": True,
                "include_mapstruct": False,
                "generate_dto": False,
                "generate_vo": False,
            },
            pattern="General",
            score=0.0,
            reasons=[
                "未匹配到已知业务模式 (RBAC/电商/CMS/工单)",
                "推荐通用 MybatisPlus-Mixed 模板,适合大多数 CRUD 场景",
            ],
            matched_tables=[],
            confidence="low",
        )

    return best


def _score_pattern(
    pattern: SchemaPattern, lower_tables: List[str]
) -> tuple[float, List[str], List[str]]:
    """对单个模式评分。

    评分逻辑:
      - 每个 required 组至少匹配一个 → +1.0,全部 required 满足才有非 0 总分
      - 每个 bonus 命中 → +0.2
      - 最高分上限: 2.0
    """
    matched_tables: List[str] = []
    reasons: List[str] = []

    # required (any-of within group)
    for group in pattern.required_table_fragments:
        hit_in_group = False
        for fragment in group:
            for t in lower_tables:
                if fragment in t:
                    hit_in_group = True
                    matched_tables.append(t)
                    break
            if hit_in_group:
                break
        if not hit_in_group:
            # 缺一个 required → 整个模式 0 分
            return 0.0, [], []

    base_score = 1.0
    reasons.append(f"匹配模式 {pattern.name}: 必需表片段全部命中")

    # bonus
    bonus_hits = 0
    for fragment in pattern.bonus_table_fragments:
        for t in lower_tables:
            if fragment in t:
                bonus_hits += 1
                matched_tables.append(t)
                break

    if bonus_hits > 0:
        reasons.append(f"额外加分: {bonus_hits} 个辅助表片段命中")

    score = base_score + 0.2 * bonus_hits
    score = min(score, 2.0)
    # 去重 matched_tables (保留顺序)
    seen = set()
    matched_unique = []
    for t in matched_tables:
        if t not in seen:
            matched_unique.append(t)
            seen.add(t)
    return score, reasons, matched_unique


def _score_to_confidence(score: float) -> str:
    if score >= 1.5:
        return "high"
    if score >= 1.0:
        return "medium"
    return "low"
