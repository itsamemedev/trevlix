"""TREVLIX – Technische Indikatoren & Trading-Strategien.

Extrahiert aus server.py für bessere Modularisierung.
Enthält compute_indicators() und die 9 Trading-Strategien.

Verwendung:
    from services.strategies import compute_indicators, STRATEGIES, STRATEGY_NAMES
"""

import logging

import numpy as np
import pandas as pd

log = logging.getLogger("trevlix.strategies")

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
    if len(df) < 80:
        return None
    try:
        c = df["close"]
        h = df["high"]
        lo = df["low"]
        v = df["volume"]
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
        rm = df["rsi"].rolling(14)
        df["stoch_rsi"] = (df["rsi"] - rm.min()) / (rm.max() - rm.min()).replace(0, np.nan) * 100
        # MACD
        e12 = c.ewm(span=12, adjust=False).mean()
        e26 = c.ewm(span=26, adjust=False).mean()
        df["macd"] = e12 - e26
        df["macd_signal"] = df["macd"].ewm(span=9, adjust=False).mean()
        df["macd_hist"] = df["macd"] - df["macd_signal"]
        df["macd_hist_slope"] = df["macd_hist"].diff()
        # ROC
        df["roc10"] = c.pct_change(10) * 100
        df["roc20"] = c.pct_change(20) * 100
        # Bollinger
        std20 = c.rolling(20).std()
        df["bb_upper"] = df["sma20"] + 2 * std20
        df["bb_lower"] = df["sma20"] - 2 * std20
        df["bb_width"] = (df["bb_upper"] - df["bb_lower"]) / df["sma20"]
        df["bb_pct"] = (c - df["bb_lower"]) / (df["bb_upper"] - df["bb_lower"]).replace(0, np.nan)
        # ATR
        tr = pd.concat([h - lo, (h - c.shift()).abs(), (lo - c.shift()).abs()], axis=1).max(axis=1)
        df["atr14"] = tr.ewm(span=14, adjust=False).mean()
        df["atr_pct"] = df["atr14"] / c * 100
        # Volume
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
        # VWAP (20-period approximation)
        tp = (h + lo + c) / 3
        df["vwap"] = (tp * v).rolling(20).sum() / v.rolling(20).sum()
        df["price_vs_vwap"] = (c - df["vwap"]) / df["vwap"].replace(0, np.nan)
        # Composite
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
        log.debug(f"Indikator: {e}")
        return None


# ═══════════════════════════════════════════════════════════════════════════════
# 9 STRATEGIEN
# ═══════════════════════════════════════════════════════════════════════════════


def strat_ema_trend(r, p):
    if r["ema8"] > r["ema21"] > r["ema50"] and r["close"] > r["ema21"]:
        return 1
    if r["ema8"] < r["ema21"] < r["ema50"] and r["close"] < r["ema21"]:
        return -1
    return 0


def strat_rsi_stoch(r, p):
    rsi = r.get("rsi", 50)
    sr = r.get("stoch_rsi", 50)
    if rsi < 35 and sr < 25:
        return 1
    if rsi > 65 and sr > 75:
        return -1
    return 0


def strat_macd(r, p):
    cu = p["macd"] < p["macd_signal"] and r["macd"] > r["macd_signal"]
    cd = p["macd"] > p["macd_signal"] and r["macd"] < r["macd_signal"]
    if cu and r["macd"] < 0:
        return 1
    if cd and r["macd"] > 0:
        return -1
    return 0


def strat_boll(r, p):
    bp = r.get("bb_pct", 0.5)
    if bp < 0.05 and r["rsi"] < 40:
        return 1
    if bp > 0.95 and r["rsi"] > 60:
        return -1
    return 0


def strat_vol(r, p):
    vs = r.get("vol_ratio", 1) > 2.0
    up = r["close"] > r.get("ema21", r["close"]) and r["close"] > p["close"] * 1.005
    dn = r["close"] < r.get("ema21", r["close"]) and r["close"] < p["close"] * 0.995
    if vs and up:
        return 1
    if vs and dn:
        return -1
    return 0


def strat_obv(r, p):
    if r["obv"] > r["obv_ema"] and p["obv"] <= p["obv_ema"]:
        return 1
    if r["obv"] < r["obv_ema"] and p["obv"] >= p["obv_ema"]:
        return -1
    return 0


def strat_roc(r, p):
    r10 = r.get("roc10", 0)
    r20 = r.get("roc20", 0)
    if r10 > 3 and r20 > 5:
        return 1
    if r10 < -3 and r20 < -5:
        return -1
    return 0


def strat_ichimoku(r, p):
    above = r.get("ichi_above", 0)
    tenkan = r.get("ichi_tenkan", r["close"])
    kijun = r.get("ichi_kijun", r["close"])
    if above and tenkan > kijun and r["close"] > tenkan:
        return 1
    if not above and tenkan < kijun and r["close"] < tenkan:
        return -1
    return 0


def strat_vwap(r, p):
    pvw = r.get("price_vs_vwap", 0)
    rsi = r.get("rsi", 50)
    if pvw > 0.01 and rsi > 50:
        return 1
    if pvw < -0.01 and rsi < 50:
        return -1
    return 0


STRATEGIES = [
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
