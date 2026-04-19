"""
TREVLIX – CryptoPanic API v2 Service Tests
===========================================
Unit-Tests für den CryptoPanic News-Sentiment-Service.
"""

from unittest.mock import MagicMock, patch

import pytest

from services.cryptopanic import (
    _API_V1_FALLBACK_URL,
    _API_V2_URL,
    BEARISH_WORDS,
    BULLISH_WORDS,
    CryptoPanicClient,
)

# ── Client Initialisierung ───────────────────────────────────────────────────


class TestCryptoPanicClientInit:
    """Tests für die Client-Initialisierung."""

    def test_default_plan(self):
        client = CryptoPanicClient(token="test-token")
        assert client.plan == "free"
        assert "/free/v2/" in client._base_url

    def test_pro_plan(self):
        client = CryptoPanicClient(token="test-token", plan="pro")
        assert client.plan == "pro"
        assert "/pro/v2/" in client._base_url

    def test_developer_plan(self):
        client = CryptoPanicClient(token="test-token", plan="developer")
        assert client.plan == "developer"
        assert "/developer/v2/" in client._base_url

    def test_empty_plan_defaults_to_free(self):
        client = CryptoPanicClient(token="test-token", plan="")
        assert client.plan == "free"

    def test_is_configured_with_token(self):
        client = CryptoPanicClient(token="my-token")
        assert client.is_configured is True

    def test_not_configured_without_token(self):
        client = CryptoPanicClient(token="")
        assert client.is_configured is False

    def test_not_configured_with_whitespace(self):
        client = CryptoPanicClient(token="   ")
        assert client.is_configured is False


# ── API v2 URL-Format ────────────────────────────────────────────────────────


class TestApiV2Url:
    """Tests für das API v2 URL-Format."""

    def test_v2_url_template(self):
        assert "/v2/posts/" in _API_V2_URL
        assert "{plan}" in _API_V2_URL

    def test_url_construction_free(self):
        url = _API_V2_URL.format(plan="free")
        assert url == "https://cryptopanic.com/api/free/v2/posts/"

    def test_url_construction_pro(self):
        url = _API_V2_URL.format(plan="pro")
        assert url == "https://cryptopanic.com/api/pro/v2/posts/"

    def test_v1_fallback_url(self):
        assert _API_V1_FALLBACK_URL == "https://cryptopanic.com/api/v1/posts/"


# ── Sentiment-Analyse ────────────────────────────────────────────────────────


class TestSentimentAnalysis:
    """Tests für die Sentiment-Score-Berechnung."""

    @pytest.fixture
    def client(self):
        return CryptoPanicClient(token="test-token")

    def test_empty_posts_returns_neutral(self, client):
        score, headline, count = client.analyze_sentiment([])
        assert score == 0.0
        assert headline == "—"
        assert count == 0

    def test_bullish_post_positive_score(self, client):
        posts = [
            {
                "title": "Bitcoin surge and rally to all-time high",
                "votes": {"positive": 10, "negative": 1},
            }
        ]
        score, headline, count = client.analyze_sentiment(posts)
        assert score > 0
        assert count == 1
        assert "surge" in headline.lower()

    def test_bearish_post_negative_score(self, client):
        posts = [
            {
                "title": "Bitcoin crash and bear market collapse",
                "votes": {"positive": 1, "negative": 10},
            }
        ]
        score, headline, count = client.analyze_sentiment(posts)
        assert score < 0
        assert count == 1

    def test_neutral_post(self, client):
        posts = [
            {
                "title": "Bitcoin price update today",
                "votes": {"positive": 5, "negative": 5},
            }
        ]
        score, headline, count = client.analyze_sentiment(posts)
        assert -0.3 <= score <= 0.3

    def test_score_clamped_to_range(self, client):
        posts = [
            {
                "title": " ".join(BULLISH_WORDS),
                "votes": {"positive": 100, "negative": 0},
            }
        ]
        score, _, _ = client.analyze_sentiment(posts)
        assert -1.0 <= score <= 1.0

    def test_multiple_posts_averaged(self, client):
        posts = [
            {"title": "bullish surge rally", "votes": {"positive": 10, "negative": 0}},
            {"title": "crash bear dump", "votes": {"positive": 0, "negative": 10}},
        ]
        score, _, count = client.analyze_sentiment(posts)
        assert count == 2
        # Should be roughly neutral (average of positive and negative)
        assert -0.5 <= score <= 0.5

    def test_max_10_posts_analyzed(self, client):
        posts = [{"title": f"Post {i}", "votes": {"positive": 1, "negative": 0}} for i in range(20)]
        # Should still work (only first 10 analyzed)
        score, _, count = client.analyze_sentiment(posts)
        assert count == 20  # Count is total posts


