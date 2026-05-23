"""
P2.3: Tool Registry - 工具元数据中心,支持渐进式发现 (Progressive Discovery)

设计:
  - 每个 MCP 工具有 (name, description, inputSchema) 之外的元数据:
    tags (关键词), category (层级), always_visible (是否默认暴露)
  - search_tools(query) 通过 case-insensitive 关键词匹配返回候选,LLM 按需调用
  - 默认模式: list_tools 返回全部工具 (向后兼容)
  - progressive 模式 (env DBJAVAGENIX_PROGRESSIVE=1): list_tools 只返回
    always_visible 工具 + search_tools,把启动 token 从 ~3200 降到 ~1100

为什么不用向量检索:
  - 工具数量 ~30 个,关键词匹配 + tag 已足够准确
  - 向量数据库引入额外依赖与启动成本,违背"工程克制"边界
"""

import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

from mcp.types import Tool


@dataclass
class ToolMetadata:
    """单个工具的元数据"""
    name: str
    tags: Set[str] = field(default_factory=set)
    category: str = "misc"
    always_visible: bool = False
    description_brief: str = ""


# ============================================================
# 工具元数据注册表 — 手工维护,与 mcp_tools.py / atomic_codegen_tools.py 工具名对齐
# ============================================================

_REGISTRY: Dict[str, ToolMetadata] = {
    # ---- 连接与查询 ----
    "db_connect_test": ToolMetadata(
        name="db_connect_test",
        tags={"connect", "connection", "database", "test", "establish", "init"},
        category="connection",
        always_visible=True,
        description_brief="建立数据库连接 (MySQL/PostgreSQL/SQLite/Oracle/SqlServer)",
    ),
    "db_query_databases": ToolMetadata(
        name="db_query_databases",
        tags={"list", "databases", "schemas"},
        category="connection",
        description_brief="列出服务器上所有数据库名",
    ),
    "db_query_tables": ToolMetadata(
        name="db_query_tables",
        tags={"list", "tables", "schema"},
        category="connection",
        always_visible=True,
        description_brief="列出指定数据库中所有表名",
    ),
    "db_query_table_exists": ToolMetadata(
        name="db_query_table_exists",
        tags={"exists", "check", "table"},
        category="connection",
        description_brief="检查表是否存在",
    ),
    "db_query_execute": ToolMetadata(
        name="db_query_execute",
        tags={"sql", "select", "query", "custom"},
        category="connection",
        description_brief="执行自定义 SELECT SQL 查询",
    ),
    # ---- 表结构分析 ----
    "db_table_describe": ToolMetadata(
        name="db_table_describe",
        tags={"describe", "table", "structure", "columns", "schema", "ddl"},
        category="schema",
        always_visible=True,
        description_brief="获取完整表结构 (列/类型/约束/Java 类型推断)",
    ),
    "db_table_columns": ToolMetadata(
        name="db_table_columns",
        tags={"columns", "fields", "table"},
        category="schema",
        description_brief="仅获取表的列定义",
    ),
    "db_table_primary_keys": ToolMetadata(
        name="db_table_primary_keys",
        tags={"primary", "key", "pk", "table"},
        category="schema",
        description_brief="获取表的主键列",
    ),
    "db_table_foreign_keys": ToolMetadata(
        name="db_table_foreign_keys",
        tags={"foreign", "key", "fk", "relation", "references"},
        category="schema",
        description_brief="获取表的外键关系 (用于 ER 图)",
    ),
    "db_table_indexes": ToolMetadata(
        name="db_table_indexes",
        tags={"index", "indexes", "btree"},
        category="schema",
        description_brief="获取表的索引信息",
    ),
    # ---- 代码生成 (legacy) ----
    "db_codegen_analyze": ToolMetadata(
        name="db_codegen_analyze",
        tags={"analyze", "codegen", "context", "build"},
        category="codegen-legacy",
        description_brief="[Legacy] 分析表结构生成模板上下文 (建议用 codegen_build_context)",
    ),
    "db_codegen_generate": ToolMetadata(
        name="db_codegen_generate",
        tags={"generate", "codegen", "java", "all-in-one", "legacy"},
        category="codegen-legacy",
        description_brief="[Legacy] 一步生成全部代码并写盘 (建议用原子工具组合)",
    ),
    # ---- 代码生成 (atomic, P2.2) ----
    "codegen_build_context": ToolMetadata(
        name="codegen_build_context",
        tags={"context", "codegen", "build", "java", "spring", "boot", "entity"},
        category="codegen-atomic",
        always_visible=True,
        description_brief="构建模板上下文 (代码生成入口,后续 render_* 工具的输入)",
    ),
    "codegen_render_entity": ToolMetadata(
        name="codegen_render_entity",
        tags={"render", "entity", "jpa", "java", "codegen"},
        category="codegen-atomic",
        description_brief="渲染 Entity 层 (JPA @Entity / MybatisPlus @TableName)",
    ),
    "codegen_render_dao": ToolMetadata(
        name="codegen_render_dao",
        tags={"render", "dao", "repository", "jpa", "mybatis", "codegen"},
        category="codegen-atomic",
        description_brief="渲染 DAO/Repository 层",
    ),
    "codegen_render_service": ToolMetadata(
        name="codegen_render_service",
        tags={"render", "service", "impl", "codegen"},
        category="codegen-atomic",
        description_brief="渲染 Service 接口 + ServiceImpl 实现",
    ),
    "codegen_render_controller": ToolMetadata(
        name="codegen_render_controller",
        tags={"render", "controller", "rest", "restcontroller", "api", "codegen"},
        category="codegen-atomic",
        description_brief="渲染 REST Controller",
    ),
    "codegen_render_mapper": ToolMetadata(
        name="codegen_render_mapper",
        tags={"render", "mapper", "mybatis", "xml", "mapstruct"},
        category="codegen-atomic",
        description_brief="渲染 MyBatis XML mapper / MapStruct mapper",
    ),
    # ---- Spring Boot 项目 ----
    "springboot_validate_project": ToolMetadata(
        name="springboot_validate_project",
        tags={"validate", "spring", "boot", "project", "structure", "precheck"},
        category="springboot",
        always_visible=True,
        description_brief="验证 Spring Boot 项目结构是否合法",
    ),
    "springboot_analyze_dependencies": ToolMetadata(
        name="springboot_analyze_dependencies",
        tags={"dependencies", "deps", "pom", "maven", "gradle", "health", "spring"},
        category="springboot",
        description_brief="分析项目依赖健康度 + 给出修复建议",
    ),
    "springboot_read_config": ToolMetadata(
        name="springboot_read_config",
        tags={"config", "application", "yml", "properties", "spring"},
        category="springboot",
        description_brief="读取 application.yml/properties 配置",
    ),
    # ---- 元工具 ----
    "search_tools": ToolMetadata(
        name="search_tools",
        tags={"search", "find", "discover", "tool", "meta"},
        category="meta",
        always_visible=True,
        description_brief="按关键词搜索可用工具 (渐进式发现)",
    ),
    # ---- 可视化 (P3 MCP Apps) ----
    "db_render_er_diagram": ToolMetadata(
        name="db_render_er_diagram",
        tags={"er", "diagram", "mermaid", "visualize", "relations", "schema"},
        category="visualization",
        description_brief="生成多表 ER 图 (Mermaid, MCP App)",
    ),
    # ---- AI 语义 (P4) ----
    "ai_infer_business_names": ToolMetadata(
        name="ai_infer_business_names",
        tags={"ai", "infer", "naming", "class", "rule", "llm", "claude", "semantic"},
        category="ai",
        description_brief="推断业务 Java 命名 (规则 + 可选 Claude API)",
    ),
    "ai_recommend_template": ToolMetadata(
        name="ai_recommend_template",
        tags={"ai", "recommend", "template", "pattern", "rbac", "ecommerce", "cms"},
        category="ai",
        description_brief="按 schema 模式推荐 template_category + 生成选项",
    ),
    "ai_summarize_schema": ToolMetadata(
        name="ai_summarize_schema",
        tags={"ai", "summarize", "schema", "overview", "narrative", "modules"},
        category="ai",
        description_brief="生成 schema 自然语言概述 (模块/核心实体/关系)",
    ),
}


