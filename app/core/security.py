"""Security-bezogene Hilfsfunktionen für Flask Request/Response."""

from __future__ import annotations

import secrets

_CSP = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline' 'unsafe-eval' "
    "cdnjs.cloudflare.com unpkg.com; "
    "style-src 'self' 'unsafe-inline' fonts.googleapis.com; "
    "font-src 'self' fonts.gstatic.com; "
    "img-src 'self' data: blob:; "
    "connect-src 'self' wss: ws:; "
    "frame-ancestors 'self';"
)


def apply_security_headers(response, *, is_secure: bool):
    """Setzt standardisierte Security-Header auf der Response."""
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = (
        "camera=(), microphone=(), geolocation=(), payment=(), usb=()"
    )
    response.headers["Content-Security-Policy"] = _CSP
    if is_secure:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


def generate_csrf_token(session_obj) -> str:
    """Generiert ein CSRF-Token pro Session."""
    if "_csrf_token" not in session_obj:
        session_obj["_csrf_token"] = secrets.token_hex(32)
    return session_obj["_csrf_token"]
