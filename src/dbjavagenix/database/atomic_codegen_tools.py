"""
P2.2: 原子化代码生成工具 - 把 db_codegen_generate 拆为 7 个职责单一的工具

工作流(对应 .claude/skills/java-codegen-from-db/SKILL.md 阶段 4):

  1. codegen_build_context     - 构建上下文(不写盘,返回 context dict)
  2. codegen_render_entity     - 渲染 Entity 层
  3. codegen_render_dao        - 渲染 DAO/Repository
  4. codegen_render_service    - 渲染 Service 接口 + ServiceImpl
  5. codegen_render_controller - 渲染 REST Controller
  6. codegen_render_mapper     - 渲染 MyBatis XML / Mapper(仅 MybatisPlus/Default)
  7. codegen_render_dto        - 渲染 sb35-java21 record DTO

设计原则:
  - 不写盘 — render 仅返回 code 字符串,写盘由 Skill 显式调用专门工具(后续阶段)
  - 显式 context — 没有 server 内部状态,纯函数式:LLM 把 build_context 的返回 dict 当参数传给后续工具
  - 错误透明 — 失败时返回 {"error": "...", "template_file": "..."} 而非吞掉
  - 统一返回结构: {"files": [{"code","file_path","template_file"}], "language": "java"}

兼容性:
  - 旧 db_codegen_generate 保留 (deprecated),作为"一步到位"的退路
  - 新工具不依赖旧工具,各自独立
"""

import json
import logging
from typing import Any, Dict, List

from mcp.types import Tool, TextContent

from ..core.exceptions import DatabaseConnectionError, MCPServiceError
from ..database.connection_manager import connection_manager

logger = logging.getLogger(__name__)


# ============================================================
# Tool 定义 - 7 个原子工具
# ============================================================


def get_atomic_codegen_tools() -> List[Tool]:
    """返回 P2.2 拆分后的 7 个原子代码生成工具"""

    # 共用的 context 参数 schema:LLM 把 build_context 返回的 dict 原样传入
    context_param_schema = {
        "type": "object",
        "description": (
            "从 codegen_build_context 返回的完整模板上下文 dict。包含 className/columns/"
            "primaryKeyType/templateCategory 等字段。LLM 应原样传递,可在传入前修改字段以重新渲染。"
        ),
    }

    return [
        Tool(
            name="codegen_build_context",
            description=(
                "构建代码生成所需的完整模板上下文(不写盘,不渲染)。"
                "这是原子代码生成工作流的第一步,后续 codegen_render_* 工具的输入。"
                "返回的 context dict 可被 LLM 检视或修改,再传给后续工具。"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "connection_id": {
                        "type": "string",
                        "description": "Database connection ID from db_connect_test",
                    },
                    "table_name": {
                        "type": "string",
                        "description": "Table name to build context for",
                    },
                    "database": {
                        "type": "string",
                        "description": "Database name (optional, uses connection default)",
                    },
                    "schema": {
                        "type": "string",
                        "description": "PostgreSQL schema (optional; required for ambiguous table names)",
                    },
                    "template_category": {
                        "type": "string",
                        "enum": ["Default", "MybatisPlus", "MybatisPlus-Mixed", "sb35-java21"],
                        "default": "MybatisPlus-Mixed",
                    },
                    "author": {"type": "string", "default": "ZXP"},
                    "package_name": {"type": "string", "default": "com.example.generated"},
                    "include_swagger": {"type": "boolean", "default": True},
                    "include_lombok": {"type": "boolean", "default": True},
                    "include_mapstruct": {"type": "boolean", "default": True},
                    "project_path": {
                        "type": "string",
                        "description": "Optional target Spring Boot project path",
                    },
                },
                "required": ["connection_id", "table_name"],
            },
        ),
        Tool(
            name="codegen_render_entity",
            description=(
                "渲染 Entity 层(JPA @Entity / MybatisPlus @TableName)。"
                "需要先调用 codegen_build_context 获取 context。返回单个 java 文件源码。"
            ),
            inputSchema={
                "type": "object",
                "properties": {"context": context_param_schema},
                "required": ["context"],
            },
        ),
        Tool(
            name="codegen_render_dao",
            description=(
                "渲染 DAO/Repository 层(JpaRepository 或 BaseMapper)。"
                "需要先调用 codegen_build_context 获取 context。"
            ),
            inputSchema={
                "type": "object",
                "properties": {"context": context_param_schema},
                "required": ["context"],
            },
        ),
        Tool(
            name="codegen_render_service",
            description=(
                "渲染 Service 接口 + ServiceImpl 实现。"
                "需要先调用 codegen_build_context 获取 context。返回 2 个 java 文件。"
            ),
            inputSchema={
                "type": "object",
                "properties": {"context": context_param_schema},
                "required": ["context"],
            },
        ),
        Tool(
            name="codegen_render_controller",
            description=(
                "渲染 REST Controller(@RestController + Bean Validation)。"
                "需要先调用 codegen_build_context 获取 context。"
            ),
            inputSchema={
                "type": "object",
                "properties": {"context": context_param_schema},
                "required": ["context"],
            },
        ),
        Tool(
            name="codegen_render_dto",
            description=(
                "渲染 sb35-java21 的 Java record DTO。需要先调用 "
                "codegen_build_context 获取 context；其他模板分类不生成 DTO。"
            ),
            inputSchema={
                "type": "object",
                "properties": {"context": context_param_schema},
                "required": ["context"],
            },
        ),
        Tool(
            name="codegen_render_mapper",
            description=(
                "渲染 MyBatis XML mapper 或 MapStruct mapper。"
                "适用模板: Default(mapper.xml) / MybatisPlus-Mixed(mapper) / 含 useMapStruct(mapstruct_mapper)。"
                "sb35-java21 分类不需要 mapper,会返回空 files 列表。"
            ),
            inputSchema={
                "type": "object",
                "properties": {"context": context_param_schema},
                "required": ["context"],
            },
        ),
    ]


