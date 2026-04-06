"""Tests für services.exchange_factory.

Verifiziert, dass alle 8 unterstützten Exchanges korrekt erstellt werden
und Passphrasen für OKX/KuCoin/Crypto.com korrekt gesetzt sind.
"""

from __future__ import annotations

import pytest

from services.exchange_factory import (
    EXCHANGE_DEFAULT_FEES,
    PASSPHRASE_REQUIRED,
    create_ccxt_exchange,
    get_exchange_class,
    invalidate_fee_cache,
    requires_passphrase,
    safe_fetch_tickers,
    supported_exchanges,
)


class TestSupportedExchanges:
    def test_eight_exchanges_supported(self):
        names = supported_exchanges()
        assert len(names) == 8
        assert set(names) == {
            "binance",
            "bybit",
            "coinbase",
            "cryptocom",
            "huobi",
            "kraken",
            "kucoin",
            "okx",
        }

    def test_default_fees_match_supported(self):
        for name in supported_exchanges():
            assert name in EXCHANGE_DEFAULT_FEES
            assert 0 < EXCHANGE_DEFAULT_FEES[name] < 0.01  # <1%


class TestPassphraseRequirements:
    def test_okx_requires_passphrase(self):
        assert requires_passphrase("okx")

    def test_kucoin_requires_passphrase(self):
        assert requires_passphrase("kucoin")

    def test_cryptocom_no_passphrase(self):
        assert not requires_passphrase("cryptocom")

    def test_binance_no_passphrase(self):
        assert not requires_passphrase("binance")

    def test_kraken_no_passphrase(self):
        assert not requires_passphrase("kraken")

    def test_passphrase_set_required_is_frozenset(self):
        assert isinstance(PASSPHRASE_REQUIRED, frozenset)


class TestGetExchangeClass:
    def test_known_exchanges_return_class(self):
        for name in supported_exchanges():
            cls = get_exchange_class(name)
            assert cls is not None, f"Exchange class for '{name}' not found"

    def test_unknown_exchange_returns_none(self):
        assert get_exchange_class("nonexistent_exchange_xyz") is None


class TestCreateCcxtExchange:
    def test_create_all_supported_exchanges(self):
        """Alle 8 Exchanges müssen ohne Fehler erstellt werden können."""
        for name in supported_exchanges():
            inst = create_ccxt_exchange(name)
            assert inst is not None, f"Creating {name} failed"

    def test_passphrase_passed_as_password(self):
        """CCXT verwendet 'password' für die Passphrase bei OKX/KuCoin."""
        ex = create_ccxt_exchange("okx", api_key="k", api_secret="s", passphrase="my-pass")
        assert ex is not None
        assert ex.password == "my-pass"

    def test_kucoin_passphrase(self):
        ex = create_ccxt_exchange("kucoin", api_key="k", api_secret="s", passphrase="kucoin-pass")
        assert ex is not None
        assert ex.password == "kucoin-pass"

    def test_api_credentials_set(self):
        ex = create_ccxt_exchange("binance", api_key="my-key", api_secret="my-sec")
        assert ex is not None
        assert ex.apiKey == "my-key"
        assert ex.secret == "my-sec"

    def test_no_credentials_still_creates_instance(self):
        """Ohne Keys kann die Instance für public endpoints verwendet werden."""
        ex = create_ccxt_exchange("binance")
        assert ex is not None

    def test_default_type_spot(self):
        ex = create_ccxt_exchange("binance")
        assert ex.options.get("defaultType") == "spot"

    def test_default_type_swap(self):
        ex = create_ccxt_exchange("bybit", default_type="swap")
        assert ex.options.get("defaultType") == "swap"

    def test_unknown_exchange_returns_none(self):
        assert create_ccxt_exchange("nonexistent_xyz") is None


class TestSafeFetchTickers:
    class MockExchange:
        def __init__(self, ex_id="binance", batch_works=True, all_tickers=None):
            self.id = ex_id
            self.batch_works = batch_works
            self.all_tickers = all_tickers or {
                "BTC/USDT": {"last": 50000},
                "ETH/USDT": {"last": 3000},
                "XRP/USDT": {"last": 0.5},
            }

        def fetch_tickers(self, symbols=None):
            if symbols is not None and not self.batch_works:
                raise Exception("Batch with symbols not supported")
            if symbols is None:
                return self.all_tickers
            return {s: self.all_tickers[s] for s in symbols if s in self.all_tickers}

        def fetch_ticker(self, symbol):
            return self.all_tickers.get(symbol)

    def test_empty_symbols_returns_empty(self):
        ex = self.MockExchange()
        assert safe_fetch_tickers(ex, []) == {}

    def test_normal_batch_fetch(self):
        ex = self.MockExchange()
        result = safe_fetch_tickers(ex, ["BTC/USDT", "ETH/USDT"])
        assert len(result) == 2
        assert "BTC/USDT" in result

    def test_cryptocom_uses_filter_strategy(self):
        ex = self.MockExchange(ex_id="cryptocom")
        result = safe_fetch_tickers(ex, ["BTC/USDT"])
        assert len(result) == 1
        assert "BTC/USDT" in result

    def test_fallback_when_batch_fails(self):
        """Wenn fetch_tickers(symbols) scheitert, fällt auf filtern zurück."""
        ex = self.MockExchange(batch_works=False)
        result = safe_fetch_tickers(ex, ["BTC/USDT", "ETH/USDT"])
        assert len(result) == 2

    def test_no_unrelated_symbols_returned(self):
        ex = self.MockExchange()
        result = safe_fetch_tickers(ex, ["BTC/USDT"])
        assert "ETH/USDT" not in result
        assert "XRP/USDT" not in result


class TestFeeCache:
    def test_invalidate_cache_all(self):
        invalidate_fee_cache()  # Should not raise

    def test_invalidate_cache_specific(self):
        invalidate_fee_cache("binance")  # Should not raise


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
