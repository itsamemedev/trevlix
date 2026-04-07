"""Default configuration assembly for the TREVLIX server entrypoint.

This module exists to keep ``server.py`` focused on runtime orchestration.
The full default configuration map is still returned as a plain dictionary to
stay API-compatible with existing code paths.
"""

from __future__ import annotations

import os
import secrets
from collections.abc import Callable
from typing import Any


def _env_bool(key: str, default: str = "false") -> bool:
    """Read a boolean env flag using common truthy values."""
    return os.getenv(key, default).lower() in ("true", "1", "yes")


def _env_int(key: str, default: int) -> int:
    """Read an integer env var with safe fallback."""
    raw = os.getenv(key, str(default))
    try:
        return int(raw)
    except (TypeError, ValueError):
        return default


def build_default_config(secret_factory: Callable[[str], Any]) -> dict[str, Any]:
    """Build the default runtime config map.

    Args:
        secret_factory: Function used to wrap sensitive values.

    Returns:
        A dict compatible with the historic global ``CONFIG`` structure.
    """
    return {
        "exchange": os.getenv("EXCHANGE", "cryptocom"),
        "api_key": secret_factory(os.getenv("API_KEY", "")),
        "secret": secret_factory(os.getenv("API_SECRET", "")),
        "api_passphrase": secret_factory(os.getenv("API_PASSPHRASE", "")),
        "quote_currency": "USDT",
        "min_volume_usdt": 1_000_000,
        "max_markets": _env_int("MAX_MARKETS", 0),
        "blacklist": ["USDC/USDT", "BUSD/USDT", "DAI/USDT", "TUSD/USDT", "FRAX/USDT", "USDP/USDT"],
        "max_workers": 5,
        "timeframe": "1h",
        "candle_limit": 250,
        "risk_per_trade": 0.015,
        "stop_loss_pct": 0.025,
        "take_profit_pct": 0.060,
        "trailing_stop": True,
        "trailing_pct": 0.015,
        "break_even_enabled": True,
        "break_even_trigger": 0.015,
        "break_even_buffer": 0.001,
        "cooldown_minutes": 60,
        "max_open_trades": 5,
        "max_position_pct": 0.20,
        "fee_rate": 0.0004,
        "min_vote_score": 0.60,
        "use_market_regime": True,
        "btc_regime_tf": "4h",
        "use_vol_filter": True,
        "paper_trading": True,
        "paper_balance": 10000.0,
        "scan_interval": 60,
        "max_daily_loss_pct": 0.05,
        "max_spread_pct": 0.5,
        "max_corr": 0.75,
        "circuit_breaker_losses": 3,
        "circuit_breaker_min": 120,
        "ai_enabled": True,
        "ai_min_samples": 20,
        "ai_min_confidence": 0.55,
        "ai_use_kelly": True,
        "ai_optimize_every": 15,
        "ai_retrain_every": 5,
        "auto_retrain_enabled": True,
        "auto_retrain_threshold": 10,
        "auto_retrain_min_wr": 0.50,
        "use_fear_greed": True,
        "fg_buy_max": 80,
        "fg_sell_min": 20,
        "mtf_enabled": True,
        "mtf_confirm_tf": "4h",
        "ob_imbalance_min": 0.45,
        "lstm_lookback": 24,
        "lstm_min_samples": 50,
        "use_sentiment": True,
        "use_news": True,
        "cryptopanic_token": os.getenv("CRYPTOPANIC_TOKEN", ""),
        "cryptopanic_plan": os.getenv("CRYPTOPANIC_API_PLAN", "free"),
        "telegram_token": os.getenv("TELEGRAM_TOKEN", ""),
        "telegram_chat_id": os.getenv("TELEGRAM_CHAT_ID", ""),
        "news_block_score": -0.4,
        "news_sentiment_min": -0.2,
        "news_require_positive": False,
        "news_boost_score": 0.3,
        "use_onchain": True,
        "whale_threshold": 500_000,
        "use_dominance": True,
        "funding_rate_filter": True,
        "funding_rate_max": 0.001,
        "funding_rate_cache": {},
        "btc_dom_max": 40.0,
        "usdt_dom_max": 12.0,
        "use_anomaly": True,
        "anomaly_contamination": 0.05,
        "use_partial_tp": True,
        "partial_tp_levels": [
            {"pct": 0.03, "sell_ratio": 0.25},
            {"pct": 0.05, "sell_ratio": 0.25},
        ],
        "use_dca": True,
        "dca_drop_pct": 0.03,
        "dca_max_levels": 3,
        "dca_size_mult": 1.5,
        "use_shorts": False,
        "short_exchange": "bybit",
        "short_api_key": secret_factory(os.getenv("SHORT_API_KEY", "")),
        "short_secret": secret_factory(os.getenv("SHORT_SECRET", "")),
        "short_leverage": 2,
        "use_arbitrage": True,
        "arb_min_spread_pct": 0.3,
        "arb_exchanges": ["binance", "bybit"],
        "arb_api_keys": {},
        "genetic_enabled": True,
        "genetic_generations": 20,
        "genetic_population": 30,
        "rl_enabled": True,
        "rl_min_episodes": 100,
        "discord_webhook": os.getenv("DISCORD_WEBHOOK", ""),
        "discord_on_buy": True,
        "discord_on_sell": True,
        "discord_on_error": True,
        "discord_on_circuit": True,
        "discord_daily_report": True,
        "discord_on_signals": _env_bool("DISCORD_ON_SIGNALS", "true"),
        "discord_signal_cooldown_sec": _env_int("DISCORD_SIGNAL_COOLDOWN_SEC", 900),
        "discord_report_hour": 20,
        "price_alerts": [],
        "portfolio_goal": 0.0,
        "tax_method": "fifo",
        "backup_enabled": True,
        "backup_keep_days": 7,
        "backup_dir": "backups",
        "backup_encrypt": True,
        "slippage_pct": 0.001,
        "max_drawdown_pct": 0.10,
        "min_order_usdt": 10.0,
        "use_atr_sizing": False,
        "atr_risk_mult": 1.5,
        "max_hold_hours": 0,
        "audit_retention_days": 90,
        "ai_sample_retention_days": 180,
        "use_trade_dna": True,
        "dna_min_matches": 5,
        "dna_boost_threshold": 0.65,
        "dna_block_threshold": 0.35,
        "use_smart_exits": True,
        "smart_exit_atr_sl_mult": 1.5,
        "smart_exit_reward_ratio": 2.0,
        "smart_exit_min_sl_pct": 0.01,
        "smart_exit_max_sl_pct": 0.08,
        "smart_exit_min_tp_pct": 0.02,
        "smart_exit_max_tp_pct": 0.15,
        "smart_exit_squeeze_threshold": 0.03,
        "admin_password": secret_factory(os.getenv("ADMIN_PASSWORD", "trevlix")),
        "jwt_secret": secret_factory(os.getenv("JWT_SECRET", secrets.token_hex(32))),
        "jwt_expiry_hours": 24,
        "multi_user": True,
        "allow_registration": _env_bool("ALLOW_REGISTRATION", "false"),
        "mysql_host": os.getenv("MYSQL_HOST", "localhost"),
        "mysql_port": _env_int("MYSQL_PORT", 3306),
        "mysql_user": os.getenv("MYSQL_USER", "root"),
        "mysql_pass": secret_factory(os.getenv("MYSQL_PASS", "")),
        "mysql_db": os.getenv("MYSQL_DB", "trevlix"),
    }
