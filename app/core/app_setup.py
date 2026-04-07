"""App-Setup-Orchestrierung für den server-Entrypoint."""

from __future__ import annotations

import logging
import os
from typing import Any

from app.core.bootstrap import (
    create_flask_app,
    create_limiter,
    create_socketio,
    init_cors,
    parse_origins_from_env,
    resolve_project_paths,
)
from app.core.logging_setup import configure_logging


def parse_session_timeout_minutes(default: int = 30) -> int:
    """Parse ``SESSION_TIMEOUT_MIN`` robust und mit Fallback."""
    min_minutes = 1
    max_minutes = 24 * 60
    try:
        fallback = int(default)
    except (TypeError, ValueError):
        fallback = 30
    fallback = min(max(fallback, min_minutes), max_minutes)
    try:
        parsed = int(os.getenv("SESSION_TIMEOUT_MIN", str(default)))
    except (TypeError, ValueError):
        return fallback

    # Defensive clamp: verhindert ungültige/gefährliche Werte wie 0 oder negativ
    # (sofortige Session-Invalidierung) und unendlich lange Session-Laufzeiten.
    if parsed < min_minutes:
        return min_minutes
    if parsed > max_minutes:
        return max_minutes
    return parsed


def initialize_runtime_objects(
    base_file: str,
    *,
    limiter_available: bool,
    limiter_cls: Any,
    key_func: Any,
) -> tuple[str, Any, Any, Any, logging.Logger, int]:
    """Erzeugt App, SocketIO, Limiter und Logger für den Einstiegspunkt."""
    base_dir, template_dir, static_dir = resolve_project_paths(base_file)
    app = create_flask_app(template_dir=template_dir, static_dir=static_dir)

    allowed_origins, flask_cors_origins = parse_origins_from_env()
    init_cors(app, flask_cors_origins=flask_cors_origins)
    socketio = create_socketio(app, allowed_origins=allowed_origins)

    limiter = create_limiter(
        app=app,
        limiter_available=limiter_available,
        limiter_cls=limiter_cls,
        key_func=key_func,
    )

    log_level = getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO)
    use_json_logs = os.getenv("JSON_LOGS", "false").lower() in ("true", "1", "yes")
    use_color_logs = os.getenv("COLOR_LOGS", "true").lower() in ("true", "1", "yes")

    log = configure_logging(
        base_dir=base_dir,
        log_level=log_level,
        use_json_logs=use_json_logs,
        use_color_logs=use_color_logs,
        logger_name="TREVLIX",
    )

    session_timeout_min = parse_session_timeout_minutes()

    return base_dir, app, socketio, limiter, log, session_timeout_min
