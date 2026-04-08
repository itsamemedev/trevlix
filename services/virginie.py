"""Core primitives for VIRGINIE 0.0.1.

This module is the first implementation step for the user-defined autonomous
assistant "VIRGINIE 0.0.1". It provides two building blocks:

1. Profit scoring via expected-value ranking.
2. Cross-LLM performance tracking with exploration support.
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
class Opportunity:
    """Represents one actionable option with upside, cost, and risk.

    Attributes:
        key: Stable identifier for the action.
        success_probability: Probability of success in range [0.0, 1.0].
        expected_profit: Gross profit if successful.
        cost: Cost to execute the action.
        risk_penalty: Additional downside penalty.
    """

    key: str
    success_probability: float
    expected_profit: float
    cost: float = 0.0
    risk_penalty: float = 0.0


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
