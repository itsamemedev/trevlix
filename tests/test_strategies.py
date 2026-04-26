"""
TREVLIX – Unit Tests für Trading-Strategien (Verbesserung #43)
===============================================================
Tests für alle 9 Voting-Strategien mit definierten Marktszenarien.
"""

import os

# ── Indicator-Berechnung laden ───────────────────────────────────────────────
# Wir importieren die Strategie-Funktionen direkt
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture
def bullish_row():
    """Simuliert ein bullishes Marktumfeld."""
    return {
        "close": 31000,
        "high": 31200,
        "low": 30800,
        "ema8": 30900,
        "ema21": 30700,
        "ema50": 30500,
        "ema200": 30000,
        "rsi": 55,
        "stoch_rsi": 50,
        "macd": 50,
        "macd_signal": 30,
        "macd_hist": 20,
        "macd_hist_slope": 5,
        "bb_pct": 0.6,
        "bb_upper": 31500,
        "bb_lower": 30200,
        "sma20": 30850,
        "vol_ratio": 1.2,
        "obv": 100000,
        "obv_ema": 95000,
        "roc10": 4.0,
        "roc20": 6.0,
        "ichi_above": 1,
        "ichi_tenkan": 30800,
        "ichi_kijun": 30600,
        "price_vs_vwap": 0.02,
        "vwap": 30700,
        "ema_alignment": 0.8,
        "price_vs_ema21": 0.01,
        "atr14": 200,
        "atr_pct": 0.65,
        "vol_ma20": 5000,
        "returns": 0.01,
    }


@pytest.fixture
def bearish_row():
    """Simuliert ein bearishes Marktumfeld."""
    return {
        "close": 29000,
        "high": 29200,
        "low": 28800,
        "ema8": 29200,
        "ema21": 29500,
        "ema50": 29800,
        "ema200": 30500,
        "rsi": 70,
        "stoch_rsi": 80,
        "macd": -50,
        "macd_signal": -30,
        "macd_hist": -20,
        "macd_hist_slope": -5,
        "bb_pct": 0.96,
        "bb_upper": 29300,
        "bb_lower": 28700,
        "sma20": 29000,
        "vol_ratio": 2.5,
        "obv": 80000,
        "obv_ema": 85000,
        "roc10": -4.0,
        "roc20": -6.0,
        "ichi_above": 0,
        "ichi_tenkan": 29300,
        "ichi_kijun": 29500,
        "price_vs_vwap": -0.02,
        "vwap": 29500,
        "ema_alignment": -0.8,
        "price_vs_ema21": -0.01,
        "atr14": 250,
        "atr_pct": 0.86,
        "vol_ma20": 4000,
        "returns": -0.01,
    }


@pytest.fixture
def neutral_row():
    """Simuliert ein neutrales Marktumfeld."""
    return {
        "close": 30000,
        "high": 30100,
        "low": 29900,
        "ema8": 30010,
        "ema21": 30000,
        "ema50": 29990,
        "ema200": 30000,
        "rsi": 50,
        "stoch_rsi": 50,
        "macd": 0,
        "macd_signal": 0,
        "macd_hist": 0,
        "macd_hist_slope": 0,
        "bb_pct": 0.5,
        "bb_upper": 30500,
        "bb_lower": 29500,
        "sma20": 30000,
        "vol_ratio": 1.0,
        "obv": 90000,
        "obv_ema": 90000,
        "roc10": 0.5,
        "roc20": 1.0,
        "ichi_above": 1,
        "ichi_tenkan": 30000,
        "ichi_kijun": 30000,
        "price_vs_vwap": 0.0,
        "vwap": 30000,
        "ema_alignment": 0.0,
        "price_vs_ema21": 0.0,
        "atr14": 150,
        "atr_pct": 0.5,
        "vol_ma20": 5000,
        "returns": 0.001,
    }


class TestEMATrend:
    """Tests für EMA-Trend-Strategie."""

    def test_buy_signal(self, bullish_row):
        from services.strategies import strat_ema_trend

        # EMA8 > EMA21 > EMA50 + Close > EMA21 → Buy
        assert strat_ema_trend(bullish_row, bullish_row) == 1

    def test_sell_signal(self, bearish_row):
        from services.strategies import strat_ema_trend

        # EMA8 < EMA21 < EMA50 + Close < EMA21 → Sell
        assert strat_ema_trend(bearish_row, bearish_row) == -1

    def test_neutral(self, neutral_row):
        from services.strategies import strat_ema_trend

        assert strat_ema_trend(neutral_row, neutral_row) == 0


class TestRSIStochastic:
    """Tests für RSI-Stochastic-Strategie."""

    def test_oversold_buy(self, bullish_row):
        from services.strategies import strat_rsi_stoch

        oversold = {**bullish_row, "rsi": 28, "stoch_rsi": 15}
        assert strat_rsi_stoch(oversold, bullish_row) == 1

    def test_overbought_sell(self, bearish_row):
        from services.strategies import strat_rsi_stoch

        overbought = {**bearish_row, "rsi": 72, "stoch_rsi": 82}
        assert strat_rsi_stoch(overbought, bearish_row) == -1

    def test_neutral_rsi(self, neutral_row):
        from services.strategies import strat_rsi_stoch

        assert strat_rsi_stoch(neutral_row, neutral_row) == 0


class TestMACD:
    """Tests für MACD-Kreuzung-Strategie."""

    def test_bullish_crossover(self):
        from services.strategies import strat_macd

        prev = {"macd": -5, "macd_signal": -3}
        curr = {"macd": -2, "macd_signal": -3}  # MACD crosses above signal, below 0
        assert strat_macd(curr, prev) == 1

    def test_bearish_crossover(self):
        from services.strategies import strat_macd

        prev = {"macd": 5, "macd_signal": 3}
        curr = {"macd": 2, "macd_signal": 3}  # MACD crosses below signal, above 0
        assert strat_macd(curr, prev) == -1


