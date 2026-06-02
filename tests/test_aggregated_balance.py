"""TREVLIX – fetch_aggregated_balance honours the per-exchange mode.

Regression for the bug where an exchange explicitly set to ``live`` reported the
simulated paper balance because the aggregation short-circuited on the GLOBAL
``paper_trading`` flag.
"""

import app.core.trading_ops as ops


class _Account:
    def __init__(self, balance: float):
        self.balance = balance


class _State:
    def __init__(self, balance: float = 1234.0):
        self.balance = balance


class _FakeEx:
    def __init__(self, name: str, totals: dict):
        self.id = name
        self._totals = totals

    def fetch_ticker(self, symbol):  # pragma: no cover - only quote conversion
        return {"last": 0.0}


def _patch(monkeypatch, *, global_paper: bool, rows: list[dict], balances: dict):
    monkeypatch.setattr(ops, "CONFIG", {"paper_trading": global_paper, "quote_currency": "USDT"})
    monkeypatch.setattr(ops, "state", _State(1234.0))
    monkeypatch.setattr(ops, "_get_all_admin_exchanges", lambda: rows)

    def _create_from_db(cfg):
        name = cfg["exchange"]
        return _FakeEx(name, balances.get(name, {}))

    monkeypatch.setattr(ops, "_create_exchange_from_db_config", _create_from_db)
    monkeypatch.setattr(ops, "create_exchange", lambda: _FakeEx("primary", {}))
    monkeypatch.setattr(ops, "_factory_safe_fetch_balance", lambda ex: {"total": ex._totals})


def test_global_paper_no_live_returns_paper_balance(monkeypatch):
    _patch(monkeypatch, global_paper=True, rows=[], balances={})
    res = ops.fetch_aggregated_balance()
    assert res["by_exchange"] == {"paper": {"USDT": 1234.0}}
    assert res["total_usdt"] == 1234.0


def test_per_exchange_live_overrides_global_paper(monkeypatch):
    rows = [{"exchange": "cryptocom", "mode": "live"}]
    _patch(
        monkeypatch,
        global_paper=True,  # global switch still paper …
        rows=rows,
        balances={"cryptocom": {"USDT": 500.0}},
    )
    res = ops.fetch_aggregated_balance()
    # … but the live exchange reports its REAL wallet, not the paper balance.
    assert "paper" not in res["by_exchange"]
    assert res["by_exchange"]["cryptocom"] == {"USDT": 500.0}
    assert res["total_usdt"] == 500.0


def test_paper_exchange_under_global_paper_is_skipped(monkeypatch):
    rows = [{"exchange": "cryptocom", "mode": "paper"}]
    _patch(monkeypatch, global_paper=True, rows=rows, balances={"cryptocom": {"USDT": 500.0}})
    res = ops.fetch_aggregated_balance()
    # No live exchange anywhere → simulated paper balance.
    assert res["by_exchange"] == {"paper": {"USDT": 1234.0}}
