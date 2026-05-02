"""Validation of admin config-update payloads.

Extracted from ``server.py:on_update_config``. The allow-list,
type-coercion sets, and sanity bounds are module-level constants so
they are explicit and unit-testable. ``coerce_config_value`` returns
the sanitised value or ``None`` (= reject) for a single key.

Special-case keys with state side-effects (``paper_trading``,
``exchange``, ``timeframe``) are NOT handled here – the WebSocket
handler keeps those because they touch ``trade_mode``, ``state``,
``_pin_user_exchange`` etc.
"""

from __future__ import annotations

from typing import Any

from app.core.request_helpers import safe_float, safe_int

# Keys that admin users may update through the WebSocket. Adding a new
# tunable to the dashboard requires adding it here AND to whichever
# subsystem reads it from CONFIG.
ALLOWED_CONFIG_KEYS: frozenset[str] = frozenset(
    {
        "stop_loss_pct",
        "take_profit_pct",
        "max_open_trades",
        "scan_interval",
        "paper_trading",
        "trailing_stop",
        "ai_min_confidence",
        "virginie_enabled",
        "virginie_primary_control",
        "virginie_autonomy_weight",
        "virginie_min_score",
        "virginie_max_risk_penalty",
        "virginie_cpu_fast_chat",
        "circuit_breaker_losses",
        "circuit_breaker_min",
        "max_spread_pct",
        "use_fear_greed",
        "ai_use_kelly",
        "mtf_enabled",
        "use_sentiment",
        "use_news",
        "use_onchain",
        "use_dominance",
        "use_anomaly",
        "use_dca",
        "use_partial_tp",
        "use_shorts",
        "use_arbitrage",
        "use_market_regime",
        "arb_min_spread_pct",
        "arb_scan_limit",
        "genetic_enabled",
        "rl_enabled",
        "backup_enabled",
        "portfolio_goal",
        "discord_daily_report",
        "discord_report_hour",
        "risk_per_trade",
        "news_block_score",
        "news_boost_score",
        "dca_max_levels",
        "dca_drop_pct",
        "trailing_pct",
        "lstm_lookback",
        # Dashboard-spezifische Einstellungen
        "language",
        "allow_registration",
        "break_even_enabled",
        "break_even_trigger",
        "break_even_buffer",
        "partial_tp_pct",
        "use_grid",
        "use_rl",
        "use_lstm",
        # Exchange selection – allowed for all authenticated users
        "exchange",
        "timeframe",
    }
)

NUMERIC_KEYS: frozenset[str] = frozenset(
    {
        "stop_loss_pct",
        "take_profit_pct",
        "ai_min_confidence",
        "virginie_autonomy_weight",
        "virginie_min_score",
        "virginie_max_risk_penalty",
        "max_spread_pct",
        "risk_per_trade",
        "news_block_score",
        "news_boost_score",
        "dca_drop_pct",
        "trailing_pct",
        "break_even_trigger",
        "break_even_buffer",
        "partial_tp_pct",
        "portfolio_goal",
        "arb_min_spread_pct",
    }
)

INT_KEYS: frozenset[str] = frozenset(
    {
        "max_open_trades",
        "scan_interval",
        "circuit_breaker_losses",
        "circuit_breaker_min",
        "dca_max_levels",
        "lstm_lookback",
        "discord_report_hour",
        "arb_scan_limit",
    }
)

VALID_EXCHANGES: frozenset[str] = frozenset(
    {
        "cryptocom",
        "binance",
        "bybit",
        "okx",
        "kucoin",
        "kraken",
        "huobi",
        "coinbase",
        "bitget",
        "mexc",
        "gateio",
        "nonkyc",
    }
)

VALID_TIMEFRAMES: frozenset[str] = frozenset(
    {"1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "8h", "12h", "1d"}
)

# Per-key (min_exclusive, max_inclusive) sanity gates. ``min_exclusive``
# means values <= min are rejected; ``max_inclusive`` accepts values up
# to and including the upper bound. ``None`` means no bound on that side.
SANITY_BOUNDS: dict[str, tuple[float | None, float | None, bool, bool]] = {
    # key: (min, max, min_inclusive, max_inclusive)
    "max_open_trades": (1, 100, True, True),
    "stop_loss_pct": (0, 50, False, True),
    "take_profit_pct": (0, 500, False, True),
    "scan_interval": (5, 3600, True, True),
    "risk_per_trade": (0, 0.5, False, True),
}


def _passes_sanity(key: str, value: float) -> bool:
    """Apply ``SANITY_BOUNDS[key]`` to ``value``. True if accepted."""
    bounds = SANITY_BOUNDS.get(key)
    if bounds is None:
        return True
    lo, hi, lo_incl, hi_incl = bounds
    if lo is not None:
        if lo_incl:
            if value < lo:
                return False
        else:
            if value <= lo:
                return False
    if hi is not None:
        if hi_incl:
            if value > hi:
                return False
        else:
            if value >= hi:
                return False
    return True


def coerce_config_value(key: str, raw: Any, current: dict[str, Any]) -> Any | None:
    """Coerce ``raw`` into the right type for ``key`` and apply sanity gates.

    Returns the sanitised value or ``None`` if the value should be
    rejected (wrong type, negative where unallowed, sanity bound
    failed). Caller decides what to do on rejection.

    Does NOT mutate ``current``. Does NOT cover keys with state
    side-effects (paper_trading, exchange, timeframe) – those are
    rejected here and handled by the caller.
    """
    if key not in ALLOWED_CONFIG_KEYS:
        return None
    # State-side-effect keys are handled by the caller, not here.
    if key in ("paper_trading", "exchange", "timeframe"):
        return None

    value: Any = raw
    if key in NUMERIC_KEYS:
        value = safe_float(raw, current.get(key, 0.0))
        if value < 0:
            return None
    elif key in INT_KEYS:
        value = safe_int(raw, current.get(key, 0))
        if value < 0:
            return None
    elif isinstance(current.get(key), bool):
        value = bool(raw)

    if isinstance(value, (int, float)) and not _passes_sanity(key, float(value)):
        return None

    return value
