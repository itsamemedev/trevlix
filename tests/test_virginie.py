"""Tests for VIRGINIE 0.0.1 primitives."""

import pytest

from services.virginie import (
    ActionResult,
    AgentResult,
    AgentTask,
    LearningExample,
    LLMPerformanceTracker,
    LLMResult,
    Opportunity,
    ProfitDecisionEngine,
    VirginieAgent,
    VirginieCore,
    VirginieGuardrails,
    VirginieIdentity,
    VirginieOrchestrator,
    VirginieRules,
    build_default_project_agents,
    build_startup_examples,
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


def test_virginie_core_examples_can_improve_from_feedback():
    core = VirginieCore()
    core.add_or_update_example(
        LearningExample(
            example_id="ex-fast-breakout",
            task_type="market_context",
            content="Momentum breakout playbook with strict stop-loss.",
            quality_score=0.4,
        )
    )
    core.add_or_update_example(
        LearningExample(
            example_id="ex-range-revert",
            task_type="market_context",
            content="Range mean-reversion playbook with conservative sizing.",
            quality_score=0.6,
        )
    )

    core.learn_from_example_result("ex-fast-breakout", 1.0)
    core.learn_from_example_result("ex-fast-breakout", 0.9)
    core.learn_from_example_result("ex-range-revert", 0.2)

    top = core.top_examples("market_context", limit=2)
    assert [item.example_id for item in top] == ["ex-fast-breakout", "ex-range-revert"]
    assert top[0].quality_score > top[1].quality_score
    snapshot = core.example_snapshot()
    assert snapshot["ex-fast-breakout"]["count"] == 2.0


def test_virginie_core_example_feedback_requires_existing_example():
    core = VirginieCore()
    with pytest.raises(KeyError):
        core.learn_from_example_result("missing-example", 0.8)


def test_virginie_core_loads_startup_examples_for_trading_and_agent_control():
    core = VirginieCore()
    trading = core.top_examples("trading_max_profit", limit=1)
    orchestration = core.top_examples("agent_orchestration", limit=1)

    assert trading
    assert orchestration
    assert "EV =" in trading[0].content
    assert "Domänenrouting" in orchestration[0].content


def test_build_startup_examples_contains_expected_playbooks():
    examples = build_startup_examples()
    ids = {item.example_id for item in examples}
    assert "startup-trading-max-profit" in ids
    assert "startup-agent-control" in ids


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


def test_virginie_orchestrator_rejects_empty_agent_name():
    orchestrator = VirginieOrchestrator()

    with pytest.raises(ValueError):
        orchestrator.register_agent(VirginieAgent(name="   ", domains=("ops",), handler=lambda _t: None))


def test_portfolio_goal_delegates_to_trading_agent_with_autonomous_allocation():
    orchestrator = VirginieOrchestrator()
    for agent in build_default_project_agents():
        orchestrator.register_agent(agent)

    result = orchestrator.execute(
        AgentTask(
            task_id="task-goal-1",
            domain="portfolio",
            objective="Reach user target quickly",
            payload={
                "target_amount": 15_000,
                "portfolio_value": 10_500,
                "min_buy_notional": 10,
                "min_sell_notional": 10,
            },
        )
    )

    assert result.success is True
    assert result.agent_name == "portfolio-agent"
    assert "trading-agent assigned" in result.summary
    assert result.data["delegate_to"] == "trading-agent"
    assert result.data["goal_gap_amount"] == 4500.0
    assert result.data["goal_tradable_under_exchange_rules"] is True
    assert result.data["delegate_task"]["domain"] == "trading"
    assert result.data["delegate_task"]["payload"]["autonomous_allocation"] is True
    assert result.data["delegate_task"]["payload"]["optimize_for_speed"] is True
    assert result.data["delegate_task"]["payload"]["respect_exchange_minimums"] is True


def test_portfolio_goal_is_not_delegated_when_exchange_minimum_blocks_trade():
    orchestrator = VirginieOrchestrator()
    for agent in build_default_project_agents():
        orchestrator.register_agent(agent)

    result = orchestrator.execute(
        AgentTask(
            task_id="task-goal-2",
            domain="portfolio",
            objective="Reach user target quickly",
            payload={
                "target_amount": 10_010,
                "portfolio_value": 10_000,
                "min_buy_notional": 25,
                "min_sell_notional": 25,
            },
        )
    )

    assert result.success is True
    assert "blocked by exchange minimum" in result.summary
    assert result.data["goal_gap_amount"] == 10.0
    assert result.data["goal_tradable_under_exchange_rules"] is False
    assert result.data["delegate_to"] is None
    assert result.data["delegate_task"] is None


def test_portfolio_goal_in_paper_mode_bypasses_exchange_minimum_block():
    orchestrator = VirginieOrchestrator()
    for agent in build_default_project_agents():
        orchestrator.register_agent(agent)

    result = orchestrator.execute(
        AgentTask(
            task_id="task-goal-3",
            domain="portfolio",
            objective="Reach user target quickly",
            payload={
                "target_amount": 10_010,
                "portfolio_value": 10_000,
                "min_buy_notional": 25,
                "min_sell_notional": 25,
                "paper_mode": True,
            },
        )
    )

    assert result.success is True
    assert "Paper mode goal received" in result.summary
    assert result.data["goal_gap_amount"] == 10.0
    assert result.data["paper_mode"] is True
    assert result.data["exchange_constraints_enforced"] is False
    assert result.data["goal_tradable_under_exchange_rules"] is True
    assert result.data["delegate_to"] == "trading-agent"
    assert result.data["delegate_task"]["payload"]["respect_exchange_minimums"] is False


def test_virginie_orchestrator_coverage_report_detects_missing_domains():
    orchestrator = VirginieOrchestrator()
    orchestrator.set_required_domains(["planning", "risk"])
    orchestrator.register_agent(build_default_project_agents()[0])  # planning-agent

    report = orchestrator.coverage_report()
    assert report["is_complete"] is False
    assert report["missing_domains"] == ["risk"]


def test_virginie_orchestrator_normalizes_domains_for_routing_and_coverage():
    orchestrator = VirginieOrchestrator()
    orchestrator.set_required_domains([" Planning ", "RISK"])
    for agent in build_default_project_agents():
        orchestrator.register_agent(agent)

    report = orchestrator.coverage_report()
    assert report["is_complete"] is True
    result = orchestrator.execute(
        AgentTask(task_id="task-case", domain="  PlAnNiNg  ", objective="Case-insensitive route")
    )
    assert result.success is True
    assert result.agent_name == "planning-agent"


def test_virginie_orchestrator_supports_domain_aliases():
    orchestrator = VirginieOrchestrator()
    for agent in build_default_project_agents():
        orchestrator.register_agent(agent)

    result = orchestrator.execute(
        AgentTask(task_id="task-alias-1", domain="ops", objective="restart service")
    )
    assert result.success is True
    assert result.agent_name == "ops-agent"


def test_virginie_orchestrator_infers_domain_from_objective_when_domain_unknown():
    orchestrator = VirginieOrchestrator()
    for agent in build_default_project_agents():
        orchestrator.register_agent(agent)

    result = orchestrator.execute(
        AgentTask(
            task_id="task-infer-1",
            domain="unknown",
            objective="Bitte sende eine Alert Message an Telegram",
            payload={"reason": "critical delivery alert"},
        )
    )

    assert result.success is True
    assert result.agent_name == "notification-agent"
    assert result.data["routing"]["domain_inferred"] == "notifications"


def test_virginie_orchestrator_tracks_agent_load_in_status():
    orchestrator = VirginieOrchestrator()
    for agent in build_default_project_agents():
        orchestrator.register_agent(agent)

    orchestrator.execute(AgentTask(task_id="task-load-1", domain="planning", objective="A"))
    orchestrator.execute(AgentTask(task_id="task-load-2", domain="planning", objective="B"))
    orchestrator.execute(AgentTask(task_id="task-load-3", domain="risk", objective="C"))

    status = orchestrator.status()
    counts = status["agent_task_counts"]
    assert counts["planning-agent"] == 2
    assert counts["risk-agent"] == 1


def test_virginie_orchestrator_catches_agent_handler_exceptions():
    def _boom(_task):
        raise RuntimeError("handler crashed")

    orchestrator = VirginieOrchestrator()
    orchestrator.register_agent(
        VirginieAgent(name="unstable-agent", domains=("ops",), handler=_boom)
    )

    result = orchestrator.execute(
        AgentTask(task_id="task-fail-1", domain="ops", objective="restart")
    )

    assert result.success is False
    assert result.agent_name == "unstable-agent"
    assert "Agent execution failed" in result.summary
    status = orchestrator.status()
    assert status["agent_health"]["unstable-agent"]["failure"] == 1
    assert status["agent_health"]["unstable-agent"]["failure_rate"] == 1.0


def test_virginie_orchestrator_prefers_healthier_agent_on_same_domain():
    def _ok_handler(task):
        return AgentResult(agent_name="agent-ok", task_id=task.task_id, success=True, summary="ok")

    def _flaky_handler(task):
        if task.task_id == "prime-failure":
            raise RuntimeError("intentional")

        return AgentResult(
            agent_name="agent-flaky",
            task_id=task.task_id,
            success=True,
            summary="unexpectedly ok",
        )

    orchestrator = VirginieOrchestrator()
    orchestrator.register_agent(
        VirginieAgent(name="agent-flaky", domains=("quality",), handler=_flaky_handler)
    )
    orchestrator.register_agent(VirginieAgent(name="agent-ok", domains=("quality",), handler=_ok_handler))

    # Prime one failure on flaky agent.
    orchestrator.execute(AgentTask(task_id="prime-failure", domain="quality", objective="prime"))

    result = orchestrator.execute(
        AgentTask(task_id="healthy-route", domain="quality", objective="run checks")
    )
    assert result.success is True
    assert result.agent_name == "agent-ok"


def test_virginie_orchestrator_applies_failure_cooldown_after_threshold():
    now = {"t": 1000.0}

    def _time():
        return now["t"]

    def _always_fail(_task):
        raise RuntimeError("down")

    def _ok_handler(task):
        return AgentResult(agent_name="agent-ok", task_id=task.task_id, success=True, summary="ok")

    orchestrator = VirginieOrchestrator(failure_cooldown_sec=60.0, failure_threshold=3, time_fn=_time)
    orchestrator.register_agent(VirginieAgent(name="agent-fail", domains=("ops",), handler=_always_fail))

    # trigger consecutive failures for agent-fail
    for idx in range(3):
        now["t"] += 1.0
        orchestrator.execute(AgentTask(task_id=f"fail-{idx}", domain="ops", objective="restart"))

    status = orchestrator.status()
    assert status["agent_health"]["agent-fail"]["consecutive_failure"] >= 3
    assert status["agent_health"]["agent-fail"]["cooldown_active"] is True

    orchestrator.register_agent(VirginieAgent(name="agent-ok", domains=("ops",), handler=_ok_handler))
    now["t"] += 1.0
    routed = orchestrator.execute(AgentTask(task_id="after-cooldown", domain="ops", objective="restart"))
    assert routed.success is True
    assert routed.agent_name == "agent-ok"
    assert "agent-fail" in routed.data["routing"]["cooldown_excluded"]


def test_virginie_orchestrator_unassigned_result_contains_routing_diagnostics():
    orchestrator = VirginieOrchestrator()
    result = orchestrator.execute(
        AgentTask(task_id="task-none", domain="mystery", objective="unmapped objective")
    )

    assert result.success is False
    assert result.agent_name == "unassigned"
    assert "routing" in result.data
    assert result.data["routing"]["matches"] == []


def test_virginie_orchestrator_unregister_and_reset_stats_and_history():
    orchestrator = VirginieOrchestrator()
    for agent in build_default_project_agents():
        orchestrator.register_agent(agent)

    orchestrator.execute(AgentTask(task_id="task-rst-1", domain="planning", objective="A"))
    assert len(orchestrator.history()) == 1
    orchestrator.reset_agent_stats("planning-agent")
    status = orchestrator.status()
    assert status["agent_task_counts"]["planning-agent"] == 0

    orchestrator.clear_history()
    assert orchestrator.history() == []
    assert orchestrator.unregister_agent("planning-agent") is True
    assert orchestrator.unregister_agent("planning-agent") is False


def test_virginie_orchestrator_status_totals_are_exposed():
    orchestrator = VirginieOrchestrator()
    for agent in build_default_project_agents():
        orchestrator.register_agent(agent)
    orchestrator.execute(AgentTask(task_id="task-total-1", domain="planning", objective="ok"))

    status = orchestrator.status()
    assert status["total_tasks"] >= 1
    assert status["failure_threshold"] >= 1
    assert status["failure_cooldown_sec"] >= 1.0


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
