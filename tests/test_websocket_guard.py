from __future__ import annotations

from unittest.mock import patch

from app.core.websocket_guard import WsRateLimiter


def test_ws_rate_limiter_blocks_within_interval():
    limiter = WsRateLimiter()

    with patch("app.core.websocket_guard.time.time", side_effect=[100.0, 101.0]):
        assert limiter.check("sid1", "start", min_interval_sec=2.0) is True
        assert limiter.check("sid1", "start", min_interval_sec=2.0) is False


def test_ws_rate_limiter_allows_after_interval():
    limiter = WsRateLimiter()

    with patch("app.core.websocket_guard.time.time", side_effect=[100.0, 102.1]):
        assert limiter.check("sid1", "start", min_interval_sec=2.0) is True
        assert limiter.check("sid1", "start", min_interval_sec=2.0) is True


def test_ws_rate_limiter_cleans_stale_entries():
    limiter = WsRateLimiter(cleanup_interval_sec=10.0, stale_after_sec=20.0)

    with patch("app.core.websocket_guard.time.time", side_effect=[100.0, 130.0]):
        assert limiter.check("sid1", "start", min_interval_sec=2.0) is True
        assert limiter.check("sid2", "start", min_interval_sec=2.0) is True

    assert limiter.size() == 1
