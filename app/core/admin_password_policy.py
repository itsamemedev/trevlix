"""Helpers for weak admin password detection."""

from __future__ import annotations

_WEAK_DEFAULTS = {"trevlix", "admin", "password", "test"}


def is_admin_password_weak(admin_password: str | None) -> bool:
    """Return True if admin password is missing or matches known weak defaults."""
    return not admin_password or admin_password in _WEAK_DEFAULTS
