"""Regression tests for AI engine dependency wiring."""

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
    assert ai_engine.CONFIG["virginie_min_score"] == 0.0
