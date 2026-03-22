"""
TREVLIX Tests – Revenue Tracking Agent
========================================

Tests for the RevenueTracker service that calculates net profit
after fees, slippage, and funding costs.

Run with:  pytest tests/test_revenue_tracking.py -v
"""

import os
import sys
import threading
from datetime import datetime, timedelta
from unittest.mock import MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.revenue_tracking import RevenueTracker


def _make_tracker(
    slippage_bps: float = 5.0,
    paper_balance: float = 10_000.0,
) -> RevenueTracker:
    """Create a RevenueTracker with mocked DB."""
    db = MagicMock()
    config = {
        "slippage_bps": slippage_bps,
        "paper_balance": paper_balance,
        "losing_strategy_window_days": 7,
        "drawdown_alert_pct": 10.0,
    }
    return RevenueTracker(db=db, config=config)


def _sample_trade(
    pnl: float = 100.0,
    fee: float = 5.0,
    amount: float = 0.1,
    price: float = 60_000.0,
    strategy: str = "EMA-Trend",
    funding_fee: float = 0.0,
    ts: datetime | None = None,
) -> dict:
    """Build a minimal valid trade dict."""
    return {
        "symbol": "BTC/USDT",
        "side": "buy",
        "amount": amount,
        "price": price,
        "fee": fee,
        "strategy": strategy,
        "pnl": pnl,
        "timestamp": ts or datetime.utcnow(),
        "funding_fee": funding_fee,
    }


