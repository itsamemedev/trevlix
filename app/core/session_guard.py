"""Session timeout and CSRF checks extracted from server.py."""

from __future__ import annotations

import hmac
import logging
from datetime import datetime
from typing import Any

from flask import abort, redirect

_log = logging.getLogger(__name__)


def handle_session_and_csrf(
    *,
    session_obj: Any,
    request_obj: Any,
    session_timeout_min: int,
    audit_fn,
):
    """Validate dashboard session timeout and CSRF token for state-changing requests."""
    if session_obj.get("user_id"):
        now = datetime.now()
        last = session_obj.get("last_active")
        created = session_obj.get("session_created")
        if last:
            try:
                elapsed = (now - datetime.fromisoformat(last)).total_seconds()
                if elapsed > session_timeout_min * 60:
                    uid = session_obj.get("user_id", 0)
                    session_obj.clear()
                    audit_fn("session_timeout", f"user_id={uid}", uid)
                    if request_obj.path.startswith("/api/"):
                        abort(401)
                    return redirect("/login")
            except (ValueError, TypeError):
                _log.warning(
                    "Ungültiger last_active-Timestamp – Session gelöscht (mögliche Manipulation)"
                )
                session_obj.clear()
                if request_obj.path.startswith("/api/"):
                    abort(401)
                return redirect("/login")

        if created:
            try:
                age = (now - datetime.fromisoformat(created)).total_seconds()
                if age > 8 * 3600:
                    uid = session_obj.get("user_id", 0)
                    session_obj.clear()
                    audit_fn("session_expired", f"user_id={uid} age={age:.0f}s", uid)
                    if request_obj.path.startswith("/api/"):
                        abort(401)
                    return redirect("/login")
            except (ValueError, TypeError):
                session_obj.clear()
                if request_obj.path.startswith("/api/"):
                    abort(401)
                return redirect("/login")

        session_obj["last_active"] = now.isoformat()

    if request_obj.method in ("POST", "PUT", "DELETE", "PATCH"):
        auth = request_obj.headers.get("Authorization", "")
        if not auth.startswith("Bearer ") and session_obj.get("user_id"):
            if not (
                request_obj.path.startswith("/socket.io")
                or request_obj.path.startswith("/static/")
                or request_obj.path in ("/favicon.ico", "/robots.txt", "/sitemap.xml")
            ):
                # Token-Quellen (in Reihenfolge): X-CSRFToken-Header → JSON-Body → Form-Body
                token = request_obj.headers.get("X-CSRFToken") or request_obj.headers.get(
                    "X-CSRF-Token"
                )
                if not token:
                    try:
                        token = (
                            (request_obj.json or {}).get("_csrf") if request_obj.is_json else None
                        )
                    except Exception:
                        token = None
                if not token:
                    try:
                        token = request_obj.form.get("_csrf")
                    except Exception:
                        token = None
                expected = session_obj.get("_csrf_token")
                if expected and (not token or not hmac.compare_digest(str(token), str(expected))):
                    audit_fn("csrf_violation", request_obj.path, session_obj.get("user_id", 0))
                    abort(403)
    return None
