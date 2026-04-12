"""WebSocket auth and admin authorization checks."""

from __future__ import annotations

import logging

_log = logging.getLogger(__name__)


def ws_auth_required(*, session_obj, emit_fn) -> bool:
    """Return True when socket user is authenticated; otherwise emit auth error."""
    if not session_obj.get("user_id"):
        emit_fn("auth_error", {"msg": "Nicht authentifiziert – bitte einloggen"})
        return False
    return True


def ws_admin_required(*, session_obj, emit_fn, db, ws_auth_required_fn) -> bool:
    """Return True when socket user is authenticated admin."""
    if not ws_auth_required_fn():
        return False
    uid = session_obj.get("user_id")
    try:
        user = db.get_user_by_id(uid)
        if not user or user.get("role") != "admin":
            emit_fn("status", {"msg": "Nur Admin", "key": "ws_admin_only", "type": "error"})
            return False
    except Exception as exc:
        _log.debug("ws_admin_required DB-Fehler für uid=%s: %s", uid, exc)
        emit_fn("status", {"msg": "Nur Admin", "key": "ws_admin_only", "type": "error"})
        return False
    return True
