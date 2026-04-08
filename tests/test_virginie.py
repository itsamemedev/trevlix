"""Tests for VIRGINIE 0.0.1 primitives."""

from services.virginie import (
    ActionResult,
    AgentTask,
    LLMPerformanceTracker,
    LLMResult,
    Opportunity,
    ProfitDecisionEngine,
    VirginieCore,
    VirginieGuardrails,
    VirginieIdentity,
    VirginieOrchestrator,
    VirginieRules,
    build_default_project_agents,
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
                key="weak",
                success_probability=0.3,
                expected_profit=40,
                cost=20,
                risk_penalty=5,
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


def test_llm_tracker_cold_start_prefers_unseen_registered_model_first():
    tracker = LLMPerformanceTracker()
    tracker.register_models("analysis", ["model_b", "model_a"])

    # Deterministic alphabetical exploration for unseen candidates.
    assert tracker.recommend("analysis") == "model_a"


def test_llm_tracker_recommend_prefers_high_reward_model():
    tracker = LLMPerformanceTracker(exploration_c=0.2)
    for _ in range(5):
        tracker.record(LLMResult(model="model_a", task_type="analysis", reward=0.9))
    for _ in range(5):
        tracker.record(LLMResult(model="model_b", task_type="analysis", reward=0.4))

    assert tracker.recommend("analysis") == "model_a"
    assert tracker.model_average_reward("analysis", "model_a") == 0.9
    assert tracker.model_average_reward("analysis", "model_missing") is None


def test_virginie_core_guardrails_filter_unprofitable_or_risky_actions():
    core = VirginieCore(guardrails=VirginieGuardrails(min_score=10.0, max_risk_penalty=25.0))
    selected = core.select_opportunity(
        [
            Opportunity(
                key="too_risky",
                success_probability=0.9,
                expected_profit=50,
                risk_penalty=40,
            ),
            Opportunity(key="negative", success_probability=0.2, expected_profit=10, cost=5),
            Opportunity(
                key="good",
                success_probability=0.8,
                expected_profit=50,
                cost=5,
                risk_penalty=10,
            ),
        ]
    )

    assert selected is not None
    assert selected.key == "good"


def test_virginie_core_report_contains_score_breakdown():
    core = VirginieCore()
    report = core.select_opportunity_with_report(
        [
            Opportunity(
                key="good", success_probability=0.7, expected_profit=50, cost=5, risk_penalty=5
            )
        ]
    )

    assert report.selected is not None
    assert report.selected.key == "good"
    assert "EV=" in report.reason


def test_virginie_core_learns_action_outcomes_for_future_selection():
    core = VirginieCore()

    selected = core.select_opportunity(
        [
            Opportunity(key="a", success_probability=0.6, expected_profit=20),
            Opportunity(key="b", success_probability=0.5, expected_profit=20),
        ]
    )
    assert selected is not None
    assert selected.key == "a"

    for _ in range(5):
        core.learn_from_action(ActionResult(opportunity_key="b", realized_profit=30.0))
    for _ in range(5):
        core.learn_from_action(ActionResult(opportunity_key="a", realized_profit=5.0))

    selected_after_learning = core.select_opportunity(
        [
            Opportunity(key="a", success_probability=0.6, expected_profit=20),
            Opportunity(key="b", success_probability=0.5, expected_profit=20),
        ]
    )

    assert selected_after_learning is not None
    assert selected_after_learning.key == "b"
    assert core.action_average_profit("b") == 30.0
    snap = core.action_snapshot()
    assert snap["b"]["count"] == 5
    assert snap["b"]["variance"] == 0.0


def test_virginie_core_routes_llm_by_recorded_rewards():
    core = VirginieCore(exploration_c=0.1)
    for _ in range(4):
        core.learn_from_llm(LLMResult(model="llm-fast", task_type="market_context", reward=0.7))
        core.learn_from_llm(LLMResult(model="llm-deep", task_type="market_context", reward=0.9))

    assert core.recommend_llm("market_context") == "llm-deep"


def test_virginie_orchestrator_routes_and_executes_default_agents():
    orchestrator = VirginieOrchestrator()
    for agent in build_default_project_agents():
        orchestrator.register_agent(agent)

    task = AgentTask(
        task_id="task-1",
        domain="planning",
        objective="Release planning",
        payload={"next_step": "ship MVP"},
    )
    result = orchestrator.execute(task)

    assert result.success is True
    assert result.agent_name == "planning-agent"
    status = orchestrator.status()
    assert status["registered_agents"] == 9
    assert status["last_task_id"] == "task-1"


def test_virginie_orchestrator_reports_unassigned_domain():
    orchestrator = VirginieOrchestrator()
    result = orchestrator.execute(
        AgentTask(task_id="task-x", domain="finance", objective="Optimize treasury")
    )

    assert result.success is False
    assert result.agent_name == "unassigned"


def test_virginie_review_and_version_bump_follow_rules():
    core = VirginieCore(
        rules=VirginieRules(
            min_samples_for_revision=4,
            min_avg_profit_for_revision=1.0,
            max_variance_for_revision=5.0,
            min_review_interval_sec=0,
        )
    )
    for _ in range(4):
        core.learn_from_action(ActionResult(opportunity_key="x", realized_profit=2.0))

    review = core.review_and_improve(now_ts=100.0)
    assert review["reviewed"] is True
    assert review["version"] == "0.0.2"
    assert "Version bump" in review["summary"]


def test_virginie_review_skips_when_rules_not_met():
    core = VirginieCore(
        rules=VirginieRules(
            min_samples_for_revision=10,
            min_avg_profit_for_revision=5.0,
            max_variance_for_revision=1.0,
            min_review_interval_sec=0,
        )
    )
    for _ in range(3):
        core.learn_from_action(ActionResult(opportunity_key="x", realized_profit=1.0))

    review = core.review_and_improve(now_ts=100.0)
    assert review["reviewed"] is True
    assert review["version"] == "0.0.1"
    assert "No bump" in review["summary"]