class TestBollinger:
    """Tests für Bollinger-Band-Strategie."""

    def test_lower_band_buy(self, bullish_row):
        from services.strategies import strat_boll

        lower = {**bullish_row, "bb_pct": 0.02, "rsi": 35}
        assert strat_boll(lower, bullish_row) == 1

    def test_upper_band_sell(self, bearish_row):
        from services.strategies import strat_boll

        upper = {**bearish_row, "bb_pct": 0.97, "rsi": 65}
        assert strat_boll(upper, bearish_row) == -1


class TestVolume:
    """Tests für Volumen-Ausbruch-Strategie."""

    def test_volume_breakout_up(self):
        from services.strategies import strat_vol

        curr = {"vol_ratio": 2.5, "close": 31000, "ema21": 30500}
        prev = {"close": 30800}
        assert strat_vol(curr, prev) == 1

    def test_volume_breakout_down(self):
        from services.strategies import strat_vol

        curr = {"vol_ratio": 2.5, "close": 29000, "ema21": 29500}
        prev = {"close": 29200}
        assert strat_vol(curr, prev) == -1


class TestROCMomentum:
    """Tests für ROC-Momentum-Strategie."""

    def test_strong_momentum_up(self, bullish_row):
        from services.strategies import strat_roc

        strong = {**bullish_row, "roc10": 5, "roc20": 8}
        assert strat_roc(strong, bullish_row) == 1

    def test_strong_momentum_down(self, bearish_row):
        from services.strategies import strat_roc

        weak = {**bearish_row, "roc10": -5, "roc20": -8}
        assert strat_roc(weak, bearish_row) == -1


class TestIchimoku:
    """Tests für Ichimoku-Strategie."""

    def test_bullish_ichimoku(self, bullish_row):
        from services.strategies import strat_ichimoku

        assert strat_ichimoku(bullish_row, bullish_row) == 1

    def test_bearish_ichimoku(self, bearish_row):
        from services.strategies import strat_ichimoku

        assert strat_ichimoku(bearish_row, bearish_row) == -1


class TestVWAP:
    """Tests für VWAP-Strategie."""

    def test_above_vwap_buy(self, bullish_row):
        from services.strategies import strat_vwap

        assert strat_vwap(bullish_row, bullish_row) == 1

    def test_below_vwap_sell(self, bearish_row):
        from services.strategies import strat_vwap

        below = {**bearish_row, "price_vs_vwap": -0.02, "rsi": 40}
        assert strat_vwap(below, bearish_row) == -1


class TestATRAdaptiveThresholds:
    """Verifies that ATR-based threshold scaling works correctly for each strategy."""

    def test_rsi_stoch_high_atr_requires_deeper_oversold(self):
        from services.strategies import strat_rsi_stoch

        # At atr_pct=3, oversold_rsi = max(25, 35 - 9.9) ≈ 25.1 — RSI 24 passes, RSI 27 doesn't
        row_passes = {"rsi": 24, "stoch_rsi": 10, "atr_pct": 3.0}
        row_blocks = {"rsi": 27, "stoch_rsi": 10, "atr_pct": 3.0}
        assert strat_rsi_stoch(row_passes, {}) == 1
        assert strat_rsi_stoch(row_blocks, {}) == 0

    def test_rsi_stoch_low_atr_uses_base_threshold(self):
        from services.strategies import strat_rsi_stoch

        # At atr_pct=0, oversold_rsi = 35, so RSI 34 passes
        row = {"rsi": 34, "stoch_rsi": 20, "atr_pct": 0.0}
        assert strat_rsi_stoch(row, {}) == 1

    def test_roc_high_atr_raises_threshold(self):
        from services.strategies import strat_roc

        # At atr_pct=3, r10_min=3.0, r20_min=5.0 — values just below threshold blocked
        row_passes = {"roc10": 3.5, "roc20": 5.5, "atr_pct": 3.0}
        row_blocks = {"roc10": 2.5, "roc20": 4.5, "atr_pct": 3.0}
        assert strat_roc(row_passes, {}) == 1
        assert strat_roc(row_blocks, {}) == 0

    def test_vol_high_atr_raises_spike_threshold(self):
        from services.strategies import strat_vol

        # At atr_pct=3, spike_min=min(3.0, 2.9)=2.9 — vol_ratio 2.5 is blocked
        row_blocked = {"vol_ratio": 2.5, "atr_pct": 3.0, "close": 100, "ema21": 90}
        prev = {"close": 99}
        assert strat_vol(row_blocked, prev) == 0
        # vol_ratio 3.0 passes the spike check
        row_passes = {**row_blocked, "vol_ratio": 3.0}
        assert strat_vol(row_passes, prev) == 1

    def test_vwap_high_atr_raises_deviation_threshold(self):
        from services.strategies import strat_vwap

        # At atr_pct=5, dev_min=min(0.03, 0.005+0.025)=0.03 — pvw 0.025 blocked
        row_blocked = {"price_vs_vwap": 0.025, "rsi": 60, "atr_pct": 5.0}
        row_passes = {"price_vs_vwap": 0.035, "rsi": 60, "atr_pct": 5.0}
        assert strat_vwap(row_blocked, {}) == 0
        assert strat_vwap(row_passes, {}) == 1

    def test_boll_high_atr_tightens_band_threshold(self):
        from services.strategies import strat_boll

        # At atr_pct=3, low_band=max(0.02, 0.05-0.03)=0.02 — bb_pct 0.015 passes
        row = {"bb_pct": 0.015, "rsi": 35, "atr_pct": 3.0}
        assert strat_boll(row, {}) == 1