# ── Wortlisten ────────────────────────────────────────────────────────────────


class TestWordLists:
    """Tests für die Bullish/Bearish-Wortlisten."""

    def test_bullish_words_not_empty(self):
        assert len(BULLISH_WORDS) > 0

    def test_bearish_words_not_empty(self):
        assert len(BEARISH_WORDS) > 0

    def test_no_overlap(self):
        overlap = set(BULLISH_WORDS) & set(BEARISH_WORDS)
        assert len(overlap) == 0, f"Überlappende Wörter: {overlap}"

    def test_all_lowercase(self):
        for w in BULLISH_WORDS + BEARISH_WORDS:
            assert w == w.lower(), f"Nicht lowercase: {w}"


# ── fetch_posts (gemockt) ────────────────────────────────────────────────────


class TestFetchPosts:
    """Tests für die API-Aufrufe (mit Mocking)."""

    @patch("services.cryptopanic.httpx.get")
    def test_fetch_posts_success(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "results": [
                {"title": "BTC Rally", "votes": {"positive": 5, "negative": 1}},
            ]
        }
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        client = CryptoPanicClient(token="test-token", plan="free")
        posts = client.fetch_posts("")

        assert len(posts) == 1
        assert posts[0]["title"] == "BTC Rally"

        # Prüfe dass v2 URL verwendet wird
        call_args = mock_get.call_args
        assert "free/v2/posts" in call_args[0][0]

    @patch("services.cryptopanic.httpx.get")
    def test_fetch_posts_with_pro_plan(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"results": []}
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        client = CryptoPanicClient(token="test-token", plan="pro")
        client.fetch_posts("ETH")

        call_args = mock_get.call_args
        assert "pro/v2/posts" in call_args[0][0]

    @patch("services.cryptopanic.httpx.get")
    def test_fetch_posts_falls_back_to_v1_when_v2_returns_404(self, mock_get):
        import httpx as hx

        req_v2 = hx.Request("GET", "https://cryptopanic.com/api/free/v2/posts/")
        resp_404 = MagicMock()
        resp_404.raise_for_status.side_effect = hx.HTTPStatusError(
            "not found", request=req_v2, response=hx.Response(404, request=req_v2)
        )

        resp_v1 = MagicMock()
        resp_v1.raise_for_status = MagicMock()
        resp_v1.json.return_value = {"results": [{"title": "Legacy endpoint works"}]}

        mock_get.side_effect = [resp_404, resp_v1]

        client = CryptoPanicClient(token="test-token", plan="free")
        posts = client.fetch_posts("")

        assert posts and posts[0]["title"] == "Legacy endpoint works"
        assert "free/v2/posts" in mock_get.call_args_list[0][0][0]
        assert "/api/v1/posts/" in mock_get.call_args_list[1][0][0]

    @patch("services.cryptopanic.httpx.get")
    def test_fetch_posts_passes_parameters(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"results": []}
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        client = CryptoPanicClient(token="my-secret-token", plan="free")
        client.fetch_posts("BTC", filter_type="rising", kind="media", regions="de")

        call_args = mock_get.call_args
        params = call_args[1]["params"]
        assert params["auth_token"] == "my-secret-token"
        assert params["currencies"] == "BTC"
        assert params["filter"] == "rising"
        assert params["kind"] == "media"
        assert params["regions"] == "de"

    def test_fetch_posts_without_token_returns_empty(self):
        client = CryptoPanicClient(token="")
        posts = client.fetch_posts("BTC")
        assert posts == []

    @patch("services.cryptopanic.httpx.get")
    def test_fetch_posts_network_error(self, mock_get):
        import httpx as hx

        mock_get.side_effect = hx.ConnectError("Network error")

        client = CryptoPanicClient(token="test-token")
        posts = client.fetch_posts("BTC")
        assert posts == []

    @patch("services.cryptopanic.httpx.get")
    def test_fetch_posts_rate_limited_sets_pause(self, mock_get):
        import httpx as hx

        response = hx.Response(
            429, headers={"Retry-After": "15"}, request=hx.Request("GET", "https://x")
        )
        mock_get.side_effect = hx.HTTPStatusError(
            "rate limited", request=response.request, response=response
        )

        client = CryptoPanicClient(token="test-token")
        posts = client.fetch_posts("BTC")

        assert posts == []
        assert client._last_fetch_was_rate_limited is True
        assert client._rate_limited_until > 0

    @patch("services.cryptopanic.httpx.get")
    def test_fetch_posts_skips_http_while_rate_limited(self, mock_get):
        client = CryptoPanicClient(token="test-token")
        client._rate_limited_until = 9999999999.0

        posts = client.fetch_posts("BTC")

        assert posts == []
        mock_get.assert_not_called()

    @patch("services.cryptopanic.httpx.get")
    def test_fetch_posts_404_with_currency_falls_back_without_currency(self, mock_get):
        import httpx as hx

        req = hx.Request("GET", "https://cryptopanic.com/api/developer/v2/posts/")
        resp_404 = hx.Response(404, request=req)
        err_404 = hx.HTTPStatusError("not found", request=req, response=resp_404)

        ok_resp = MagicMock()
        ok_resp.headers = {}
        ok_resp.raise_for_status = MagicMock()
        ok_resp.json.return_value = {"results": [{"title": "Fallback news"}]}

        mock_get.side_effect = [err_404, ok_resp]

        client = CryptoPanicClient(token="test-token", plan="developer")
        posts = client.fetch_posts("MORPHO")

        assert posts
        assert posts[0]["title"] == "Fallback news"
        assert mock_get.call_count == 2
        first_params = mock_get.call_args_list[0].kwargs["params"]
        second_params = mock_get.call_args_list[1].kwargs["params"]
        assert first_params["currencies"] == "MORPHO"
        assert "currencies" not in second_params

    @patch("services.cryptopanic.httpx.get")
    def test_fetch_posts_chains_v2_404_to_free_when_currency_fallback_also_404(self, mock_get):
        """developer/v2 404 mit + ohne currencies → muss auf free/v2/ weiterfallen (v1 ist deprecated)."""
        import httpx as hx

        req_v2 = hx.Request("GET", "https://cryptopanic.com/api/developer/v2/posts/")
        err_404 = hx.HTTPStatusError(
            "not found", request=req_v2, response=hx.Response(404, request=req_v2)
        )

        ok_resp = MagicMock()
        ok_resp.headers = {}
        ok_resp.raise_for_status = MagicMock()
        ok_resp.json.return_value = {"results": [{"title": "free/v2 news"}]}

        # Erwartete Aufrufreihenfolge:
        # 1) developer/v2 mit currencies=RENDER → 404
        # 2) developer/v2 ohne currencies → 404
        # 3) free/v2 mit currencies=RENDER → 404  (use_currency_filter war vor Loop True)
        # 4) free/v2 ohne currencies → 200
        resp_404_a = MagicMock()
        resp_404_a.raise_for_status.side_effect = err_404
        resp_404_b = MagicMock()
        resp_404_b.raise_for_status.side_effect = err_404
        resp_404_c = MagicMock()
        resp_404_c.raise_for_status.side_effect = err_404

        mock_get.side_effect = [resp_404_a, resp_404_b, resp_404_c, ok_resp]

        client = CryptoPanicClient(token="test-token", plan="developer")
        posts = client.fetch_posts("RENDER")

        assert posts
        assert posts[0]["title"] == "free/v2 news"
        assert mock_get.call_count == 4
        assert "developer/v2/posts" in mock_get.call_args_list[0][0][0]
        assert "developer/v2/posts" in mock_get.call_args_list[1][0][0]
        assert "free/v2/posts" in mock_get.call_args_list[2][0][0]
        assert "free/v2/posts" in mock_get.call_args_list[3][0][0]
        # Nachfolgende Calls sollten direkt auf free/v2 gehen
        assert "free/v2/posts/" in client._active_url

    @patch("services.cryptopanic.httpx.get")
    def test_fetch_posts_skips_currency_filter_after_known_404(self, mock_get):
        ok_resp = MagicMock()
        ok_resp.headers = {}
        ok_resp.raise_for_status = MagicMock()
        ok_resp.json.return_value = {"results": []}
        mock_get.return_value = ok_resp

        client = CryptoPanicClient(token="test-token", plan="developer")
        client._unsupported_currencies["MORPHO"] = 9999999999.0

        client.fetch_posts("MORPHO")
        params = mock_get.call_args.kwargs["params"]
        assert "currencies" not in params


