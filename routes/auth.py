"""[#9] TREVLIX – Auth Blueprint (Login, Register, Logout).

Enthält alle Authentifizierungs-Routes als Flask Blueprint.
Wird von server.py über ``register_auth_blueprint()`` eingebunden.

Verwendung:
    from routes.auth import create_auth_blueprint
    bp = create_auth_blueprint(db, CONFIG, limiter, db_audit_fn, check_rate_fn, record_fn, audit_fn)
    app.register_blueprint(bp)
"""

from __future__ import annotations

import logging
import os
import secrets
from collections.abc import Callable
from datetime import datetime
from typing import Any

from flask import Blueprint, redirect, request, send_file, session

log = logging.getLogger("NEXUS.auth")

# Auth-Seite HTML-Template (minimales Inline-CSS für Login/Register)
_AUTH_TEMPLATE = """<!DOCTYPE html><html><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>TREVLIX %(page_title)s</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'Segoe UI',sans-serif;background:#060912;color:#ccd6f6;
  min-height:100vh;display:flex;align-items:center;justify-content:center}
.box{background:#0a0f1e;border:1px solid rgba(255,255,255,.07);border-radius:20px;
  padding:40px 36px;width:100%%;max-width:380px}
.logo{text-align:center;margin-bottom:28px}
.logo-icon{font-size:44px;margin-bottom:8px}
.logo-name{font-size:26px;font-weight:900;letter-spacing:-1px}
.logo-name span{color:#00d4ff}
.logo-sub{font-size:11px;color:#3a4a6a;letter-spacing:2px;text-transform:uppercase;margin-top:2px}
label{display:block;font-size:11px;font-weight:700;color:#5a7090;letter-spacing:.5px;
  text-transform:uppercase;margin-bottom:5px}
input{width:100%%;background:#0f1628;border:1px solid rgba(255,255,255,.08);
  border-radius:10px;padding:13px 14px;color:#ccd6f6;font-size:14px;outline:none;
  margin-bottom:14px;transition:.2s}
input:focus{border-color:rgba(0,212,255,.4)}
.msg{font-size:12px;margin-bottom:12px;padding:8px 10px;border-radius:8px;
  display:%(msg_display)s;text-align:center}
.msg-err{background:rgba(255,61,113,.12);color:#ff3d71;border:1px solid rgba(255,61,113,.25)}
.msg-ok{background:rgba(0,212,255,.1);color:#00d4ff;border:1px solid rgba(0,212,255,.2)}
button{width:100%%;padding:15px;border-radius:12px;background:linear-gradient(135deg,#00d4ff,#0090b0);
  color:#000;font-size:15px;font-weight:800;border:none;cursor:pointer;transition:.15s}
button:hover{transform:translateY(-1px)}
.ver{text-align:center;margin-top:20px;font-size:10px;color:#3a4a6a}
.alt-link{text-align:center;margin-top:14px;font-size:12px;color:#5a7090}
.alt-link a{color:#00d4ff;text-decoration:none}
</style></head><body>
<div class="box">
  <div class="logo">
    <div class="logo-icon">&#9889;</div>
    <div class="logo-name">TREV<span>LIX</span></div>
    <div class="logo-sub">Algorithmic Trading Bot &middot; v1.1.1</div>
  </div>
  %(body)s
  <div class="ver">TREVLIX &middot; Open-Source Trading Bot</div>
</div>
</body></html>"""


