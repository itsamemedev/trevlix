"""TREVLIX – Revenue Tracking Agent.

Tracks real profit metrics including fees, slippage, and funding costs.
Provides daily/weekly/monthly PnL aggregation, strategy attribution,
drawdown monitoring, and structured snapshots for dashboard and AI agents.

Usage:
    from services.revenue_tracking import RevenueTracker

    tracker = RevenueTracker(db=db_manager, config=config_dict)
    tracker.record_trade({
        "symbol": "BTC/USDT", "side": "buy", "amount": 0.1,
        "price": 60000.0, "fee": 6.0, "strategy": "EMA-Trend",
        "pnl": 120.0, "timestamp": datetime.now(),
    })
    summary = tracker.get_daily_summary()
"""

import logging
import threading
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import Any

log = logging.getLogger("trevlix.revenue")

# Required keys in every trade dict passed to record_trade()
_REQUIRED_TRADE_KEYS = frozenset(
    {"symbol", "side", "amount", "price", "fee", "strategy", "pnl", "timestamp"}
)


class RevenueTracker:
    """Revenue tracking agent for real profit analysis.

    Calculates net profit after fees, slippage, and funding costs.
    Aggregates PnL over configurable time windows, tracks drawdown,
    and detects losing strategies via rolling-window analysis.
    """

    def __init__(self, db: Any, config: dict) -> None:
        """Initialise the revenue tracker.

        Args:
            db: MySQLManager instance with ``_get_conn()`` context manager.
            config: Application configuration dict.  Recognised keys:
                - ``slippage_bps`` (float): Estimated slippage in basis
                  points.  Defaults to 5.0 (0.05 %).
                - ``losing_strategy_window_days`` (int): Rolling window
                  for losing-strategy detection.  Defaults to 7.
                - ``drawdown_alert_pct`` (float): Drawdown percentage
                  that triggers an alert.  Defaults to 10.0.
                - ``paper_balance`` (float): Starting capital used for
                  ROI calculation.  Defaults to 10 000.
        """
        self._db = db
        self._config = config
        self._lock = threading.Lock()

        # In-memory trade ledger: list of enriched trade dicts
        self._trades: list[dict] = []

        # Running totals for fast snapshot access
        self._total_pnl: float = 0.0
        self._total_fees: float = 0.0
        self._total_slippage: float = 0.0
        self._total_funding: float = 0.0
        self._total_net: float = 0.0

        # Drawdown tracking
        self._peak_equity: float = config.get("paper_balance", 10_000.0)
        self._current_equity: float = self._peak_equity
        self._max_drawdown_pct: float = 0.0

        # Win / loss counters per strategy
        self._strategy_wins: dict[str, int] = defaultdict(int)
        self._strategy_losses: dict[str, int] = defaultdict(int)
        self._strategy_pnl: dict[str, float] = defaultdict(float)

        # Configuration knobs
        self._slippage_bps: float = config.get("slippage_bps", 5.0)
        self._losing_window_days: int = config.get("losing_strategy_window_days", 7)
        self._drawdown_alert_pct: float = config.get("drawdown_alert_pct", 10.0)

    # ── Public API ────────────────────────────────────────────────────

    def record_trade(self, trade: dict) -> dict:
        """Record a single trade and compute net profit metrics.

        Args:
            trade: Trade dictionary with keys: ``symbol``, ``side``,
                ``amount``, ``price``, ``fee``, ``strategy``, ``pnl``,
                ``timestamp``.  Optional keys: ``funding_fee`` (float,
                defaults to 0.0).

        Returns:
            Enriched trade dict with added fields ``slippage_est``,
            ``funding_fee``, ``net_pnl``.

        Raises:
            ValueError: If any required key is missing from *trade*.
        """
        missing = _REQUIRED_TRADE_KEYS - trade.keys()
        if missing:
            raise ValueError(f"Trade dict missing required keys: {sorted(missing)}")

        fee: float = float(trade["fee"])
        notional: float = float(trade["amount"]) * float(trade["price"])
        slippage_est: float = notional * (self._slippage_bps / 10_000)
        funding_fee: float = float(trade.get("funding_fee", 0.0))
        gross_pnl: float = float(trade["pnl"])
        net_pnl: float = gross_pnl - fee - slippage_est - funding_fee

        enriched: dict = {
            **trade,
            "slippage_est": round(slippage_est, 8),
            "funding_fee": round(funding_fee, 8),
            "net_pnl": round(net_pnl, 8),
        }

        strategy: str = trade["strategy"]

        with self._lock:
            self._trades.append(enriched)
            self._total_pnl += gross_pnl
            self._total_fees += fee
            self._total_slippage += slippage_est
            self._total_funding += funding_fee
            self._total_net += net_pnl

            # Strategy attribution
            self._strategy_pnl[strategy] += net_pnl
            if net_pnl >= 0:
                self._strategy_wins[strategy] += 1
            else:
                self._strategy_losses[strategy] += 1

            # Drawdown tracking
            self._current_equity += net_pnl
            if self._current_equity > self._peak_equity:
                self._peak_equity = self._current_equity
            if self._peak_equity > 0:
                dd_pct = (self._peak_equity - self._current_equity) / self._peak_equity * 100
                if dd_pct > self._max_drawdown_pct:
                    self._max_drawdown_pct = dd_pct

        self._persist_trade(enriched)

        # Drawdown alert (outside lock to avoid holding it during I/O)
        if self._max_drawdown_pct >= self._drawdown_alert_pct:
            log.warning(
                "Drawdown alert: %.2f%% (threshold %.2f%%)",
                self._max_drawdown_pct,
                self._drawdown_alert_pct,
            )

        return enriched

    def get_daily_summary(self, date: datetime | None = None) -> dict:
        """Return PnL summary for a single day.

        Args:
            date: The day to summarise.  Defaults to today (UTC).

        Returns:
            Dict with keys ``date``, ``gross_pnl``, ``fees``,
            ``slippage``, ``funding``, ``net_pnl``, ``trade_count``,
            ``win_rate``.
        """
        target = (date or datetime.now(UTC)).date()
        return self._aggregate_period(target, target)

    def get_weekly_summary(self, week_start: datetime | None = None) -> dict:
        """Return PnL summary for a 7-day window.

        Args:
            week_start: First day of the window.  Defaults to 7 days
                ago (UTC).

        Returns:
            Aggregated summary dict (same schema as daily).
        """
        end = (week_start or datetime.now(UTC)).date()
        start = end - timedelta(days=6)
        return self._aggregate_period(start, end)

    def get_monthly_summary(self, month_start: datetime | None = None) -> dict:
        """Return PnL summary for a 30-day window.

        Args:
            month_start: First day of the window.  Defaults to 30 days
                ago (UTC).

        Returns:
            Aggregated summary dict (same schema as daily).
        """
        end = (month_start or datetime.now(UTC)).date()
        start = end - timedelta(days=29)
        return self._aggregate_period(start, end)

    def get_strategy_performance(self) -> dict[str, dict]:
        """Return per-strategy performance metrics.

        Returns:
            Dict mapping strategy name to a dict with ``total_pnl``,
            ``trade_count``, ``win_rate``, ``avg_win``, ``avg_loss``.
        """
        with self._lock:
            strategies: set[str] = set(self._strategy_pnl.keys())
            trades_copy = list(self._trades)

        result: dict[str, dict] = {}
        for strat in sorted(strategies):
            strat_trades = [t for t in trades_copy if t["strategy"] == strat]
            wins = [t["net_pnl"] for t in strat_trades if t["net_pnl"] >= 0]
            losses = [t["net_pnl"] for t in strat_trades if t["net_pnl"] < 0]
            total = len(strat_trades)
            result[strat] = {
                "total_pnl": round(sum(t["net_pnl"] for t in strat_trades), 8),
                "trade_count": total,
                "win_rate": (round(len(wins) / total * 100, 2) if total else 0.0),
                "avg_win": (round(sum(wins) / len(wins), 8) if wins else 0.0),
                "avg_loss": (round(sum(losses) / len(losses), 8) if losses else 0.0),
            }
        return result

    def detect_losing_strategies(self) -> list[dict]:
        """Identify strategies with negative PnL over the rolling window.

        Scans trades from the last ``losing_strategy_window_days`` and
        flags any strategy whose net PnL is negative.  Also flags
        strategies where fees exceed 50 % of gross profit (hidden
        losses).

        Returns:
            List of dicts, each with ``strategy``, ``net_pnl``,
            ``reason``.
        """
        cutoff = datetime.now(UTC) - timedelta(days=self._losing_window_days)

        with self._lock:
            recent = []
            for t in self._trades:
                ts = t["timestamp"]
                # Handle both naive and aware datetimes
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=UTC)
                if ts >= cutoff:
                    recent.append(t)

        # Aggregate by strategy
        strat_gross: dict[str, float] = defaultdict(float)
        strat_fees: dict[str, float] = defaultdict(float)
        strat_net: dict[str, float] = defaultdict(float)
        for t in recent:
            s = t["strategy"]
            strat_gross[s] += float(t["pnl"])
            strat_fees[s] += float(t["fee"]) + t["slippage_est"] + t["funding_fee"]
            strat_net[s] += t["net_pnl"]

        alerts: list[dict] = []
        for strat in sorted(strat_net.keys()):
            net = strat_net[strat]
            gross = strat_gross[strat]
            fees = strat_fees[strat]

            if net < 0:
                alerts.append(
                    {
                        "strategy": strat,
                        "net_pnl": round(net, 8),
                        "reason": "negative_pnl",
                    }
                )
                log.warning(
                    "Losing strategy detected: %s (net PnL %.4f over %d days)",
                    strat,
                    net,
                    self._losing_window_days,
                )

            # Hidden losses: fees eat more than half of gross profit
            if gross > 0 and fees > gross * 0.5:
                alerts.append(
                    {
                        "strategy": strat,
                        "net_pnl": round(net, 8),
                        "reason": "hidden_fee_losses",
                    }
                )
                log.warning(
                    "Hidden fee losses: %s – fees %.4f vs gross %.4f",
                    strat,
                    fees,
                    gross,
                )

        # Drawdown alert (global, not per strategy)
        if self._max_drawdown_pct >= self._drawdown_alert_pct:
            alerts.append(
                {
                    "strategy": "__global__",
                    "net_pnl": round(self._total_net, 8),
                    "reason": "max_drawdown_exceeded",
                }
            )

        return alerts

    def snapshot(self) -> dict:
        """Return a full performance snapshot for the dashboard.

        Returns:
            Dict with top-level metrics and nested strategy breakdown,
            suitable for JSON serialisation and AI agent consumption.
        """
        starting_capital: float = self._config.get("paper_balance", 10_000.0)

        with self._lock:
            total_trades = len(self._trades)
            wins = sum(1 for t in self._trades if t["net_pnl"] >= 0)
            win_amounts = [t["net_pnl"] for t in self._trades if t["net_pnl"] >= 0]
            loss_amounts = [t["net_pnl"] for t in self._trades if t["net_pnl"] < 0]

            snapshot_data: dict = {
                "timestamp": datetime.now(UTC).isoformat(),
                "total_trades": total_trades,
                "gross_pnl": round(self._total_pnl, 8),
                "total_fees": round(self._total_fees, 8),
                "total_slippage": round(self._total_slippage, 8),
                "total_funding_fees": round(self._total_funding, 8),
                "net_pnl": round(self._total_net, 8),
                "roi_pct": (
                    round(self._total_net / starting_capital * 100, 4)
                    if starting_capital > 0
                    else 0.0
                ),
                "current_equity": round(self._current_equity, 8),
                "peak_equity": round(self._peak_equity, 8),
                "max_drawdown_pct": round(self._max_drawdown_pct, 4),
                "win_rate": (round(wins / total_trades * 100, 2) if total_trades else 0.0),
                "avg_win": (round(sum(win_amounts) / len(win_amounts), 8) if win_amounts else 0.0),
                "avg_loss": (
                    round(sum(loss_amounts) / len(loss_amounts), 8) if loss_amounts else 0.0
                ),
                "profit_factor": self._calc_profit_factor(win_amounts, loss_amounts),
            }

        snapshot_data["strategy_performance"] = self.get_strategy_performance()
        snapshot_data["alerts"] = self.detect_losing_strategies()

        return snapshot_data

    # ── Private helpers ───────────────────────────────────────────────

    def _aggregate_period(self, start: Any, end: Any) -> dict:
        """Aggregate trades within a date range (inclusive).

        Args:
            start: Start date (``datetime.date``).
            end: End date (``datetime.date``).

        Returns:
            Summary dict with PnL breakdown and win rate.
        """
        with self._lock:
            filtered = [t for t in self._trades if start <= t["timestamp"].date() <= end]

        gross = sum(float(t["pnl"]) for t in filtered)
        fees = sum(float(t["fee"]) for t in filtered)
        slippage = sum(t["slippage_est"] for t in filtered)
        funding = sum(t["funding_fee"] for t in filtered)
        net = sum(t["net_pnl"] for t in filtered)
        wins = sum(1 for t in filtered if t["net_pnl"] >= 0)
        total = len(filtered)

        return {
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "gross_pnl": round(gross, 8),
            "fees": round(fees, 8),
            "slippage": round(slippage, 8),
            "funding": round(funding, 8),
            "net_pnl": round(net, 8),
            "trade_count": total,
            "win_rate": (round(wins / total * 100, 2) if total else 0.0),
        }

    @staticmethod
    def _calc_profit_factor(wins: list[float], losses: list[float]) -> float:
        """Calculate the profit factor (gross wins / gross losses).

        Args:
            wins: List of winning trade net PnL values.
            losses: List of losing trade net PnL values.

        Returns:
            Profit factor as a float, or 0.0 if there are no losses.
        """
        total_wins = sum(wins)
        total_losses = abs(sum(losses))
        if total_losses == 0:
            return 0.0 if total_wins == 0 else 999.99
        return round(total_wins / total_losses, 4)

    def _persist_trade(self, trade: dict) -> None:
        """Persist an enriched trade record to the database.

        Silently logs errors to avoid disrupting the trading loop.

        Args:
            trade: Enriched trade dict (output of ``record_trade``).
        """
        try:
            with self._db._get_conn() as conn:
                with conn.cursor() as c:
                    c.execute(
                        """INSERT INTO revenue_trades
                        (symbol, side, amount, price, fee,
                         slippage_est, funding_fee, strategy,
                         gross_pnl, net_pnl, recorded_at)
                        VALUES
                        (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            trade["symbol"],
                            trade["side"],
                            float(trade["amount"]),
                            float(trade["price"]),
                            float(trade["fee"]),
                            trade["slippage_est"],
                            trade["funding_fee"],
                            trade["strategy"],
                            float(trade["pnl"]),
                            trade["net_pnl"],
                            trade["timestamp"],
                        ),
                    )
        except Exception as e:
            log.error("Failed to persist revenue trade: %s", e)
