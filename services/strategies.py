"""TREVLIX – Technische Indikatoren & Trading-Strategien.

Enthält compute_indicators() und die 9 Trading-Strategien.

Verwendung:
    from services.strategies import compute_indicators, STRATEGIES, STRATEGY_NAMES
"""

import logging
import math
from typing import Any

import numpy as np
import pandas as pd

log = logging.getLogger("trevlix.strategies")

# Row type alias — a dict of indicator values (current or previous candle)
Row = dict[str, Any]


def _nz(val: object, default: float) -> float:
    """Return *val* as float, or *default* if None / NaN / invalid.

    Replaces the broken ``float(row.get(k, d) or d)`` pattern where
    a legitimate ``0.0`` would be treated as missing because ``0.0``
    is falsy in Python.
    """
    if val is None:
        return default
    try:
        f = float(val)
        return default if math.isnan(f) else f
    except (TypeError, ValueError):
        return default


STRATEGY_NAMES = [
    "EMA-Trend",
    "RSI-Stochastic",
    "MACD-Kreuzung",
    "Bollinger",
    "Volumen-Ausbruch",
    "OBV-Trend",
    "ROC-Momentum",
    "Ichimoku",
    "VWAP",
]


def compute_indicators(df: pd.DataFrame) -> pd.DataFrame | None:
    """Berechnet alle technischen Indikatoren auf einem OHLCV-DataFrame.

    Args:
        df: DataFrame mit Spalten 'open', 'high', 'low', 'close', 'volume'.

    Returns:
        DataFrame mit Indikatoren oder None bei zu wenig Daten / Fehler.
    """
    if df is None or df.empty or len(df) < 80:
        return None
    try:
        df = df.copy()
        c = df["close"]
        h = df["high"]
        lo = df["low"]
        v = df["volume"]

        # EMAs
        df["ema8"] = c.ewm(span=8, adjust=False).mean()
        df["ema21"] = c.ewm(span=21, adjust=False).mean()
        df["ema50"] = c.ewm(span=50, adjust=False).mean()
        df["ema200"] = c.ewm(span=200, adjust=False).mean()
        df["sma20"] = c.rolling(20).mean()

        # RSI
        delta = c.diff()
        gain = delta.clip(lower=0).ewm(span=14, adjust=False).mean()
        loss = (-delta.clip(upper=0)).ewm(span=14, adjust=False).mean()
        df["rsi"] = 100 - (100 / (1 + gain / loss.replace(0, np.nan)))
        df["rsi"] = df["rsi"].fillna(50.0)
        rm = df["rsi"].rolling(14)
        rsi_range = (rm.max() - rm.min()).replace(0, np.nan)
        df["stoch_rsi"] = ((df["rsi"] - rm.min()) / rsi_range) * 100
        df["stoch_rsi"] = df["stoch_rsi"].fillna(50.0)

        # MACD
        e12 = c.ewm(span=12, adjust=False).mean()
        e26 = c.ewm(span=26, adjust=False).mean()
        df["macd"] = e12 - e26
        df["macd_signal"] = df["macd"].ewm(span=9, adjust=False).mean()
        df["macd_hist"] = df["macd"] - df["macd_signal"]
        df["macd_hist_slope"] = df["macd_hist"].diff()

        # Rate of Change
        df["roc10"] = c.pct_change(10) * 100
        df["roc20"] = c.pct_change(20) * 100

        # Bollinger Bands
        std20 = c.rolling(20).std()
        df["bb_upper"] = df["sma20"] + 2 * std20
        df["bb_lower"] = df["sma20"] - 2 * std20
        sma20_safe = df["sma20"].replace(0, np.nan)
        df["bb_width"] = (df["bb_upper"] - df["bb_lower"]) / sma20_safe
        df["bb_width"] = df["bb_width"].fillna(0.0)
        bb_range = (df["bb_upper"] - df["bb_lower"]).replace(0, np.nan)
        df["bb_pct"] = (c - df["bb_lower"]) / bb_range
        df["bb_pct"] = df["bb_pct"].fillna(0.5)

        # ATR
        tr = pd.concat([h - lo, (h - c.shift()).abs(), (lo - c.shift()).abs()], axis=1).max(axis=1)
        df["atr14"] = tr.ewm(span=14, adjust=False).mean()
        df["atr_pct"] = df["atr14"] / c.replace(0, np.nan) * 100

        # Volume indicators
        df["vol_ma20"] = v.rolling(20).mean()
        df["vol_ratio"] = v / df["vol_ma20"].replace(0, np.nan)
        df["obv"] = (np.sign(c.diff()) * v).cumsum()
        df["obv_ema"] = df["obv"].ewm(span=20, adjust=False).mean()

        # Ichimoku (simplified)
        hi9 = h.rolling(9).max()
        lo9 = lo.rolling(9).min()
        hi26 = h.rolling(26).max()
        lo26 = lo.rolling(26).min()
        df["ichi_tenkan"] = (hi9 + lo9) / 2
        df["ichi_kijun"] = (hi26 + lo26) / 2
        df["ichi_above"] = (c > df["ichi_kijun"]).astype(float)

        # VWAP (20-period rolling approximation)
        tp = (h + lo + c) / 3
        df["vwap"] = (tp * v).rolling(20).sum() / v.rolling(20).sum().replace(0, np.nan)
        df["price_vs_vwap"] = (c - df["vwap"]) / df["vwap"].replace(0, np.nan)

        # Composite alignment score
        df["ema_alignment"] = (
            np.sign(df["ema8"] - df["ema21"]) * 0.4
            + np.sign(df["ema21"] - df["ema50"]) * 0.4
            + np.sign(df["ema50"] - df["ema200"]) * 0.2
        )
        df["price_vs_ema21"] = (c - df["ema21"]) / df["ema21"].replace(0, np.nan)
        df["returns"] = c.pct_change()

        result = df.dropna()
        return result if len(result) >= 20 else None
    except Exception as e:
        log.warning(f"compute_indicators failed: {e}", exc_info=True)
        return None


