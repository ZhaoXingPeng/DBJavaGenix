"""单元测试: utils.logging_config (P5.2)"""

import json
import logging
import os

from unittest.mock import patch

from dbjavagenix.utils.logging_config import (
    JsonFormatter,
    TraceContext,
    configure_logging,
    new_trace_id,
)


class TestJsonFormatter:
    def test_basic_record(self):
        f = JsonFormatter()
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="x.py",
            lineno=1,
            msg="hello %s",
            args=("world",),
            exc_info=None,
        )
        out = f.format(record)
        payload = json.loads(out)
        assert payload["level"] == "INFO"
        assert payload["logger"] == "test.logger"
        assert payload["msg"] == "hello world"
        assert "ts" in payload

    def test_trace_id_attached(self):
        f = JsonFormatter()
        record = logging.LogRecord(
            name="x", level=logging.INFO, pathname="x.py", lineno=1,
            msg="m", args=(), exc_info=None,
        )
        record.trace_id = "abc123"
        out = f.format(record)
        payload = json.loads(out)
        assert payload["trace_id"] == "abc123"

    def test_exception_included(self):
        f = JsonFormatter()
        try:
            raise ValueError("boom")
        except Exception:
            import sys
            record = logging.LogRecord(
                name="x", level=logging.ERROR, pathname="x.py", lineno=1,
                msg="err", args=(), exc_info=sys.exc_info(),
            )
        out = f.format(record)
        payload = json.loads(out)
        assert "exception" in payload
        assert "ValueError" in payload["exception"]

    def test_custom_extra_field(self):
        f = JsonFormatter()
        record = logging.LogRecord(
            name="x", level=logging.INFO, pathname="x.py", lineno=1,
            msg="m", args=(), exc_info=None,
        )
        record.tool_name = "search_tools"
        out = f.format(record)
        payload = json.loads(out)
        assert payload["tool_name"] == "search_tools"


class TestConfigureLogging:
    def setup_method(self):
        # 备份并清空 root handlers
        self._old_handlers = list(logging.getLogger().handlers)
        self._old_level = logging.getLogger().level

    def teardown_method(self):
        # 恢复
        root = logging.getLogger()
        for h in list(root.handlers):
            root.removeHandler(h)
        for h in self._old_handlers:
            root.addHandler(h)
        root.setLevel(self._old_level)

    def test_plain_format_by_default(self):
        with patch.dict(os.environ, {}, clear=True):
            configure_logging()
            root = logging.getLogger()
            assert len(root.handlers) == 1
            formatter = root.handlers[0].formatter
            # plain formatter 不是 JsonFormatter
            assert not isinstance(formatter, JsonFormatter)

    def test_json_format_from_env(self):
        with patch.dict(os.environ, {"DBJAVAGENIX_LOG_FORMAT": "json"}):
            configure_logging()
            root = logging.getLogger()
            assert isinstance(root.handlers[0].formatter, JsonFormatter)

    def test_explicit_param_overrides_env(self):
        with patch.dict(os.environ, {"DBJAVAGENIX_LOG_FORMAT": "plain"}):
            configure_logging(fmt="json")
            root = logging.getLogger()
            assert isinstance(root.handlers[0].formatter, JsonFormatter)

    def test_level_from_env(self):
        with patch.dict(os.environ, {"DBJAVAGENIX_LOG_LEVEL": "DEBUG"}):
            configure_logging()
            assert logging.getLogger().level == logging.DEBUG


class TestNewTraceId:
    def test_returns_8_chars(self):
        tid = new_trace_id()
        assert len(tid) == 8
        # hex 字符
        assert all(c in "0123456789abcdef" for c in tid)

    def test_unique(self):
        ids = {new_trace_id() for _ in range(100)}
        # 至少 95 个唯一 (碰撞极低概率)
        assert len(ids) >= 95


class TestTraceContext:
    def test_trace_id_in_log(self, caplog):
        base_logger = logging.getLogger("test.trace")
        ctx = TraceContext(base_logger, "trace-abc")

        with caplog.at_level(logging.INFO, logger="test.trace"):
            ctx.info("test message")

        assert any("test message" in r.message for r in caplog.records)
        # extra 字段附加
        assert any(getattr(r, "trace_id", None) == "trace-abc" for r in caplog.records)
