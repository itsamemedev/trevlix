"""
TREVLIX – CryptoPanic News Sentiment Service (API v2)
=====================================================
Analysiert Crypto-Nachrichten von CryptoPanic für Sentiment-Signale.

API v2 Basis-URL:
    https://cryptopanic.com/api/{plan}/v2/posts/

Unterstützte Plans: free, pro, developer
"""

import logging
import time

import httpx
import numpy as np

log = logging.getLogger("trevlix.cryptopanic")

# ── Sentiment-Wortlisten ─────────────────────────────────────────────────────
BULLISH_WORDS: list[str] = [
    "surge",
    "rally",
    "bull",
    "breakout",
    "all-time high",
    "adoption",
    "partnership",
    "launch",
    "upgrade",
    "integration",
    "bullish",
    "buy",
    "moon",
    "pump",
    "growth",
    "record",
    "positive",
    "gains",
    "rise",
    "soar",
]

BEARISH_WORDS: list[str] = [
    "crash",
    "bear",
    "hack",
    "scam",
    "ban",
    "lawsuit",
    "fraud",
    "dump",
    "sell",
    "plunge",
    "collapse",
    "regulation",
    "fear",
    "warning",
    "risk",
    "attack",
    "breach",
    "loss",
    "decline",
    "fall",
    "drop",
]

# CryptoPanic API v2 Basis-URL
_API_V2_URL = "https://cryptopanic.com/api/{plan}/v2/posts/"

# Standard-Timeout für API-Requests
_REQUEST_TIMEOUT = 10

# Cache-Dauer in Sekunden (30 Minuten)
CACHE_TTL = 1800
_RATE_LIMIT_FALLBACK_SECONDS = 60


