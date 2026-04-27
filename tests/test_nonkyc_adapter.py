"""Tests für services.nonkyc_adapter.

Verifiziert die CCXT-kompatible Schnittstelle des NonKYC-Adapters mit
gemockten REST-Responses (kein echter Netzwerk-Traffic).
"""

from __future__ import annotations

import base64
from unittest.mock import patch

import pytest

from services.nonkyc_adapter import (
    NonKYCError,
    NonKYCExchange,
    _aggregate_trades_to_ohlcv,
    _normalize_order,
    _normalize_ticker,
)


class TestAuthHeader:
    def test_basic_auth_encodes_correctly(self):
        ex = NonKYCExchange({"apiKey": "key", "secret": "sec"})
        headers = ex._auth_header()
        expected = base64.b64encode(b"key:sec").decode()
        assert headers["Authorization"] == f"Basic {expected}"

    def test_no_credentials_returns_empty_header(self):
        ex = NonKYCExchange()
        assert ex._auth_header() == {}

    def test_private_endpoint_without_credentials_raises(self):
        ex = NonKYCExchange()
        with pytest.raises(NonKYCError, match="API-Key/Secret"):
            ex._request("GET", "/balances", private=True)


class TestNormalizeTicker:
    def test_basic_fields_mapped(self):
        raw = {
            "lastPrice": "0.0123",
            "bestBid": "0.0122",
            "bestAsk": "0.0124",
            "highPrice": "0.013",
            "lowPrice": "0.011",
            "primaryVolume": "1000",
        }
        t = _normalize_ticker("XRG/USDT", raw)
        assert t["symbol"] == "XRG/USDT"
        assert t["last"] == 0.0123
        assert t["bid"] == 0.0122
        assert t["ask"] == 0.0124
        assert t["high"] == 0.013
        assert t["low"] == 0.011
        assert t["baseVolume"] == 1000.0
        assert t["info"] is raw

    def test_missing_fields_become_none(self):
        t = _normalize_ticker("FOO/BAR", {})
        assert t["last"] is None
        assert t["bid"] is None
        assert t["ask"] is None


class TestNormalizeOrder:
    def test_status_mapping(self):
        cases = [
            ("new", "open"),
            ("partiallyFilled".lower(), "open"),
            ("filled", "closed"),
            ("cancelled", "canceled"),
        ]
        for raw_status, expected in cases:
            o = _normalize_order("BTC/USDT", {"id": "1", "status": raw_status})
            assert o["status"] == expected, f"{raw_status} → {o['status']} (expected {expected})"

    def test_remaining_calculated(self):
        o = _normalize_order(
            "BTC/USDT",
            {"id": "1", "quantity": "10", "executedQuantity": "3", "status": "open"},
        )
        assert o["amount"] == 10.0
        assert o["filled"] == 3.0
        assert o["remaining"] == 7.0


class TestOhlcvAggregation:
    def test_empty_trades_returns_empty(self):
        assert _aggregate_trades_to_ohlcv([], 60, 100) == []

    def test_single_trade_creates_one_candle(self):
        trades = [{"timestamp": 1_700_000_000_000, "price": "100", "quantity": "1"}]
        result = _aggregate_trades_to_ohlcv(trades, 60, 100)
        assert len(result) == 1
        ts, o, h, low, c, v = result[0]
        assert o == h == low == c == 100.0
        assert v == 1.0

    def test_open_close_respect_chronological_order(self):
        # Trades aus API kommen oft desc – Adapter muss intern sortieren.
        trades = [
            {"timestamp": 1_700_000_030_000, "price": "120", "quantity": "1"},  # neuer
            {"timestamp": 1_700_000_010_000, "price": "100", "quantity": "1"},  # älter
            {"timestamp": 1_700_000_020_000, "price": "110", "quantity": "1"},
        ]
        result = _aggregate_trades_to_ohlcv(trades, 60, 100)
        assert len(result) == 1
        _, o, h, low, c, _ = result[0]
        assert o == 100.0  # ältester
        assert c == 120.0  # neuester
        assert h == 120.0
        assert low == 100.0

    def test_limit_keeps_most_recent(self):
        # 3 Buckets à 60s, limit=2 → die letzten 2
        trades = [
            {"timestamp": 1_700_000_000_000, "price": "100", "quantity": "1"},
            {"timestamp": 1_700_000_060_000, "price": "200", "quantity": "1"},
            {"timestamp": 1_700_000_120_000, "price": "300", "quantity": "1"},
        ]
        result = _aggregate_trades_to_ohlcv(trades, 60, 2)
        assert len(result) == 2
        assert result[0][1] == 200.0
        assert result[1][1] == 300.0

    def test_invalid_trades_skipped(self):
        trades = [
            {"timestamp": None, "price": "100", "quantity": "1"},
            {"timestamp": 1_700_000_000_000, "price": "0", "quantity": "1"},  # ungültig
            {"timestamp": 1_700_000_000_000, "price": "100", "quantity": "1"},
        ]
        result = _aggregate_trades_to_ohlcv(trades, 60, 100)
        assert len(result) == 1


