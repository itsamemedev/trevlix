"""Tests for app.core.config_validation – the Allow-list + coercion
pulled out of server.py:on_update_config (Lession 59 in lessons.md)."""

from __future__ import annotations

from app.core.config_validation import (
    ALLOWED_CONFIG_KEYS,
    INT_KEYS,
    NUMERIC_KEYS,
    SANITY_BOUNDS,
    VALID_EXCHANGES,
    VALID_TIMEFRAMES,
    coerce_config_value,
)


class TestAllowList:
    def test_allow_list_is_frozen(self):
        assert isinstance(ALLOWED_CONFIG_KEYS, frozenset)

    def test_state_side_effect_keys_are_in_allow_list(self):
        # paper_trading / exchange / timeframe must be allow-listed even
        # though coerce_config_value rejects them (caller handles them).
        for k in ("paper_trading", "exchange", "timeframe"):
            assert k in ALLOWED_CONFIG_KEYS

    def test_critical_security_keys_not_in_allow_list(self):
        # Lession 59: the Allow-list MUST NOT include secrets, even if
        # they exist in CONFIG. Adding them here would let any admin WS
        # connection rotate credentials.
        for forbidden in (
            "admin_password",
            "jwt_secret",
            "secret_key",
            "encryption_key",
            "mysql_pass",
            "api_key",
            "secret",
            "discord_webhook",
            "telegram_token",
        ):
            assert forbidden not in ALLOWED_CONFIG_KEYS, (
                f"{forbidden!r} must NOT be in ALLOWED_CONFIG_KEYS – "
                "would let admins rotate secrets via WS"
            )


class TestCoerceConfigValue:
    def test_unknown_key_returns_none(self):
        assert coerce_config_value("does_not_exist", 42, {}) is None

    def test_state_side_effect_keys_return_none(self):
        # paper_trading / exchange / timeframe are caller's job
        for k in ("paper_trading", "exchange", "timeframe"):
            assert coerce_config_value(k, "irrelevant", {}) is None

    def test_numeric_key_coerced_to_float(self):
        result = coerce_config_value("ai_min_confidence", "0.6", {"ai_min_confidence": 0.5})
        assert result == 0.6
        assert isinstance(result, float)

    def test_numeric_key_negative_rejected(self):
        assert coerce_config_value("ai_min_confidence", -0.1, {"ai_min_confidence": 0.5}) is None

    def test_numeric_key_invalid_uses_fallback(self):
        # safe_float returns the fallback for non-numeric strings
        result = coerce_config_value("ai_min_confidence", "abc", {"ai_min_confidence": 0.7})
        assert result == 0.7

    def test_int_key_coerced(self):
        result = coerce_config_value("dca_max_levels", "3", {"dca_max_levels": 1})
        assert result == 3
        assert isinstance(result, int)

    def test_int_key_negative_rejected(self):
        assert coerce_config_value("dca_max_levels", -1, {"dca_max_levels": 0}) is None

    def test_bool_key_coerced(self):
        # use_arbitrage exists in current as bool
        assert coerce_config_value("use_arbitrage", 1, {"use_arbitrage": False}) is True
        assert coerce_config_value("use_arbitrage", 0, {"use_arbitrage": True}) is False
        assert coerce_config_value("use_arbitrage", "", {"use_arbitrage": True}) is False

    def test_max_open_trades_sanity_low(self):
        # min=1 inclusive
        assert coerce_config_value("max_open_trades", 0, {"max_open_trades": 5}) is None
        assert coerce_config_value("max_open_trades", 1, {"max_open_trades": 5}) == 1

    def test_max_open_trades_sanity_high(self):
        # max=100 inclusive
        assert coerce_config_value("max_open_trades", 100, {"max_open_trades": 5}) == 100
        assert coerce_config_value("max_open_trades", 101, {"max_open_trades": 5}) is None

    def test_stop_loss_pct_sanity(self):
        # min=0 exclusive, max=50 inclusive
        assert coerce_config_value("stop_loss_pct", 0, {"stop_loss_pct": 0.025}) is None
        assert coerce_config_value("stop_loss_pct", 0.001, {"stop_loss_pct": 0.025}) == 0.001
        assert coerce_config_value("stop_loss_pct", 50, {"stop_loss_pct": 0.025}) == 50
        assert coerce_config_value("stop_loss_pct", 50.0001, {"stop_loss_pct": 0.025}) is None

    def test_take_profit_pct_sanity(self):
        # min=0 exclusive, max=500 inclusive
        assert coerce_config_value("take_profit_pct", 0, {"take_profit_pct": 0.06}) is None
        assert coerce_config_value("take_profit_pct", 500, {"take_profit_pct": 0.06}) == 500
        assert coerce_config_value("take_profit_pct", 500.1, {"take_profit_pct": 0.06}) is None

    def test_scan_interval_sanity(self):
        # min=5 inclusive, max=3600 inclusive
        assert coerce_config_value("scan_interval", 4, {"scan_interval": 60}) is None
        assert coerce_config_value("scan_interval", 5, {"scan_interval": 60}) == 5
        assert coerce_config_value("scan_interval", 3600, {"scan_interval": 60}) == 3600
        assert coerce_config_value("scan_interval", 3601, {"scan_interval": 60}) is None

    def test_risk_per_trade_sanity(self):
        # min=0 exclusive, max=0.5 inclusive
        assert coerce_config_value("risk_per_trade", 0, {"risk_per_trade": 0.015}) is None
        assert coerce_config_value("risk_per_trade", 0.5, {"risk_per_trade": 0.015}) == 0.5
        assert coerce_config_value("risk_per_trade", 0.501, {"risk_per_trade": 0.015}) is None

    def test_does_not_mutate_current_dict(self):
        cfg = {"ai_min_confidence": 0.5}
        coerce_config_value("ai_min_confidence", 0.7, cfg)
        assert cfg == {"ai_min_confidence": 0.5}


class TestExchangesAndTimeframes:
    def test_valid_exchanges_match_services_utils(self):
        from services.utils import EXCHANGE_MAP

        # Every supported exchange in EXCHANGE_MAP must be allow-listed.
        assert set(EXCHANGE_MAP.keys()) <= VALID_EXCHANGES

    def test_valid_timeframes_are_ccxt_compatible(self):
        # All listed timeframes must be standard ccxt format.
        for tf in VALID_TIMEFRAMES:
            assert tf[-1] in {"m", "h", "d"}
            assert tf[:-1].isdigit()


class TestSanityBoundsCoverage:
    def test_all_bounded_keys_are_in_numeric_or_int(self):
        # Sanity bounds only make sense for numeric/int keys.
        for k in SANITY_BOUNDS:
            assert k in NUMERIC_KEYS or k in INT_KEYS, (
                f"{k!r} has sanity bounds but is neither numeric nor int – "
                "the bounds will never fire"
            )