class TestRevenueTracker:
    """Tests for the RevenueTracker."""

    def test_record_trade_basic(self) -> None:
        """Record a trade and verify enriched output fields."""
        tracker = _make_tracker()
        trade = _sample_trade()
        result = tracker.record_trade(trade)
        assert "slippage_est" in result
        assert "funding_fee" in result
        assert "net_pnl" in result
        assert result["symbol"] == "BTC/USDT"

    def test_record_trade_missing_keys(self) -> None:
        """ValueError is raised when required keys are missing."""
        tracker = _make_tracker()
        import pytest

        with pytest.raises(ValueError, match="missing required keys"):
            tracker.record_trade({"symbol": "BTC/USDT"})

    def test_slippage_calculation(self) -> None:
        """Slippage = amount * price * slippage_bps / 10000."""
        tracker = _make_tracker(slippage_bps=10.0)
        trade = _sample_trade(amount=1.0, price=50_000.0)
        result = tracker.record_trade(trade)
        expected_slippage = 1.0 * 50_000.0 * (10.0 / 10_000)
        assert abs(result["slippage_est"] - expected_slippage) < 1e-6

    def test_net_pnl_calculation(self) -> None:
        """Net PnL = gross pnl - fee - slippage - funding."""
        tracker = _make_tracker(slippage_bps=5.0)
        trade = _sample_trade(
            pnl=200.0,
            fee=10.0,
            amount=0.5,
            price=40_000.0,
            funding_fee=2.0,
        )
        result = tracker.record_trade(trade)
        slippage = 0.5 * 40_000.0 * (5.0 / 10_000)
        expected_net = 200.0 - 10.0 - slippage - 2.0
        assert abs(result["net_pnl"] - round(expected_net, 8)) < 1e-6

    def test_daily_summary(self) -> None:
        """Record trades today and verify daily summary structure."""
        tracker = _make_tracker()
        now = datetime.utcnow()
        tracker.record_trade(_sample_trade(pnl=50.0, ts=now))
        tracker.record_trade(_sample_trade(pnl=-20.0, ts=now))
        summary = tracker.get_daily_summary(now)
        expected_keys = {
            "start_date",
            "end_date",
            "gross_pnl",
            "fees",
            "slippage",
            "funding",
            "net_pnl",
            "trade_count",
            "win_rate",
        }
        assert set(summary.keys()) == expected_keys
        assert summary["trade_count"] == 2

    def test_weekly_summary(self) -> None:
        """Verify 7-day aggregation window."""
        tracker = _make_tracker()
        now = datetime.utcnow()
        for i in range(7):
            ts = now - timedelta(days=i)
            tracker.record_trade(_sample_trade(pnl=10.0, ts=ts))
        summary = tracker.get_weekly_summary(now)
        assert summary["trade_count"] == 7

    def test_monthly_summary(self) -> None:
        """Verify 30-day aggregation window."""
        tracker = _make_tracker()
        now = datetime.utcnow()
        for i in range(30):
            ts = now - timedelta(days=i)
            tracker.record_trade(_sample_trade(pnl=5.0, ts=ts))
        summary = tracker.get_monthly_summary(now)
        assert summary["trade_count"] == 30

    def test_strategy_performance(self) -> None:
        """Record wins and losses per strategy, verify metrics."""
        tracker = _make_tracker()
        now = datetime.utcnow()
        tracker.record_trade(_sample_trade(pnl=100.0, strategy="A", ts=now))
        tracker.record_trade(_sample_trade(pnl=50.0, strategy="A", ts=now))
        tracker.record_trade(_sample_trade(pnl=-30.0, strategy="B", ts=now))

        perf = tracker.get_strategy_performance()
        assert "A" in perf
        assert "B" in perf
        assert perf["A"]["trade_count"] == 2
        assert perf["B"]["trade_count"] == 1

    def test_detect_losing_strategies(self) -> None:
        """Strategies with negative net PnL are flagged."""
        tracker = _make_tracker()
        now = datetime.utcnow()
        # Large losing trades for strategy "Loser"
        for _ in range(3):
            tracker.record_trade(_sample_trade(pnl=-500.0, fee=5.0, strategy="Loser", ts=now))
        alerts = tracker.detect_losing_strategies()
        losers = [a for a in alerts if a["strategy"] == "Loser"]
        assert len(losers) >= 1
        assert losers[0]["reason"] == "negative_pnl"

    def test_snapshot_structure(self) -> None:
        """Snapshot contains all expected top-level keys."""
        tracker = _make_tracker()
        tracker.record_trade(_sample_trade())
        snap = tracker.snapshot()
        expected_keys = {
            "timestamp",
            "total_trades",
            "gross_pnl",
            "total_fees",
            "total_slippage",
            "total_funding_fees",
            "net_pnl",
            "roi_pct",
            "current_equity",
            "peak_equity",
            "max_drawdown_pct",
            "win_rate",
            "avg_win",
            "avg_loss",
            "profit_factor",
            "strategy_performance",
            "alerts",
        }
        assert expected_keys.issubset(set(snap.keys()))

    def test_drawdown_tracking(self) -> None:
        """Simulate equity drop and verify max drawdown is recorded."""
        tracker = _make_tracker(paper_balance=10_000.0)
        now = datetime.utcnow()
        # First a win to set peak, then losses
        tracker.record_trade(_sample_trade(pnl=500.0, fee=0.0, ts=now))
        tracker.record_trade(_sample_trade(pnl=-2000.0, fee=0.0, ts=now))
        assert tracker._max_drawdown_pct > 0.0

    def test_win_rate_calculation(self) -> None:
        """Verify wins / total ratio in snapshot."""
        tracker = _make_tracker()
        now = datetime.utcnow()
        # 3 wins, 1 loss (net_pnl depends on fees/slippage but large
        # positive pnl should still be net-positive)
        for _ in range(3):
            tracker.record_trade(_sample_trade(pnl=1000.0, fee=1.0, ts=now))
        tracker.record_trade(_sample_trade(pnl=-1000.0, fee=1.0, ts=now))
        snap = tracker.snapshot()
        assert snap["win_rate"] == 75.0

    def test_profit_factor(self) -> None:
        """Verify profit factor = gross_wins / gross_losses."""
        tracker = _make_tracker(slippage_bps=0.0)
        now = datetime.utcnow()
        tracker.record_trade(_sample_trade(pnl=200.0, fee=0.0, ts=now))
        tracker.record_trade(_sample_trade(pnl=-100.0, fee=0.0, ts=now))
        snap = tracker.snapshot()
        # With zero fees/slippage: net_pnl == pnl, factor = 200/100 = 2.0
        assert abs(snap["profit_factor"] - 2.0) < 0.01

    def test_thread_safety(self) -> None:
        """Concurrent record_trade calls do not corrupt state."""
        tracker = _make_tracker()
        now = datetime.utcnow()
        errors: list[Exception] = []
        n_threads = 10
        trades_per_thread = 20

        def worker() -> None:
            try:
                for _ in range(trades_per_thread):
                    tracker.record_trade(_sample_trade(pnl=10.0, fee=0.5, ts=now))
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=worker) for _ in range(n_threads)]
        for th in threads:
            th.start()
        for th in threads:
            th.join()

        assert len(errors) == 0
        snap = tracker.snapshot()
        assert snap["total_trades"] == n_threads * trades_per_thread