# Admin-Login Template (Gold/Amber Akzent statt Cyan um Admin-Bereich zu kennzeichnen)
_ADMIN_AUTH_TEMPLATE = """<!DOCTYPE html><html><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>TREVLIX %(page_title)s</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'Segoe UI',sans-serif;background:#0a0608;color:#ccd6f6;
  min-height:100vh;display:flex;align-items:center;justify-content:center}
.box{background:#1a0f1e;border:1px solid rgba(255,180,0,.15);border-radius:20px;
  padding:40px 36px;width:100%%;max-width:380px}
.logo{text-align:center;margin-bottom:28px}
.logo-icon{font-size:44px;margin-bottom:8px}
.logo-name{font-size:26px;font-weight:900;letter-spacing:-1px}
.logo-name span{color:#ffb400}
.logo-sub{font-size:11px;color:#6a5a3a;letter-spacing:2px;text-transform:uppercase;margin-top:2px}
.admin-badge{display:inline-block;background:rgba(255,180,0,.15);color:#ffb400;
  font-size:10px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;
  padding:4px 12px;border-radius:6px;border:1px solid rgba(255,180,0,.3);margin-top:10px}
label{display:block;font-size:11px;font-weight:700;color:#907050;letter-spacing:.5px;
  text-transform:uppercase;margin-bottom:5px}
input{width:100%%;background:#150d1a;border:1px solid rgba(255,180,0,.12);
  border-radius:10px;padding:13px 14px;color:#ccd6f6;font-size:14px;outline:none;
  margin-bottom:14px;transition:.2s}
input:focus{border-color:rgba(255,180,0,.5)}
.msg{font-size:12px;margin-bottom:12px;padding:8px 10px;border-radius:8px;
  display:%(msg_display)s;text-align:center}
.msg-err{background:rgba(255,61,113,.12);color:#ff3d71;border:1px solid rgba(255,61,113,.25)}
button{width:100%%;padding:15px;border-radius:12px;background:linear-gradient(135deg,#ffb400,#c08800);
  color:#000;font-size:15px;font-weight:800;border:none;cursor:pointer;transition:.15s}
button:hover{transform:translateY(-1px)}
.ver{text-align:center;margin-top:20px;font-size:10px;color:#5a4a3a}
.alt-link{text-align:center;margin-top:14px;font-size:12px;color:#5a7090}
.alt-link a{color:#ffb400;text-decoration:none}
</style></head><body>
<div class="box">
  <div class="logo">
    <div class="logo-icon">&#128274;</div>
    <div class="logo-name">TREV<span>LIX</span></div>
    <div class="logo-sub">Algorithmic Trading Bot</div>
    <div class="admin-badge">Admin-Bereich</div>
  </div>
  %(body)s
  <div class="ver">TREVLIX &middot; Admin Panel</div>
</div>
</body></html>"""


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
        return send_file(os.path.join(template_dir, "dashboard.html"))

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
            return _AUTH_TEMPLATE % {"page_title": "Login", "msg_display": "none", "body": body}

        csrf_submitted = request.form.get("_csrf", "")
        if not csrf_submitted or csrf_submitted != session.get("_csrf_token"):
            return redirect("/login?err=1")

        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        if not username or not password:
            return redirect("/login?err=1")

        client_ip = request.remote_addr or "unknown"
        if not check_login_rate_fn(client_ip):
            db_audit_fn(
                0, "login_blocked", f"Brute-Force-Schutz: {username} von {client_ip}", client_ip
            )
            return redirect("/login?err=1")
        record_login_attempt_fn(client_ip)

        user = db.get_user(username)
        if user and db.verify_password(user["password_hash"], password):
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["user_role"] = user.get("role", "user")
            session["last_active"] = datetime.now().isoformat()
            db.update_user_login(user["id"])
            db_audit_fn(user["id"], "login", f"Login · {client_ip}", client_ip)
            return redirect("/")

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
            return _AUTH_TEMPLATE % {
                "page_title": "Registrierung",
                "msg_display": "none",
                "body": body,
            }, 403

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
                    "Passwort muss mind. 12 Zeichen mit Groß+Klein+Zahl haben.",
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
            return _AUTH_TEMPLATE % {
                "page_title": "Registrierung",
                "msg_display": "none",
                "body": body,
            }

        csrf_submitted = request.form.get("_csrf", "")
        if not csrf_submitted or csrf_submitted != session.get("_csrf_token"):
            return redirect("/register?err=short")

        username = request.form.get("username", "").strip()[:32]
        password = request.form.get("password", "")
        password2 = request.form.get("password2", "")

        if len(username) < 3:
            return redirect("/register?err=uname")
        if len(password) < 12 or not (
            _re.search(r"[A-Z]", password)
            and _re.search(r"[a-z]", password)
            and _re.search(r"\d", password)
        ):
            return redirect("/register?err=short")
        if password != password2:
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
        return redirect("/login")

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
            if err == "role":
                msg_txt = "Kein Admin-Zugang für diesen Benutzer"
            elif err:
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
  <div class="alt-link"><a href="/login">&larr; Zum normalen Login</a></div>"""
            return _ADMIN_AUTH_TEMPLATE % {
                "page_title": "Admin Login",
                "msg_display": "none",
                "body": body,
            }

        csrf_submitted = request.form.get("_csrf", "")
        if not csrf_submitted or csrf_submitted != session.get("_csrf_token"):
            return redirect("/admin/login?err=1")

        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        if not username or not password:
            return redirect("/admin/login?err=1")

        client_ip = request.remote_addr or "unknown"
        if not check_login_rate_fn(client_ip):
            db_audit_fn(
                0,
                "admin_login_blocked",
                f"Brute-Force-Schutz (Admin): {username} von {client_ip}",
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
                return redirect("/admin/login?err=role")
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["user_role"] = "admin"
            session["last_active"] = datetime.now().isoformat()
            db.update_user_login(user["id"])
            db_audit_fn(user["id"], "admin_login", f"Admin-Login · {client_ip}", client_ip)
            return redirect("/")

        audit_fn("admin_login_failed", f"user={username} ip={client_ip}")
        return redirect("/admin/login?err=1")

    @bp.route("/admin/logout")
    def admin_logout():
        """Admin-Abmeldung."""
        session.clear()
        return redirect("/admin/login")

    return bp
