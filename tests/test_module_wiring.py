"""Regression checks for extracted module symbol wiring."""

import time

from app.core import trading_classes, trading_ops


def test_trading_classes_has_required_helpers_wired():
    assert trading_classes.pd is not None
    assert callable(trading_classes.safe_float)
    assert callable(trading_classes.safe_fetch_tickers)


def test_trading_ops_has_safe_float_wired():
    assert callable(trading_ops.safe_float)
    assert trading_ops.safe_float("1.25", 0.0) == 1.25


class _DummyLogger:
    def warning(self, *_args, **_kwargs):
        return None


def test_trading_ops_optional_helpers_are_noop_without_dependencies():
    trading_ops.log = _DummyLogger()
    trading_ops.healer = None
    trading_ops.db = None
    trading_ops.knowledge_base = None
    trading_ops.regime = None
    trading_ops.fg_idx = None

    trading_ops._maybe_healer_heartbeat()
    trading_ops._maybe_check_db_pool_health()
    trading_ops._maybe_generate_market_context()


def test_trading_ops_market_context_helper_calls_knowledge_base_when_available():
    class _KB:
        called = False

        def generate_market_context_async(self, **_kwargs):
            self.called = True

    class _Regime:
        is_bull = True

    class _FG:
        value = 50

    class _State:
        positions = {"BTC/USDT": {}}
        iteration = 7

    kb = _KB()
    trading_ops.log = _DummyLogger()
    trading_ops.knowledge_base = kb
    trading_ops.regime = _Regime()
    trading_ops.fg_idx = _FG()
    trading_ops.state = _State()

    trading_ops._maybe_generate_market_context()
    assert kb.called is True


def test_trading_ops_heatmap_uses_cached_payload_within_ttl():
    class _News:
        def get_score(self, _symbol):
            return (0.0, "", "")

    class _State:
        markets = ["BTC/USDT"]
        positions = {}

    calls = {"tickers": 0}

    def _fake_fetch(_exchange, _symbols):
        calls["tickers"] += 1
        return {"BTC/USDT": {"percentage": 2.5, "quoteVolume": 1_500_000, "last": 64000.0}}

    trading_ops.log = _DummyLogger()
    trading_ops.state = _State()
    trading_ops.news_fetcher = _News()
    trading_ops.safe_fetch_tickers = _fake_fetch
    trading_ops._heatmap_cache = []
    trading_ops._heatmap_ts = None

    first = trading_ops.get_heatmap_data(ex=None)
    second = trading_ops.get_heatmap_data(ex=None)

    assert calls["tickers"] == 1
    assert first == second


def test_resolve_admin_user_id_uses_db_and_cache():
    class _Cursor:
        def execute(self, _sql):
            return None

        def fetchone(self):
            return {"id": 42}

        def __enter__(self):
            return self

        def __exit__(self, *_exc):
            return False

    class _Conn:
        def cursor(self):
            return _Cursor()

        def __enter__(self):
            return self

        def __exit__(self, *_exc):
            return False

    class _DB:
        db_available = True

        def __init__(self):
            self.calls = 0

        def _get_conn(self):
            self.calls += 1
            return _Conn()

    old_db = trading_ops.db
    old_cache_id = trading_ops._ADMIN_USER_ID_CACHE
    old_cache_ts = trading_ops._ADMIN_USER_ID_CACHE_TS
    old_cache_valid = trading_ops._ADMIN_USER_ID_CACHE_VALID
    fake_db = _DB()
    trading_ops.db = fake_db
    trading_ops._ADMIN_USER_ID_CACHE = None
    trading_ops._ADMIN_USER_ID_CACHE_TS = 0.0
    trading_ops._ADMIN_USER_ID_CACHE_VALID = False

    try:
        first = trading_ops._resolve_admin_user_id(cache_ttl_sec=60.0)
        second = trading_ops._resolve_admin_user_id(cache_ttl_sec=60.0)
    finally:
        trading_ops.db = old_db
        trading_ops._ADMIN_USER_ID_CACHE = old_cache_id
        trading_ops._ADMIN_USER_ID_CACHE_TS = old_cache_ts
        trading_ops._ADMIN_USER_ID_CACHE_VALID = old_cache_valid

    assert first == 42
    assert second == 42
    assert fake_db.calls == 1


def test_resolve_admin_user_id_returns_none_without_db():
    old_db = trading_ops.db
    old_cache_id = trading_ops._ADMIN_USER_ID_CACHE
    old_cache_ts = trading_ops._ADMIN_USER_ID_CACHE_TS
    old_cache_valid = trading_ops._ADMIN_USER_ID_CACHE_VALID
    trading_ops.db = None
    trading_ops._ADMIN_USER_ID_CACHE = None
    trading_ops._ADMIN_USER_ID_CACHE_TS = time.time()
    trading_ops._ADMIN_USER_ID_CACHE_VALID = False

    try:
        resolved_first = trading_ops._resolve_admin_user_id(cache_ttl_sec=60.0)
        resolved_second = trading_ops._resolve_admin_user_id(cache_ttl_sec=60.0)
    finally:
        trading_ops.db = old_db
        trading_ops._ADMIN_USER_ID_CACHE = old_cache_id
        trading_ops._ADMIN_USER_ID_CACHE_TS = old_cache_ts
        trading_ops._ADMIN_USER_ID_CACHE_VALID = old_cache_valid

    assert resolved_first is None
    assert resolved_second is None
