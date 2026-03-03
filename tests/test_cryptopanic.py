"""
TREVLIX – CryptoPanic API v2 Service Tests
===========================================
Unit-Tests für den CryptoPanic News-Sentiment-Service.
"""

from unittest.mock import MagicMock, patch

import pytest

from services.cryptopanic import (
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
        posts = [{
            "title": "Bitcoin surge and rally to all-time high",
            "votes": {"positive": 10, "negative": 1},
        }]
        score, headline, count = client.analyze_sentiment(posts)
        assert score > 0
        assert count == 1
        assert "surge" in headline.lower()

    def test_bearish_post_negative_score(self, client):
        posts = [{
            "title": "Bitcoin crash and bear market collapse",
            "votes": {"positive": 1, "negative": 10},
        }]
        score, headline, count = client.analyze_sentiment(posts)
        assert score < 0
        assert count == 1

    def test_neutral_post(self, client):
        posts = [{
            "title": "Bitcoin price update today",
            "votes": {"positive": 5, "negative": 5},
        }]
        score, headline, count = client.analyze_sentiment(posts)
        assert -0.3 <= score <= 0.3

    def test_score_clamped_to_range(self, client):
        posts = [{
            "title": " ".join(BULLISH_WORDS),
            "votes": {"positive": 100, "negative": 0},
        }]
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
        posts = [
            {"title": f"Post {i}", "votes": {"positive": 1, "negative": 0}}
            for i in range(20)
        ]
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

    @patch("services.cryptopanic.requests.get")
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
        posts = client.fetch_posts("BTC")

        assert len(posts) == 1
        assert posts[0]["title"] == "BTC Rally"

        # Prüfe dass v2 URL verwendet wird
        call_args = mock_get.call_args
        assert "free/v2/posts" in call_args[0][0]

    @patch("services.cryptopanic.requests.get")
    def test_fetch_posts_with_pro_plan(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"results": []}
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        client = CryptoPanicClient(token="test-token", plan="pro")
        client.fetch_posts("ETH")

        call_args = mock_get.call_args
        assert "pro/v2/posts" in call_args[0][0]

    @patch("services.cryptopanic.requests.get")
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

    @patch("services.cryptopanic.requests.get")
    def test_fetch_posts_network_error(self, mock_get):
        import requests as req
        mock_get.side_effect = req.exceptions.ConnectionError("Network error")

        client = CryptoPanicClient(token="test-token")
        posts = client.fetch_posts("BTC")
        assert posts == []


# ── get_score Integration ─────────────────────────────────────────────────────


class TestGetScore:
    """Tests für die get_score Methode mit DB-Mock."""

    @patch("services.cryptopanic.requests.get")
    def test_get_score_with_db_cache(self, mock_get):
        db_mock = MagicMock()
        db_mock.get_news.return_value = {
            "score": 0.5, "headline": "Cached headline", "article_count": 3
        }

        client = CryptoPanicClient(token="test-token")
        score, headline, count = client.get_score("BTC/USDT", db=db_mock)

        assert score == 0.5
        assert headline == "Cached headline"
        assert count == 3
        mock_get.assert_not_called()

    @patch("services.cryptopanic.requests.get")
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
