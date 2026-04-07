"""Tests für app.core.trading_ops.fetch_markets."""

from __future__ import annotations

from types import SimpleNamespace

from app.core import trading_ops


class _MockExchange:
    def load_markets(self):
        return {
            "BTC/USDT": {"quote": "USDT", "active": True, "spot": True},
            "ETH/USDT": {"quote": "USDT", "active": True, "spot": True},
            "SOL/USDT": {"quote": "USDT", "active": True, "spot": True},
            "XRP/USD": {"quote": "USD", "active": True, "spot": True},
        }


def test_fetch_markets_keeps_symbols_without_ticker_volume():
    trading_ops.CONFIG = {
        "quote_currency": "USDT",
        "blacklist": [],
        "use_vol_filter": True,
        "min_volume_usdt": 1_000_000,
        "max_markets": 0,
    }
    trading_ops.sentiment_f = SimpleNamespace(get_trending=lambda: [])
    trading_ops.safe_fetch_tickers = lambda _ex, _symbols: {
        "BTC/USDT": {"quoteVolume": 2_000_000},
        "ETH/USDT": {"quoteVolume": 500_000},
        # SOL/USDT fehlt absichtlich in den Ticker-Daten
    }
    trading_ops._save_market_cache = lambda _m: None

    markets = trading_ops.fetch_markets(_MockExchange())

    assert "BTC/USDT" in markets
    assert "SOL/USDT" in markets
    assert "ETH/USDT" not in markets
    assert "XRP/USD" not in markets


def test_fetch_markets_respects_max_markets():
    trading_ops.CONFIG = {
        "quote_currency": "USDT",
        "blacklist": [],
        "use_vol_filter": False,
        "max_markets": 2,
    }
    trading_ops.sentiment_f = SimpleNamespace(get_trending=lambda: ["SOL/USDT"])
    trading_ops.safe_fetch_tickers = lambda _ex, _symbols: {}
    trading_ops._save_market_cache = lambda _m: None

    markets = trading_ops.fetch_markets(_MockExchange())

    assert len(markets) == 2
    assert markets[0] == "SOL/USDT"
