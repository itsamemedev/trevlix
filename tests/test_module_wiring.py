"""Regression checks for extracted module symbol wiring."""

from collections import deque

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


def test_notify_virginie_sell_decision_emits_monitored_exit_payload():
    emitted = []
    trading_ops.emit_event = lambda event, payload: emitted.append((event, payload))
    trading_ops._VIRGINIE_FORECAST_FEED = deque(maxlen=200)

    pos = {
        "ai_reason": "✅ VIRGINIE-Primary:78.0% | setup bestätigt",
        "entry": 100.0,
        "peak_price": 112.0,
        "trough_price": 97.5,
        "last_observed_price": 108.0,
        "observed_ticks": 14,
        "opened_ts": 0,
    }
    trading_ops._notify_virginie_sell_decision(
        symbol="BTC/USDT",
        reason="Take-Profit 🎯",
        pnl=8.4,
        pnl_pct=8.4,
        pos=pos,
    )

    assert emitted
    event, payload = emitted[-1]
    assert event == "virginie_forecast"
    assert payload["side"] == "sell"
    assert payload["recommended_action"] == "SELL"
    assert payload["observed_ticks"] == 14
