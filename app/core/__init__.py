"""Core bootstrap, logging and runtime helpers for TREVLIX."""

from .bootstrap import (
    create_flask_app,
    create_limiter,
    create_socketio,
    init_cors,
    parse_origins_from_env,
    resolve_project_paths,
)
from .http_routes import register_default_blueprints, register_system_routes
from .lifecycle import build_graceful_shutdown_handler, register_signal_handlers
from .logging_setup import configure_logging
from .runtime import run_server

__all__ = [
    "create_flask_app",
    "create_limiter",
    "create_socketio",
    "init_cors",
    "parse_origins_from_env",
    "resolve_project_paths",
    "configure_logging",
    "run_server",
    "register_system_routes",
    "register_default_blueprints",
    "build_graceful_shutdown_handler",
    "register_signal_handlers",
]
