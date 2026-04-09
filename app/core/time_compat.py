"""Timezone compatibility helpers shared across Trevlix modules."""

from __future__ import annotations

from datetime import datetime, timezone

UTC = getattr(datetime, "UTC", timezone.utc)  # noqa: UP017


def utc_now() -> datetime:
    """Return the current aware UTC datetime across Python 3.10/3.11+."""
    return datetime.now(UTC)
