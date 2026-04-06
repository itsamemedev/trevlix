"""Bot-loop heartbeat sleep helper."""

from __future__ import annotations

import time


def heartbeat_sleep(*, seconds: float, state, healer) -> None:
    """Sleep in short chunks and continuously send healer heartbeat."""
    remaining = max(0.0, float(seconds))
    while remaining > 0 and state.running:
        try:
            healer.heartbeat()
        except Exception:
            pass
        chunk = min(1.0, remaining)
        time.sleep(chunk)
        remaining -= chunk
