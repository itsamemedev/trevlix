"""Core self-learning components for VIRGINIE 0.0.1.

This module integrates the self-learning pieces discussed for VIRGINIE:

1. Opportunity scoring with profit, costs, and risk penalties.
2. Cross-LLM learning with per-task reward tracking.
3. Bandit-style action selection that improves from outcome feedback.
4. Guardrails to avoid unbounded risk while optimizing expected value.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from math import log, sqrt
from typing import Any


@dataclass(frozen=True)
class VirginieIdentity:
    """Static identity metadata for the self-learning assistant."""

    name: str = "VIRGINIE"
    version: str = "0.0.1"


@dataclass(frozen=True)
class VirginieGuardrails:
    """Risk boundaries for autonomous decisions.

    Attributes:
        min_score: Minimum combined score required to execute an action.
        max_risk_penalty: Hard upper bound on accepted risk penalty.
    """

    min_score: float = 0.0
    max_risk_penalty: float = 1_000.0


@dataclass(frozen=True)
class Opportunity:
    """Represents one actionable option with upside, cost, and risk."""

    key: str
    success_probability: float
    expected_profit: float
    cost: float = 0.0
    risk_penalty: float = 0.0


@dataclass(frozen=True)
class ActionResult:
    """Observed outcome for an executed opportunity."""

    opportunity_key: str
    realized_profit: float


@dataclass(frozen=True)
class LLMResult:
    """One scored outcome for a model-task pair."""

    model: str
    task_type: str
    reward: float


@dataclass(frozen=True)
class VirginieDecision:
    """Decision report with explainable score components."""

    selected: Opportunity | None
    base_score: float
    action_bonus: float
    total_score: float
    reason: str


class ProfitDecisionEngine:
    """Ranks opportunities by expected net value.

    Score formula:
        P(success) * expected_profit - cost - risk_penalty
    """

    @staticmethod
    def score(opportunity: Opportunity) -> float:
        """Return the expected net value for an opportunity."""
        probability = min(1.0, max(0.0, opportunity.success_probability))
        return (
            probability * opportunity.expected_profit - opportunity.cost - opportunity.risk_penalty
        )

    def rank(self, opportunities: list[Opportunity]) -> list[tuple[Opportunity, float]]:
        """Return opportunities sorted by descending expected value."""
        scored = [(item, self.score(item)) for item in opportunities]
        return sorted(scored, key=lambda item: item[1], reverse=True)


class LLMPerformanceTracker:
    """Tracks model rewards per task and recommends the next model.

    Uses a UCB-style score to balance exploitation and exploration.
    """

    def __init__(self, exploration_c: float = 0.8) -> None:
        self._exploration_c = exploration_c
        self._stats: dict[str, dict[str, dict[str, float]]] = {}
        self._lock = threading.Lock()

    def register_models(self, task_type: str, models: list[str]) -> None:
        """Register candidate models for a task (cold-start exploration)."""
        with self._lock:
            task_stats = self._stats.setdefault(task_type, {})
            for model in models:
                task_stats.setdefault(model, {"count": 0.0, "sum_reward": 0.0})

    def record(self, result: LLMResult) -> None:
        """Record one reward outcome for a model-task pair."""
        with self._lock:
            task_stats = self._stats.setdefault(result.task_type, {})
            model_stats = task_stats.setdefault(result.model, {"count": 0.0, "sum_reward": 0.0})
            model_stats["count"] += 1
            model_stats["sum_reward"] += result.reward

    def recommend(self, task_type: str) -> str | None:
        """Recommend the best model for a task using UCB.

        Returns None when no observations exist for this task.
        """
        with self._lock:
            task_stats = self._stats.get(task_type)
            if not task_stats:
                return None

            unseen = [model for model, stats in task_stats.items() if stats["count"] <= 0]
            if unseen:
                return sorted(unseen)[0]

            total = sum(entry["count"] for entry in task_stats.values())
            if total <= 0:
                return None

            best_model: str | None = None
            best_score = float("-inf")
            for model, stats in task_stats.items():
                count = stats["count"]
                avg = (stats["sum_reward"] / count) if count > 0 else 0.0
                bonus = self._exploration_c * sqrt(log(total + 1) / count) if count > 0 else 0.0
                ucb_score = avg + bonus
                if ucb_score > best_score:
                    best_score = ucb_score
                    best_model = model
            return best_model

    def model_average_reward(self, task_type: str, model: str) -> float | None:
        """Return average reward for a model-task pair."""
        with self._lock:
            task_stats = self._stats.get(task_type, {})
            model_stats = task_stats.get(model)
            if not model_stats or model_stats["count"] <= 0:
                return None
            return model_stats["sum_reward"] / model_stats["count"]


class VirginieCore:
    """Integrated core for profit optimization and self-improvement.

    This class combines deterministic expected-value scoring with online
    learning from realized outcomes and optional cross-LLM feedback.
    """

    def __init__(
        self,
        *,
        guardrails: VirginieGuardrails | None = None,
        exploration_c: float = 0.8,
        action_exploration_c: float = 0.5,
    ) -> None:
        self.identity = VirginieIdentity()
        self.guardrails = guardrails or VirginieGuardrails()
        self.profit_engine = ProfitDecisionEngine()
        self.llm_tracker = LLMPerformanceTracker(exploration_c=exploration_c)
        self._action_exploration_c = action_exploration_c
        self._action_stats: dict[str, dict[str, float]] = {}
        self._lock = threading.Lock()

    def select_opportunity(self, opportunities: list[Opportunity]) -> Opportunity | None:
        """Select the best allowed opportunity using EV + action UCB."""
        return self.select_opportunity_with_report(opportunities).selected

    def select_opportunity_with_report(self, opportunities: list[Opportunity]) -> VirginieDecision:
        """Select opportunity and return a score breakdown for explainability."""
        candidates = [item for item in opportunities if self._passes_guardrails(item)]
        if not candidates:
            return VirginieDecision(
                selected=None,
                base_score=0.0,
                action_bonus=0.0,
                total_score=0.0,
                reason="No opportunity passed VIRGINIE guardrails",
            )

        with self._lock:
            total_count = sum(stats["count"] for stats in self._action_stats.values())

        best_item = candidates[0]
        best_base = self.profit_engine.score(best_item)
        best_bonus = self._action_bonus(best_item.key, total_count)
        best_total = best_base + best_bonus

        for item in candidates[1:]:
            base = self.profit_engine.score(item)
            bonus = self._action_bonus(item.key, total_count)
            total = base + bonus
            if total > best_total:
                best_item, best_base, best_bonus, best_total = item, base, bonus, total

        reason = (
            f"Selected {best_item.key} | EV={best_base:.3f} | "
            f"bonus={best_bonus:.3f} | total={best_total:.3f}"
        )
        return VirginieDecision(
            selected=best_item,
            base_score=best_base,
            action_bonus=best_bonus,
            total_score=best_total,
            reason=reason,
        )

    def learn_from_action(self, result: ActionResult) -> None:
        """Store realized profit feedback for future action selection."""
        with self._lock:
            stats = self._action_stats.setdefault(
                result.opportunity_key,
                {"count": 0.0, "sum_profit": 0.0, "sum_sq_profit": 0.0},
            )
            stats["count"] += 1
            stats["sum_profit"] += result.realized_profit
            stats["sum_sq_profit"] += result.realized_profit * result.realized_profit

    def learn_from_llm(self, result: LLMResult) -> None:
        """Store cross-LLM reward feedback for task routing."""
        self.llm_tracker.record(result)

    def recommend_llm(self, task_type: str) -> str | None:
        """Return recommended model for the given task type."""
        return self.llm_tracker.recommend(task_type)

    def action_average_profit(self, opportunity_key: str) -> float | None:
        """Return average realized profit for an opportunity."""
        with self._lock:
            stats = self._action_stats.get(opportunity_key)
            if not stats or stats["count"] <= 0:
                return None
            return stats["sum_profit"] / stats["count"]

    def action_snapshot(self) -> dict[str, dict[str, float]]:
        """Return a copy of action learning statistics."""
        with self._lock:
            snapshot: dict[str, dict[str, float]] = {}
            for key, stats in self._action_stats.items():
                count = stats.get("count", 0.0)
                avg = (stats.get("sum_profit", 0.0) / count) if count > 0 else 0.0
                var = 0.0
                if count > 1:
                    mean_sq = stats.get("sum_sq_profit", 0.0) / count
                    var = max(0.0, mean_sq - avg * avg)
                snapshot[key] = {
                    "count": count,
                    "avg_profit": avg,
                    "variance": var,
                }
            return snapshot

    def _passes_guardrails(self, opportunity: Opportunity) -> bool:
        score = self.profit_engine.score(opportunity)
        return (
            score >= self.guardrails.min_score
            and opportunity.risk_penalty <= self.guardrails.max_risk_penalty
        )

    def _action_bonus(self, key: str, total_count: float) -> float:
        with self._lock:
            stats = self._action_stats.get(key)
            if not stats or stats["count"] <= 0:
                return self._action_exploration_c

            count = stats["count"]
            avg_profit = stats["sum_profit"] / count
            mean_sq = stats.get("sum_sq_profit", 0.0) / count if count > 0 else 0.0
            variance = max(0.0, mean_sq - avg_profit * avg_profit)

        if total_count <= 0:
            return avg_profit

        exploration = self._action_exploration_c * sqrt(log(total_count + 1) / count)
        uncertainty_penalty = 0.1 * sqrt(variance)
        return avg_profit + exploration - uncertainty_penalty


@dataclass(frozen=True)
class AgentTask:
    """Task definition for a VIRGINIE project agent."""

    task_id: str
    domain: str
    objective: str
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AgentResult:
    """Execution result returned by an agent."""

    agent_name: str
    task_id: str
    success: bool
    summary: str
    data: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class VirginieAgent:
    """Agent descriptor used by the orchestrator."""

    name: str
    domains: tuple[str, ...]
    handler: Callable[[AgentTask], AgentResult]


class VirginieOrchestrator:
    """Routes project-control tasks to specialized VIRGINIE agents."""

    def __init__(self) -> None:
        self._agents: dict[str, VirginieAgent] = {}
        self._history: list[AgentResult] = []
        self._lock = threading.Lock()

    def register_agent(self, agent: VirginieAgent) -> None:
        """Register or replace an agent by name."""
        with self._lock:
            self._agents[agent.name] = agent

    def route_task(self, task: AgentTask) -> str | None:
        """Return best matching agent name for a task domain."""
        with self._lock:
            matches = [a.name for a in self._agents.values() if task.domain in a.domains]
        if not matches:
            return None
        return sorted(matches)[0]

    def execute(self, task: AgentTask) -> AgentResult:
        """Execute a task via its routed agent and store history."""
        agent_name = self.route_task(task)
        if agent_name is None:
            result = AgentResult(
                agent_name="unassigned",
                task_id=task.task_id,
                success=False,
                summary=f"No agent registered for domain '{task.domain}'",
            )
            with self._lock:
                self._history.insert(0, result)
                self._history = self._history[:200]
            return result

        with self._lock:
            agent = self._agents[agent_name]

        result = agent.handler(task)
        with self._lock:
            self._history.insert(0, result)
            self._history = self._history[:200]
        return result

    def status(self) -> dict[str, Any]:
        """Return orchestrator metadata for backend/dashboard diagnostics."""
        with self._lock:
            last = self._history[0] if self._history else None
            return {
                "registered_agents": len(self._agents),
                "domains": sorted({d for a in self._agents.values() for d in a.domains}),
                "history_size": len(self._history),
                "last_task_id": last.task_id if last else None,
                "last_agent": last.agent_name if last else None,
                "last_success": last.success if last else None,
                "last_summary": last.summary if last else None,
                "updated_at": datetime.utcnow().isoformat(timespec="seconds"),
            }


def build_default_project_agents() -> list[VirginieAgent]:
    """Build default management agents for project steering and operations."""

    def _planning(task: AgentTask) -> AgentResult:
        return AgentResult(
            agent_name="planning-agent",
            task_id=task.task_id,
            success=True,
            summary=f"Roadmap updated for objective: {task.objective}",
            data={"next_step": task.payload.get("next_step", "define milestones")},
        )

    def _ops(task: AgentTask) -> AgentResult:
        return AgentResult(
            agent_name="ops-agent",
            task_id=task.task_id,
            success=True,
            summary=f"Operations check completed for: {task.objective}",
            data={"health": task.payload.get("health", "ok")},
        )

    def _quality(task: AgentTask) -> AgentResult:
        return AgentResult(
            agent_name="quality-agent",
            task_id=task.task_id,
            success=True,
            summary=f"Quality review executed for: {task.objective}",
            data={"risk_level": task.payload.get("risk_level", "medium")},
        )

    return [
        VirginieAgent(name="planning-agent", domains=("planning", "product"), handler=_planning),
        VirginieAgent(name="ops-agent", domains=("operations", "deployment"), handler=_ops),
        VirginieAgent(
            name="quality-agent", domains=("quality", "testing", "security"), handler=_quality
        ),
    ]