class TestFetchMarkets:
    def test_fetch_markets_normalizes_response(self):
        fake_response = [
            {
                "id": "abc",
                "symbol": "XRG/USDT",
                "primaryAsset": "XRG",
                "secondaryAsset": "USDT",
                "isActive": True,
                "minimumQuantity": "1",
                "minimumValue": "0.5",
            },
            {
                "id": "def",
                "symbol": "DOGE/USDT",
                "primaryAsset": "DOGE",
                "secondaryAsset": "USDT",
                "isActive": False,
            },
        ]
        ex = NonKYCExchange()
        with patch.object(ex, "_request", return_value=fake_response):
            markets = ex.fetch_markets()
        assert len(markets) == 2
        xrg = next(m for m in markets if m["symbol"] == "XRG/USDT")
        assert xrg["base"] == "XRG"
        assert xrg["quote"] == "USDT"
        assert xrg["spot"] is True
        assert xrg["limits"]["amount"]["min"] == 1.0
        doge = next(m for m in markets if m["symbol"] == "DOGE/USDT")
        assert doge["active"] is False


class TestFetchBalance:
    def test_fetch_balance_format(self):
        fake = [
            {"asset": "BTC", "available": "0.5", "held": "0.1"},
            {"asset": "USDT", "available": "1000", "held": "0"},
        ]
        ex = NonKYCExchange({"apiKey": "k", "secret": "s"})
        with patch.object(ex, "_request", return_value=fake):
            bal = ex.fetch_balance()
        assert bal["free"]["BTC"] == 0.5
        assert bal["used"]["BTC"] == 0.1
        assert bal["total"]["BTC"] == 0.6
        assert bal["BTC"] == {"free": 0.5, "used": 0.1, "total": 0.6}
        assert bal["USDT"]["total"] == 1000.0


class TestCreateOrder:
    def test_market_buy_order_calls_correct_endpoint(self):
        ex = NonKYCExchange({"apiKey": "k", "secret": "s"})
        ex.markets = {"XRG/USDT": {"info": {"symbol": "XRG/USDT"}, "id": "XRG/USDT"}}
        captured: dict = {}

        def fake_request(method, path, **kwargs):
            captured["method"] = method
            captured["path"] = path
            captured["body"] = kwargs.get("json_body")
            captured["private"] = kwargs.get("private")
            return {"id": "ord-1", "status": "filled", "quantity": "10", "executedQuantity": "10"}

        with patch.object(ex, "_request", side_effect=fake_request):
            result = ex.create_market_buy_order("XRG/USDT", 10)
        assert captured["method"] == "POST"
        assert captured["path"] == "/order"
        assert captured["body"]["side"] == "buy"
        assert captured["body"]["type"] == "market"
        assert captured["body"]["quantity"] == "10"
        assert captured["private"] is True
        assert result["status"] == "closed"

    def test_limit_order_requires_price(self):
        ex = NonKYCExchange({"apiKey": "k", "secret": "s"})
        ex.markets = {"XRG/USDT": {"info": {"symbol": "XRG/USDT"}, "id": "XRG/USDT"}}
        with pytest.raises(NonKYCError, match="price"):
            ex.create_order("XRG/USDT", "limit", "buy", 10)

    def test_invalid_side_rejected(self):
        ex = NonKYCExchange({"apiKey": "k", "secret": "s"})
        ex.markets = {"XRG/USDT": {"info": {"symbol": "XRG/USDT"}, "id": "XRG/USDT"}}
        with pytest.raises(NonKYCError, match="order-side"):
            ex.create_order("XRG/USDT", "market", "swap", 10)


class TestCcxtCompatibility:
    def test_id_attribute(self):
        ex = NonKYCExchange()
        assert ex.id == "nonkyc"

    def test_options_default_type_spot(self):
        ex = NonKYCExchange()
        assert ex.options["defaultType"] == "spot"

    def test_timeframes_match_ccxt_strings(self):
        ex = NonKYCExchange()
        assert "1m" in ex.timeframes
        assert "1h" in ex.timeframes
        assert "1d" in ex.timeframes
