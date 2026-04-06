"""Socket.IO error logging helpers."""

from __future__ import annotations


def log_socket_error(*, log, error: Exception) -> None:
    """Log socket default handler errors in unified format."""
    log.error("⚠️ SocketIO-Fehler: %s: %s", type(error).__name__, error)
