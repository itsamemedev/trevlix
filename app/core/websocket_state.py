"""WebSocket state snapshot helper."""

from __future__ import annotations

import logging

_log = logging.getLogger(__name__)


def build_ws_state_snapshot(*, uid: int, state, db) -> dict:
    """Build socket state payload including user role."""
    snap = state.snapshot()
    try:
        user = db.get_user_by_id(uid)
        snap["user_role"] = user.get("role", "user") if user else "user"
    except Exception as exc:
        _log.debug("Benutzerrolle konnte nicht geladen werden (uid=%s): %s", uid, exc)
        snap["user_role"] = "user"
    return snap
