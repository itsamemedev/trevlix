"""Backtest: final_balance must stay consistent with total_pnl (EOD force-close)."""

from __future__ import annotations

from services.backtest import BacktestEngine


class _FakeEx:
    def __init__(self, ohlcv):
        self._ohlcv = ohlcv

    def fetch_ohlcv(self, symbol, tf, limit=500):
        return self._ohlcv


def _ramp_ohlcv(n=150, start=100.0, step=0.5):
    # Steadily rising market so a buy never hits SL/TP and stays open at the end.
    rows = []
    ts = 1_700_000_000_000
    price = start
    for i in range(n):
        o = price
        price = price + step
        rows.append([ts + i * 3_600_000, o, price + 1, o - 1, price, 1000.0])
    return rows


def test_open_position_force_closed_keeps_balance_consistent():
    # Strategy: always vote buy (1) so a position opens early and never exits
    # via SL/TP on a monotonically rising series.
    strategies = [("always_buy", lambda row, prev: 1)]
    eng = BacktestEngine(
        compute_indicators_fn=lambda df: df,
        strategies=strategies,
        fee_rate=0.0,
    )
    ex = _FakeEx(_ramp_ohlcv())
    res = eng.run(ex, "BTC/USDT", "1h", 150, sl_pct=0.99, tp_pct=0.99, vote_thr=0.5)

    assert "error" not in res, res
    # The final candle force-closes any open position, so reported realized PnL
    # must equal the mark-to-market balance change exactly.
    expected_balance = res["start_balance"] + res["total_pnl"]
    assert abs(res["final_balance"] - expected_balance) < 0.01
    # And at least one trade was recorded (the forced EOD close).
    assert res["total_trades"] >= 1
    assert any(t["reason"] == "EOD" for t in res["trades"])