# ═══════════════════════════════════════════════════════════════════════════════
# 9 STRATEGIEN
# Each function signature: (current_row: Row, prev_row: Row) -> int
# Returns: 1 = buy, -1 = sell, 0 = neutral
# All dict accesses on `prev_row` use .get() to guard against incomplete rows.
# ═══════════════════════════════════════════════════════════════════════════════


def strat_ema_trend(r: Row, p: Row) -> int:
    """EMA-Alignment: alle drei EMAs stacken in Trendrichtung."""
    ema8 = _nz(r.get("ema8"), 0.0)
    ema21 = _nz(r.get("ema21"), 0.0)
    ema50 = _nz(r.get("ema50"), 0.0)
    close = _nz(r.get("close"), 0.0)
    if close <= 0 or ema21 <= 0:
        return 0
    if ema8 > ema21 > ema50 and close > ema21:
        return 1
    if ema8 < ema21 < ema50 and close < ema21:
        return -1
    return 0


def strat_rsi_stoch(r: Row, p: Row) -> int:
    """RSI + Stochastic RSI oversold/overbought filter with ATR-adaptive thresholds."""
    rsi = _nz(r.get("rsi"), 50.0)
    sr = _nz(r.get("stoch_rsi"), 50.0)
    atr = _nz(r.get("atr_pct"), 0.0)
    oversold_rsi = max(25.0, 35.0 - atr * 3.3)
    overbought_rsi = min(75.0, 65.0 + atr * 3.3)
    oversold_sr = max(15.0, 25.0 - atr * 3.3)
    overbought_sr = min(85.0, 75.0 + atr * 3.3)
    if rsi < oversold_rsi and sr < oversold_sr:
        return 1
    if rsi > overbought_rsi and sr > overbought_sr:
        return -1
    return 0


def strat_macd(r: Row, p: Row) -> int:
    """MACD-Kreuzung: Signal-Linie Crossover mit Null-Linien-Filter."""
    macd_cur = _nz(r.get("macd"), 0.0)
    sig_cur = _nz(r.get("macd_signal"), 0.0)
    macd_prev = _nz(p.get("macd"), macd_cur)
    sig_prev = _nz(p.get("macd_signal"), sig_cur)

    crossed_up = macd_prev < sig_prev and macd_cur > sig_cur
    crossed_dn = macd_prev > sig_prev and macd_cur < sig_cur

    # Bullish crossover below zero line = stronger signal
    if crossed_up and macd_cur < 0:
        return 1
    # Bearish crossover above zero line = stronger signal
    if crossed_dn and macd_cur > 0:
        return -1
    return 0