def get_all_metadata() -> List[ToolMetadata]:
    return list(_REGISTRY.values())


def get_metadata(name: str) -> Optional[ToolMetadata]:
    return _REGISTRY.get(name)


def get_always_visible_names() -> Set[str]:
    return {m.name for m in _REGISTRY.values() if m.always_visible}


def is_progressive_mode_enabled() -> bool:
    """通过环境变量 DBJAVAGENIX_PROGRESSIVE 启用 (默认关闭以保持向后兼容)"""
    return os.environ.get("DBJAVAGENIX_PROGRESSIVE", "").lower() in ("1", "true", "yes", "on")


# ============================================================
# 搜索逻辑
# ============================================================

def search_tools_by_query(
    query: str, limit: int = 10
) -> List[Dict[str, str]]:
    """按 query 搜索匹配的工具元数据。

    匹配规则 (case-insensitive):
      1. 完全匹配 name → 排在最前
      2. tag 包含 query 的 token → score += 3 per match
      3. name 包含 query → score += 2
      4. description_brief 包含 query → score += 1

    Args:
        query: 搜索关键词,允许空格分隔多 token
        limit: 返回前 N 个结果

    Returns:
        匹配工具列表,每项: {name, category, description_brief, score}
    """
    if not query or not query.strip():
        # 空 query → 返回 always_visible + 类别样例
        candidates = [
            m for m in _REGISTRY.values() if m.always_visible
        ]
        return [
            {
                "name": m.name,
                "category": m.category,
                "description_brief": m.description_brief,
                "score": 1.0,
            }
            for m in candidates
        ]

    tokens = [t.lower() for t in query.split() if t.strip()]
    scored: List[tuple] = []
    for meta in _REGISTRY.values():
        score = 0.0
        name_lower = meta.name.lower()
        desc_lower = meta.description_brief.lower()
        for tok in tokens:
            if tok == name_lower:
                score += 10
            elif tok in meta.tags:
                score += 3
            elif tok in name_lower:
                score += 2
            elif tok in desc_lower:
                score += 1
        if score > 0:
            scored.append((score, meta))

    scored.sort(key=lambda x: (-x[0], x[1].name))
    return [
        {
            "name": meta.name,
            "category": meta.category,
            "description_brief": meta.description_brief,
            "score": score,
        }
        for score, meta in scored[:limit]
    ]


def filter_tools_for_listing(all_tools: List[Tool]) -> List[Tool]:
    """根据 progressive 模式过滤 list_tools 输出。

    - 默认 (非 progressive): 原样返回全部工具
    - progressive 开启: 只保留 always_visible 工具 + search_tools
    """
    if not is_progressive_mode_enabled():
        return all_tools

    visible = get_always_visible_names()
    return [t for t in all_tools if t.name in visible]
