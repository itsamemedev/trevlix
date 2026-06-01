"""Tests für unabhängige Multi-Exchange-Konten + Paper/Live pro Exchange.

Stellt sicher, dass mehrere Exchanges gleichzeitig und unabhängig voneinander
handeln können (eigene Balance, eigene Positionen) und jeder seinen eigenen
Modus (paper/live) hat – während die Legacy-Single-Account-Facade unverändert
auf das Primärkonto zeigt.
"""

from __future__ import annotations

import threading

import app.core.trading_classes as tc


class _DB:
    def load_trades(self, limit=500):
        return []


def _make_state(**cfg):
    base = {"exchange": "binance", "paper_trading": True, "paper_balance": 10000}
    base.update(cfg)
    tc.CONFIG = base
    return tc.BotState(_DB())


class TestExchangeAccount:
    def test_account_defaults(self):
        acc = tc.ExchangeAccount("binance", "paper", 500.0)
        assert acc.name == "binance"
        assert acc.mode == "paper"
        assert acc.balance == 500.0
        assert acc.initial_balance == 500.0
        assert acc.positions == {}

    def test_mode_normalised(self):
        assert tc.ExchangeAccount("x", "LIVE", 0).mode == "live"
        assert tc.ExchangeAccount("x", "anything", 0).mode == "paper"


class TestPrimaryFacade:
    def test_facade_routes_to_primary(self):
        st = _make_state()
        assert st.balance == 10000
        st.balance = 9000
        assert st.primary_account.balance == 9000
        st.positions["BTC/USDT"] = {"qty": 1}
        assert st.primary_account.positions["BTC/USDT"] == {"qty": 1}

    def test_current_mode_follows_global_flag_off_loop(self):
        st = _make_state(paper_trading=False)
        # No active account in this thread → global flag decides
        assert st.current_mode() == "live"
        tc.CONFIG["paper_trading"] = True
        assert st.current_mode() == "paper"


class TestIndependentExchanges:
    def test_same_symbol_no_collision(self):
        st = _make_state()
        st.get_account("binance").positions["BTC/USDT"] = {"qty": 1, "entry": 100}
        st.get_account("bybit", mode="live").positions["BTC/USDT"] = {"qty": 2, "entry": 200}
        assert st.get_account("binance").positions["BTC/USDT"]["qty"] == 1
        assert st.get_account("bybit").positions["BTC/USDT"]["qty"] == 2

    def test_total_balance_aggregates(self):
        st = _make_state()
        st.get_account("bybit", mode="live").balance = 500.0
        assert st.total_balance() == 10500.0

    def test_use_account_scopes_facade_and_mode(self):
        st = _make_state()
        bybit = st.get_account("bybit", mode="live")
        bybit.balance = 500.0
        with st.use_account("bybit"):
            assert st.current_mode() == "live"
            assert st.balance == 500.0
            st.balance -= 100
            st.positions["ETH/USDT"] = {"qty": 5}
        assert st.get_account("bybit").balance == 400.0
        # Primary untouched
        assert st.balance == 10000
        assert "ETH/USDT" not in st.get_account("binance").positions
        assert st.current_mode() == "paper"

    def test_independent_modes(self):
        st = _make_state()
        st.get_account("binance", mode="paper")
        st.get_account("bybit", mode="live")
        with st.use_account("binance"):
            assert st.current_mode() == "paper"
        with st.use_account("bybit"):
            assert st.current_mode() == "live"

    def test_active_account_is_thread_local(self):
        st = _make_state()
        st.get_account("bybit", mode="live").balance = 500.0
        seen = {}

        def worker():
            # Another thread must still see the primary account
            seen["mode"] = st.current_mode()
            seen["balance"] = st.balance

        with st.use_account("bybit"):
            t = threading.Thread(target=worker)
            t.start()
            t.join()
        assert seen["mode"] == "paper"
        assert seen["balance"] == 10000

    def test_set_primary_account(self):
        st = _make_state()
        st.get_account("kraken", mode="live")
        st.set_primary_account("kraken")
        assert st.primary_account.name == "kraken"