class CryptoPanicClient:
    """
    CryptoPanic API v2 Client für News-Sentiment-Analyse.

    Nutzt die v2 API mit plan-basierter URL-Struktur:
        https://cryptopanic.com/api/{plan}/v2/posts/

    Args:
        token: CryptoPanic API Auth-Token
        plan: API-Plan (free, pro, developer). Default: free
    """

    def __init__(self, token: str, plan: str = "free"):
        self.token = token
        self.plan = plan if plan else "free"
        self._base_url = _API_V2_URL.format(plan=self.plan)
        self._cache: dict = {}
        self._cache_max_size: int = 200
        self._rate_limited_until: float = 0.0
        self._last_fetch_was_rate_limited: bool = False

    @property
    def is_configured(self) -> bool:
        """Prüft ob ein gültiger Token konfiguriert ist."""
        return bool(self.token and self.token.strip())

    def _is_cache_valid(self, symbol: str) -> bool:
        """Prüft ob der Cache für ein Symbol noch gültig ist."""
        if symbol not in self._cache:
            return False
        return (time.time() - self._cache[symbol]["ts"]) < CACHE_TTL

    def fetch_posts(
        self, currency: str, filter_type: str = "hot", kind: str = "news", regions: str = "en"
    ) -> list:
        """
        Holt Posts von der CryptoPanic API v2.

        Args:
            currency: Währungskürzel (z.B. "BTC", "ETH")
            filter_type: Filter (rising, hot, bullish, bearish, important)
            kind: Art der Posts (news, media)
            regions: Sprachregion (en, de, es, etc.)

        Returns:
            Liste von Post-Dictionaries
        """
        if not self.is_configured:
            return []
        self._last_fetch_was_rate_limited = False

        now = time.time()
        if now < self._rate_limited_until:
            self._last_fetch_was_rate_limited = True
            wait_s = int(self._rate_limited_until - now)
            log.debug("CryptoPanic Rate-Limit aktiv (%ss verbleibend) – überspringe %s", wait_s, currency)
            return []

        params = {
            "auth_token": self.token,
            "currencies": currency.upper(),
            "filter": filter_type,
            "kind": kind,
            "regions": regions,
            "public": "true",
        }

        try:
            resp = httpx.get(self._base_url, params=params, timeout=_REQUEST_TIMEOUT)
            resp.raise_for_status()
            return resp.json().get("results", [])
        except httpx.HTTPStatusError as e:
            if e.response is not None and e.response.status_code == 429:
                retry_after_raw = (e.response.headers or {}).get("Retry-After", "").strip()
                try:
                    retry_after = max(int(float(retry_after_raw)), 1)
                except (TypeError, ValueError):
                    retry_after = _RATE_LIMIT_FALLBACK_SECONDS

                self._rate_limited_until = max(self._rate_limited_until, time.time() + retry_after)
                self._last_fetch_was_rate_limited = True
                log.warning(
                    "CryptoPanic API v2 Rate-Limit (429) für %s – pausiere %ss",
                    currency,
                    retry_after,
                )
                return []
            log.warning("CryptoPanic API v2 HTTP-Fehler für %s: %s", currency, e)
            return []
        except httpx.RequestError as e:
            log.debug("CryptoPanic API v2 Fehler für %s: %s", currency, e)
            return []
        except (ValueError, KeyError) as e:
            log.debug("CryptoPanic API v2 Parse-Fehler für %s: %s", currency, e)
            return []

    def analyze_sentiment(self, posts: list) -> tuple[float, str, int]:
        """
        Analysiert die Sentiment-Werte einer Liste von Posts.

        Scoring:
            - Vote-basiert: (positive - negative) / max(total, 1) * 0.5
            - Keyword-basiert: +0.1 pro bullish Wort, -0.1 pro bearish Wort
            - Ergebnis wird auf [-1, +1] geclippt

        Args:
            posts: Liste von CryptoPanic Post-Dicts

        Returns:
            Tuple von (score, headline, article_count)
        """
        if not posts:
            return 0.0, "—", 0

        count = len(posts)
        scores = []

        for p in posts[:10]:
            title = p.get("title", "").lower()
            votes = p.get("votes") or {}
            if not isinstance(votes, dict):
                votes = {}
            pos = votes.get("positive", 0) or 0
            neg = votes.get("negative", 0) or 0

            # Vote-basierter Score
            vote_score = (pos - neg) / max(pos + neg, 1) * 0.5

            # Keyword-basierter Score
            kw_score = sum(0.1 for w in BULLISH_WORDS if w in title)
            kw_score -= sum(0.1 for w in BEARISH_WORDS if w in title)

            scores.append(float(np.clip(vote_score + kw_score, -1, 1)))

        if scores and posts:
            score = float(np.clip(np.mean(scores), -1, 1))
            headline = posts[0].get("title", "—")[:200]
        else:
            score = 0.0
            headline = "—"

        return score, headline, count

    def get_score(self, symbol: str, db=None) -> tuple[float, str, int]:
        """
        Holt den Sentiment-Score für ein Symbol.

        Nutzt internen Cache (30 Min) und optionalen DB-Cache.

        Args:
            symbol: Trading-Paar (z.B. "BTC/USDT")
            db: Optionale DB-Instanz mit get_news/save_news Methoden

        Returns:
            Tuple von (score, headline, article_count)
        """
        # DB-Cache prüfen
        if db:
            cached = db.get_news(symbol)
            if cached:
                return float(cached["score"]), cached["headline"], cached["article_count"]

        # In-Memory-Cache prüfen
        if self._is_cache_valid(symbol):
            c = self._cache[symbol]
            return c["score"], c["headline"], c["count"]

        coin = symbol.replace("/USDT", "").replace("/USD", "").upper()

        # Ohne Token: Feature deaktiviert, neutraler Score
        if not self.is_configured:
            score, headline, count = 0.0, "—", 0
        else:
            posts = self.fetch_posts(coin)
            if self._last_fetch_was_rate_limited and symbol in self._cache:
                c = self._cache[symbol]
                return c["score"], c["headline"], c["count"]
            score, headline, count = self.analyze_sentiment(posts)

            if self._last_fetch_was_rate_limited and count == 0:
                return 0.0, "—", 0

        # Caches aktualisieren (mit Max-Size-Eviction)
        self._cache[symbol] = {
            "score": score,
            "headline": headline,
            "count": count,
            "ts": time.time(),
        }
        if len(self._cache) > self._cache_max_size:
            oldest = min(self._cache, key=lambda k: self._cache[k].get("ts", 0))
            if oldest != symbol:
                del self._cache[oldest]

        if db:
            db.save_news(symbol, score, headline, count)

        return score, headline, count
