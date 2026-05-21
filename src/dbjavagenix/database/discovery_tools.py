"""
P2.3: search_tools 工具 - 渐进式工具发现入口

LLM 在 progressive 模式下,通过此工具按需查询完整工具元数据。
返回的工具名,LLM 仍可直接 call_tool — server 端不限制 (progressive 仅影响 list_tools)。
"""

import json
from typing import Any, Dict, List

from mcp.types import TextContent, Tool

from ..utils.tool_registry import is_progressive_mode_enabled, search_tools_by_query


def get_discovery_tools() -> List[Tool]:
    return [
        Tool(
            name="search_tools",
            description=(
                "按关键词搜索可用 MCP 工具,用于渐进式发现 (Progressive Discovery)。"
                "当用户提到的操作不在当前可见工具列表中时,先用此工具搜索,再调用返回的工具。"
                "示例: query='render dao' → 返回 codegen_render_dao + 相关工具。"
                "传空 query 列出所有 always_visible 工具。"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "搜索关键词 (支持空格分隔多 token)",
                        "default": "",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "返回前 N 个结果",
                        "default": 10,
                        "minimum": 1,
                        "maximum": 30,
                    },
                },
                "required": [],
            },
        ),
    ]


async def handle_search_tools(arguments: Dict[str, Any]) -> List[TextContent]:
    query = arguments.get("query", "") or ""
    limit = int(arguments.get("limit", 10))
    limit = max(1, min(30, limit))

    results = search_tools_by_query(query, limit=limit)

    payload: Dict[str, Any] = {
        "query": query,
        "progressive_mode": is_progressive_mode_enabled(),
        "results": results,
        "result_count": len(results),
    }
    if not results:
        payload["hint"] = (
            "无匹配工具。提示: 试试更宽泛的关键词,如 'connect' / 'table' / 'codegen' / 'spring'。"
        )

    return [TextContent(type="text", text=json.dumps(payload, ensure_ascii=False, indent=2))]
