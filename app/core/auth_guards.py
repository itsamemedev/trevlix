"""Authentication and authorization helpers shared by the Flask entrypoint."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from functools import wraps
from typing import Any

from flask import jsonify, redirect, request, session


class LoginAttemptTracker:
    """Tracks login attempts per IP with bounded memory usage."""

    def __init__(self) -> None:
        self._attempts: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def check_rate(self, ip: str, max_attempts: int = 5, window: int = 60) -> bool:
        """Return whether another login attempt is allowed for this IP."""
        now = time.time()
        with self._lock:
            attempts = self._attempts.get(ip, [])
            attempts = [t for t in attempts if now - t < window]
            if attempts:
                self._attempts[ip] = attempts
            else:
                self._attempts.pop(ip, None)
            return len(attempts) < max_attempts

    def record_attempt(self, ip: str) -> None:
        """Record a login attempt and prune stale or oversized entries."""
        with self._lock:
            attempts = self._attempts.setdefault(ip, [])
            attempts.append(time.time())
            if len(attempts) > 50:
                self._attempts[ip] = attempts[-50:]
            if len(self._attempts) > 10_000:
                cutoff = time.time() - 3600
                stale = [k for k, v in self._attempts.items() if not v or max(v) < cutoff]
                for key in stale:
                    self._attempts.pop(key, None)


def build_api_auth_required(db: Any) -> Callable:
    """Create decorator for REST endpoints requiring API token or dashboard session."""

    def api_auth_required(func):
        @wraps(func)
        def decorated(*args, **kwargs):
            auth = request.headers.get("Authorization", "")
            token = auth.replace("Bearer ", "").strip() if auth.startswith("Bearer ") else ""
            if not token:
                token = request.args.get("token", "")
            if token:
                uid = db.verify_api_token(token)
                if uid:
                    request.user_id = uid
                    return func(*args, **kwargs)
            if session.get("user_id"):
                request.user_id = session["user_id"]
                return func(*args, **kwargs)
            return jsonify({"error": "Nicht autorisiert"}), 401

        return decorated

    return api_auth_required


def build_dashboard_auth() -> Callable:
    """Create decorator for dashboard session access."""

    def dashboard_auth(func):
        @wraps(func)
        def decorated(*args, **kwargs):
            if not session.get("user_id"):
                return redirect("/login")
            return func(*args, **kwargs)

        return decorated

    return dashboard_auth


def build_admin_required(db: Any) -> Callable:
    """Create decorator for admin-only endpoints."""

    def admin_required(func):
        @wraps(func)
        def decorated(*args, **kwargs):
            uid = getattr(request, "user_id", session.get("user_id"))
            if not uid:
                return jsonify({"error": "Nicht autorisiert"}), 401
            user = db.get_user_by_id(uid)
            if not user or user.get("role") != "admin":
                return jsonify({"error": "Nur Admin"}), 403
            return func(*args, **kwargs)

        return decorated

    return admin_required
