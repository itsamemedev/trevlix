"""Tests für services/knowledge.py – KI-Gemeinschaftswissen."""

import pytest

from services.knowledge import KnowledgeBase


class MockDB:
    """Mock für MySQLManager mit in-memory Storage."""

    def __init__(self):
        self._data = {}  # (category, key) → row dict

    class _MockConn:
        def __init__(self, db):
            self._db = db

        def cursor(self):
            return self._db._MockCursor(self._db)

        def close(self):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    class _MockCursor:
        def __init__(self, db):
            self._db = db
            self._result = None

        def execute(self, query, params=None):
            if "INSERT INTO shared_knowledge" in query:
                cat, key = params[0], params[1]
                self._db._data[(cat, key)] = {
                    "value_json": params[2],
                    "confidence": params[3],
                    "source": params[4],
                    "updated_at": None,
                }
            elif "SELECT value_json" in query and "WHERE category" in query:
                row = self._db._data.get((params[0], params[1]))
                self._result = row
            elif "SELECT key_name" in query:
                cat = params[0]
                rows = []
                for (c, k), v in self._db._data.items():
                    if c == cat:
                        rows.append({"key_name": k, **v})
                self._result = rows

        def fetchone(self):
            return self._result

        def fetchall(self):
            return self._result if isinstance(self._result, list) else []

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    def _get_conn(self):
        from contextlib import contextmanager

        @contextmanager
        def ctx():
            yield self._MockConn(self)

        return ctx()


@pytest.fixture
def kb():
    mock_db = MockDB()
    return KnowledgeBase(mock_db)


class TestKnowledgeBase:
    def test_store_and_get(self, kb):
        ok = kb.store("market_insight", "btc_trend", {"direction": "bull"}, 0.8)
        assert ok is True
        result = kb.get("market_insight", "btc_trend")
        assert result is not None
        assert result["value"]["direction"] == "bull"
        assert result["confidence"] == 0.8

    def test_invalid_category_rejected(self, kb):
        ok = kb.store("invalid_cat", "key", {"data": 1})
        assert ok is False

    def test_get_nonexistent_returns_none(self, kb):
        result = kb.get("market_insight", "nonexistent")
        assert result is None

    def test_get_category(self, kb):
        kb.store("symbol_info", "BTC", {"trades": 5})
        kb.store("symbol_info", "ETH", {"trades": 3})
        results = kb.get_category("symbol_info")
        assert len(results) == 2

    def test_learn_from_trade(self, kb):
        trade = {
            "symbol": "BTC/USDT",
            "pnl": 100.0,
            "reason": "EMA-Trend",
            "regime": "bull",
        }
        kb.learn_from_trade(trade)
        sym = kb.get("symbol_info", "BTC/USDT")
        assert sym is not None
        assert sym["value"]["total_trades"] == 1
        assert sym["value"]["wins"] == 1

    def test_learn_from_losing_trade(self, kb):
        trade = {
            "symbol": "ETH/USDT",
            "pnl": -50.0,
            "reason": "RSI-Stoch",
            "regime": "bear",
        }
        kb.learn_from_trade(trade)
        sym = kb.get("symbol_info", "ETH/USDT")
        assert sym["value"]["wins"] == 0
        assert sym["value"]["total_pnl"] == -50.0

    def test_market_summary(self, kb):
        summary = kb.get_market_summary()
        assert "insights" in summary
        assert "top_symbols" in summary
        assert "strategy_ranking" in summary

    def test_query_llm_without_endpoint(self, kb):
        result = kb.query_llm("test prompt")
        assert result is None

    def test_cache_invalidation_on_store(self, kb):
        kb.store("market_insight", "test", {"v": 1})
        # Get fills cache
        kb.get("market_insight", "test")
        assert "market_insight:test" in kb._cache
        # Store again should invalidate
        kb.store("market_insight", "test", {"v": 2})
        assert "market_insight:test" not in kb._cache

    def test_valid_categories(self):
        assert "market_insight" in KnowledgeBase.CATEGORIES
        assert "strategy_perf" in KnowledgeBase.CATEGORIES
        assert "symbol_info" in KnowledgeBase.CATEGORIES
        assert "risk_pattern" in KnowledgeBase.CATEGORIES
