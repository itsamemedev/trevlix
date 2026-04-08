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
_PLAN_MIN_REQUEST_INTERVAL = {
    "free": 2.0,
    "pro": 0.8,
    "developer": 0.3,
}


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
        self._last_api_call_at: float = 0.0
        self._min_request_interval: float = _PLAN_MIN_REQUEST_INTERVAL.get(self.plan, 1.0)
        self._max_currencies_per_request: int = (
            6 if self.plan == "free" else 20 if self.plan == "pro" else 40
        )

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
            return results if isinstance(results, list) else []
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

    def fetch_posts_multi(
        self,
        currencies: list[str],
        filter_type: str = "hot",
        kind: str = "news",
        regions: str = "en",
    ) -> list:
        """Batch-Request für mehrere Coins in EINEM API-Call.

        CryptoPanic akzeptiert kommagetrennte currencies. Diese Methode reduziert
        API-Calls deutlich und hilft, Limits einzuhalten.
        """
        if not currencies:
            return []
        normalized = []
        seen = set()
        for c in currencies:
            cc = self._normalize_coin(c)
            if cc and cc not in seen:
                normalized.append(cc)
                seen.add(cc)
        if not normalized:
            return []
        joined = ",".join(normalized[: self._max_currencies_per_request])
        return self.fetch_posts(joined, filter_type=filter_type, kind=kind, regions=regions)

    @staticmethod
    def _extract_post_currencies(post: dict) -> set[str]:
        out: set[str] = set()
        raw = post.get("currencies", [])
        if isinstance(raw, list):
            for c in raw:
                if isinstance(c, dict):
                    code = str(c.get("code", "")).upper().strip()
                    if code:
                        out.add(code)
                elif isinstance(c, str):
                    code = c.upper().strip()
                    if code:
                        out.add(code)
        return out

    def prefetch_scores(self, symbols: list[str], db=None) -> dict[str, tuple[float, str, int]]:
        """Prefetch für viele Symbole mit wenigen API-Calls.

        Returns:
            Mapping symbol -> (score, headline, count)
        """
        if not symbols:
            return {}
        now = time.time()
        result: dict[str, tuple[float, str, int]] = {}
        unresolved: list[str] = []
        for sym in symbols:
            key = self._cache_key_for_symbol(sym)
            if self._is_cache_valid(key):
                c = self._cache[key]
                result[sym] = (c["score"], c["headline"], c["count"])
                continue
            unresolved.append(sym)
        if not unresolved:
            return result
        # Gruppiert in batches entsprechend Plan-Limits
        batch_size = max(1, self._max_currencies_per_request)
        for i in range(0, len(unresolved), batch_size):
            batch_syms = unresolved[i : i + batch_size]
            coins = [self._normalize_coin(s) for s in batch_syms]
            posts = self.fetch_posts_multi(coins)
            if not posts and self._last_fetch_was_rate_limited:
                break
            by_coin: dict[str, list] = {c: [] for c in coins}
            for p in posts:
                pcs = self._extract_post_currencies(p)
                if not pcs:
                    # Falls API kein currency-tag liefert, als generisch für alle im Batch werten
                    for c in by_coin:
                        by_coin[c].append(p)
                else:
                    for c in pcs:
                        if c in by_coin:
                            by_coin[c].append(p)
            for sym in batch_syms:
                coin = self._normalize_coin(sym)
                coin_posts = by_coin.get(coin, [])
                score, headline, count = self.analyze_sentiment(coin_posts)
                key = self._cache_key_for_symbol(sym)
                self._cache[key] = {
                    "score": score,
                    "headline": headline,
                    "count": count,
                    "ts": now,
                }
                result[sym] = (score, headline, count)
                if db:
                    db.save_news(sym, score, headline, count)
        return result

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

        # In-Memory-Cache zuerst prüfen (schnellster Weg)
        if self._is_cache_valid(cache_key):
            c = self._cache[cache_key]
            return c["score"], c["headline"], c["count"]

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

        # Ohne Token: Feature deaktiviert, neutraler Score
        if not self.is_configured:
            score, headline, count = 0.0, "—", 0
        else:
            posts = self.fetch_posts(coin)
            if self._last_fetch_was_rate_limited and cache_key in self._cache:
                c = self._cache[cache_key]
                return c["score"], c["headline"], c["count"]
            score, headline, count = self.analyze_sentiment(posts)

            if self._last_fetch_was_rate_limited and count == 0:
                if stale_db_cached is not None:
                    return stale_db_cached
                return 0.0, "—", 0

        # Caches aktualisieren (mit Max-Size-Eviction)
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
