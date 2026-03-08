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
    static_dir: str,
    require_auth_fn: Callable,
) -> Blueprint:
    """Erstellt den Dashboard-Blueprint für statische Web-Seiten.

    Args:
        template_dir: Absoluter Pfad zum Templates-Verzeichnis.
        static_dir: Absoluter Pfad zum Static-Files-Verzeichnis.
        require_auth_fn: Decorator-Funktion für Login-Anforderung.

    Returns:
        Konfigurierter Flask Blueprint für Dashboard-Routes.
    """
    bp = Blueprint("dashboard", __name__)

    @bp.route("/about")
    def about():
        """About-Seite der TREVLIX-Anwendung.

        Returns:
            about.html Template als Response.
        """
        return send_from_directory(template_dir, "about.html")

    @bp.route("/api-docs")
    def api_docs():
        """API-Dokumentationsseite.

        Returns:
            api-docs.html Template als Response.
        """
        return send_from_directory(template_dir, "api-docs.html")

    @bp.route("/strategies")
    def strategies():
        """Strategien-Übersichtsseite.

        Returns:
            strategies.html Template als Response.
        """
        return send_from_directory(template_dir, "strategies.html")

    @bp.route("/faq")
    def faq():
        """FAQ-Seite.

        Returns:
            faq.html Template als Response.
        """
        return send_from_directory(template_dir, "faq.html")

    @bp.route("/security")
    def security():
        """Sicherheits-Informationsseite.

        Returns:
            security.html Template als Response.
        """
        return send_from_directory(template_dir, "security.html")

    @bp.route("/changelog")
    def changelog():
        """Changelog-Seite mit Versionsverlauf.

        Returns:
            changelog.html Template als Response.
        """
        return send_from_directory(template_dir, "changelog.html")

    @bp.route("/roadmap")
    def roadmap():
        """Roadmap-Seite mit geplanten Features.

        Returns:
            roadmap.html Template als Response.
        """
        return send_from_directory(template_dir, "roadmap.html")

    @bp.route("/installation")
    def installation():
        """Installationsanleitung.

        Returns:
            INSTALLATION.html Template als Response.
        """
        return send_from_directory(template_dir, "INSTALLATION.html")

    return bp
