"""Request-ID / correlation-ID context helper.

Tags every request (HTTP or WebSocket) with a short correlation ID and makes
it available to logs via a :class:`logging.Filter`. No hard dependency on
Flask – the context store is a thread-local so it also works from the bot
loop or background tasks.

Typical wiring::

    from services.request_context import (
        install_flask_request_id,
        install_log_filter,
    )

    install_log_filter(logging.getLogger())
    install_flask_request_id(app)
"""

from __future__ import annotations

import logging
import secrets
import threading

_local = threading.local()

REQUEST_ID_HEADER = "X-Request-ID"
_ID_BYTES = 6


def new_request_id() -> str:
    """Return a short, collision-resistant hex request ID."""
    return secrets.token_hex(_ID_BYTES)


def set_request_id(request_id: str | None) -> None:
    """Bind a request ID to the current thread (None clears it)."""
    if request_id is None:
        if hasattr(_local, "request_id"):
            del _local.request_id
        return
    _local.request_id = str(request_id)[:64]


def get_request_id() -> str | None:
    """Return the request ID for the current thread, if any."""
    return getattr(_local, "request_id", None)


class RequestIdLogFilter(logging.Filter):
    """Attach the active request ID to each log record as ``record.request_id``."""

    def filter(self, record: logging.LogRecord) -> bool:  # noqa: D401 - Filter contract
        record.request_id = get_request_id() or "-"
        return True


def install_log_filter(logger: logging.Logger | None = None) -> RequestIdLogFilter:
    """Install :class:`RequestIdLogFilter` on the given logger (root by default)."""
    target = logger or logging.getLogger()
    filt = RequestIdLogFilter()
    target.addFilter(filt)
    for handler in target.handlers:
        handler.addFilter(filt)
    return filt


def install_flask_request_id(app) -> None:  # type: ignore[no-untyped-def]
    """Install before/after request hooks that manage the request ID.

    The hook reads an incoming ``X-Request-ID`` header if present, falls back
    to a freshly generated ID, and echoes it back to the client so downstream
    clients can correlate their logs with ours.
    """
    try:
        from flask import g, request
    except ImportError:  # pragma: no cover - Flask is a hard dep in prod
        return

    @app.before_request
    def _assign_request_id() -> None:  # noqa: ANN202
        incoming = request.headers.get(REQUEST_ID_HEADER)
        rid = _sanitize(incoming) if incoming else new_request_id()
        set_request_id(rid)
        g.request_id = rid

    @app.after_request
    def _echo_request_id(response):  # type: ignore[no-untyped-def]
        rid = getattr(g, "request_id", None) or get_request_id()
        if rid:
            response.headers[REQUEST_ID_HEADER] = rid
        set_request_id(None)
        return response

    @app.teardown_request
    def _clear_request_id(_exc) -> None:  # noqa: ANN202
        set_request_id(None)


def _sanitize(value: str) -> str:
    cleaned = "".join(ch for ch in value if ch.isalnum() or ch in "-_")
    return cleaned[:64] or new_request_id()
