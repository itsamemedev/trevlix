"""Tests für die Rehydration offener Positionen beim Neustart.

Verifiziert, dass ``BotState`` beim Start nicht nur geschlossene Trades,
sondern auch offene Positionen aus ``trade_positions`` (``status='open'``)
in den In-Memory-State zurücklädt und die Paper-Balance konsistent
rekonstruiert. Ohne diesen Schritt wären offene Positionen und der
Kontostand nach jedem Neustart verloren.
"""

from __future__ import annotations

import json
import logging

import app.core.trading_classes as tc


class _DB:
    def __init__(self, trades=None, positions=None):
        self._trades = trades or []
        self._positions = positions or []

    def load_trades(self, limit=500):
        return list(self._trades)

    def load_open_positions(self, user_id=None, trade_mode=None):
        return [
            p for p in self._positions if (trade_mode is None or p.get("trade_mode") == trade_mode)
        ]


def _make_state(db, **cfg):
    base = {"exchange": "binance", "paper_trading": True, "paper_balance": 10000}
    base.update(cfg)
    tc.CONFIG = base
    tc.log = logging.getLogger("test_rehydration")
    return tc.BotState(db)


class TestRehydrateOpenPositions:
    def test_no_loader_method_is_safe(self):
        class _MinimalDB:
            def load_trades(self, limit=500):
                return []

        state = _make_state(_MinimalDB())
        assert state.positions == {}

    def test_no_open_positions(self):
        state = _make_state(_DB())
        assert state.positions == {}
        assert state.short_positions == {}

    def test_long_positions_rehydrated(self):
        positions = [
            {
                "symbol": "BTC/USDT",
                "side": "long",
                "qty": 0.5,
                "entry_price": 40000.0,
                "invested": 2000.0,
                "stop_loss": 39000.0,
                "take_profit": 44000.0,
                "trade_mode": "paper",
                "exchange": "binance",
                "opened_at": "2026-06-01T12:00:00",
                "meta_json": json.dumps({"confidence": 0.7, "algo_reason": "rsi"}),
            }
        ]
        state = _make_state(_DB(positions=positions))
        assert "BTC/USDT" in state.positions
        pos = state.positions["BTC/USDT"]
        assert pos["entry"] == 40000.0
        assert pos["qty"] == 0.5
        assert pos["invested"] == 2000.0
        assert pos["sl"] == 39000.0
        assert pos["tp"] == 44000.0
        assert pos["confidence"] == 0.7
        assert pos["rehydrated"] is True

    def test_short_positions_routed_separately(self):
        positions = [
            {
                "symbol": "ETH/USDT",
                "side": "short",
                "qty": 1.0,
                "entry_price": 2000.0,
                "invested": 500.0,
                "trade_mode": "paper",
            }
        ]
        state = _make_state(_DB(positions=positions))
        assert "ETH/USDT" in state.short_positions
        assert state.short_positions["ETH/USDT"]["side"] == "short"
        assert state.positions == {}

    def test_paper_balance_reconstructed(self):
        # Startkapital 10000, eine geschlossene Trade mit +300 PnL,
        # eine offene Position mit 2000 gebundenem Kapital.
        trades = [{"pnl": 300.0}]
        positions = [
            {
                "symbol": "BTC/USDT",
                "side": "long",
                "invested": 2000.0,
                "entry_price": 40000.0,
                "trade_mode": "paper",
            }
        ]
        state = _make_state(_DB(trades=trades, positions=positions))
        # 10000 + 300 - 2000 = 8300
        assert state.balance == 8300.0

    def test_paper_balance_never_negative(self):
        positions = [
            {
                "symbol": "BTC/USDT",
                "side": "long",
                "invested": 999999.0,
                "entry_price": 1.0,
                "trade_mode": "paper",
            }
        ]
        state = _make_state(_DB(positions=positions))
        assert state.balance == 0.0

    def test_live_mode_balance_untouched(self):
        positions = [
            {
                "symbol": "BTC/USDT",
                "side": "long",
                "invested": 2000.0,
                "entry_price": 40000.0,
                "trade_mode": "live",
            }
        ]
        state = _make_state(_DB(positions=positions), paper_trading=False)
        # Live: Balance wird NICHT rekonstruiert (kommt aus Exchange-Wallet),
        # Default-Init bleibt erhalten.
        assert state.balance == 10000.0
        assert "BTC/USDT" in state.positions

    def test_malformed_meta_json_does_not_crash(self):
        positions = [
            {
                "symbol": "BTC/USDT",
                "side": "long",
                "entry_price": 40000.0,
                "invested": 100.0,
                "trade_mode": "paper",
                "meta_json": "{not valid json",
            }
        ]
        state = _make_state(_DB(positions=positions))
        assert state.positions["BTC/USDT"]["confidence"] == 0.0

    def test_loader_exception_is_swallowed(self):
        class _BrokenDB:
            def load_trades(self, limit=500):
                return []

            def load_open_positions(self, user_id=None, trade_mode=None):
                raise RuntimeError("db down")

        state = _make_state(_BrokenDB())
        assert state.positions == {}
