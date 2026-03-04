"""
TREVLIX – Unit Tests für Indicator Cache (Verbesserung #20)
=============================================================
Tests für TTL, LRU-Eviction, Cache-Stats.
"""

import os
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Direkt laden ohne services/__init__.py (vermeidet cryptography-Abhängigkeit)
import importlib.util

_spec = importlib.util.spec_from_file_location(
    "indicator_cache",
    os.path.join(os.path.dirname(__file__), "..", "services", "indicator_cache.py"),
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)  # type: ignore[union-attr]
MAX_CACHE_SIZE = _mod.MAX_CACHE_SIZE
cache_stats = _mod.cache_stats
get_cached = _mod.get_cached
invalidate = _mod.invalidate
set_cached = _mod.set_cached


@pytest.fixture(autouse=True)
def clear_cache():
    """Cache vor jedem Test leeren."""
    invalidate()
    yield
    invalidate()


def _make_df(n=5):
    return pd.DataFrame({"close": np.random.randn(n)})


class TestCacheBasics:
    def test_set_and_get(self):
        df = _make_df()
        set_cached("BTC/USDT", "2024-01-01T00:00", df)
        result = get_cached("BTC/USDT", "2024-01-01T00:00")
        assert result is not None
        assert len(result) == len(df)

    def test_cache_miss_on_different_timestamp(self):
        df = _make_df()
        set_cached("BTC/USDT", "2024-01-01T00:00", df)
        result = get_cached("BTC/USDT", "2024-01-01T01:00")
        assert result is None

    def test_cache_miss_on_unknown_symbol(self):
        result = get_cached("UNKNOWN/USDT", "2024-01-01T00:00")
        assert result is None

    def test_invalidate_single(self):
        set_cached("BTC/USDT", "ts1", _make_df())
        set_cached("ETH/USDT", "ts2", _make_df())
        invalidate("BTC/USDT")
        assert get_cached("BTC/USDT", "ts1") is None
        assert get_cached("ETH/USDT", "ts2") is not None

    def test_invalidate_all(self):
        set_cached("BTC/USDT", "ts1", _make_df())
        set_cached("ETH/USDT", "ts2", _make_df())
        invalidate()
        assert get_cached("BTC/USDT", "ts1") is None
        assert get_cached("ETH/USDT", "ts2") is None


class TestCacheStats:
    def test_empty_stats(self):
        stats = cache_stats()
        assert stats["total_entries"] == 0
        assert stats["fresh_entries"] == 0

    def test_stats_after_insert(self):
        set_cached("BTC/USDT", "ts1", _make_df())
        stats = cache_stats()
        assert stats["total_entries"] == 1
        assert stats["fresh_entries"] == 1


class TestLRUEviction:
    """[Verbesserung #20] LRU-Eviction Tests."""

    def test_eviction_when_over_max_size(self):
        """Cache evicted älteste Einträge wenn MAX_CACHE_SIZE überschritten."""
        # Füge MAX_CACHE_SIZE + 5 Einträge ein
        for i in range(MAX_CACHE_SIZE + 5):
            set_cached(f"SYM{i}/USDT", f"ts{i}", _make_df())

        stats = cache_stats()
        # Cache sollte nicht größer als MAX_CACHE_SIZE sein
        assert stats["total_entries"] <= MAX_CACHE_SIZE

    def test_newest_entries_survive_eviction(self):
        """Die neuesten Einträge überleben die Eviction."""
        for i in range(MAX_CACHE_SIZE + 10):
            set_cached(f"SYM{i}/USDT", f"ts{i}", _make_df())

        # Die letzten Einträge sollten noch da sein
        last_idx = MAX_CACHE_SIZE + 9
        result = get_cached(f"SYM{last_idx}/USDT", f"ts{last_idx}")
        assert result is not None
