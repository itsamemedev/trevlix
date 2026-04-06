"""Socket.IO emit helpers for background-safe event publishing."""

from __future__ import annotations

from typing import Any


def emit_socket_event(*, socketio, log, event: str, data: Any, to: str | None = None) -> None:
    """Emit a socket event and log failures as debug only."""
    try:
        socketio.emit(event, data, to=to, namespace="/")
    except Exception as exc:  # pragma: no cover - defensive logging
        log.debug("emit_event(%s) fehlgeschlagen: %s", event, exc)