# ============================================================
# Handler 实现
# ============================================================


async def handle_codegen_build_context(arguments: Dict[str, Any]) -> List[TextContent]:
    """构建并返回完整模板上下文 dict(JSON 序列化在 TextContent.text)"""
    try:
        from .codegen_tools import CodegenAnalyzer

        connection_id = arguments["connection_id"]
        table_name = arguments["table_name"]
        database = arguments.get("database")
        schema = arguments.get("schema") or None
        template_category = arguments.get("template_category", "MybatisPlus-Mixed")
        author = arguments.get("author", "ZXP")
        package_name = arguments.get("package_name", "com.example.generated")
        include_swagger = arguments.get("include_swagger", True)
        include_lombok = arguments.get("include_lombok", True)
        include_mapstruct = arguments.get("include_mapstruct", True)
        project_path = arguments.get("project_path")

        from ..generator.template_context import TemplateConfigManager

        supported_categories = TemplateConfigManager.get_supported_categories()
        if template_category not in supported_categories:
            supported = ", ".join(supported_categories)
            raise MCPServiceError(f"不支持的模板分类: {template_category!r}；支持分类: {supported}")

        config = connection_manager.get_connection_info(connection_id)
        if not config:
            raise DatabaseConnectionError(f"Connection {connection_id} not found")
        if not database:
            database = config.database or "information_schema"

        # 收集所有表名用于前缀分析(沿用旧逻辑)
        all_table_names = _collect_all_table_names(connection_id, config)

        analyzer = CodegenAnalyzer(connection_manager)
        analysis = await analyzer.analyze_table_for_codegen(
            connection_id,
            table_name,
            all_table_names=all_table_names,
            template_category=template_category,
            project_root=project_path,
            schema=schema,
        )

        context = analysis["template_context"]
        context.update(
            {
                "author": author,
                "packageName": package_name,
                "hasPackageName": bool(package_name),
                "templateCategory": template_category,
                "isDefault": template_category == "Default",
                "isMybatisPlus": template_category == "MybatisPlus",
                "isMybatisPlusMixed": template_category == "MybatisPlus-Mixed",
                "isSb35Java21": template_category == "sb35-java21",
                "useSwagger": include_swagger,
                "useLombok": include_lombok,
                "useMapStruct": include_mapstruct,
            }
        )

        # 重写包路径(尊重 package_suffix)
        _rebuild_package_paths(context, package_name)
        _normalize_tech_flags(context)

        result = {
            "table_name": table_name,
            "template_category": template_category,
            "context": context,
            "_meta": {
                "build_context_version": "p2.2",
                "next_tools": [
                    "codegen_render_entity",
                    "codegen_render_dao",
                    "codegen_render_service",
                    "codegen_render_controller",
                    "codegen_render_dto",
                    "codegen_render_mapper",
                ],
            },
        }
        return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]

    except (DatabaseConnectionError, MCPServiceError) as e:
        return [
            TextContent(
                type="text",
                text=json.dumps({"error": str(e), "stage": "build_context"}, ensure_ascii=False),
            )
        ]
    except Exception as e:  # noqa: BLE001
        logger.error(f"codegen_build_context unexpected error: {e}")
        return [
            TextContent(
                type="text",
                text=json.dumps(
                    {"error": f"unexpected: {e}", "stage": "build_context"}, ensure_ascii=False
                ),
            )
        ]


