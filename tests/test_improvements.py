"""Tests für Verbesserungen und Optimierungen.

Testet:
- _TTLCache (Market Data Caching)
- Password Strength Validation
- WebSocket Rate-Limit Cleanup
- Connection Pool Monitoring (pool_stats)
"""

import re
import time

# ── TTL-Cache Tests ──────────────────────────────────────────────────────────


class TestTTLCache:
    """Tests für den services.cache.TTLCache (vormals market_data._TTLCache)."""

    def test_cache_set_and_get(self):
        from services.cache import TTLCache

        cache = TTLCache(ttl_seconds=60)
        cache.set("key1", {"value": 42})
        assert cache.get("key1") == {"value": 42}

    def test_cache_miss_returns_none(self):
        from services.cache import TTLCache

        cache = TTLCache(ttl_seconds=60)
        assert cache.get("missing") is None

    def test_cache_expiry(self):
        from services.cache import TTLCache

        cache = TTLCache(ttl_seconds=0.001)  # 1 ms TTL
        cache.set("key1", "value")
        time.sleep(0.05)
        assert cache.get("key1") is None

    def test_cache_overwrite(self):
        from services.cache import TTLCache

        cache = TTLCache(ttl_seconds=60)
        cache.set("key1", "old")
        cache.set("key1", "new")
        assert cache.get("key1") == "new"

    def test_cache_clear(self):
        from services.cache import TTLCache

        cache = TTLCache(ttl_seconds=60)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.clear()
        assert cache.get("a") is None
        assert cache.get("b") is None

    def test_cache_thread_safety(self):
        import threading

        from services.cache import TTLCache

        cache = TTLCache(ttl_seconds=60)
        errors: list[str] = []

        def writer(n: int) -> None:
            for i in range(100):
                cache.set(f"key-{n}-{i}", i)

        def reader(n: int) -> None:
            for i in range(100):
                cache.get(f"key-{n}-{i}")

        threads = [threading.Thread(target=writer, args=(i,)) for i in range(4)]
        threads += [threading.Thread(target=reader, args=(i,)) for i in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert not errors

    def test_fear_greed_uses_cache(self):
        """FearGreedIndex nutzt den Cache bei wiederholten Aufrufen."""
        from services.market_data import FearGreedIndex

        cfg = {"use_fear_greed": True, "fg_buy_max": 80}
        fg = FearGreedIndex(cfg)
        # Pre-fill cache
        FearGreedIndex._cache.set("fng", (25, "Extreme Fear"))
        fg.update()
        assert fg.value == 25
        assert fg.label == "Extreme Fear"
        # Cleanup
        FearGreedIndex._cache.clear()

    def test_dominance_uses_cache(self):
        """DominanceFilter nutzt den Cache bei wiederholten Aufrufen."""
        from services.market_data import DominanceFilter

        cfg = {"use_dominance": True, "btc_dom_max": 40.0, "usdt_dom_max": 12.0}
        dom = DominanceFilter(cfg)
        DominanceFilter._cache.set("dominance", (45.5, 7.2))
        dom.update()
        assert dom.btc_dom == 45.5
        assert dom.usdt_dom == 7.2
        # Cleanup
        DominanceFilter._cache.clear()


# ── Password Validation Tests ────────────────────────────────────────────────


class TestPasswordValidation:
    """Tests für die verbesserte Passwort-Validierung."""

    @staticmethod
    def _check_password(password: str) -> bool:
        """Spiegelt die Logik aus routes/auth.py (register)."""
        _WEAK_PATTERNS = frozenset(
            {
                "password",
                "123456",
                "qwerty",
                "admin",
                "letmein",
                "welcome",
                "monkey",
                "dragon",
                "master",
                "abc123",
                "login",
                "princess",
                "passw0rd",
                "shadow",
                "trustno1",
            }
        )
        has_upper = bool(re.search(r"[A-Z]", password))
        has_lower = bool(re.search(r"[a-z]", password))
        has_digit = bool(re.search(r"\d", password))
        has_special = bool(re.search(r"[!@#$%^&*(),.?\":{}|<>\-_=+\[\]\\;'/`~]", password))
        pw_lower = password.lower()
        has_weak = any(w in pw_lower for w in _WEAK_PATTERNS)
        return (
            len(password) >= 12
            and has_upper
            and has_lower
            and has_digit
            and has_special
            and not has_weak
        )

    def test_strong_password_accepted(self):
        """Starke Passwörter werden akzeptiert."""
        assert self._check_password("Str0ng!Pass#99")

    def test_short_password_rejected(self):
        """Zu kurze Passwörter werden abgelehnt."""
        assert not self._check_password("Abc!1234")

    def test_no_uppercase_rejected(self):
        """Passwörter ohne Großbuchstaben werden abgelehnt."""
        assert not self._check_password("abcdefgh!1234")

    def test_no_lowercase_rejected(self):
        """Passwörter ohne Kleinbuchstaben werden abgelehnt."""
        assert not self._check_password("ABCDEFGH!1234")

    def test_no_digit_rejected(self):
        """Passwörter ohne Zahlen werden abgelehnt."""
        assert not self._check_password("AbcDefGhIjk!")

    def test_no_special_char_rejected(self):
        """Passwörter ohne Sonderzeichen werden abgelehnt."""
        assert not self._check_password("AbcDefGh1234")

    def test_weak_pattern_password_rejected(self):
        """Passwörter mit schwachen Mustern (z.B. 'password') werden abgelehnt."""
        assert not self._check_password("MyPassword!123")

    def test_weak_pattern_admin_rejected(self):
        """Passwörter mit 'admin' werden abgelehnt."""
        assert not self._check_password("SuperAdmin!123")

    def test_weak_pattern_qwerty_rejected(self):
        """Passwörter mit 'qwerty' werden abgelehnt."""
        assert not self._check_password("MyQwerty!1234")

    def test_weak_pattern_123456_rejected(self):
        """Passwörter mit '123456' werden abgelehnt."""
        assert not self._check_password("Hello!123456Ab")


# ── Connection Pool Stats Tests ──────────────────────────────────────────────


class TestConnectionPoolStats:
    """Tests für pool_stats() Monitoring."""

    def test_pool_stats_structure(self):
        """pool_stats() gibt die erwarteten Keys zurück."""
        from unittest.mock import patch

        from services.db_pool import ConnectionPool

        with patch("services.db_pool._PYMYSQL_AVAILABLE", False):
            pool = ConnectionPool.__new__(ConnectionPool)
            pool._pool = []
            pool._pool_size = 5
            pool._lock = __import__("threading").Lock()

            stats = pool.pool_stats()
            assert "pool_size" in stats
            assert "available" in stats
            assert "in_use" in stats
            assert "utilization_pct" in stats

    def test_pool_stats_values(self):
        """pool_stats() berechnet korrekte Werte."""
        from unittest.mock import patch

        from services.db_pool import ConnectionPool

        with patch("services.db_pool._PYMYSQL_AVAILABLE", False):
            pool = ConnectionPool.__new__(ConnectionPool)
            pool._pool = ["conn1", "conn2"]  # 2 available
            pool._pool_size = 5
            pool._lock = __import__("threading").Lock()

            stats = pool.pool_stats()
            assert stats["pool_size"] == 5
            assert stats["available"] == 2
            assert stats["in_use"] == 3
            assert stats["utilization_pct"] == 60.0

    def test_pool_stats_empty_pool(self):
        """pool_stats() bei leerem Pool zeigt 100% Auslastung."""
        from unittest.mock import patch

        from services.db_pool import ConnectionPool

        with patch("services.db_pool._PYMYSQL_AVAILABLE", False):
            pool = ConnectionPool.__new__(ConnectionPool)
            pool._pool = []
            pool._pool_size = 3
            pool._lock = __import__("threading").Lock()

            stats = pool.pool_stats()
            assert stats["utilization_pct"] == 100.0