# ── get_score Integration ─────────────────────────────────────────────────────


class TestGetScore:
    """Tests für die get_score Methode mit DB-Mock."""

    @patch("services.cryptopanic.httpx.get")
    def test_get_score_with_db_cache(self, mock_get):
        db_mock = MagicMock()
        db_mock.get_news.return_value = {
            "score": 0.5,
            "headline": "Cached headline",
            "article_count": 3,
        }

        client = CryptoPanicClient(token="test-token")
        score, headline, count = client.get_score("BTC/USDT", db=db_mock)

        assert score == 0.5
        assert headline == "Cached headline"
        assert count == 3
        mock_get.assert_not_called()

    @patch("services.cryptopanic.httpx.get")
    def test_get_score_saves_to_db(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "results": [
                {"title": "Bitcoin surge", "votes": {"positive": 8, "negative": 2}},
            ]
        }
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        db_mock = MagicMock()
        db_mock.get_news.return_value = None

        client = CryptoPanicClient(token="test-token")
        score, headline, count = client.get_score("BTC/USDT", db=db_mock)

        assert score > 0
        db_mock.save_news.assert_called_once()

    def test_get_score_without_token(self):
        client = CryptoPanicClient(token="")
        score, headline, count = client.get_score("BTC/USDT")
        assert score == 0.0
        assert headline == "—"
        assert count == 0

    @patch("services.cryptopanic.httpx.get")
    def test_get_score_normalizes_symbol_without_slash(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.headers = {}
        mock_resp.json.return_value = {
            "results": [
                {"title": "Bitcoin surge", "votes": {"positive": 5, "negative": 1}},
            ]
        }
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        client = CryptoPanicClient(token="test-token")
        score, headline, count = client.get_score("BTCUSDT")
        assert count == 1
        assert score > 0
        assert "Bitcoin" in headline

    @patch("services.cryptopanic.httpx.get")
    def test_get_score_uses_stale_cache_on_rate_limit(self, mock_get):
        import httpx as hx

        response = hx.Response(
            429, headers={"Retry-After": "10"}, request=hx.Request("GET", "https://x")
        )
        mock_get.side_effect = hx.HTTPStatusError(
            "rate limited", request=response.request, response=response
        )

        client = CryptoPanicClient(token="test-token")
        client._cache["BTC:free"] = {
            "score": 0.42,
            "headline": "Cached BTC headline",
            "count": 7,
            "ts": 1.0,  # absichtlich veraltet
        }

        score, headline, count = client.get_score("BTC/USDT")

        assert score == 0.42
        assert headline == "Cached BTC headline"
        assert count == 7

    @patch("services.cryptopanic.httpx.get")
    def test_get_score_uses_shared_coin_cache_for_usd_pairs(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.headers = {}
        mock_resp.json.return_value = {
            "results": [
                {"title": "Bitcoin surge", "votes": {"positive": 8, "negative": 2}},
            ]
        }
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        client = CryptoPanicClient(token="test-token")
        first = client.get_score("BTC/USDT")
        second = client.get_score("BTC/USD")

        assert mock_get.call_count == 1
        assert second == first


class TestRateLimitMitigation:
    @patch("services.cryptopanic.httpx.get")
    def test_fetch_posts_honors_min_request_interval(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.headers = {}
        mock_resp.json.return_value = {"results": [{"title": "BTC"}]}
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        client = CryptoPanicClient(token="test-token", plan="developer")
        posts1 = client.fetch_posts("BTC")
        posts2 = client.fetch_posts("ETH")

        assert posts1
        assert posts2 == []
        assert client._last_fetch_was_rate_limited is True
        assert mock_get.call_count == 1

    def test_get_score_ignores_broken_db_cache_payload(self):
        db_mock = MagicMock()
        db_mock.get_news.return_value = {"score": "x", "headline": None, "article_count": "oops"}

        client = CryptoPanicClient(token="")
        score, headline, count = client.get_score("BTC/USDT", db=db_mock)

        assert score == 0.0
        assert headline == "—"
        assert count == 0
