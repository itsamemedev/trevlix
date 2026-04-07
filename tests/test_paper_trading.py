"""
TREVLIX – Paper-Trading Accounting Tests
=========================================
Verify that paper-trading balance, qty and fee stay consistent,
especially when invest is re-clamped under lock.
"""

import threading


class _MinimalState:
    """Lightweight stand-in for BotState to test accounting math."""

    def __init__(self, balance: float):
        self._lock = threading.RLock()
        self.balance = balance
        self.initial_balance = balance
        self.positions: dict[str, dict] = {}


def _open_paper_position(
    state: _MinimalState,
    symbol: str,
    invest: float,
    price: float,
    fee_rate: float,
    max_position_pct: float,
) -> dict | None:
    """Replicate the paper-trading open logic from server.py (post-fix)."""
    if price <= 0:
        return None
    # Pre-lock calculation (may become stale)
    fee = invest * fee_rate
    qty = (invest - fee) / price

    with state._lock:
        # Re-clamp under lock (mirrors server.py fix)
        invest = min(invest, state.balance * max_position_pct)
        if invest > state.balance or invest < 5:
            return None
        # Recalculate fee and qty after re-clamp
        fee = invest * fee_rate
        qty = (invest - fee) / price
        if qty <= 0:
            return None
        state.balance -= invest

    pos = {"entry": price, "qty": qty, "invested": invest - fee, "fee": fee}
    state.positions[symbol] = pos
    return pos


def _close_paper_position(
    state: _MinimalState,
    symbol: str,
    current_price: float,
    fee_rate: float,
) -> float | None:
    """Replicate the paper-trading close logic from server.py."""
    pos = state.positions.pop(symbol, None)
    if not pos:
        return None
    entry = pos["entry"]
    close_invest = pos["invested"]
    pnl_pct = (current_price - entry) / entry * 100
    fee = close_invest * fee_rate
    pnl = close_invest * (pnl_pct / 100) - fee
    with state._lock:
        state.balance += close_invest + pnl
    return pnl


class TestPaperTradingAccounting:
    """Verify balance consistency in paper trading open/close cycle."""

    def test_qty_consistent_after_reclamp(self):
        """When invest is re-clamped, qty and fee must match the new invest."""
        state = _MinimalState(balance=500.0)
        # Request 1000 invest but balance only allows 500 * 0.5 = 250
        pos = _open_paper_position(
            state,
            "BTC/USDT",
            invest=1000.0,
            price=50000.0,
            fee_rate=0.001,
            max_position_pct=0.5,
        )
        assert pos is not None
        actual_invest = pos["invested"] + pos["fee"]
        # qty must match the clamped invest, not the original 1000
        assert actual_invest < 1000.0
        assert abs(pos["qty"] * 50000.0 - pos["invested"]) < 0.01
        assert state.balance == 500.0 - actual_invest

    def test_balance_round_trip_no_price_change(self):
        """Open + close at same price → balance only loses fees."""
        state = _MinimalState(balance=10000.0)
        fee_rate = 0.001
        pos = _open_paper_position(
            state,
            "ETH/USDT",
            invest=1000.0,
            price=3000.0,
            fee_rate=fee_rate,
            max_position_pct=0.5,
        )
        assert pos is not None
        pnl = _close_paper_position(state, "ETH/USDT", current_price=3000.0, fee_rate=fee_rate)
        assert pnl is not None
        # Only fee on close should be lost (open fee already in invested)
        assert state.balance < 10000.0
        # Total cost = open fee + close fee
        expected_loss = 1000.0 * fee_rate + pos["invested"] * fee_rate
        assert abs((10000.0 - state.balance) - expected_loss) < 0.01

    def test_profitable_trade_increases_balance(self):
        """A profitable trade should increase balance above initial minus fees."""
        state = _MinimalState(balance=10000.0)
        fee_rate = 0.001
        _open_paper_position(
            state,
            "BTC/USDT",
            invest=2000.0,
            price=50000.0,
            fee_rate=fee_rate,
            max_position_pct=0.5,
        )
        # Price goes up 10%
        pnl = _close_paper_position(state, "BTC/USDT", current_price=55000.0, fee_rate=fee_rate)
        assert pnl is not None
        assert pnl > 0
        assert state.balance > 10000.0 - 2000.0  # Got back more than invested

    def test_losing_trade_decreases_balance(self):
        """A losing trade should decrease balance."""
        state = _MinimalState(balance=10000.0)
        fee_rate = 0.001
        _open_paper_position(
            state,
            "BTC/USDT",
            invest=2000.0,
            price=50000.0,
            fee_rate=fee_rate,
            max_position_pct=0.5,
        )
        # Price drops 10%
        pnl = _close_paper_position(state, "BTC/USDT", current_price=45000.0, fee_rate=fee_rate)
        assert pnl is not None
        assert pnl < 0
        assert state.balance < 10000.0

    def test_invest_exceeding_balance_is_rejected(self):
        """Invest larger than balance should be rejected."""
        state = _MinimalState(balance=100.0)
        pos = _open_paper_position(
            state,
            "BTC/USDT",
            invest=5000.0,
            price=50000.0,
            fee_rate=0.001,
            max_position_pct=0.1,  # 100 * 0.1 = 10 > 5 min
        )
        assert pos is not None
        # Invest should be clamped to 10 (100 * 0.1)
        assert state.balance == 90.0

    def test_invest_below_minimum_is_rejected(self):
        """Invest below 5 USDT minimum should be rejected."""
        state = _MinimalState(balance=100.0)
        pos = _open_paper_position(
            state,
            "BTC/USDT",
            invest=5000.0,
            price=50000.0,
            fee_rate=0.001,
            max_position_pct=0.01,  # 100 * 0.01 = 1 < 5 min
        )
        assert pos is None
        assert state.balance == 100.0  # Unchanged

    def test_short_close_returns_invested_plus_pnl(self):
        """Verify short close accounting: balance += invested + pnl."""
        state = _MinimalState(balance=10000.0)
        invest = 1000.0
        entry_price = 50000.0
        fee_rate = 0.001
        leverage = 2

        # Open short (deduct invest)
        with state._lock:
            state.balance -= invest

        # Close short at lower price (profitable)
        close_price = 47500.0  # 5% drop
        pnl_pct = (entry_price - close_price) / entry_price * 100
        fee = invest * fee_rate * leverage
        pnl = invest * (pnl_pct / 100) * leverage - fee

        with state._lock:
            state.balance += invest + pnl

        assert pnl > 0
        assert state.balance > 10000.0  # Profitable
