"""Validierungshilfen für Admin-User-Erstellung (HTTP + WebSocket)."""

from __future__ import annotations

from app.core.request_helpers import safe_float

_ALLOWED_ROLES = frozenset({"admin", "user", "viewer"})


def validate_admin_user_payload(data: dict) -> tuple[bool, dict, str, str]:
    """Validiert Nutzerdaten und liefert normalisierte Werte.

    Returns:
        (is_valid, normalized_payload, error_key, error_message)
    """
    username = str(data.get("username", "")).strip()
    password = str(data.get("password", ""))
    role = str(data.get("role", "user")).strip().lower()
    balance = safe_float(data.get("balance", 10000), 10000.0)

    if not username or len(username) < 3 or len(username) > 64:
        return False, {}, "err_username_length", "❌ Username muss 3-64 Zeichen haben"

    if not username.replace("_", "").replace("-", "").isalnum():
        return False, {}, "err_username_chars", "❌ Username: nur Buchstaben, Zahlen, -, _"

    if len(password) < 12:
        return False, {}, "err_password_length", "❌ Passwort muss mind. 12 Zeichen haben"

    if not any(c.isupper() for c in password) or not any(c.islower() for c in password):
        return (
            False,
            {},
            "err_password_case",
            "❌ Passwort braucht Groß- und Kleinbuchstaben",
        )

    if not any(c.isdigit() for c in password):
        return False, {}, "err_password_digit", "❌ Passwort braucht mindestens eine Zahl"

    if role not in _ALLOWED_ROLES:
        return False, {}, "err_invalid_role", "❌ Ungültige Rolle"

    return (
        True,
        {"username": username, "password": password, "role": role, "balance": balance},
        "",
        "",
    )
