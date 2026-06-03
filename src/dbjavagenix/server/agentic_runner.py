"""
P8.4: Agentic runner mode using Claude Agent SDK.

启动模式对比:
- `mcp_server.py`: 经典 MCP server,被动等待客户端调用 tools
- `agentic_runner.py`: 主动 agent,内嵌 Claude Agent SDK,自己规划/调用/迭代

用途:
- 一次性批处理:"分析 host=X 的 schema,生成代码到 ./out" 单条命令完成全流程
- 离线/CI:无人值守生成 (需要 ANTHROPIC_API_KEY)
- 教学 demo:让面试官看到"同样的 tools 既能被 Claude Desktop 用,
  也能被独立 agent 用"

设计:
- 复用 mcp_tools 的所有工具定义 (zero duplication)
- Agent SDK 不可用 (没装 claude-agent-sdk 或没 ANTHROPIC_API_KEY) 时
  优雅退出并提示用户走 mcp_server 模式
- 不直接 import claude_agent_sdk - 用 lazy import,避免没装 SDK 的开发环境
  import 项目就报错
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


# ============================================================
# 可用性探测
# ============================================================

def is_agentic_available() -> tuple[bool, str]:
    """返回 (是否可用, 不可用原因)。

    可用条件:
    1. ANTHROPIC_API_KEY 环境变量存在
    2. claude_agent_sdk 包已安装
    """
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return False, "ANTHROPIC_API_KEY not set"
    try:
        import claude_agent_sdk  # noqa: F401
        return True, ""
    except ImportError:
        return False, "claude-agent-sdk not installed (pip install claude-agent-sdk)"


# ============================================================
# 配置 + 结果
# ============================================================

@dataclass
class AgenticConfig:
    """Agentic runner 启动参数"""
    goal: str  # 自然语言目标,例如 "分析 host=X 的 schema 并生成代码到 ./out"
    model: str = "claude-opus-4-7"
    max_iterations: int = 20
    allowed_tools: Optional[list[str]] = None  # None = 所有 tools
    dry_run: bool = False  # True 时不真正调 LLM,只打印 plan

    def __post_init__(self) -> None:
        if not self.goal or not isinstance(self.goal, str):
            raise ValueError("goal must be non-empty string")
        if self.max_iterations < 1 or self.max_iterations > 100:
            raise ValueError("max_iterations must be in [1, 100]")


@dataclass
class AgenticResult:
    """Agent 跑完后的总结"""
    success: bool
    iterations_used: int = 0
    final_message: str = ""
    tool_calls_made: int = 0
    error: Optional[str] = None


# ============================================================
# 主入口
# ============================================================

def run_agentic(
    config: AgenticConfig,
    tool_registry_factory: Callable[[], dict[str, Any]] | None = None,
) -> AgenticResult:
    """启动 agentic runner。

    Args:
        config: 启动配置
        tool_registry_factory: 返回 tool 注册表的工厂函数,默认用 dbjavagenix 自带
            的全套 tools。测试时可注入空 registry。

    Returns:
        AgenticResult: 跑完(成功 / 达到 max_iterations / 出错)的总结
    """
    available, reason = is_agentic_available()
    if not available:
        return AgenticResult(
            success=False,
            error=f"agentic mode unavailable: {reason}",
        )

    if config.dry_run:
        # dry_run 不调 SDK,只把 plan 打出来。便于 CI 验证配置正确性
        registry = tool_registry_factory() if tool_registry_factory else {}
        tool_count = len(config.allowed_tools or registry.keys())
        return AgenticResult(
            success=True,
            iterations_used=0,
            final_message=(
                f"[dry-run] goal={config.goal!r} model={config.model} "
                f"max_iter={config.max_iterations} tools={tool_count}"
            ),
            tool_calls_made=0,
        )

    # 真实启动 — lazy import 避免没装 SDK 时 import 此模块直接炸
    try:
        from claude_agent_sdk import Agent  # type: ignore
    except ImportError as e:  # pragma: no cover - 被 is_agentic_available 拦住
        return AgenticResult(success=False, error=f"import failed: {e}")

    registry = tool_registry_factory() if tool_registry_factory else _default_tool_registry()
    try:
        agent = Agent(
            model=config.model,
            tools=_filter_tools(registry, config.allowed_tools),
            max_iterations=config.max_iterations,
        )
        result = agent.run(config.goal)
        return AgenticResult(
            success=True,
            iterations_used=getattr(result, "iterations", 0),
            final_message=getattr(result, "final_message", ""),
            tool_calls_made=getattr(result, "tool_calls", 0),
        )
    except Exception as e:  # noqa: BLE001
        logger.error("agentic run failed: %s", e)
        return AgenticResult(success=False, error=str(e))


# ============================================================
# 工具注册表 (default = 复用 mcp_tools)
# ============================================================

def _default_tool_registry() -> dict[str, Any]:
    """复用 mcp_server 的工具定义。lazy import 避免循环依赖"""
    try:
        from ..database import mcp_tools  # type: ignore
        registry: dict[str, Any] = {}
        for getter in (
            "get_connection_tools",
            "get_table_analysis_tools",
            "get_codegen_tools",
            "get_springboot_project_tools",
        ):
            fn = getattr(mcp_tools, getter, None)
            if fn is None:
                continue
            for tool in fn():
                name = getattr(tool, "name", None) or (
                    tool.get("name") if isinstance(tool, dict) else None
                )
                if name:
                    registry[name] = tool
        return registry
    except Exception as e:  # noqa: BLE001
        logger.warning("default tool registry build failed: %s", e)
        return {}


def _filter_tools(registry: dict[str, Any], allowed: Optional[list[str]]) -> dict[str, Any]:
    if not allowed:
        return registry
    return {k: v for k, v in registry.items() if k in allowed}
