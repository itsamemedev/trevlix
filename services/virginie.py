"""Core self-learning components for VIRGINIE 0.0.1.

This module integrates the self-learning pieces discussed for VIRGINIE:

1. Opportunity scoring with profit, costs, and risk penalties.
2. Cross-LLM learning with per-task reward tracking.
3. Bandit-style action selection that improves from outcome feedback.
4. Guardrails to avoid unbounded risk while optimizing expected value.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import log, sqrt


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

    def record(self, result: LLMResult) -> None:
        """Record one reward outcome for a model-task pair."""
        task_stats = self._stats.setdefault(result.task_type, {})
        model_stats = task_stats.setdefault(result.model, {"count": 0.0, "sum_reward": 0.0})
        model_stats["count"] += 1
        model_stats["sum_reward"] += result.reward

    def recommend(self, task_type: str) -> str | None:
        """Recommend the best model for a task using UCB.

        Returns None when no observations exist for this task.
        """
        task_stats = self._stats.get(task_type)
        if not task_stats:
            return None

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

    def select_opportunity(self, opportunities: list[Opportunity]) -> Opportunity | None:
        """Select the best allowed opportunity using EV + action UCB.

        Guardrails filter out unsafe opportunities before ranking.
        """
        candidates = [item for item in opportunities if self._passes_guardrails(item)]
        if not candidates:
            return None

        scored: list[tuple[Opportunity, float]] = []
        total_count = sum(stats["count"] for stats in self._action_stats.values())
        for item in candidates:
            base_score = self.profit_engine.score(item)
            bandit_bonus = self._action_bonus(item.key, total_count)
            scored.append((item, base_score + bandit_bonus))

        scored.sort(key=lambda entry: entry[1], reverse=True)
        return scored[0][0]

    def learn_from_action(self, result: ActionResult) -> None:
        """Store realized profit feedback for future action selection."""
        stats = self._action_stats.setdefault(
            result.opportunity_key,
            {"count": 0.0, "sum_profit": 0.0},
        )
        stats["count"] += 1
        stats["sum_profit"] += result.realized_profit

    def learn_from_llm(self, result: LLMResult) -> None:
        """Store cross-LLM reward feedback for task routing."""
        self.llm_tracker.record(result)

    def recommend_llm(self, task_type: str) -> str | None:
        """Return recommended model for the given task type."""
        return self.llm_tracker.recommend(task_type)

    def action_average_profit(self, opportunity_key: str) -> float | None:
        """Return average realized profit for an opportunity."""
        stats = self._action_stats.get(opportunity_key)
        if not stats or stats["count"] <= 0:
            return None
        return stats["sum_profit"] / stats["count"]

    def _passes_guardrails(self, opportunity: Opportunity) -> bool:
        score = self.profit_engine.score(opportunity)
        return (
            score >= self.guardrails.min_score
            and opportunity.risk_penalty <= self.guardrails.max_risk_penalty
        )

    def _action_bonus(self, key: str, total_count: float) -> float:
        stats = self._action_stats.get(key)
        if not stats or stats["count"] <= 0:
            return self._action_exploration_c

        count = stats["count"]
        avg_profit = stats["sum_profit"] / count
        if total_count <= 0:
            return avg_profit

        exploration = self._action_exploration_c * sqrt(log(total_count + 1) / count)
        return avg_profit + exploration
