import threading

from services.trade_execution import TradeExecutionService


class _State:
    def __init__(self, balance=1000.0):
        self.balance = balance
        self._lock = threading.Lock()


class _Exchange:
    def __init__(self):
        self.buy_called = False
        self.sell_called = False
        self._balance = {"USDT": {"free": 0.0}, "BTC": {"free": 0.0}}
        self.raise_on_balance = False

    def market(self, _symbol):
        return {"active": True, "precision": {"amount": 3}, "base": "BTC", "quote": "USDT"}

    def create_market_buy_order(self, _symbol, _qty):
        self.buy_called = True
        return {"id": "buy-1"}

    def create_market_sell_order(self, _symbol, _qty):
        self.sell_called = True
        return {"id": "sell-1"}

    def fetch_balance(self):
        if self.raise_on_balance:
            raise RuntimeError("balance error")
        return self._balance


def _svc(*, paper=True):
    return TradeExecutionService(
        config={"paper_trading": paper},
        state=_State(),
        get_fee_rate=lambda: 0.001,
        mode_manager=None,
    )


def _svc_with_fee(*, fee_rate, paper=True):
    return TradeExecutionService(
        config={"paper_trading": paper},
        state=_State(),
        get_fee_rate=lambda: fee_rate,
        mode_manager=None,
    )


def test_execute_buy_rejects_zero_quantity():
    svc = _svc(paper=False)
    ex = _Exchange()

    res = svc.execute_buy(ex, symbol="BTC/USDT", price=1_000_000.0, invest_usdt=0.0)

    assert res.ok is False
    assert res.reason == "Ungültige Orderparameter"
    assert ex.buy_called is False


def test_execute_sell_rejects_non_positive_quantity():
    svc = _svc(paper=False)
    ex = _Exchange()

    res = svc.execute_sell(ex, symbol="BTC/USDT", qty=0.0, invest_usdt=100.0)

    assert res.ok is False
    assert res.reason == "Ungültige Ordermenge"
    assert ex.sell_called is False


def test_execute_sell_rejects_non_numeric_quantity():
    svc = _svc(paper=False)
    ex = _Exchange()

    res = svc.execute_sell(ex, symbol="BTC/USDT", qty="not-a-number", invest_usdt=100.0)

    assert res.ok is False
    assert res.reason == "Ungültige Ordermenge"
    assert ex.sell_called is False


def test_execute_buy_rejects_invalid_order_parameters():
    svc = _svc(paper=False)
    ex = _Exchange()

    res = svc.execute_buy(ex, symbol="BTC/USDT", price=0.0, invest_usdt=100.0)

    assert res.ok is False
    assert res.reason == "Ungültige Orderparameter"
    assert ex.buy_called is False


def test_execute_buy_live_rejects_zero_balance():
    svc = _svc(paper=False)
    ex = _Exchange()
    ex.market = lambda _symbol: {"active": True, "precision": {}}

    res = svc.execute_buy(ex, symbol="BTC/USDT", price=100.0, invest_usdt=50.0)

    assert res.ok is False
    assert res.reason == "Live-Guthaben zu niedrig"
    assert ex.buy_called is False


def test_execute_buy_live_rejects_when_balance_fetch_fails():
    svc = _svc(paper=False)
    ex = _Exchange()
    ex.market = lambda _symbol: {"active": True, "precision": {}, "quote": "USDT"}
    ex.raise_on_balance = True

    res = svc.execute_buy(ex, symbol="BTC/USDT", price=100.0, invest_usdt=50.0)

    assert res.ok is False
    assert res.reason == "Live-Balance-Abfrage fehlgeschlagen"
    assert ex.buy_called is False


def test_execute_buy_rejects_invalid_fee_rate():
    svc = _svc_with_fee(fee_rate=1.5, paper=False)
    ex = _Exchange()

    res = svc.execute_buy(ex, symbol="BTC/USDT", price=100.0, invest_usdt=100.0)

    assert res.ok is False
    assert res.reason == "Ungültige Orderparameter"
    assert ex.buy_called is False


def test_execute_buy_rejects_under_min_cost_limit():
    svc = _svc(paper=False)
    ex = _Exchange()
    ex.market = lambda _symbol: {
        "active": True,
        "precision": {},
        "limits": {"amount": {"min": 0.0}, "cost": {"min": 100.0}},
    }

    res = svc.execute_buy(ex, symbol="BTC/USDT", price=100.0, invest_usdt=50.0)

    assert res.ok is False
    assert res.reason == "Orderwert unter Mindestwert"
    assert ex.buy_called is False


def test_execute_sell_rejects_under_min_amount_limit():
    svc = _svc(paper=False)
    ex = _Exchange()
    ex.market = lambda _symbol: {
        "active": True,
        "precision": {},
        "limits": {"amount": {"min": 1.0}},
    }

    res = svc.execute_sell(ex, symbol="BTC/USDT", qty=0.5, invest_usdt=100.0)

    assert res.ok is False
    assert res.reason == "Ordermenge unter Mindestgröße"
    assert ex.sell_called is False


def test_execute_sell_live_rejects_when_base_balance_too_low():
    svc = _svc(paper=False)
    ex = _Exchange()
    ex.market = lambda _symbol: {"active": True, "precision": {}, "base": "BTC"}
    ex._balance = {"BTC": {"free": 0.1}}

    res = svc.execute_sell(ex, symbol="BTC/USDT", qty=0.5, invest_usdt=100.0)

    assert res.ok is False
    assert res.reason == "Live-Basisguthaben zu niedrig"
    assert ex.sell_called is False


def test_execute_sell_live_places_order_when_base_balance_is_sufficient():
    svc = _svc(paper=False)
    ex = _Exchange()
    ex.market = lambda _symbol: {"active": True, "precision": {}, "base": "BTC"}
    ex._balance = {"BTC": {"free": 1.0}}

    res = svc.execute_sell(ex, symbol="BTC/USDT", qty=0.5, invest_usdt=100.0)

    assert res.ok is True
    assert ex.sell_called is True
