"""
╔══════════════════════════════════════════════════════════════╗
║  TREVLIX Tests – Technische Indikatoren                      ║
╚══════════════════════════════════════════════════════════════╝

Führe aus mit:  pytest tests/test_indicators.py -v
"""

import pytest
import numpy as np
import pandas as pd
import sys
import os

# Server-Modul im Pfad
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def make_ohlcv(n: int = 200, seed: int = 42) -> pd.DataFrame:
    """Erstellt synthetische OHLCV-Daten für Tests."""
    rng = np.random.default_rng(seed)
    close = 100 + np.cumsum(rng.normal(0, 1, n))
    close = np.clip(close, 1, None)
    high  = close * (1 + rng.uniform(0, 0.02, n))
    low   = close * (1 - rng.uniform(0, 0.02, n))
    open_ = close * (1 + rng.normal(0, 0.005, n))
    vol   = rng.uniform(1_000_000, 5_000_000, n)
    ts = pd.date_range("2024-01-01", periods=n, freq="1h")
    return pd.DataFrame({
        "open": open_, "high": high, "low": low,
        "close": close, "volume": vol,
    }, index=ts)


class TestComputeIndicators:
    """Tests für die compute_indicators Funktion."""

    def test_returns_dataframe(self):
        """compute_indicators soll einen DataFrame zurückgeben."""
        from server import compute_indicators
        df = make_ohlcv(200)
        result = compute_indicators(df.copy())
        assert result is not None
        assert isinstance(result, pd.DataFrame)

    def test_requires_minimum_rows(self):
        """Weniger als 80 Zeilen → None."""
        from server import compute_indicators
        df = make_ohlcv(50)
        result = compute_indicators(df.copy())
        assert result is None

    def test_ema_columns_exist(self):
        """EMA-Spalten müssen vorhanden sein."""
        from server import compute_indicators
        df = make_ohlcv(200)
        result = compute_indicators(df.copy())
        assert result is not None
        for col in ["ema8", "ema21", "ema50", "ema200"]:
            assert col in result.columns, f"Spalte {col} fehlt"

    def test_rsi_in_range(self):
        """RSI muss zwischen 0 und 100 liegen."""
        from server import compute_indicators
        df = make_ohlcv(200)
        result = compute_indicators(df.copy())
        assert result is not None
        rsi = result["rsi"].dropna()
        assert (rsi >= 0).all(), "RSI < 0 gefunden"
        assert (rsi <= 100).all(), "RSI > 100 gefunden"

    def test_macd_columns_exist(self):
        """MACD-Spalten müssen vorhanden sein."""
        from server import compute_indicators
        df = make_ohlcv(200)
        result = compute_indicators(df.copy())
        assert result is not None
        for col in ["macd", "macd_signal", "macd_hist"]:
            assert col in result.columns, f"Spalte {col} fehlt"

    def test_bollinger_bands_consistent(self):
        """Bollinger Bands: upper >= sma20 >= lower."""
        from server import compute_indicators
        df = make_ohlcv(200)
        result = compute_indicators(df.copy())
        assert result is not None
        assert (result["bb_upper"] >= result["sma20"]).all()
        assert (result["sma20"] >= result["bb_lower"]).all()

    def test_atr_positive(self):
        """ATR muss positiv sein."""
        from server import compute_indicators
        df = make_ohlcv(200)
        result = compute_indicators(df.copy())
        assert result is not None
        assert (result["atr14"].dropna() > 0).all()

    def test_volume_ratio_positive(self):
        """Volumen-Verhältnis muss positiv sein."""
        from server import compute_indicators
        df = make_ohlcv(200)
        result = compute_indicators(df.copy())
        assert result is not None
        vr = result["vol_ratio"].dropna()
        assert (vr > 0).all()


class TestStrategies:
    """Tests für die Trading-Strategien."""

    def _get_rows(self):
        from server import compute_indicators
        df = make_ohlcv(200)
        result = compute_indicators(df.copy())
        assert result is not None
        return result.iloc[-1], result.iloc[-2]

    def test_ema_trend_returns_valid_signal(self):
        from server import strat_ema_trend
        row, prev = self._get_rows()
        sig = strat_ema_trend(row, prev)
        assert sig in (-1, 0, 1)

    def test_rsi_stoch_returns_valid_signal(self):
        from server import strat_rsi_stoch
        row, prev = self._get_rows()
        sig = strat_rsi_stoch(row, prev)
        assert sig in (-1, 0, 1)

    def test_macd_returns_valid_signal(self):
        from server import strat_macd
        row, prev = self._get_rows()
        sig = strat_macd(row, prev)
        assert sig in (-1, 0, 1)

    def test_bollinger_returns_valid_signal(self):
        from server import strat_boll
        row, prev = self._get_rows()
        sig = strat_boll(row, prev)
        assert sig in (-1, 0, 1)

    def test_roc_returns_valid_signal(self):
        from server import strat_roc
        row, prev = self._get_rows()
        sig = strat_roc(row, prev)
        assert sig in (-1, 0, 1)


class TestIndicatorCache:
    """Tests für den Indicator-Cache."""

    def test_cache_miss_returns_none(self):
        from services.indicator_cache import get_cached, invalidate
        invalidate()
        result = get_cached("BTC/USDT", "2024-01-01 00:00:00")
        assert result is None

    def test_cache_stores_and_retrieves(self):
        from services.indicator_cache import get_cached, set_cached, invalidate
        invalidate()
        df = make_ohlcv(200)
        ts = "2024-01-01 12:00:00"
        set_cached("ETH/USDT", ts, df)
        result = get_cached("ETH/USDT", ts)
        assert result is not None
        assert len(result) == len(df)

    def test_cache_miss_on_different_timestamp(self):
        from services.indicator_cache import get_cached, set_cached, invalidate
        invalidate()
        df = make_ohlcv(200)
        set_cached("BTC/USDT", "2024-01-01 12:00:00", df)
        result = get_cached("BTC/USDT", "2024-01-01 13:00:00")
        assert result is None

    def test_cache_invalidate_specific(self):
        from services.indicator_cache import get_cached, set_cached, invalidate
        invalidate()
        df = make_ohlcv(200)
        ts = "2024-01-01 12:00:00"
        set_cached("BTC/USDT", ts, df)
        set_cached("ETH/USDT", ts, df)
        invalidate("BTC/USDT")
        assert get_cached("BTC/USDT", ts) is None
        assert get_cached("ETH/USDT", ts) is not None

    def test_cache_stats(self):
        from services.indicator_cache import set_cached, cache_stats, invalidate
        invalidate()
        df = make_ohlcv(200)
        set_cached("SOL/USDT", "ts1", df)
        stats = cache_stats()
        assert stats["total_entries"] >= 1
        assert "ttl_seconds" in stats
