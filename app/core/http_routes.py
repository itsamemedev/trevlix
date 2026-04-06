"""Registration helpers for system routes, error handlers and blueprints."""

from __future__ import annotations

import os

from flask import jsonify, redirect, request, send_from_directory


def register_system_routes(app, *, base_dir: str, static_dir: str, template_dir: str, log) -> None:
    """Registriert statische Systemrouten und globale Error-Handler."""

    @app.route("/favicon.ico")
    def favicon():
        favicon_path = os.path.join(static_dir, "favicon.ico")
        if os.path.isfile(favicon_path):
            return send_from_directory(static_dir, "favicon.ico", mimetype="image/x-icon")
        return "", 204

    @app.route("/robots.txt")
    def robots_txt():
        return send_from_directory(base_dir, "robots.txt", mimetype="text/plain")

    @app.route("/sitemap.xml")
    def sitemap_xml():
        sitemap_path = os.path.join(base_dir, "sitemap.xml")
        if os.path.isfile(sitemap_path):
            return send_from_directory(base_dir, "sitemap.xml", mimetype="application/xml")
        return "", 404

    @app.route("/static/icon-192.png")
    def icon_192():
        icon_path = os.path.join(static_dir, "icon-192.png")
        if os.path.isfile(icon_path):
            return send_from_directory(static_dir, "icon-192.png", mimetype="image/png")
        return "", 204

    @app.route("/404")
    def page_not_found():
        return send_from_directory(template_dir, "404.html"), 404

    @app.errorhandler(404)
    def handle_404(_e):
        if request.path.startswith("/api/"):
            return jsonify({"error": "Endpunkt nicht gefunden", "path": request.path}), 404
        if request.path == "/404":
            return send_from_directory(template_dir, "404.html"), 404
        return redirect("/404")

    @app.errorhandler(500)
    def handle_500(e):
        log.error(f"Internal Server Error: {e}", exc_info=True)
        if request.path.startswith("/api/"):
            return jsonify({"error": "Interner Serverfehler"}), 500
        return "Interner Fehler", 500

    @app.errorhandler(429)
    def handle_429(_e):
        return jsonify({"error": "Zu viele Anfragen. Bitte warten."}), 429


def register_default_blueprints(
    app,
    *,
    db,
    config: dict,
    limiter,
    db_audit_fn,
    check_login_rate_fn,
    record_login_attempt_fn,
    audit_fn,
    template_dir: str,
    static_dir: str,
    require_auth_fn,
    log,
) -> None:
    """Registriert Standard-Blueprints (auth + dashboard)."""
    try:
        from routes.auth import create_auth_blueprint
        from routes.dashboard import create_dashboard_blueprint

        auth_bp = create_auth_blueprint(
            db=db,
            config=config,
            limiter=limiter,
            db_audit_fn=db_audit_fn,
            check_login_rate_fn=check_login_rate_fn,
            record_login_attempt_fn=record_login_attempt_fn,
            audit_fn=audit_fn,
            template_dir=template_dir,
        )
        dashboard_bp = create_dashboard_blueprint(
            template_dir=template_dir,
            static_dir=static_dir,
            require_auth_fn=require_auth_fn,
        )
        app.register_blueprint(auth_bp, name="auth_bp")
        app.register_blueprint(dashboard_bp, name="dashboard_bp")
        log.info("✅ Blueprints registriert: auth, dashboard")
    except Exception as bp_err:  # noqa: BLE001
        log.error(f"Blueprint-Registrierung fehlgeschlagen: {bp_err}", exc_info=True)
