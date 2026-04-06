"""[#9] TREVLIX – Dashboard & Seiten Blueprint.

Enthält alle Web-Seiten-Routes (nicht API, nicht Auth) als Flask Blueprint.
Wird von server.py über ``create_dashboard_blueprint()`` eingebunden.

Verwendung:
    from routes.dashboard import create_dashboard_blueprint
    bp = create_dashboard_blueprint(template_dir, require_auth_fn)
    app.register_blueprint(bp)
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from flask import Blueprint, send_from_directory

log = logging.getLogger("NEXUS.dashboard")


def create_dashboard_blueprint(
    template_dir: str,
    require_auth_fn: Callable,
) -> Blueprint:
    """Erstellt den Dashboard-Blueprint für statische Web-Seiten.

    Args:
        template_dir: Absoluter Pfad zum Templates-Verzeichnis.
        require_auth_fn: Decorator-Funktion für Login-Anforderung.

    Returns:
        Konfigurierter Flask Blueprint für Dashboard-Routes.
    """
    bp = Blueprint("dashboard", __name__)

    @bp.route("/dashboard")
    @require_auth_fn
    def dashboard():
        """Login-geschützte Dashboard-Seite."""
        return send_from_directory(template_dir, "dashboard.html")

    page_routes = {
        "/about": "about.html",
        "/api-docs": "api-docs.html",
        "/strategies": "strategies.html",
        "/faq": "faq.html",
        "/security": "security.html",
        "/changelog": "changelog.html",
        "/roadmap": "roadmap.html",
        "/installation": "INSTALLATION.html",
    }

    def _make_handler(filename: str):
        def _handler():
            return send_from_directory(template_dir, filename)

        _handler.__name__ = f"page_{filename.replace('.', '_').replace('-', '_')}"
        return _handler

    for route, filename in page_routes.items():
        bp.add_url_rule(route, view_func=_make_handler(filename))

    return bp
