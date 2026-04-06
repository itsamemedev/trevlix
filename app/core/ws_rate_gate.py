"""WebSocket rate-gating helper."""

from __future__ import annotations


def ws_rate_check(*, limiter, sid: str, action: str, min_interval: float = 2.0) -> bool:
    """Check per-sid action rate limit via WsRateLimiter."""
    return limiter.check(sid, action, min_interval_sec=min_interval)
