"""Tests für services.request_context."""

from __future__ import annotations

import logging
import threading

from services.request_context import (
    REQUEST_ID_HEADER,
    RequestIdLogFilter,
    get_request_id,
    install_log_filter,
    new_request_id,
    set_request_id,
)


class TestRequestId:
    def test_new_request_id_is_hex(self):
        rid = new_request_id()
        assert isinstance(rid, str)
        assert len(rid) == 12  # 6 bytes hex
        int(rid, 16)  # must be valid hex

    def test_set_and_get(self):
        set_request_id("abc123")
        assert get_request_id() == "abc123"
        set_request_id(None)
        assert get_request_id() is None

    def test_clears_properly(self):
        set_request_id("x")
        set_request_id(None)
        assert get_request_id() is None

    def test_thread_isolation(self):
        set_request_id("main-thread-id")
        results: dict[str, str | None] = {}

        def worker() -> None:
            results["seen"] = get_request_id()
            set_request_id("worker-id")
            results["after_set"] = get_request_id()

        t = threading.Thread(target=worker)
        t.start()
        t.join()
        assert results["seen"] is None  # thread-local, no bleed
        assert results["after_set"] == "worker-id"
        assert get_request_id() == "main-thread-id"
        set_request_id(None)

    def test_long_ids_are_truncated(self):
        set_request_id("x" * 200)
        assert len(get_request_id() or "") == 64
        set_request_id(None)


class TestLogFilter:
    def test_filter_attaches_request_id(self):
        set_request_id("req-42")
        filt = RequestIdLogFilter()
        record = logging.LogRecord(
            name="t",
            level=logging.INFO,
            pathname="p",
            lineno=1,
            msg="msg",
            args=(),
            exc_info=None,
        )
        assert filt.filter(record) is True
        assert record.request_id == "req-42"
        set_request_id(None)

    def test_filter_defaults_to_dash(self):
        set_request_id(None)
        filt = RequestIdLogFilter()
        record = logging.LogRecord(
            name="t",
            level=logging.INFO,
            pathname="p",
            lineno=1,
            msg="msg",
            args=(),
            exc_info=None,
        )
        filt.filter(record)
        assert record.request_id == "-"

    def test_install_log_filter(self):
        logger = logging.getLogger("test_rid_install")
        filt = install_log_filter(logger)
        assert filt in logger.filters
        logger.removeFilter(filt)


class TestFlaskIntegration:
    def test_install_flask_hooks(self):
        try:
            from flask import Flask
        except ImportError:
            return

        from services.request_context import install_flask_request_id

        app = Flask(__name__)
        install_flask_request_id(app)

        @app.route("/ping")
        def ping():
            from flask import g

            return g.request_id

        client = app.test_client()
        resp = client.get("/ping")
        assert resp.status_code == 200
        assert REQUEST_ID_HEADER in resp.headers
        assert resp.headers[REQUEST_ID_HEADER] == resp.get_data(as_text=True)

    def test_echoes_incoming_header(self):
        try:
            from flask import Flask
        except ImportError:
            return

        from services.request_context import install_flask_request_id

        app = Flask(__name__)
        install_flask_request_id(app)

        @app.route("/ping")
        def ping():
            return "ok"

        client = app.test_client()
        resp = client.get("/ping", headers={REQUEST_ID_HEADER: "custom-abc-123"})
        assert resp.headers[REQUEST_ID_HEADER] == "custom-abc-123"

    def test_sanitizes_dirty_header(self):
        try:
            from flask import Flask
        except ImportError:
            return

        from services.request_context import install_flask_request_id

        app = Flask(__name__)
        install_flask_request_id(app)

        @app.route("/ping")
        def ping():
            return "ok"

        client = app.test_client()
        resp = client.get("/ping", headers={REQUEST_ID_HEADER: "bad id; DROP TABLE users"})
        rid = resp.headers[REQUEST_ID_HEADER]
        assert all(ch.isalnum() or ch in "-_" for ch in rid)
