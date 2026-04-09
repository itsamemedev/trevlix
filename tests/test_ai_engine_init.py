"""Regression tests for AI engine dependency wiring."""

import numpy as np

from app.core import ai_engine


class _DummyLogger:
    def info(self, *_args, **_kwargs):
        return None

    def warning(self, *_args, **_kwargs):
        return None

    def error(self, *_args, **_kwargs):
        return None


def test_init_ai_engine_accepts_optional_knowledge_base_reference():
    kb = object()
    regime = object()
    rl_agent = object()
    genetic = object()
    ai_engine.init_ai_engine(
        config={"lstm_lookback": 30},
        logger=_DummyLogger(),
        knowledge_base_ref=kb,
        regime_ref=regime,
        rl_agent_ref=rl_agent,
        genetic_ref=genetic,
    )
    assert ai_engine.knowledge_base is kb
    assert ai_engine.regime is regime
    assert ai_engine.rl_agent is rl_agent
    assert ai_engine.genetic is genetic


def test_init_ai_engine_is_backward_compatible_without_knowledge_base():
    ai_engine.init_ai_engine(
        config={"lstm_lookback": 30},
        logger=_DummyLogger(),
    )
    assert ai_engine.knowledge_base is None
    assert ai_engine.regime is None
    assert ai_engine.rl_agent is None
    assert ai_engine.genetic is None


def test_init_ai_engine_merges_required_defaults_for_partial_configs():
    ai_engine.init_ai_engine(
        config={},
        logger=_DummyLogger(),
    )

    assert ai_engine.CONFIG["lstm_lookback"] == 24
    assert ai_engine.CONFIG["ai_min_samples"] == 20
    assert ai_engine.CONFIG["stop_loss_pct"] == 0.025
    assert ai_engine.CONFIG["virginie_enabled"] is True
    assert ai_engine.CONFIG["virginie_primary_control"] is True
    assert ai_engine.CONFIG["virginie_autonomy_weight"] == 0.7
    assert ai_engine.CONFIG["virginie_min_score"] == 0.0


def test_should_buy_syncs_virginie_guardrails_after_runtime_config_change(monkeypatch):
    class _DummyScaler:
        def transform(self, value):
            return value

    class _DummyDB:
        def load_ai_samples(self):
            return [], [], []

    monkeypatch.setattr(ai_engine.AIEngine, "_load_from_db", lambda self: None)
    engine = ai_engine.AIEngine(db_ref=_DummyDB())
    engine.scaler = _DummyScaler()
    engine.is_trained = True
    monkeypatch.setattr(engine, "_predict", lambda _x, _f: 0.9)

    old_cfg = dict(ai_engine.CONFIG)
    try:
        ai_engine.CONFIG["ai_enabled"] = True
        ai_engine.CONFIG["ai_min_confidence"] = 0.5
        ai_engine.CONFIG["virginie_enabled"] = True
        ai_engine.CONFIG["take_profit_pct"] = 0.06
        ai_engine.CONFIG["stop_loss_pct"] = 0.025

        ai_engine.CONFIG["virginie_min_score"] = 50.0
        blocked, _, _ = engine.should_buy(features=np.array([0.0]), conf=0.9)
        assert blocked is False

        ai_engine.CONFIG["virginie_min_score"] = 0.0
        allowed, _, _ = engine.should_buy(features=np.array([0.0]), conf=0.9)
        assert allowed is True
        assert engine.virginie.guardrails.min_score == 0.0
    finally:
        ai_engine.CONFIG.clear()
        ai_engine.CONFIG.update(old_cfg)


def test_should_buy_uses_virginie_primary_control_when_model_not_trained(monkeypatch):
    class _DummyDB:
        def load_ai_samples(self):
            return [], [], []

    monkeypatch.setattr(ai_engine.AIEngine, "_load_from_db", lambda self: None)
    engine = ai_engine.AIEngine(db_ref=_DummyDB())
    engine.is_trained = False

    old_cfg = dict(ai_engine.CONFIG)
    try:
        ai_engine.CONFIG["ai_enabled"] = True
        ai_engine.CONFIG["virginie_enabled"] = True
        ai_engine.CONFIG["virginie_primary_control"] = True
        ai_engine.CONFIG["virginie_min_score"] = 20.0
        ai_engine.CONFIG["take_profit_pct"] = 0.01
        ai_engine.CONFIG["stop_loss_pct"] = 0.05

        allowed, _, reason = engine.should_buy(features=np.array([0.0]), conf=0.5)
        assert allowed is False
        assert "VIRGINIE-Primary" in reason
    finally:
        ai_engine.CONFIG.clear()
        ai_engine.CONFIG.update(old_cfg)
