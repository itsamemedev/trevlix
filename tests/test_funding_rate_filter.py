"""FundingRateTracker.is_short_too_expensive sign convention (Bybit perps)."""

from __future__ import annotations

from services.risk import FundingRateTracker


def _tracker(rate, max_rate=0.001, enabled=True):
    t = FundingRateTracker({"funding_rate_filter": enabled, "funding_rate_max": max_rate})
    t._rates["BTC/USDT"] = rate
    return t


def test_strongly_negative_funding_is_expensive_for_shorts():
    # Negative funding → shorts pay longs → expensive → blocked.
    assert _tracker(-0.005).is_short_too_expensive("BTC/USDT") is True


def test_positive_funding_is_cheap_for_shorts():
    # Positive funding → shorts receive funding → cheap → allowed.
    assert _tracker(0.005).is_short_too_expensive("BTC/USDT") is False


def test_small_negative_within_threshold_allowed():
    assert _tracker(-0.0005, max_rate=0.001).is_short_too_expensive("BTC/USDT") is False


def test_disabled_filter_never_blocks():
    assert _tracker(-0.5, enabled=False).is_short_too_expensive("BTC/USDT") is False


def test_unknown_symbol_not_blocked():
    assert _tracker(-0.005).is_short_too_expensive("ETH/USDT") is False
