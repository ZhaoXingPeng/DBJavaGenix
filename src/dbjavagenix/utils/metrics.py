"""
P5.1: 轻量级工具调用 metrics。

实现:
  - ToolCallMetrics: 每个工具记录 (calls, errors, total_duration_ms, last_call_at)
  - @track_tool_call 装饰器: wrap async handler 自动累加
  - GLOBAL_TOOL_METRICS: 进程级单例

设计取舍:
  - 不引入 prometheus_client (重) — MCP stdio 进程没有 HTTP endpoint 暴露
  - 内置 ai_metrics / server_metrics 工具是查询入口
  - 时延用毫秒 (避免浮点累加误差)
  - 错误不阻塞: handler 抛异常时记录后向上抛
"""

import asyncio
import time
from collections import defaultdict
from dataclasses import dataclass, field
from functools import wraps
from typing import Any, Awaitable, Callable, Dict, List


@dataclass
class ToolStats:
    """单个工具的累积统计"""
    name: str
    calls: int = 0
    errors: int = 0
    total_duration_ms: float = 0.0
    last_duration_ms: float = 0.0
    last_call_at_epoch: float = 0.0
    min_duration_ms: float = float("inf")
    max_duration_ms: float = 0.0

    def record(self, duration_ms: float, is_error: bool) -> None:
        self.calls += 1
        if is_error:
            self.errors += 1
        self.total_duration_ms += duration_ms
        self.last_duration_ms = duration_ms
        self.last_call_at_epoch = time.time()
        self.min_duration_ms = min(self.min_duration_ms, duration_ms)
        self.max_duration_ms = max(self.max_duration_ms, duration_ms)

    @property
    def avg_duration_ms(self) -> float:
        return self.total_duration_ms / self.calls if self.calls else 0.0

    @property
    def error_rate(self) -> float:
        return self.errors / self.calls if self.calls else 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "calls": self.calls,
            "errors": self.errors,
            "error_rate": round(self.error_rate, 4),
            "avg_duration_ms": round(self.avg_duration_ms, 2),
            "last_duration_ms": round(self.last_duration_ms, 2),
            "min_duration_ms": round(self.min_duration_ms, 2) if self.calls else 0.0,
            "max_duration_ms": round(self.max_duration_ms, 2),
            "last_call_at_epoch": round(self.last_call_at_epoch, 2),
        }


class ToolCallMetrics:
    """进程级工具调用累计器"""

    def __init__(self) -> None:
        self._stats: Dict[str, ToolStats] = defaultdict(lambda: ToolStats(name=""))
        self._start_epoch = time.time()

    def record(self, tool_name: str, duration_ms: float, is_error: bool) -> None:
        if tool_name not in self._stats:
            self._stats[tool_name] = ToolStats(name=tool_name)
        self._stats[tool_name].record(duration_ms, is_error)

    def get_stats(self, tool_name: str) -> ToolStats:
        return self._stats.get(tool_name, ToolStats(name=tool_name))

    def all_stats(self) -> List[ToolStats]:
        return list(self._stats.values())

    @property
    def uptime_seconds(self) -> float:
        return time.time() - self._start_epoch

    def snapshot(self) -> Dict[str, Any]:
        all_stats = self.all_stats()
        total_calls = sum(s.calls for s in all_stats)
        total_errors = sum(s.errors for s in all_stats)
        return {
            "uptime_seconds": round(self.uptime_seconds, 2),
            "total_tool_calls": total_calls,
            "total_errors": total_errors,
            "overall_error_rate": round(total_errors / total_calls, 4) if total_calls else 0.0,
            "tools": [s.to_dict() for s in sorted(all_stats, key=lambda x: -x.calls)],
        }

    def reset(self) -> None:
        self._stats.clear()
        self._start_epoch = time.time()


# 进程级单例
GLOBAL_TOOL_METRICS = ToolCallMetrics()


# ============================================================
# 装饰器
# ============================================================

def track_tool_call(
    tool_name: str,
) -> Callable[[Callable[..., Awaitable[Any]]], Callable[..., Awaitable[Any]]]:
    """async handler 装饰器: 自动记录调用次数 + 时延 + 错误"""

    def decorator(
        fn: Callable[..., Awaitable[Any]]
    ) -> Callable[..., Awaitable[Any]]:
        @wraps(fn)
        async def wrapped(*args: Any, **kwargs: Any) -> Any:
            start = time.perf_counter()
            is_error = False
            try:
                return await fn(*args, **kwargs)
            except Exception:
                is_error = True
                raise
            finally:
                duration_ms = (time.perf_counter() - start) * 1000
                GLOBAL_TOOL_METRICS.record(tool_name, duration_ms, is_error)

        return wrapped

    return decorator


async def track_call_async(
    tool_name: str, coro: Awaitable[Any]
) -> Any:
    """直接 wrap 一个 await 表达式 (运行时使用,不能用 @decorator 时备选)"""
    start = time.perf_counter()
    is_error = False
    try:
        return await coro
    except Exception:
        is_error = True
        raise
    finally:
        duration_ms = (time.perf_counter() - start) * 1000
        GLOBAL_TOOL_METRICS.record(tool_name, duration_ms, is_error)
