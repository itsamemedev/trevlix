"""Tests für services.structured_logger."""

from __future__ import annotations

import json
import logging

from services.request_context import set_request_id
from services.structured_logger import JsonFormatter, install_json_logging


def _make_record(msg: str = "hello", **extra) -> logging.LogRecord:
    record = logging.LogRecord(
        name="t",
        level=logging.INFO,
        pathname="p",
        lineno=1,
        msg=msg,
        args=(),
        exc_info=None,
    )
    for k, v in extra.items():
        setattr(record, k, v)
    return record


class TestJsonFormatter:
    def test_basic_fields(self):
        fmt = JsonFormatter()
        out = json.loads(fmt.format(_make_record("hi")))
        assert out["level"] == "INFO"
        assert out["logger"] == "t"
        assert out["message"] == "hi"
        assert "timestamp" in out
        assert out["timestamp"].endswith("Z")

    def test_includes_request_id_when_set(self):
        set_request_id("abc-42")
        try:
            fmt = JsonFormatter()
            out = json.loads(fmt.format(_make_record()))
            assert out["request_id"] == "abc-42"
        finally:
            set_request_id(None)

    def test_omits_request_id_when_unset(self):
        set_request_id(None)
        fmt = JsonFormatter()
        out = json.loads(fmt.format(_make_record()))
        assert "request_id" not in out

    def test_includes_extra_fields(self):
        fmt = JsonFormatter()
        record = _make_record(symbol="BTC/USDT", qty=0.5)
        out = json.loads(fmt.format(record))
        assert out["symbol"] == "BTC/USDT"
        assert out["qty"] == 0.5

    def test_non_jsonable_extra_is_repr(self):
        class Weird:
            def __repr__(self) -> str:
                return "<weird>"

        fmt = JsonFormatter()
        record = _make_record(blob=Weird())
        out = json.loads(fmt.format(record))
        assert out["blob"] == "<weird>"

    def test_exception_included(self):
        fmt = JsonFormatter()
        try:
            raise RuntimeError("boom")
        except RuntimeError:
            import sys

            exc_info = sys.exc_info()
        record = logging.LogRecord(
            name="t",
            level=logging.ERROR,
            pathname="p",
            lineno=1,
            msg="err",
            args=(),
            exc_info=exc_info,
        )
        out = json.loads(fmt.format(record))
        assert "exception" in out
        assert "RuntimeError" in out["exception"]

    def test_include_extras_flag_disables(self):
        fmt = JsonFormatter(include_extras=False)
        record = _make_record(symbol="X")
        out = json.loads(fmt.format(record))
        assert "symbol" not in out

    def test_single_line_output(self):
        fmt = JsonFormatter()
        out = fmt.format(_make_record("multi\nline"))
        assert out.count("\n") == 0


class TestInstall:
    def test_install_adds_handler(self):
        logger = logging.getLogger("test_json_install")
        h = install_json_logging(logger=logger, level=logging.DEBUG)
        try:
            assert h in logger.handlers
            assert logger.level == logging.DEBUG
            assert isinstance(h.formatter, JsonFormatter)
        finally:
            logger.removeHandler(h)

    def test_install_replaces_existing(self):
        logger = logging.getLogger("test_json_replace")
        old = logging.StreamHandler()
        logger.addHandler(old)
        new = install_json_logging(logger=logger, replace_handlers=True)
        try:
            assert old not in logger.handlers
            assert new in logger.handlers
        finally:
            logger.removeHandler(new)
