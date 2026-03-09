"""
TREVLIX – pytest conftest.py
=============================
Gemeinsame Fixtures und Konfiguration für alle Unit-Tests.

Verwendung in Tests:
    def test_something(sample_ohlcv, encryption_key):
        ...
"""

import os

import numpy as np
import pandas as pd
import pytest


# ── Umgebungsvariablen für Tests ───────────────────────────────────────────────
@pytest.fixture(autouse=True)
def set_test_env(monkeypatch):
    """Setzt sichere Test-Umgebungsvariablen für alle Tests."""
    # Valider Fernet-Key: URL-safe base64, exakt 32 Bytes decoded (test-key-for-unit-tests-12345678)
    monkeypatch.setenv("ENCRYPTION_KEY", "dGVzdC1rZXktZm9yLXVuaXQtdGVzdHMtMTIzNDU2Nzg=")
    monkeypatch.setenv("JWT_SECRET", "test-jwt-secret-not-for-production")
    monkeypatch.setenv("SECRET_KEY", "test-flask-secret-not-for-production")
    monkeypatch.setenv("PAPER_TRADING", "true")
    monkeypatch.setenv("LANGUAGE", "de")


# ── OHLCV Test-Daten ───────────────────────────────────────────────────────────
@pytest.fixture
def sample_ohlcv() -> pd.DataFrame:
    """Erzeugt einen realistischen OHLCV-DataFrame für Tests."""
    np.random.seed(42)
    n = 200

    # Simulierter Preisverlauf (Random Walk)
    close = 30000 + np.cumsum(np.random.randn(n) * 100)
    high = close + np.abs(np.random.randn(n) * 50)
    low = close - np.abs(np.random.randn(n) * 50)
    open_ = close + np.random.randn(n) * 30
    volume = np.abs(np.random.randn(n) * 1000) + 500

    timestamps = pd.date_range("2025-01-01", periods=n, freq="1h")

    return pd.DataFrame(
        {
            "timestamp": timestamps,
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
        }
    )


@pytest.fixture
def small_ohlcv(sample_ohlcv) -> pd.DataFrame:
    """Kleiner OHLCV-DataFrame (50 Kerzen) für schnelle Tests."""
    return sample_ohlcv.head(50).reset_index(drop=True)


# ── Verschlüsselungs-Fixtures ──────────────────────────────────────────────────
@pytest.fixture
def encryption_key() -> str:
    """Gibt den Test-Encryption-Key zurück."""
    return os.environ["ENCRYPTION_KEY"]


@pytest.fixture
def sample_api_key() -> str:
    """Beispiel-API-Key für Verschlüsselungstests."""
    return "test-api-key-1234567890abcdef"


# ── Trade-Daten Fixtures ───────────────────────────────────────────────────────
@pytest.fixture
def sample_trade() -> dict:
    """Beispiel-Trade-Daten."""
    return {
        "symbol": "BTC/USDT",
        "entry": 30000.0,
        "exit_price": 31500.0,
        "qty": 0.1,
        "pnl": 150.0,
        "pnl_pct": 5.0,
        "reason": "EMA-Trend",
        "confidence": 0.75,
        "win_prob": 0.68,
        "regime": "bull",
        "trade_type": "long",
    }


@pytest.fixture
def sample_trades(sample_trade) -> list:
    """Liste von 10 Beispiel-Trades."""
    trades = []
    for i in range(10):
        t = sample_trade.copy()
        t["pnl"] = 150.0 if i % 3 != 0 else -80.0  # 6 Wins, 4 Losses (i=0,3,6,9 → loss)
        t["pnl_pct"] = 5.0 if i % 3 != 0 else -2.5
        trades.append(t)
    return trades
