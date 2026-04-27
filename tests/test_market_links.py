"""Tests für services.market_links."""

from __future__ import annotations

from services.market_links import build_market_url


class TestBuildMarketUrl:
    def test_cryptocom_url(self):
        assert (
            build_market_url("cryptocom", "BTC/USDT")
            == "https://crypto.com/exchange/trade/spot/BTC_USDT"
        )

    def test_binance_url(self):
        assert (
            build_market_url("binance", "ETH/USDT") == "https://www.binance.com/en/trade/ETH_USDT"
        )

    def test_okx_lowercases(self):
        assert build_market_url("okx", "BTC/USDT") == "https://www.okx.com/trade-spot/btc-usdt"

    def test_kraken_lowercases(self):
        assert build_market_url("kraken", "BTC/USD") == "https://pro.kraken.com/app/trade/btc-usd"

    def test_bybit_uses_slash(self):
        assert build_market_url("bybit", "BTC/USDT") == "https://www.bybit.com/trade/spot/BTC/USDT"

    def test_nonkyc_url(self):
        assert build_market_url("nonkyc", "PEPE/USDT") == "https://nonkyc.io/market/PEPE_USDT"

    def test_uppercases_input_symbol(self):
        assert (
            build_market_url("cryptocom", "btc/usdt")
            == "https://crypto.com/exchange/trade/spot/BTC_USDT"
        )

    def test_unknown_exchange_returns_empty(self):
        assert build_market_url("unknown", "BTC/USDT") == ""

    def test_invalid_symbol_returns_empty(self):
        assert build_market_url("binance", "BTCUSDT") == ""
        assert build_market_url("binance", "") == ""
        assert build_market_url("binance", "BTC/") == ""

    def test_empty_exchange_returns_empty(self):
        assert build_market_url("", "BTC/USDT") == ""
        assert build_market_url(None, "BTC/USDT") == ""

    def test_case_insensitive_exchange_name(self):
        assert (
            build_market_url("CryptoCom", "BTC/USDT")
            == "https://crypto.com/exchange/trade/spot/BTC_USDT"
        )
