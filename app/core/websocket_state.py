"""WebSocket state snapshot helper."""

from __future__ import annotations


def build_ws_state_snapshot(*, uid: int, state, db) -> dict:
    """Build socket state payload including user role."""
    snap = state.snapshot()
    try:
        user = db.get_user_by_id(uid)
        snap["user_role"] = user.get("role", "user") if user else "user"
    except Exception:
        snap["user_role"] = "user"
    return snap
