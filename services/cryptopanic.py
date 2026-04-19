"""
TREVLIX – CryptoPanic News Sentiment Service (API v2 + v1 Fallback)
====================================================================
Analysiert Crypto-Nachrichten von CryptoPanic für Sentiment-Signale.

API Basis-URL:
    https://cryptopanic.com/api/{plan}/v2/posts/
Fallback (legacy):
    https://cryptopanic.com/api/v1/posts/

Unterstützte Plans: free, pro, developer
"""

import logging
import threading
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

# CryptoPanic API v2 Basis-URL + v1 Fallback
_API_V2_URL = "https://cryptopanic.com/api/{plan}/v2/posts/"
_API_V1_FALLBACK_URL = "https://cryptopanic.com/api/v1/posts/"

# Standard-Timeout für API-Requests
_REQUEST_TIMEOUT = 10

# Cache-Dauer in Sekunden (30 Minuten)
CACHE_TTL = 1800
_RATE_LIMIT_FALLBACK_SECONDS = 60
_UNSUPPORTED_CURRENCY_TTL_SECONDS = 6 * 3600
_PLAN_MIN_REQUEST_INTERVAL = {
    "free": 2.0,
    "pro": 0.8,
    "developer": 0.3,
}


class CryptoPanicClient:
    """
    CryptoPanic API Client für News-Sentiment-Analyse.

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
        # Non-free plans fall back to free/v2/ before legacy v1 (v1 is deprecated and returns 404)
        _free_v2_url = _API_V2_URL.format(plan="free")
        self._fallback_url = _free_v2_url if self.plan != "free" else _API_V1_FALLBACK_URL
        self._active_url = self._base_url
        self._cache: dict = {}
        self._cache_max_size: int = 200
        self._cache_lock = threading.Lock()
        self._rate_limited_until: float = 0.0
        self._last_fetch_was_rate_limited: bool = False
        self._last_api_call_at: float = 0.0
        self._min_request_interval: float = _PLAN_MIN_REQUEST_INTERVAL.get(self.plan, 1.0)
        self._unsupported_currencies: dict[str, float] = {}

    def _normalize_coin(self, symbol: str) -> str:
        """Normalisiert Symbolnamen auf Coin-Ebene für API/Cache."""
        raw = str(symbol or "").upper().strip()
        if "/" in raw:
            raw = raw.split("/", 1)[0]
        for suffix in ("USDT", "USD", "USDC"):
            if raw.endswith(suffix) and len(raw) > len(suffix):
                raw = raw[: -len(suffix)]
                break
        return raw or "BTC"

    def _cache_key_for_symbol(self, symbol: str) -> str:
        return f"{self._normalize_coin(symbol)}:{self.plan}"

    @property
    def is_configured(self) -> bool:
        """Prüft ob ein gültiger Token konfiguriert ist."""
        return bool(self.token and self.token.strip())

    def _is_cache_valid(self, cache_key: str) -> bool:
        """Prüft ob der Cache für den Cache-Key noch gültig ist."""
        if cache_key not in self._cache:
            return False
        return (time.time() - self._cache[cache_key]["ts"]) < CACHE_TTL

    def _request_posts(
        self, url: str, params: dict, currency: str
    ) -> tuple[bool, list, int | None]:
        """
        Führt einen einzelnen API-Request aus.

        Returns:
            Tuple (success, results, error_status).
            - success=True, results=list, error_status=None bei 2xx-Antworten.
            - success=False, results=[], error_status=<code> bei HTTP-Fehler.
            - success=False, results=[], error_status=None bei Netzwerk-/Parse-Fehlern
              oder wenn der Call aufgrund eines 429 als rate-limited markiert wurde.
        """
        try:
            resp = httpx.get(url, params=params, timeout=_REQUEST_TIMEOUT)
            self._last_api_call_at = time.time()
            resp.raise_for_status()
            remaining = (resp.headers or {}).get("X-RateLimit-Remaining")
            reset_raw = (resp.headers or {}).get("X-RateLimit-Reset")
            if str(remaining).strip() == "0":
                try:
                    reset_after = max(int(float(reset_raw)), 1)
                except (TypeError, ValueError):
                    reset_after = _RATE_LIMIT_FALLBACK_SECONDS
                self._rate_limited_until = max(self._rate_limited_until, time.time() + reset_after)
                log.warning(
                    "CryptoPanic API-Limit erschöpft laut Header für %s – pausiere %ss",
                    currency,
                    reset_after,
                )
            payload = resp.json()
            results = payload.get("results", []) if isinstance(payload, dict) else []
            return True, (results if isinstance(results, list) else []), None
        except httpx.HTTPStatusError as e:
            self._last_api_call_at = time.time()
            status = e.response.status_code if e.response is not None else None
            if status == 429:
                retry_after_raw = (e.response.headers or {}).get("Retry-After", "").strip()
                try:
                    retry_after = max(int(float(retry_after_raw)), 1)
                except (TypeError, ValueError):
                    retry_after = _RATE_LIMIT_FALLBACK_SECONDS
                self._rate_limited_until = max(self._rate_limited_until, time.time() + retry_after)
                self._last_fetch_was_rate_limited = True
                log.warning(
                    "CryptoPanic API Rate-Limit (429) für %s – pausiere %ss", currency, retry_after
                )
                return False, [], None
            return False, [], status
        except httpx.RequestError as e:
            log.debug("CryptoPanic Netzwerk-Fehler für %s: %s", currency, e)
            return False, [], None
        except (ValueError, KeyError) as e:
            log.debug("CryptoPanic Parse-Fehler für %s: %s", currency, e)
            return False, [], None

    def fetch_posts(
        self, currency: str, filter_type: str = "hot", kind: str = "news", regions: str = "en"
    ) -> list:
        """
        Holt Posts von der CryptoPanic API.

        Versucht zunächst die aktive URL (standardmäßig v2). Bei 404/410 wird der
        currencies-Filter entfernt und bei Bedarf auf v1 zurückgefallen, damit auch
        Accounts ohne v2-Zugriff und nicht-indexierte Coins Ergebnisse liefern.

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
            log.debug(
                "CryptoPanic Rate-Limit aktiv (%ss verbleibend) – überspringe %s", wait_s, currency
            )
            return []
        if (
            self._last_api_call_at > 0
            and (now - self._last_api_call_at) < self._min_request_interval
        ):
            self._last_fetch_was_rate_limited = True
            return []

        currency_norm = str(currency or "").upper().strip()
        unsupported_until = self._unsupported_currencies.get(currency_norm, 0.0)
        use_currency_filter = bool(currency_norm) and now >= unsupported_until

        base_params = {
            "auth_token": self.token,
            "filter": filter_type,
            "kind": kind,
            "regions": regions,
            "public": "true",
        }

        # Kandidaten-URLs: aktuelle URL zuerst, dann ggf. v1-Legacy.
        urls_to_try: list[str] = [self._active_url]
        if self._active_url != self._fallback_url:
            urls_to_try.append(self._fallback_url)

        not_found_seen = False
        currency_fallback_used = False
        for url in urls_to_try:
            # 1. Versuch: mit currencies-Filter (falls aktiv)
            if use_currency_filter:
                params = {**base_params, "currencies": currency_norm}
                success, results, err_status = self._request_posts(url, params, currency)
                if success:
                    self._promote_url(url)
                    return results
                if err_status is None:
                    # Rate-Limit, Netzwerk- oder Parse-Fehler → nicht weiter versuchen
                    return []
                if err_status in (404, 410):
                    not_found_seen = True
                    # currencies-Filter nicht unterstützt → ohne erneut versuchen
                    self._unsupported_currencies[currency_norm] = (
                        time.time() + _UNSUPPORTED_CURRENCY_TTL_SECONDS
                    )
                    currency_fallback_used = True
                else:
                    log.warning(
                        "CryptoPanic HTTP-Fehler %s für %s auf %s", err_status, currency, url
                    )
                    return []

            # 2. Versuch: ohne currencies-Filter
            success, results, err_status = self._request_posts(url, base_params, currency)
            if success:
                if currency_fallback_used:
                    log.info(
                        "CryptoPanic: currencies=%s nicht unterstützt – nutze Fallback ohne currencies",
                        currency_norm,
                    )
                self._promote_url(url)
                return results
            if err_status is None:
                return []
            if err_status in (404, 410):
                not_found_seen = True
                # Nächste URL (v1) versuchen
                continue
            log.warning("CryptoPanic HTTP-Fehler %s für %s auf %s", err_status, currency, url)
            return []

        if not_found_seen:
            log.warning(
                "CryptoPanic: v2 und v1 Endpunkte lieferten 404/410 für %s – keine News verfügbar",
                currency,
            )
        return []

    def _promote_url(self, url: str) -> None:
        """Setzt die übergebene URL als aktive URL für nachfolgende Requests."""
        if url != self._active_url:
            if url == self._fallback_url:
                log.info("CryptoPanic: v2 Endpoint nicht verfügbar – fallback auf v1 aktiviert")
            self._active_url = url

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
        coin = self._normalize_coin(symbol)
        cache_key = self._cache_key_for_symbol(symbol)
        stale_db_cached = None

        # DB-Cache prüfen
        if db:
            cached = db.get_news(symbol)
            if cached:
                try:
                    stale_db_cached = (
                        float(cached.get("score", 0.0)),
                        str(cached.get("headline", "—") or "—"),
                        int(cached.get("article_count", 0) or 0),
                    )
                except (TypeError, ValueError, AttributeError):
                    stale_db_cached = None
                if stale_db_cached is not None:
                    return stale_db_cached

        # In-Memory-Cache prüfen (atomares Read unter Lock – verhindert Race
        # mit gleichzeitiger Eviction am Ende der Methode).
        with self._cache_lock:
            if self._is_cache_valid(cache_key):
                c = self._cache[cache_key]
                return c["score"], c["headline"], c["count"]

        # Ohne Token: Feature deaktiviert, neutraler Score
        if not self.is_configured:
            score, headline, count = 0.0, "—", 0
        else:
            posts = self.fetch_posts(coin)
            if self._last_fetch_was_rate_limited:
                with self._cache_lock:
                    if cache_key in self._cache:
                        c = self._cache[cache_key]
                        return c["score"], c["headline"], c["count"]
            score, headline, count = self.analyze_sentiment(posts)

            if self._last_fetch_was_rate_limited and count == 0:
                if stale_db_cached is not None:
                    return stale_db_cached
                return 0.0, "—", 0

        # Caches aktualisieren (mit Max-Size-Eviction) – atomar unter Lock
        with self._cache_lock:
            self._cache[cache_key] = {
                "score": score,
                "headline": headline,
                "count": count,
                "ts": time.time(),
            }
            if len(self._cache) > self._cache_max_size:
                oldest = min(self._cache, key=lambda k: self._cache[k].get("ts", 0))
                if oldest != cache_key:
                    del self._cache[oldest]

        if db:
            db.save_news(symbol, score, headline, count)

        return score, headline, count
