"""Grid trade-count semantics: total_trades counts round-trips, not fills."""

from __future__ import annotations

from services.grid_trading import GridTradingEngine


def test_total_trades_counts_round_trips_not_fills():
    eng = GridTradingEngine()
    eng.create_grid("BTC/USDT", lower=100.0, upper=110.0, levels=10, invest_per_level=100.0)
    bal = [1000.0]

    # Drop to the lowest level → triggers a BUY (a fill, not a completed trade).
    eng.update("BTC/USDT", 100.0, bal)
    grid = eng.grids["BTC/USDT"]
    assert grid["buy_fills"] >= 1
    assert grid["total_trades"] == 0  # no round-trip completed yet

    # Rise so the next level's sell triggers → completes the round-trip.
    eng.update("BTC/USDT", 109.9, bal)
    assert grid["sell_fills"] >= 1
    # One completed round-trip = one trade (not 2 as before the fix).
    assert grid["total_trades"] == grid["sell_fills"]


def test_status_exposes_fill_counters():
    eng = GridTradingEngine()
    eng.create_grid("ETH/USDT", lower=10.0, upper=20.0, levels=5, invest_per_level=50.0)
    st = eng.status()
    assert st and "buy_fills" in st[0] and "sell_fills" in st[0]
    assert st[0]["total_trades"] == 0