def strat_boll(r: Row, p: Row) -> int:
    """Bollinger-Band mean-reversion: near band edges with RSI confirmation and ATR-adaptive thresholds."""
    bp = _nz(r.get("bb_pct"), 0.5)
    rsi = _nz(r.get("rsi"), 50.0)
    atr = _nz(r.get("atr_pct"), 0.0)
    low_band = max(0.02, 0.05 - atr * 0.01)
    high_band = min(0.98, 0.95 + atr * 0.01)
    if bp < low_band and rsi < 40:
        return 1
    if bp > high_band and rsi > 60:
        return -1
    return 0


def strat_vol(r: Row, p: Row) -> int:
    """Volumen-Ausbruch: high-volume candle in EMA-consistent direction with ATR-adaptive spike threshold.

    Bug fixed: previously used r.get("ema21", r["close"]) which made
    `close > close` (always False) when ema21 was absent. Now uses 0.0
    as fallback so the ema21 condition degrades gracefully to `close > 0`.
    The prev-row close returns 0 if missing (skip signal).
    """
    atr = _nz(r.get("atr_pct"), 0.0)
    spike_min = min(3.0, 2.0 + atr * 0.3)
    vol_spike = _nz(r.get("vol_ratio"), 1.0) > spike_min
    if not vol_spike:
        return 0

    close = r.get("close", 0.0)
    ema21 = r.get("ema21", 0.0)
    prev_close = p.get("close")
    if prev_close is None or prev_close <= 0 or close <= 0 or ema21 <= 0:
        return 0

    above_ema = close > ema21
    below_ema = close < ema21

    if above_ema and close > prev_close * 1.005:
        return 1
    if below_ema and close < prev_close * 0.995:
        return -1
    return 0


def strat_obv(r: Row, p: Row) -> int:
    """OBV momentum crossover with EMA."""
    obv_cur = _nz(r.get("obv"), 0.0)
    obv_ema_cur = _nz(r.get("obv_ema"), obv_cur)
    obv_prev = _nz(p.get("obv"), obv_cur)
    obv_ema_prev = _nz(p.get("obv_ema"), obv_ema_cur)

    if obv_cur > obv_ema_cur and obv_prev <= obv_ema_prev:
        return 1
    if obv_cur < obv_ema_cur and obv_prev >= obv_ema_prev:
        return -1
    return 0


def strat_roc(r: Row, p: Row) -> int:
    """ROC-Momentum: dual-timeframe rate-of-change with ATR-adaptive thresholds."""
    r10 = _nz(r.get("roc10"), 0.0)
    r20 = _nz(r.get("roc20"), 0.0)
    atr = _nz(r.get("atr_pct"), 0.0)
    r10_min = 1.5 + atr * 0.5
    r20_min = 2.0 + atr * 1.0
    if r10 > r10_min and r20 > r20_min:
        return 1
    if r10 < -r10_min and r20 < -r20_min:
        return -1
    return 0


def strat_ichimoku(r: Row, p: Row) -> int:
    """Ichimoku cloud: price vs kijun + tenkan/kijun alignment."""
    above = r.get("ichi_above", 0.0)
    close = _nz(r.get("close"), 0.0)
    tenkan = _nz(r.get("ichi_tenkan"), close)
    kijun = _nz(r.get("ichi_kijun"), close)

    if above and tenkan > kijun and close > tenkan:
        return 1
    if not above and tenkan < kijun and close < tenkan:
        return -1
    return 0


def strat_vwap(r: Row, p: Row) -> int:
    """VWAP deviation with RSI trend confirmation and ATR-adaptive deviation threshold."""
    pvw = _nz(r.get("price_vs_vwap"), 0.0)
    rsi = _nz(r.get("rsi"), 50.0)
    atr = _nz(r.get("atr_pct"), 0.0)
    dev_min = min(0.03, 0.005 + atr * 0.005)
    if pvw > dev_min and rsi > 50:
        return 1
    if pvw < -dev_min and rsi < 50:
        return -1
    return 0


STRATEGIES: list[tuple[str, Any]] = [
    ("EMA-Trend", strat_ema_trend),
    ("RSI-Stochastic", strat_rsi_stoch),
    ("MACD-Kreuzung", strat_macd),
    ("Bollinger", strat_boll),
    ("Volumen-Ausbruch", strat_vol),
    ("OBV-Trend", strat_obv),
    ("ROC-Momentum", strat_roc),
    ("Ichimoku", strat_ichimoku),
    ("VWAP", strat_vwap),
]
