"""Monte-Carlo portfolio risk simulation.

Single source of truth for the simulation that previously lived as a
verbatim copy in both ``server.py`` and ``routes/api/system.py``.

The simulator samples per-trade PnL from the realised distribution of
closed trades, models trades-per-day with a Poisson process, and
returns percentile bands plus a Value-at-Risk and ruin-probability
summary. Pure NumPy, deterministic via fixed RNG seed.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import numpy as np


def simulate_monte_carlo(
    *,
    state: Any,
    config: dict[str, Any],
    n_simulations: int = 10_000,
    n_days: int = 30,
) -> dict[str, Any]:
    """Run a Monte-Carlo portfolio simulation over ``n_days``.

    Args:
        state: Bot state. Must expose ``closed_trades`` (list of dicts
            with ``pnl``, ``invested``, ``opened`` keys) and a
            ``portfolio_value()`` callable.
        config: CONFIG dict, only ``risk_per_trade`` is consulted.
        n_simulations: Number of MC paths to run.
        n_days: Horizon in days.

    Returns:
        Dict with percentile bands, VaR, ruin probability, expected
        return, and the simulation parameters that were used. On
        insufficient data the dict carries a single ``"error"`` key.
    """
    trades = state.closed_trades
    if len(trades) < 5:
        return {"error": "Mindestens 5 abgeschlossene Trades erforderlich"}
    pnl_pcts = [
        t.get("pnl", 0) / max(t.get("invested", 1), 1) for t in trades if t.get("invested", 0) > 0
    ]
    if not pnl_pcts:
        return {"error": "Keine PnL-Daten vorhanden"}

    mu = float(np.mean(pnl_pcts))
    sigma = float(np.std(pnl_pcts))
    start_value = state.portfolio_value()

    if trades:
        span_days = max(
            1,
            (
                datetime.now()
                - datetime.fromisoformat(
                    str(trades[-1].get("opened", datetime.now().isoformat()))[:19]
                )
            ).days,
        )
        trades_per_day = max(0.1, len(trades) / span_days)
    else:
        trades_per_day = 1.0

    results: list[float] = []
    rng = np.random.default_rng(42)
    risk_per_trade = config.get("risk_per_trade", 0.015)
    for _ in range(n_simulations):
        val = start_value
        for _day in range(n_days):
            n_trades_today = max(0, int(rng.poisson(trades_per_day)))
            for _ in range(n_trades_today):
                pnl_pct = rng.normal(mu, sigma)
                invested = val * risk_per_trade
                val = max(0, val + invested * pnl_pct)
        results.append(val)

    results_arr = np.array(results)
    p5, p25, p50, p75, p95 = np.percentile(results_arr, [5, 25, 50, 75, 95])

    var_95 = start_value - float(p5)
    var_pct = var_95 / start_value * 100 if start_value > 0 else 0.0
    prob_profit = float(np.mean(results_arr > start_value) * 100)
    prob_ruin = float(np.mean(results_arr < start_value * 0.5) * 100)

    return {
        "n_simulations": n_simulations,
        "n_days": n_days,
        "start_value": round(start_value, 2),
        "mu_per_trade": round(mu * 100, 3),
        "sigma_per_trade": round(sigma * 100, 3),
        "trades_per_day": round(trades_per_day, 2),
        "percentile_5": round(float(p5), 2),
        "percentile_25": round(float(p25), 2),
        "percentile_50": round(float(p50), 2),
        "percentile_75": round(float(p75), 2),
        "percentile_95": round(float(p95), 2),
        "var_95_usdt": round(var_95, 2),
        "var_95_pct": round(var_pct, 2),
        "prob_profit_pct": round(prob_profit, 1),
        "prob_ruin_pct": round(prob_ruin, 1),
        "expected_return": round((float(p50) - start_value) / start_value * 100, 2)
        if start_value > 0
        else 0.0,
    }
