"""Bootstrap-Helfer für App-, CORS-, SocketIO- und Limiter-Initialisierung.

Dieses Modul hält den Setup-Code klein und wiederverwendbar, sodass `server.py`
primär Orchestrierung übernimmt.
"""

from __future__ import annotations

import os
import secrets
from typing import Any

from flask import Flask
from flask_cors import CORS
from flask_socketio import SocketIO


class DummyLimiter:
    """No-op Limiter als Fallback wenn flask-limiter fehlt."""

    def limit(self, *args, **kwargs):
        return lambda func: func

    def shared_limit(self, *args, **kwargs):
        return lambda func: func


def resolve_project_paths(base_file: str) -> tuple[str, str, str]:
    """Liefert Basis-, Template- und Static-Pfad relativ zur server.py."""
    base_dir = os.path.dirname(os.path.abspath(base_file))
    template_dir = os.path.join(base_dir, "templates")
    static_dir = os.path.join(base_dir, "static")
    return base_dir, template_dir, static_dir


def create_flask_app(template_dir: str, static_dir: str) -> Flask:
    """Erzeugt und konfiguriert die Flask-App mit sicheren Session-Cookies."""
    app = Flask(
        __name__,
        static_folder=static_dir,
        static_url_path="/static",
        template_folder=template_dir,
    )
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", secrets.token_hex(32))
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    _env = (os.getenv("TREVLIX_ENV") or os.getenv("FLASK_ENV") or "").lower()
    if os.getenv("ALLOWED_ORIGINS", "").startswith("https") or _env == "production":
        app.config["SESSION_COOKIE_SECURE"] = True
    return app


def parse_origins_from_env() -> tuple[Any, Any]:
    """Parst ALLOWED_ORIGINS und ergänzt APP_DOMAIN falls gesetzt."""
    raw_origins = os.getenv("ALLOWED_ORIGINS", "*")
    if raw_origins.strip() == "*":
        return "*", "*"

    allowed_origins = [origin.strip() for origin in raw_origins.split(",") if origin.strip()]
    app_domain = os.getenv("APP_DOMAIN", "")
    if app_domain:
        for scheme in ("https://", "http://"):
            origin = f"{scheme}{app_domain}"
            if origin not in allowed_origins:
                allowed_origins.append(origin)

    return allowed_origins, allowed_origins


def init_cors(app: Flask, flask_cors_origins: Any) -> None:
    """Initialisiert Flask-CORS."""
    CORS(
        app,
        origins=flask_cors_origins,
        supports_credentials=(flask_cors_origins != "*"),
    )


def resolve_socketio_async_mode() -> str:
    """Ermittelt einen robusten Async-Modus für Flask-SocketIO.

    Priorität:
      1) `SOCKETIO_ASYNC_MODE` aus Environment (wenn gesetzt)
      2) eventlet (falls importierbar)
      3) gevent (falls importierbar)
      4) threading (Fallback)

    Hintergrund:
    Im reinen `threading`-Modus sind WebSocket-Verbindungen nicht verfügbar.
    Einige Clients versuchen dennoch den `websocket`-Transport zuerst, was mit
    Werkzeug in Fehlern enden kann. Mit eventlet/gevent wird echter WebSocket-
    Support aktiviert.
    """
    forced = os.getenv("SOCKETIO_ASYNC_MODE", "").strip().lower()
    if forced:
        return forced

    try:
        import eventlet  # noqa: F401

        return "eventlet"
    except Exception:  # noqa: BLE001
        pass

    try:
        import gevent  # noqa: F401

        return "gevent"
    except Exception:  # noqa: BLE001
        return "threading"


def create_socketio(app: Flask, allowed_origins: Any) -> SocketIO:
    """Erzeugt die SocketIO-Instanz mit stabilen Standardwerten."""
    async_mode = resolve_socketio_async_mode()
    return SocketIO(
        app,
        cors_allowed_origins=allowed_origins,
        async_mode=async_mode,
        logger=False,
        engineio_logger=False,
        ping_timeout=30,
        ping_interval=25,
        max_http_buffer_size=1_000_000,
        manage_session=True,
    )


def create_limiter(app: Flask, limiter_available: bool, limiter_cls: Any, key_func: Any) -> Any:
    """Erzeugt echten Limiter oder Dummy-Fallback."""
    if not limiter_available:
        return DummyLimiter()

    return limiter_cls(
        key_func=key_func,
        app=app,
        default_limits=["200 per minute"],
        storage_uri="memory://",
    )
