"""Tests for VIRGINIE 0.0.1 primitives."""

from services.virginie import (
    LLMPerformanceTracker,
    LLMResult,
    Opportunity,
    ProfitDecisionEngine,
    VirginieIdentity,
)


def test_virginie_identity_defaults():
    identity = VirginieIdentity()
    assert identity.name == "VIRGINIE"
    assert identity.version == "0.0.1"


def test_profit_engine_ranks_highest_expected_value_first():
    engine = ProfitDecisionEngine()
    ranked = engine.rank(
        [
            Opportunity(
                key="safe", success_probability=0.8, expected_profit=100, cost=10, risk_penalty=5
            ),
            Opportunity(
                key="aggressive",
                success_probability=0.4,
                expected_profit=300,
                cost=10,
                risk_penalty=30,
            ),
            Opportunity(
                key="weak", success_probability=0.3, expected_profit=40, cost=20, risk_penalty=5
            ),
        ]
    )

    assert [item.key for item, _score in ranked] == ["aggressive", "safe", "weak"]


def test_profit_engine_clamps_invalid_probability_values():
    engine = ProfitDecisionEngine()
    too_high = Opportunity(key="high", success_probability=2.0, expected_profit=20, cost=5)
    too_low = Opportunity(key="low", success_probability=-1.0, expected_profit=20, cost=5)

    assert engine.score(too_high) == 15.0
    assert engine.score(too_low) == -5.0


def test_llm_tracker_recommend_returns_none_without_data():
    tracker = LLMPerformanceTracker()
    assert tracker.recommend("analysis") is None


def test_llm_tracker_recommend_prefers_high_reward_model():
    tracker = LLMPerformanceTracker(exploration_c=0.2)
    for _ in range(5):
        tracker.record(LLMResult(model="model_a", task_type="analysis", reward=0.9))
    for _ in range(5):
        tracker.record(LLMResult(model="model_b", task_type="analysis", reward=0.4))

    assert tracker.recommend("analysis") == "model_a"
    assert tracker.model_average_reward("analysis", "model_a") == 0.9
    assert tracker.model_average_reward("analysis", "model_missing") is None
