"""[#9] TREVLIX – Auth Blueprint (Login, Register, Logout).

Enthält alle Authentifizierungs-Routes als Flask Blueprint.
Wird von server.py über ``register_auth_blueprint()`` eingebunden.

Verwendung:
    from routes.auth import create_auth_blueprint
    bp = create_auth_blueprint(db, CONFIG, limiter, db_audit_fn, check_rate_fn, record_fn, audit_fn)
    app.register_blueprint(bp)
"""

from __future__ import annotations

import hmac
import logging
import secrets
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any

import jwt as pyjwt
from flask import Blueprint, make_response, redirect, render_template, request, session

from app.core.time_compat import UTC

log = logging.getLogger("trevlix.auth")

# Auth-Seiten liegen als Jinja-Templates unter templates/auth.html
# (User-Login/Register) und templates/auth_admin.html (Admin-Login/Reset).
# Die Routen rendern sie mit `render_template(...)` und den Variablen
# page_title, msg_display und body (bereits gerenderter Formular-HTML-Snippet).


def _ensure_csrf() -> str:
    """CSRF-Token in Session erzeugen/abrufen."""
    if "_csrf_token" not in session:
        session["_csrf_token"] = secrets.token_hex(32)
    return session["_csrf_token"]


def create_auth_blueprint(
    db: Any,
    config: dict,
    limiter: Any,
    db_audit_fn: Callable,
    check_login_rate_fn: Callable,
    record_login_attempt_fn: Callable,
    audit_fn: Callable,
    template_dir: str,
) -> Blueprint:
    """Erstellt und konfiguriert den Auth Blueprint.

    Args:
        db: MySQLManager-Instanz für DB-Zugriffe.
        config: CONFIG-Dict mit app-weiten Einstellungen.
        limiter: Flask-Limiter Instanz für Rate-Limiting.
        db_audit_fn: Funktion zum Schreiben von Audit-Log-Einträgen.
        check_login_rate_fn: Prüft ob IP-Adresse im Ratelimit ist.
        record_login_attempt_fn: Zeichnet Login-Versuch auf.
        audit_fn: Interne Audit-Funktion (kürzer als db_audit_fn).
        template_dir: Pfad zum Templates-Verzeichnis.

    Returns:
        Konfigurierter Flask Blueprint für Auth-Routes.
    """
    bp = Blueprint("auth", __name__)

    @bp.route("/")
    def index():
        """Hauptseite - leitet zu Login um wenn nicht eingeloggt.

        Returns:
            Dashboard HTML oder Redirect zu /login.
        """
        if not session.get("user_id"):
            return redirect("/login")
        return render_template("dashboard.html")

    @bp.route("/login", methods=["GET", "POST"])
    @limiter.limit("10 per minute")
    def login():
        """Login-Route für Benutzerauthentifizierung.

        GET: Zeigt Login-Formular.
        POST: Verarbeitet Login-Daten mit Brute-Force-Schutz.

        Returns:
            Login-Seite (HTML) oder Redirect nach erfolgreichem Login.
        """
        allow_reg = config.get("allow_registration", False)
        reg_link = (
            '<div class="alt-link">Noch kein Konto? <a href="/register">Registrieren</a></div>'
            if allow_reg
            else ""
        )
        if request.method == "GET":
            err = request.args.get("err", "")
            msg_cls = "msg msg-err"
            msg_txt = "Falsches Passwort oder Benutzer nicht gefunden" if err else ""
            csrf = _ensure_csrf()
            body = f"""  <form method="POST" action="/login">
    <input type="hidden" name="_csrf" value="{csrf}">
    <div class="{msg_cls}" style="display:{"block" if err else "none"}">{msg_txt}</div>
    <label>Benutzername</label>
    <input type="text" name="username" required autocomplete="username">
    <label>Passwort</label>
    <input type="password" name="password" required autofocus autocomplete="current-password">
    <button type="submit">Anmelden &rarr;</button>
  </form>
  {reg_link}"""
            return render_template("auth.html", page_title="Login", msg_display="none", body=body)

        csrf_submitted = request.form.get("_csrf", "")
        csrf_expected = session.get("_csrf_token", "")
        if not csrf_submitted or not hmac.compare_digest(csrf_submitted, csrf_expected):
            return redirect("/login?err=1")

        username = request.form.get("username", "").strip()[:64]
        password = request.form.get("password", "")
        if not username or not password or len(password) > 128:
            return redirect("/login?err=1")

        client_ip = request.remote_addr or "unknown"
        if not check_login_rate_fn(client_ip):
            db_audit_fn(
                0,
                "login_blocked",
                f"Brute-Force-Schutz: {username[:32]} von {client_ip}",
                client_ip,
            )
            return redirect("/login?err=1")
        record_login_attempt_fn(client_ip)

        user = db.get_user(username)
        if user and db.verify_password(user["password_hash"], password):
            # Session regenerieren um Session Fixation zu verhindern
            session.clear()
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["user_role"] = user.get("role", "user")
            now_iso = datetime.now().isoformat()
            session["last_active"] = now_iso
            session["session_created"] = now_iso
            _ensure_csrf()  # CSRF-Token nach Login neu generieren
            db.update_user_login(user["id"])
            db_audit_fn(user["id"], "login", f"Login · {client_ip}", client_ip)
            # JWT-Token als Cookie setzen für Socket.io Fallback-Auth
            resp = make_response(redirect("/"))
            try:
                jwt_secret = config.get("jwt_secret", "")
                if jwt_secret:
                    token = pyjwt.encode(
                        {
                            "user_id": user["id"],
                            "username": user["username"],
                            "exp": datetime.now(UTC) + timedelta(hours=8),
                        },
                        jwt_secret,
                        algorithm="HS256",
                    )
                    resp.set_cookie(
                        "token",
                        token,
                        httponly=False,  # JS muss lesen können
                        samesite="Lax",
                        max_age=8 * 3600,
                        path="/",
                    )
            except Exception as e:
                log.warning("JWT cookie generation failed: %s", e)
            return resp

        audit_fn("login_failed", f"user={username} ip={client_ip}")
        return redirect("/login?err=1")

    @bp.route("/register", methods=["GET", "POST"])
    @limiter.limit("5 per minute")
    def register():
        """Registrierungs-Route für neue Benutzerkonten.

        Nur verfügbar wenn ``allow_registration`` in CONFIG aktiv.
        Erzwingt Passwort-Policy (min. 12 Zeichen, Groß+Klein+Zahl).

        GET: Zeigt Registrierungs-Formular.
        POST: Erstellt neues Benutzerkonto.

        Returns:
            Registrierungs-Seite (HTML) oder Redirect.
        """
        import re as _re

        if not config.get("allow_registration", False):
            body = """  <div class="msg msg-err" style="display:block">
    Registrierung ist deaktiviert. Bitte wende dich an den Administrator.
  </div>
  <div class="alt-link" style="margin-top:20px"><a href="/login">&larr; Zur Anmeldung</a></div>"""
            return (
                render_template(
                    "auth.html",
                    page_title="Registrierung",
                    msg_display="none",
                    body=body,
                ),
                403,
            )

        if request.method == "GET":
            err = request.args.get("err", "")
            ok = request.args.get("ok", "")
            if err == "exists":
                msg_txt, msg_cls, show = "Benutzername bereits vergeben.", "msg msg-err", "block"
            elif err == "uname":
                msg_txt, msg_cls, show = (
                    "Benutzername muss mind. 3 Zeichen haben.",
                    "msg msg-err",
                    "block",
                )
            elif err == "short":
                msg_txt, msg_cls, show = (
                    "Passwort muss mind. 12 Zeichen mit Groß+Klein+Zahl+Sonderzeichen"
                    " haben und darf keine gängigen Muster enthalten.",
                    "msg msg-err",
                    "block",
                )
            elif err == "match":
                msg_txt, msg_cls, show = "Passwörter stimmen nicht überein.", "msg msg-err", "block"
            elif ok:
                msg_txt, msg_cls, show = (
                    "Konto erstellt! Du kannst dich jetzt anmelden.",
                    "msg msg-ok",
                    "block",
                )
            else:
                msg_txt, msg_cls, show = "", "msg msg-err", "none"

            csrf = _ensure_csrf()
            body = f"""  <form method="POST" action="/register">
    <input type="hidden" name="_csrf" value="{csrf}">
    <div class="{msg_cls}" style="display:{show}">{msg_txt}</div>
    <label>Benutzername</label>
    <input type="text" name="username" required autocomplete="username" minlength="3" maxlength="32">
    <label>Passwort</label>
    <input type="password" name="password" required autocomplete="new-password" minlength="12">
    <label>Passwort bestätigen</label>
    <input type="password" name="password2" required autocomplete="new-password" minlength="12">
    <button type="submit">Konto erstellen &rarr;</button>
  </form>
  <div class="alt-link"><a href="/login">&larr; Zur Anmeldung</a></div>"""
            return render_template(
                "auth.html",
                page_title="Registrierung",
                msg_display="none",
                body=body,
            )

        csrf_submitted = request.form.get("_csrf", "")
        csrf_expected = session.get("_csrf_token", "")
        if not csrf_submitted or not hmac.compare_digest(csrf_submitted, csrf_expected):
            return redirect("/register")

        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        password2 = request.form.get("password2", "")

        if len(username) < 3 or len(username) > 32:
            return redirect("/register?err=uname")
        _WEAK_PATTERNS = frozenset(
            {
                "password",
                "123456",
                "qwerty",
                "admin",
                "letmein",
                "welcome",
                "monkey",
                "dragon",
                "master",
                "abc123",
                "login",
                "princess",
                "passw0rd",
                "shadow",
                "trustno1",
            }
        )
        if len(password) > 128:
            return redirect("/register?err=short")
        has_upper = _re.search(r"[A-Z]", password)
        has_lower = _re.search(r"[a-z]", password)
        has_digit = _re.search(r"\d", password)
        has_special = _re.search(r"[!@#$%^&*(),.?\":{}|<>\-_=+\[\]\\;'/`~]", password)
        pw_lower = password.lower()
        has_weak = any(w in pw_lower for w in _WEAK_PATTERNS)
        if (
            len(password) < 12
            or not (has_upper and has_lower and has_digit and has_special)
            or has_weak
        ):
            return redirect("/register?err=short")
        if not hmac.compare_digest(password, password2):
            return redirect("/register?err=match")
        if db.get_user(username):
            return redirect("/register?err=exists")

        if db.create_user(username, password, role="user"):
            db_audit_fn(
                0,
                "register",
                f"Neues Konto: {username} · {request.remote_addr}",
                request.remote_addr or "",
            )
            return redirect("/register?ok=1")
        return redirect("/register?err=exists")

    @bp.route("/logout")
    def logout():
        """Meldet den Benutzer ab und löscht die Session.

        Returns:
            Redirect zur Login-Seite.
        """
        session.clear()
        resp = make_response(redirect("/login"))
        resp.delete_cookie("token", path="/")
        return resp

    # ── Admin Login ──────────────────────────────────────────────────────

    @bp.route("/admin/login", methods=["GET", "POST"])
    @limiter.limit("5 per minute")
    def admin_login():
        """Separates Admin-Login mit strengerem Rate-Limiting.

        GET: Zeigt Admin-Login-Formular.
        POST: Authentifiziert nur Benutzer mit role='admin'.

        Returns:
            Admin-Login-Seite (HTML) oder Redirect zum Dashboard.
        """
        if request.method == "GET":
            err = request.args.get("err", "")
            msg_cls = "msg msg-err"
            if err:
                msg_txt = "Falsches Passwort oder Benutzer nicht gefunden"
            else:
                msg_txt = ""
            csrf = _ensure_csrf()
            body = f"""  <form method="POST" action="/admin/login">
    <input type="hidden" name="_csrf" value="{csrf}">
    <div class="{msg_cls}" style="display:{"block" if err else "none"}">{msg_txt}</div>
    <label>Admin Benutzername</label>
    <input type="text" name="username" required autocomplete="username">
    <label>Admin Passwort</label>
    <input type="password" name="password" required autofocus autocomplete="current-password">
    <button type="submit">Admin-Anmeldung &rarr;</button>
  </form>
  <div class="alt-link"><a href="/login">&larr; Zum normalen Login</a></div>
  <div class="alt-link" style="margin-top:8px"><a href="/admin/reset-password">Passwort vergessen?</a></div>"""
            return render_template(
                "auth_admin.html",
                page_title="Admin Login",
                msg_display="none",
                body=body,
            )

        csrf_submitted = request.form.get("_csrf", "")
        csrf_expected = session.get("_csrf_token", "")
        if not csrf_submitted or not hmac.compare_digest(csrf_submitted, csrf_expected):
            return redirect("/admin/login?err=1")

        username = request.form.get("username", "").strip()[:64]
        password = request.form.get("password", "")
        if not username or not password or len(password) > 128:
            return redirect("/admin/login?err=1")

        client_ip = request.remote_addr or "unknown"
        if not check_login_rate_fn(client_ip):
            db_audit_fn(
                0,
                "admin_login_blocked",
                f"Brute-Force-Schutz (Admin): {username[:32]} von {client_ip}",
                client_ip,
            )
            return redirect("/admin/login?err=1")
        record_login_attempt_fn(client_ip)

        user = db.get_user(username)
        if user and db.verify_password(user["password_hash"], password):
            if user.get("role") != "admin":
                audit_fn(
                    "admin_login_denied", f"user={username} ip={client_ip} role={user.get('role')}"
                )
                return redirect("/admin/login?err=1")
            # Session regenerieren um Session Fixation zu verhindern
            session.clear()
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["user_role"] = "admin"
            now_iso = datetime.now().isoformat()
            session["last_active"] = now_iso
            session["session_created"] = now_iso
            _ensure_csrf()  # CSRF-Token nach Admin-Login neu generieren
            db.update_user_login(user["id"])
            db_audit_fn(user["id"], "admin_login", f"Admin-Login · {client_ip}", client_ip)
            return redirect("/")

        audit_fn("admin_login_failed", f"user={username} ip={client_ip}")
        return redirect("/admin/login?err=1")

    @bp.route("/admin/reset-password", methods=["GET", "POST"])
    @limiter.limit("5 per minute")
    def admin_reset_password():
        """Admin-Passwort zurücksetzen ohne E-Mail-Bestätigung.

        Verifiziert den Benutzer über das aktuelle ADMIN_PASSWORD aus
        der Umgebungsvariable. Kein E-Mail-Workflow nötig.

        GET: Zeigt Passwort-Reset-Formular.
        POST: Setzt das Admin-Passwort nach Verifizierung zurück.

        Returns:
            Reset-Seite (HTML) oder Redirect nach Erfolg.
        """
        import re as _re

        if request.method == "GET":
            err = request.args.get("err", "")
            ok = request.args.get("ok", "")
            if ok:
                msg_txt = "Passwort erfolgreich geändert! Bitte neu anmelden."
                msg_cls = "msg msg-ok"
                show = "block"
            elif err == "verify":
                msg_txt = "Master-Passwort ungültig."
                msg_cls = "msg msg-err"
                show = "block"
            elif err == "policy":
                msg_txt = (
                    "Neues Passwort muss mind. 12 Zeichen mit Groß+Klein+Zahl+Sonderzeichen haben."
                )
                msg_cls = "msg msg-err"
                show = "block"
            elif err == "match":
                msg_txt = "Passwörter stimmen nicht überein."
                msg_cls = "msg msg-err"
                show = "block"
            elif err:
                msg_txt = "Fehler beim Zurücksetzen."
                msg_cls = "msg msg-err"
                show = "block"
            else:
                msg_txt = ""
                msg_cls = "msg msg-err"
                show = "none"

            csrf = _ensure_csrf()
            body = f"""  <form method="POST" action="/admin/reset-password">
    <input type="hidden" name="_csrf" value="{csrf}">
    <div class="{msg_cls}" style="display:{show}">{msg_txt}</div>
    <label>Admin Benutzername</label>
    <input type="text" name="username" required autocomplete="username">
    <label>Master-Passwort (ADMIN_PASSWORD)</label>
    <input type="password" name="master_password" required autocomplete="off">
    <label>Neues Passwort</label>
    <input type="password" name="new_password" required autocomplete="new-password" minlength="12">
    <label>Neues Passwort bestätigen</label>
    <input type="password" name="new_password2" required autocomplete="new-password" minlength="12">
    <button type="submit">Passwort zurücksetzen &rarr;</button>
  </form>
  <div class="alt-link"><a href="/admin/login">&larr; Zum Admin-Login</a></div>"""
            return render_template(
                "auth_admin.html",
                page_title="Passwort zurücksetzen",
                msg_display="none",
                body=body,
            )

        # POST
        csrf_submitted = request.form.get("_csrf", "")
        csrf_expected = session.get("_csrf_token", "")
        if not csrf_submitted or not hmac.compare_digest(csrf_submitted, csrf_expected):
            return redirect("/admin/reset-password?err=1")

        username = request.form.get("username", "").strip()[:64]
        master_password = request.form.get("master_password", "")
        new_password = request.form.get("new_password", "")
        new_password2 = request.form.get("new_password2", "")

        if not username or not master_password or not new_password:
            return redirect("/admin/reset-password?err=1")

        client_ip = request.remote_addr or "unknown"
        if not check_login_rate_fn(client_ip):
            return redirect("/admin/reset-password?err=1")
        record_login_attempt_fn(client_ip)

        # Verifiziere Master-Passwort gegen ADMIN_PASSWORD aus Config
        # Always run compare_digest to prevent timing attacks that reveal
        # whether ADMIN_PASSWORD is configured.
        admin_pw = config.get("admin_password", "") or "disabled"
        if not hmac.compare_digest(master_password, admin_pw):
            audit_fn("admin_reset_failed", f"user={username[:32]} ip={client_ip} reason=master_pw")
            return redirect("/admin/reset-password?err=verify")

        # Verifiziere, dass der User existiert und Admin ist
        user = db.get_user(username)
        if not user or user.get("role") != "admin":
            audit_fn("admin_reset_failed", f"user={username[:32]} ip={client_ip} reason=not_admin")
            return redirect("/admin/reset-password?err=verify")

        # Passwort-Policy prüfen
        if len(new_password) > 128:
            return redirect("/admin/reset-password?err=policy")
        has_upper = _re.search(r"[A-Z]", new_password)
        has_lower = _re.search(r"[a-z]", new_password)
        has_digit = _re.search(r"\d", new_password)
        has_special = _re.search(r"[!@#$%^&*(),.?\":{}|<>\-_=+\[\]\\;'/`~]", new_password)
        if len(new_password) < 12 or not (has_upper and has_lower and has_digit and has_special):
            return redirect("/admin/reset-password?err=policy")

        if not hmac.compare_digest(new_password, new_password2):
            return redirect("/admin/reset-password?err=match")

        # Passwort aktualisieren
        if db.update_password(user["id"], new_password):
            db_audit_fn(
                user["id"],
                "admin_password_reset",
                f"Admin-PW-Reset für '{username[:32]}' · {client_ip}",
                client_ip,
            )
            # Session UND JWT-Cookie invalidieren, sonst bleibt altes Token
            # bis zu 8 h gültig obwohl das Passwort bereits getauscht wurde.
            session.clear()
            resp = make_response(redirect("/admin/reset-password?ok=1"))
            resp.delete_cookie("token", path="/")
            return resp

        return redirect("/admin/reset-password?err=1")

    @bp.route("/admin/logout")
    def admin_logout():
        """Admin-Abmeldung: Session UND JWT-Cookie löschen."""
        session.clear()
        resp = make_response(redirect("/admin/login"))
        resp.delete_cookie("token", path="/")
        return resp

    return bp
