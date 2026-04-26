"""TREVLIX – Safety tests for TradeExecutionService.

Covers the hardened paths:
- Invalid price / qty rejection
- Mark-order cooldown activated BEFORE the exchange call (prevents duplicate
  orders if the exchange call raises after sending)
- _safe_mark_order swallows exceptions
"""

import threading

import pytest

from services.trade_execution import TradeExecutionService


class _State:
    def __init__(self, balance: float = 1000.0):
        self._lock = threading.RLock()
        self.balance = balance


class _Mode:
    """Fake ModeManager that records mark_order calls and allows orders."""

    def __init__(self):
        self.marked: list[str] = []

    def can_place_order(self, **kw):
        class _R:
            allowed = True
            reason = "ok"

        return _R()

    def mark_order(self, symbol: str) -> None:
        self.marked.append(symbol)


class _RaisingMode(_Mode):
    def mark_order(self, symbol: str) -> None:
        raise RuntimeError("boom")


class _FakeEx:
    def __init__(self, *, raise_on_buy: bool = False, raise_on_sell: bool = False):
        self.raise_on_buy = raise_on_buy
        self.raise_on_sell = raise_on_sell
        self.buys = 0
        self.sells = 0

    def market(self, symbol):
        return {"active": True, "precision": {"amount": 8}}

    def fetch_balance(self):
        return {"USDT": {"free": 1_000_000.0}}

    def create_market_buy_order(self, symbol, qty):
        self.buys += 1
        if self.raise_on_buy:
            raise RuntimeError("exchange network error")
        return {"id": f"buy-{self.buys}"}

    def create_market_sell_order(self, symbol, qty):
        self.sells += 1
        if self.raise_on_sell:
            raise RuntimeError("exchange network error")
        return {"id": f"sell-{self.sells}"}


def _make_service(*, paper: bool, mode: _Mode | None = None):
    cfg = {"paper_trading": paper}
    return TradeExecutionService(
        config=cfg,
        state=_State(1000.0),
        get_fee_rate=lambda: 0.001,
        mode_manager=mode,
    )


class TestExecuteBuyValidation:
    def test_rejects_zero_price(self):
        svc = _make_service(paper=True)
        r = svc.execute_buy(_FakeEx(), symbol="BTC/USDT", price=0.0, invest_usdt=100.0)
        assert not r.ok
        assert "Preis" in r.reason

    def test_rejects_negative_price(self):
        svc = _make_service(paper=True)
        r = svc.execute_buy(_FakeEx(), symbol="BTC/USDT", price=-1.0, invest_usdt=100.0)
        assert not r.ok

    def test_rejects_zero_invest(self):
        svc = _make_service(paper=True)
        r = svc.execute_buy(_FakeEx(), symbol="BTC/USDT", price=50000.0, invest_usdt=0.0)
        assert not r.ok
        assert "Investment" in r.reason


class TestCooldownBeforeLiveOrder:
    def test_cooldown_marked_even_when_exchange_raises(self):
        """If the exchange call raises (order may or may not have landed),
        the cooldown MUST be set so the bot does not retry immediately."""
        mode = _Mode()
        svc = _make_service(paper=False, mode=mode)
        ex = _FakeEx(raise_on_buy=True)
        r = svc.execute_buy(ex, symbol="BTC/USDT", price=50000.0, invest_usdt=100.0)
        assert not r.ok
        assert "live_buy_failed" in r.reason
        assert "BTC/USDT" in mode.marked  # cooldown was activated

    def test_cooldown_marked_on_successful_live_buy(self):
        mode = _Mode()
        svc = _make_service(paper=False, mode=mode)
        r = svc.execute_buy(_FakeEx(), symbol="BTC/USDT", price=50000.0, invest_usdt=100.0)
        assert r.ok
        assert mode.marked == ["BTC/USDT"]

    def test_sell_cooldown_marked_even_when_exchange_raises(self):
        mode = _Mode()
        svc = _make_service(paper=False, mode=mode)
        ex = _FakeEx(raise_on_sell=True)
        r = svc.execute_sell(ex, symbol="BTC/USDT", qty=0.01, invest_usdt=500.0)
        assert not r.ok
        assert "live_sell_failed" in r.reason
        assert "BTC/USDT" in mode.marked


