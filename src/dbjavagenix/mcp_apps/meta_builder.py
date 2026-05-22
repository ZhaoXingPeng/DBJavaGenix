"""
MCP App meta 构建工具。

MCP Apps 规范约定:
  - `mcp-apps/component`: UI 组件类型 (mermaid / dashboard / code-diff / tree)
  - `mcp-apps/<其他字段>`: 组件专属数据
  - 客户端通过读取 _meta 字段渲染 UI;不支持的客户端忽略

实现说明:
  - mcp.types.TextContent 模型有 `meta: dict[str, Any] | None` 字段
  - 序列化为 JSON 时会变成 `_meta` (Pydantic alias)
  - 通过 .model_copy(update={"meta": {...}}) 或直接赋值附加
"""

from typing import Any, Dict, List, Optional

from mcp.types import TextContent


def build_mcp_app_meta(
    component: str, **kwargs: Any
) -> Dict[str, Any]:
    """构建 mcp-apps namespace 下的 _meta dict。

    Args:
        component: 组件类型 (mermaid / dashboard / code-diff / tree)
        **kwargs: 任意组件专属字段, key 会自动加 'mcp-apps/' 前缀

    Returns:
        形如 {'mcp-apps/component': 'mermaid', 'mcp-apps/source': '...'} 的 dict

    Example:
        meta = build_mcp_app_meta('mermaid', source='erDiagram\\n  ...', version='1.0')
        # → {'mcp-apps/component': 'mermaid', 'mcp-apps/source': '...', 'mcp-apps/version': '1.0'}
    """
    result: Dict[str, Any] = {"mcp-apps/component": component}
    for key, value in kwargs.items():
        if value is None:
            continue
        ns_key = key if key.startswith("mcp-apps/") else f"mcp-apps/{key}"
        result[ns_key] = value
    return result


def attach_meta(
    content: TextContent, meta: Dict[str, Any]
) -> TextContent:
    """把 meta dict 附加到 TextContent 上,返回更新后的对象。

    使用 model_copy 而非直接赋值,保持不可变语义。
    若 content 已有 meta,会被新 meta 完全替换 (不做合并)。
    """
    return content.model_copy(update={"meta": meta})


def merge_meta(
    existing: Optional[Dict[str, Any]], new_fields: Dict[str, Any]
) -> Dict[str, Any]:
    """合并两份 meta dict,后者覆盖前者"""
    if existing is None:
        return dict(new_fields)
    return {**existing, **new_fields}


def with_meta_list(
    contents: List[TextContent], meta: Dict[str, Any]
) -> List[TextContent]:
    """把 meta 附加到 contents 列表的第一个 TextContent 上 (MCP App 渲染惯例)"""
    if not contents:
        return contents
    head = attach_meta(contents[0], merge_meta(contents[0].meta, meta))
    return [head, *contents[1:]]
