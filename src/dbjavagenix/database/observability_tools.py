"""
P5: 可观测性工具 - server_metrics + server_health。
"""

import json
import os
import platform
import sys
import time
from typing import Any, Dict, List

from mcp.types import TextContent, Tool

from ..utils.metrics import GLOBAL_TOOL_METRICS


def get_observability_tools() -> List[Tool]:
    return [
        Tool(
            name="server_metrics",
            description=(
                "返回 DBJavaGenix MCP server 的运行时指标: uptime、每个工具的"
                "调用次数 / 平均时延 / 错误率。轻量级 in-process,不依赖 Prometheus。"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "reset": {
                        "type": "boolean",
                        "description": "查询后重置计数器 (默认 false)",
                        "default": False,
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="server_health",
            description=(
                "返回 server 健康状态: Python 版本、mcp SDK 版本、"
                "核心模块导入是否成功、DB 连接活跃数、OS 信息。用于部署后冒烟检查。"
            ),
            inputSchema={
                "type": "object",
                "properties": {},
                "required": [],
            },
        ),
    ]


async def handle_server_metrics(arguments: Dict[str, Any]) -> List[TextContent]:
    """返回累积工具调用指标"""
    snapshot = GLOBAL_TOOL_METRICS.snapshot()
    payload = {
        "metrics": snapshot,
        "note": (
            "时延单位 ms。total_tool_calls 含 server_metrics 自身。"
            "reset=true 清零,uptime_seconds 重置为 0。"
        ),
    }
    if arguments.get("reset"):
        GLOBAL_TOOL_METRICS.reset()
        payload["reset"] = True
    return [TextContent(
        type="text",
        text=json.dumps(payload, ensure_ascii=False, indent=2),
    )]


async def handle_server_health(arguments: Dict[str, Any]) -> List[TextContent]:
    """返回 server 健康检查信息"""
    modules_ok: Dict[str, Any] = {}

    for mod_name in (
        "dbjavagenix.database.mcp_tools",
        "dbjavagenix.database.atomic_codegen_tools",
        "dbjavagenix.database.ai_tools",
        "dbjavagenix.database.visualization_tools",
        "dbjavagenix.database.discovery_tools",
        "dbjavagenix.mcp_apps",
        "dbjavagenix.generator.mustache_engine",
        "dbjavagenix.generator.template_context",
        "dbjavagenix.ai.naming_rules",
        "dbjavagenix.utils.tool_registry",
    ):
        try:
            __import__(mod_name)
            modules_ok[mod_name] = "ok"
        except Exception as e:  # noqa: BLE001
            modules_ok[mod_name] = f"FAIL: {e}"

    try:
        import mcp
        mcp_version = getattr(mcp, "__version__", "unknown")
    except Exception:  # noqa: BLE001
        mcp_version = "unknown"

    try:
        from ..database.connection_manager import connection_manager
        active_connections = len(connection_manager.list_connections())
    except Exception:  # noqa: BLE001
        active_connections = -1  # not initialized

    try:
        import anthropic
        anthropic_version = getattr(anthropic, "__version__", "installed")
    except ImportError:
        anthropic_version = "not_installed"

    health = {
        "status": "ok" if all(v == "ok" for v in modules_ok.values()) else "degraded",
        "uptime_seconds": round(GLOBAL_TOOL_METRICS.uptime_seconds, 2),
        "server": {
            "name": "dbjavagenix",
            "version": _read_version(),
            "start_epoch": round(time.time() - GLOBAL_TOOL_METRICS.uptime_seconds, 2),
        },
        "runtime": {
            "python_version": sys.version.split()[0],
            "platform": platform.platform(),
            "mcp_sdk_version": mcp_version,
            "anthropic_sdk_version": anthropic_version,
        },
        "modules": modules_ok,
        "database": {
            "active_connections": active_connections,
        },
        "ai": {
            "llm_available": bool(os.environ.get("ANTHROPIC_API_KEY")) and anthropic_version != "not_installed",
            "progressive_mode": os.environ.get("DBJAVAGENIX_PROGRESSIVE", "").lower() in ("1", "true", "yes", "on"),
        },
    }
    return [TextContent(
        type="text",
        text=json.dumps(health, ensure_ascii=False, indent=2),
    )]


def _read_version() -> str:
    """从 dbjavagenix.__init__ 读取版本"""
    try:
        import dbjavagenix
        return getattr(dbjavagenix, "__version__", "0.2.0")
    except Exception:  # noqa: BLE001
        return "0.2.0"
