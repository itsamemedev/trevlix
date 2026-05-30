"""Helpers for weak admin password detection."""

from __future__ import annotations

_WEAK_DEFAULTS = {"trevlix", "admin", "password", "test"}


def is_admin_password_weak(admin_password: str | None) -> bool:
    """Return True if admin password is missing or matches known weak defaults.

    Comparison is case-insensitive and whitespace-trimmed so trivial variants
    like ``"Admin"``, ``"PASSWORD"`` or ``" trevlix "`` are still flagged.
    """
    normalized = (admin_password or "").strip().lower()
    return not normalized or normalized in _WEAK_DEFAULTS