class TestSafeMarkOrder:
    def test_mark_order_exception_does_not_break_buy(self):
        """A failing mode_manager.mark_order must not cause a successful
        exchange order to be reported as failed."""
        mode = _RaisingMode()
        svc = _make_service(paper=False, mode=mode)
        r = svc.execute_buy(_FakeEx(), symbol="BTC/USDT", price=50000.0, invest_usdt=100.0)
        assert r.ok

    def test_mark_order_exception_does_not_break_paper(self):
        mode = _RaisingMode()
        svc = _make_service(paper=True, mode=mode)
        r = svc.execute_buy(_FakeEx(), symbol="BTC/USDT", price=50000.0, invest_usdt=100.0)
        assert r.ok


class TestSellValidation:
    def test_rejects_zero_qty(self):
        svc = _make_service(paper=True)
        r = svc.execute_sell(_FakeEx(), symbol="BTC/USDT", qty=0.0, invest_usdt=500.0)
        assert not r.ok
        assert "Menge" in r.reason


class TestPaperSlippage:
    """Paper mode applies configurable slippage to buy and sell prices."""

    def test_buy_slippage_reduces_qty(self):
        cfg = {"paper_trading": True, "paper_slippage_bps": 10}
        svc = TradeExecutionService(config=cfg, state=_State(1000.0), get_fee_rate=lambda: 0.001)
        r = svc.execute_buy(_FakeEx(), symbol="BTC/USDT", price=1000.0, invest_usdt=100.0)
        assert r.ok
        # Without slippage: qty ≈ (100 - 0.1) / 1000 = 0.0999
        # With 10bps slippage: effective_price = 1001.0, qty ≈ 0.0988
        assert r.meta["actual_price"] == pytest.approx(1001.0, rel=1e-9)
        assert r.meta["qty"] < 0.0999
        assert r.meta["slippage_bps"] == 10

    def test_sell_slippage_reduces_proceeds(self):
        cfg = {"paper_trading": True, "paper_slippage_bps": 10}
        svc = TradeExecutionService(config=cfg, state=_State(1000.0), get_fee_rate=lambda: 0.001)
        r = svc.execute_sell(_FakeEx(), symbol="BTC/USDT", qty=0.1, invest_usdt=500.0)
        assert r.ok
        assert r.meta["effective_proceeds"] < 500.0
        assert r.meta["slippage_bps"] == 10

    def test_zero_slippage_config(self):
        cfg = {"paper_trading": True, "paper_slippage_bps": 0}
        svc = TradeExecutionService(config=cfg, state=_State(1000.0), get_fee_rate=lambda: 0.001)
        r = svc.execute_buy(_FakeEx(), symbol="BTC/USDT", price=1000.0, invest_usdt=100.0)
        assert r.meta["actual_price"] == 1000.0


class _FakeExWithFill(_FakeEx):
    """FakeEx that returns filled/average fields in order response."""

    def create_market_buy_order(self, symbol, qty):
        self.buys += 1
        return {"id": "buy-1", "filled": qty * 0.99, "average": 50250.0}

    def create_market_sell_order(self, symbol, qty):
        self.sells += 1
        return {"id": "sell-1", "filled": qty * 0.98, "average": 49800.0}


class TestLiveFillVerification:
    """Live orders extract actual filled qty and average price."""

    def test_buy_extracts_filled_and_average(self):
        svc = _make_service(paper=False)
        r = svc.execute_buy(_FakeExWithFill(), symbol="BTC/USDT", price=50000.0, invest_usdt=100.0)
        assert r.ok
        assert r.meta["actual_price"] == 50250.0
        assert r.meta["qty"] < 0.002  # 0.001 * 0.99

    def test_sell_extracts_filled_and_average(self):
        svc = _make_service(paper=False)
        r = svc.execute_sell(
            _FakeExWithFill(), symbol="BTC/USDT", qty=0.1, invest_usdt=5000.0, price=50000.0
        )
        assert r.ok
        assert r.meta["actual_price"] == 49800.0
        assert r.meta["actual_qty"] == pytest.approx(0.098, rel=1e-2)

    def test_buy_falls_back_to_requested_qty_when_order_missing_filled(self):
        svc = _make_service(paper=False)
        r = svc.execute_buy(_FakeEx(), symbol="BTC/USDT", price=50000.0, invest_usdt=100.0)
        assert r.ok
        # _FakeEx returns {"id": "buy-1"} with no filled/average — should fall back
        assert r.meta["actual_price"] == 50000.0
