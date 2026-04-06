"""Prometheus metrics payload helper."""

from __future__ import annotations

import time


def build_prometheus_lines(*, bot_version: str, state, db) -> list[str]:
    """Build Prometheus metric lines for current runtime state."""
    lines = []
    lines.append(f'trevlix_bot_running {{version="{bot_version}"}} {1 if state.running else 0}')
    lines.append(f"trevlix_open_trades {len(state.positions)}")
    lines.append(f"trevlix_closed_trades_total {len(getattr(state, 'closed_trades', []))}")
    total_pnl = sum(t.get("pnl", 0) for t in getattr(state, "closed_trades", []))
    lines.append(f"trevlix_total_pnl {total_pnl:.2f}")
    wins = sum(1 for t in getattr(state, "closed_trades", []) if t.get("pnl", 0) > 0)
    n = len(getattr(state, "closed_trades", []))
    lines.append(f"trevlix_win_rate {wins / n * 100 if n else 0:.1f}")
    if hasattr(state, "_start_time"):
        lines.append(f"trevlix_uptime_seconds {time.time() - state._start_time:.0f}")
    if db._pool:
        lines.append(f"trevlix_db_pool_available {db._pool.available}")
        lines.append(f"trevlix_db_pool_size {db._pool.pool_size}")
    return lines