async def handle_codegen_render_entity(arguments: Dict[str, Any]) -> List[TextContent]:
    return await _render_single_layer(arguments, ["entity.mustache"])


async def handle_codegen_render_dao(arguments: Dict[str, Any]) -> List[TextContent]:
    return await _render_single_layer(arguments, ["dao.mustache"])


async def handle_codegen_render_service(arguments: Dict[str, Any]) -> List[TextContent]:
    return await _render_single_layer(arguments, ["service.mustache", "serviceImpl.mustache"])


async def handle_codegen_render_controller(arguments: Dict[str, Any]) -> List[TextContent]:
    return await _render_single_layer(arguments, ["controller.mustache"])


async def handle_codegen_render_dto(arguments: Dict[str, Any]) -> List[TextContent]:
    """Render the Java 21 record DTO exposed by the sb35-java21 template family."""
    context = _extract_context(arguments)
    if not isinstance(context, dict):
        return [TextContent(type="text", text=json.dumps({"error": "context missing or invalid"}))]

    if context.get("templateCategory") != "sb35-java21":
        return [
            TextContent(
                type="text",
                text=json.dumps(
                    {
                        "files": [],
                        "language": "java",
                        "note": "template_category does not provide a record DTO",
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
            )
        ]

    return await _render_single_layer(arguments, ["dto.mustache"])


async def handle_codegen_render_mapper(arguments: Dict[str, Any]) -> List[TextContent]:
    """根据模板分类选择渲染哪个 mapper 文件:
    - Default            → mapper.xml.mustache(MyBatis XML)
    - MybatisPlus-Mixed  → mapper.mustache
    - MybatisPlus(plain) → 不需要 XML mapper(BaseMapper 内置)
    - sb35-java21        → 不需要(用 JpaRepository)
    若启用 useMapStruct → 追加 mapstruct_mapper.mustache
    """
    context = _extract_context(arguments)
    if not isinstance(context, dict):
        return [TextContent(type="text", text=json.dumps({"error": "context missing or invalid"}))]

    category = context.get("templateCategory", "")
    templates: List[str] = []

    if category == "Default":
        templates.append("mapper.xml.mustache")
    elif category == "MybatisPlus-Mixed":
        templates.append("mapper.mustache")
    # MybatisPlus / sb35-java21 → 无 XML mapper

    if context.get("useMapStruct"):
        templates.append("mapstruct_mapper.mustache")

    if not templates:
        return [
            TextContent(
                type="text",
                text=json.dumps(
                    {
                        "files": [],
                        "language": "java",
                        "note": f"template_category={category} 不需要 mapper 层(BaseMapper/JpaRepository 内置)",
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
            )
        ]

    return await _render_single_layer(arguments, templates)


# ============================================================
# 内部辅助
# ============================================================


def _extract_context(arguments: Dict[str, Any]) -> Any:
    """从 MCP arguments 中提取 context dict。容忍两种形态:
    1. arguments["context"] 是 dict (MCP 标准 path)
    2. arguments["context"] 是 JSON 字符串 (LLM 序列化后传入)
    """
    ctx = arguments.get("context")
    if isinstance(ctx, str):
        try:
            ctx = json.loads(ctx)
        except json.JSONDecodeError:
            return None
    return ctx


async def _render_single_layer(
    arguments: Dict[str, Any], template_files: List[str]
) -> List[TextContent]:
    """渲染指定的模板文件列表,返回统一格式的 files"""
    context = _extract_context(arguments)
    if not isinstance(context, dict):
        return [
            TextContent(
                type="text",
                text=json.dumps({"error": "context missing or not a dict"}, ensure_ascii=False),
            )
        ]

    category = context.get("templateCategory") or "MybatisPlus-Mixed"

    from ..generator.template_context import TemplateConfigManager

    supported_categories = TemplateConfigManager.get_supported_categories()
    if category not in supported_categories:
        return [
            TextContent(
                type="text",
                text=json.dumps(
                    {
                        "error": "unsupported template category",
                        "template_category": category,
                        "supported_categories": supported_categories,
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
            )
        ]

    from ..generator.mustache_engine import MustacheTemplateEngine
    from pathlib import Path

    template_base = Path(__file__).parent.parent / "templates" / "java"
    path_mapping = TemplateConfigManager.get_output_path_mapping()
    engine = MustacheTemplateEngine()

    files: List[Dict[str, Any]] = []
    for tpl in template_files:
        # Prefer category-specific templates, then fall back to shared common templates.
        category_path = template_base / category / tpl
        common_path = template_base / tpl
        effective_category = category if category_path.exists() else "common"
        if effective_category == "common":
            template_path = common_path
        else:
            template_path = category_path

        if not template_path.exists():
            files.append(
                {
                    "template_file": tpl,
                    "error": f"template not found: {template_path}",
                }
            )
            continue

        try:
            code = engine.render_file(str(template_path), context)
            file_path = _compute_file_path(tpl, context, path_mapping)
            files.append(
                {
                    "template_file": tpl,
                    "file_path": file_path,
                    "code": code,
                    "lines": code.count("\n") + 1,
                }
            )
        except Exception as e:  # noqa: BLE001
            files.append(
                {
                    "template_file": tpl,
                    "error": f"render failed: {e}",
                }
            )

    # P3.3: 附加 code-diff MCP App meta (合并模板未渲染失败的项)
    from ..mcp_apps.code_diff import build_code_diff_data
    from ..mcp_apps.meta_builder import attach_meta, build_mcp_app_meta

    project_root = context.get("projectPath") or context.get("project_root")
    diff_data = build_code_diff_data(files, language="java", project_root=project_root)
    diff_meta = build_mcp_app_meta(
        "code-diff",
        language="java",
        files=diff_data["files"],
        version="1.0",
    )

    content = TextContent(
        type="text",
        text=json.dumps({"files": files, "language": "java"}, ensure_ascii=False, indent=2),
    )
    return [attach_meta(content, diff_meta)]


def _compute_file_path(
    template_file: str, context: Dict[str, Any], path_mapping: Dict[str, str]
) -> str:
    """根据模板和 context 计算输出路径(含包路径)。沿用 CodegenGenerator._get_output_filename 逻辑。"""
    relative = path_mapping.get(template_file)
    if not relative:
        return template_file.replace(".mustache", ".java")

    try:
        file_path = relative.format(**context)
    except KeyError:
        # context 缺字段时退化为基础路径
        file_path = relative.replace("{packageSuffix}", context.get("packageSuffix", "")).replace(
            "{className}", context.get("className", "Unknown")
        )

    package_name = context.get("package", "com.example")
    package_path = package_name.replace(".", "/")
    if file_path.endswith(".java"):
        return f"{package_path}/{file_path}"
    return f"resources/{file_path}"


def _collect_all_table_names(connection_id: str, config) -> List[str]:
    """收集库内所有表名(用于前缀分析)。失败时返回空列表。"""
    try:
        conn = connection_manager.get_connection(connection_id)
        cursor = conn.cursor()
        try:
            if config.type.name == "MYSQL":
                cursor.execute("SHOW TABLES")
                return [row[0] for row in cursor.fetchall()]
            if config.type.name == "SQLITE":
                cursor.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
                )
                return [row[0] for row in cursor.fetchall()]
            if config.type.name == "POSTGRESQL":
                cursor.execute(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_catalog = current_database() "
                    "AND table_type = 'BASE TABLE' "
                    "AND table_schema NOT IN ('pg_catalog', 'information_schema') "
                    "ORDER BY table_schema, table_name"
                )
                return [row[0] for row in cursor.fetchall()]
            return []
        finally:
            cursor.close()
    except Exception as e:  # noqa: BLE001
        logger.warning(f"_collect_all_table_names failed: {e}")
        return []


def _rebuild_package_paths(context: Dict[str, Any], package_name: str) -> None:
    """根据 package_name + 已有 packageSuffix 重建各层包名"""
    base_pkg = package_name or context.get("packageName") or context.get("package") or "com.example"
    suffix = context.get("packageSuffix") or ""

    def with_suffix(kind: str) -> str:
        return f"{base_pkg}.{kind}.{suffix}" if suffix else f"{base_pkg}.{kind}"

    context.update(
        {
            "package": base_pkg,
            "packageName": base_pkg,
            "basePackage": base_pkg,
            "controllerPackage": with_suffix("controller"),
            "servicePackage": with_suffix("service"),
            "entityPackage": with_suffix("entity"),
            "daoPackage": with_suffix("dao"),
            "dtoPackage": with_suffix("dto"),
            "voPackage": with_suffix("vo"),
            "serviceImplPackage": (
                f"{base_pkg}.service.impl.{suffix}" if suffix else f"{base_pkg}.service.impl"
            ),
        }
    )


def _normalize_tech_flags(context: Dict[str, Any]) -> None:
    """避免技术栈混用:SpringDoc 与 Swagger2 / Jakarta 与 Javax 二选一"""
    if context.get("hasSpringDoc"):
        context["hasSwagger2"] = False
    elif context.get("hasSwagger2"):
        context["hasSpringDoc"] = False

    if context.get("hasJakarta"):
        context["hasJavax"] = False
    elif context.get("hasJavax"):
        context["hasJakarta"] = False
