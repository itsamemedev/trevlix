"""JSON log formatter that integrates with the request-context module.

Standard ``logging.Formatter`` emits free-form strings which are fine for
local debugging but painful to ingest into log aggregators (Loki, ELK,
Datadog). This module provides a drop-in ``JsonFormatter`` that writes one
JSON object per record, enriched with:

- ``timestamp`` (ISO-8601 UTC)
- ``level``, ``logger``, ``message``
- ``request_id`` (from :mod:`services.request_context` when present)
- any LogRecord extras (``exc_info``, ``module``, ``lineno``)

Install it once during bootstrap::

    from services.structured_logger import install_json_logging
    install_json_logging(level=logging.INFO)

The formatter intentionally does NOT import third-party libs (no ``orjson``
or ``structlog``) – stdlib ``json`` is fast enough for the volume Trevlix
produces.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from services.request_context import get_request_id

_RESERVED_LOGRECORD_ATTRS = frozenset(
    {
        "args",
        "asctime",
        "created",
        "exc_info",
        "exc_text",
        "filename",
        "funcName",
        "levelname",
        "levelno",
        "lineno",
        "message",
        "module",
        "msecs",
        "msg",
        "name",
        "pathname",
        "process",
        "processName",
        "relativeCreated",
        "stack_info",
        "taskName",
        "thread",
        "threadName",
    }
)


class JsonFormatter(logging.Formatter):
    """Render each :class:`LogRecord` as a single-line JSON object."""

    def __init__(self, *, include_extras: bool = True) -> None:
        super().__init__()
        self._include_extras = bool(include_extras)

    def format(self, record: logging.LogRecord) -> str:  # noqa: D401 - Formatter contract
        payload: dict[str, Any] = {
            "timestamp": _iso_utc(record.created),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        request_id = get_request_id()
        if request_id:
            payload["request_id"] = request_id
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        if record.stack_info:
            payload["stack"] = self.formatStack(record.stack_info)

        if self._include_extras:
            for key, value in record.__dict__.items():
                if key in _RESERVED_LOGRECORD_ATTRS or key.startswith("_"):
                    continue
                if key == "request_id":
                    # Already handled above – avoid overwriting with placeholder.
                    continue
                payload[key] = _jsonable(value)

        return json.dumps(payload, default=_jsonable, ensure_ascii=False)


def install_json_logging(
    level: int = logging.INFO,
    *,
    logger: logging.Logger | None = None,
    replace_handlers: bool = True,
) -> logging.Handler:
    """Attach a ``JsonFormatter`` stream handler to ``logger`` (root by default).

    When ``replace_handlers=True`` existing handlers are removed first so that
    log lines are not duplicated in both text and JSON form. Returns the new
    handler so the caller can further customise it (e.g. attach filters).
    """
    target = logger or logging.getLogger()
    target.setLevel(level)
    if replace_handlers:
        for h in list(target.handlers):
            target.removeHandler(h)
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    target.addHandler(handler)
    return handler


def _iso_utc(epoch_seconds: float) -> str:
    gm = time.gmtime(epoch_seconds)
    msec = int((epoch_seconds - int(epoch_seconds)) * 1000)
    return time.strftime("%Y-%m-%dT%H:%M:%S", gm) + f".{msec:03d}Z"


def _jsonable(value: Any) -> Any:
    """Best-effort conversion of arbitrary values into JSON-friendly types."""
    if value is None or isinstance(value, str | int | float | bool):
        return value
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    return repr(value)
