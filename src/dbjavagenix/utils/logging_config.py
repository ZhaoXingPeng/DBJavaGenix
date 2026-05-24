"""
P5.2: 结构化日志支持。

通过 DBJAVAGENIX_LOG_FORMAT 环境变量切换:
  - 'plain' (默认): 人类可读 timestamp + level + module + message
  - 'json': JSON line 格式, 适合日志聚合系统 (Loki / ELK / Datadog)

MCP server 是 stdio 进程 — 所有日志必须走 stderr (stdout 是 JSON-RPC 通道)。
"""

import json
import logging
import os
import sys
import time
import uuid
from typing import Any, Optional


# ============================================================
# JSON formatter
# ============================================================

class JsonFormatter(logging.Formatter):
    """日志行序列化为单行 JSON, 自动附加 trace_id 和时间戳"""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(record.created))
                  + f".{int((record.created % 1) * 1000):03d}Z",
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        # 附加 trace_id 如果上下文有
        trace_id = getattr(record, "trace_id", None)
        if trace_id:
            payload["trace_id"] = trace_id

        # 附加 exception
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        # 附加任何 LogRecord 额外属性 (LogAdapter.extra)
        for key, value in record.__dict__.items():
            if key in ("name", "msg", "args", "levelname", "levelno", "pathname",
                       "filename", "module", "exc_info", "exc_text", "stack_info",
                       "lineno", "funcName", "created", "msecs", "relativeCreated",
                       "thread", "threadName", "processName", "process",
                       "trace_id"):
                continue
            if not key.startswith("_") and isinstance(value, (str, int, float, bool, type(None))):
                payload[key] = value

        return json.dumps(payload, ensure_ascii=False)


# ============================================================
# 配置入口
# ============================================================

def configure_logging(
    level: Optional[str] = None, fmt: Optional[str] = None
) -> None:
    """根据环境变量配置日志。

    Args:
        level: 日志级别, 默认 INFO; 可被 DBJAVAGENIX_LOG_LEVEL 覆盖
        fmt: 'plain' / 'json'; 可被 DBJAVAGENIX_LOG_FORMAT 覆盖

    All output goes to stderr (stdout reserved for JSON-RPC).
    """
    level = level or os.environ.get("DBJAVAGENIX_LOG_LEVEL", "INFO")
    fmt = fmt or os.environ.get("DBJAVAGENIX_LOG_FORMAT", "plain")

    root = logging.getLogger()
    # 移除任何已有 handler 避免重复
    for h in list(root.handlers):
        root.removeHandler(h)

    handler = logging.StreamHandler(stream=sys.stderr)

    if fmt == "json":
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        ))

    root.addHandler(handler)
    root.setLevel(getattr(logging, level.upper(), logging.INFO))


# ============================================================
# trace_id 上下文
# ============================================================

def new_trace_id() -> str:
    """生成 8 字符短 UUID 作 trace_id"""
    return uuid.uuid4().hex[:8]


class TraceContext:
    """以 LogAdapter 形式给 logger 加 trace_id"""

    def __init__(self, logger: logging.Logger, trace_id: str) -> None:
        self.logger = logger
        self.trace_id = trace_id

    def __getattr__(self, name: str) -> Any:
        # 转发 logger 方法
        target = getattr(self.logger, name)
        if not callable(target):
            return target

        def wrapped(msg: str, *args: Any, **kwargs: Any) -> Any:
            extra = kwargs.pop("extra", {})
            extra.setdefault("trace_id", self.trace_id)
            return target(msg, *args, extra=extra, **kwargs)

        return wrapped
