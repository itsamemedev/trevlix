"""Core self-learning components for VIRGINIE 0.0.1.

This module integrates the self-learning pieces discussed for VIRGINIE:

1. Opportunity scoring with profit, costs, and risk penalties.
2. Cross-LLM learning with per-task reward tracking.
3. Bandit-style action selection that improves from outcome feedback.
4. Guardrails to avoid unbounded risk while optimizing expected value.
"""

from __future__ import annotations

import threading
import time
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
class VirginieRules:
    """Ruleset controlling autonomous tuning and version updates."""

    min_samples_for_revision: int = 20
    min_avg_profit_for_revision: float = 1.0
    max_variance_for_revision: float = 2500.0
    min_review_interval_sec: int = 60


class VirginieVersionManager:
    """Simple semantic patch-version manager for autonomous upgrades."""

    def __init__(self, initial_version: str) -> None:
        self._current = initial_version
        self._history: list[dict[str, str]] = []

    @property
    def current(self) -> str:
        return self._current

    @property
    def history(self) -> list[dict[str, str]]:
        return list(self._history)

    def bump_patch(self, reason: str) -> str:
        parts = self._current.split(".")
        if len(parts) != 3 or not all(p.isdigit() for p in parts):
            parts = ["0", "0", "1"]
        major, minor, patch = (int(parts[0]), int(parts[1]), int(parts[2]))
        patch += 1
        self._current = f"{major}.{minor}.{patch}"
        self._history.insert(0, {"version": self._current, "reason": reason})
        self._history = self._history[:30]
        return self._current


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
class LearningExample:
    """Reusable example that can be improved through outcome feedback."""

    example_id: str
    task_type: str
    content: str
    quality_score: float = 0.5


def build_startup_examples() -> list[LearningExample]:
    """Return built-in examples that VIRGINIE should load on startup."""
    return [
        LearningExample(
            example_id="startup-trading-max-profit",
            task_type="trading_max_profit",
            content=(
                "Bewerte pro Marktchance: EV = P(success) * expected_profit - cost - risk_penalty. "
                "Priorisiere Chancen mit hohem EV, niedriger Varianz und klaren Exit-Regeln "
                "(Stop-Loss + Take-Profit), respektiere Guardrails und minimiere Overtrading."
            ),
            quality_score=0.75,
        ),
        LearningExample(
            example_id="startup-agent-control",
            task_type="agent_orchestration",
            content=(
                "Steuere alle Agenten über Domänenrouting, Failure-Cooldown und Priorisierung. "
                "Delegiere Portfolio-Ziele an Trading-Agenten, blocke riskante Aktionen bei "
                "Guardrail-Verletzungen und eskaliere bei wiederholten Fehlern."
            ),
            quality_score=0.72,
        ),
        LearningExample(
            example_id="startup-bear-market",
            task_type="trading_max_profit",
            content=(
                "Im Bärenmarkt (EMA50 < EMA200, RSI < 45): Positionsgrößen um 50% reduzieren, "
                "Stop-Loss enger setzen (1.5%), nur Signale mit mindestens 6/9 Strategie-Stimmen "
                "handeln. Gewinne schneller realisieren (TP bei 2-3% statt 6%)."
            ),
            quality_score=0.78,
        ),
        LearningExample(
            example_id="startup-bull-market",
            task_type="trading_max_profit",
            content=(
                "Im Bullenmarkt (EMA8 > EMA21 > EMA50, vol_ratio > 1.5): Normale Positionsgröße, "
                "Trend-Strategien (EMA, MACD, VWAP) höher gewichten. DCA bei Rücksetzern erlaubt. "
                "Take-Profit kann auf 8-10% erhöht werden wenn Momentum stark."
            ),
            quality_score=0.76,
        ),
        LearningExample(
            example_id="startup-risk-management",
            task_type="risk_management",
            content=(
                "Circuit Breaker sofort aktivieren wenn: daily_loss > 3% oder 3 Verluste in Folge. "
                "Max 5 offene Positionen gleichzeitig. Nie mehr als 2% des Portfolios pro Trade riskieren. "
                "Bei ATR > 3% Positionsgröße halbieren. Drawdown > 10%: Bot pausieren."
            ),
            quality_score=0.82,
        ),
        LearningExample(
            example_id="startup-signal-quality",
            task_type="trading_max_profit",
            content=(
                "Hochqualitative Kauf-Signale: RSI 35-55 (nicht überkauft), OBV steigend, "
                "MACD-Histogramm positiv und wachsend, Volumen 20% über MA, MTF-Bestätigung aktiv. "
                "Schwache Signale (< 4 Stimmen, bb_pct > 0.9, news_score < -0.3) immer ablehnen."
            ),
            quality_score=0.80,
        ),
        LearningExample(
            example_id="startup-exit-strategy",
            task_type="trading_max_profit",
            content=(
                "Exit-Regeln: Stop-Loss bei 2.5% unter Einstieg. Take-Profit gestaffelt: "
                "25% bei 3%, 50% bei 5%, Rest bei 8% oder Trailing-Stop. "
                "Sofortiger Ausstieg bei: RSI > 80, MACD-Kreuzung nach unten, Volumen-Einbruch > 40%. "
                "Gewinnende Trades nie unter Break-Even fallen lassen."
            ),
            quality_score=0.79,
        ),
        LearningExample(
            example_id="startup-multi-exchange",
            task_type="agent_orchestration",
            content=(
                "Multi-Exchange-Betrieb: Primary Exchange für alle Trades nutzen. "
                "Sekundäre Exchanges nur für Arbitrage oder wenn Primary nicht erreichbar. "
                "Balance über alle Exchanges aggregieren für korrekte Positionsgrößen-Berechnung. "
                "Exchange-Fehler eskalieren an Notifications-Agent, nicht ignorieren."
            ),
            quality_score=0.71,
        ),
        LearningExample(
            example_id="startup-dca-strategy",
            task_type="trading_max_profit",
            content=(
                "DCA (Dollar-Cost-Averaging): Nur bei bestehender Position mit unrealisiertem Verlust < 4%. "
                "Max 2 DCA-Levels pro Position. Jedes Level verdoppelt die ursprüngliche Positionsgröße. "
                "DCA-Einstieg bei RSI < 40 und Volumen-Bestätigung. Gesamt-Exposure max 6% des Portfolios."
            ),
            quality_score=0.74,
        ),
    ]


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
        rules: VirginieRules | None = None,
        exploration_c: float = 0.8,
        action_exploration_c: float = 0.5,
    ) -> None:
        self.identity = VirginieIdentity()
        self.guardrails = guardrails or VirginieGuardrails()
        self.rules = rules or VirginieRules()
        self.profit_engine = ProfitDecisionEngine()
        self.llm_tracker = LLMPerformanceTracker(exploration_c=exploration_c)
        self._action_exploration_c = action_exploration_c
        self._action_stats: dict[str, dict[str, float]] = {}
        self._lock = threading.Lock()
        self._version_manager = VirginieVersionManager(self.identity.version)
        self._last_review_at = 0.0
        self._last_review_summary = "No review yet"
        self._examples: dict[str, dict[str, Any]] = {}
        self._load_startup_examples()

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

    def add_or_update_example(self, example: LearningExample) -> None:
        """Register a reusable example for a task."""
        example_id = str(example.example_id or "").strip()
        task_type = str(example.task_type or "").strip()
        if not example_id or not task_type:
            raise ValueError("example_id and task_type must not be empty")
        with self._lock:
            current = self._examples.get(example_id)
            count = float(current.get("count", 0.0)) if current else 0.0
            self._examples[example_id] = {
                "example_id": example_id,
                "task_type": task_type,
                "content": str(example.content or "").strip(),
                "quality_score": min(1.0, max(0.0, float(example.quality_score))),
                "count": count,
            }

    def _load_startup_examples(self) -> None:
        """Load built-in examples so VIRGINIE starts with useful playbooks."""
        for example in build_startup_examples():
            self.add_or_update_example(example)

    def learn_from_example_result(self, example_id: str, reward: float) -> None:
        """Update one example quality score from real-world feedback.

        Reward is expected in range 0..1 and clamped if needed.
        """
        key = str(example_id or "").strip()
        if not key:
            raise ValueError("example_id must not be empty")

        bounded_reward = min(1.0, max(0.0, float(reward)))
        with self._lock:
            if key not in self._examples:
                raise KeyError(f"Unknown example_id: {key}")
            data = self._examples[key]
            count = float(data.get("count", 0.0))
            score = float(data.get("quality_score", 0.5))
            new_count = count + 1.0
            data["quality_score"] = ((score * count) + bounded_reward) / new_count
            data["count"] = new_count

    def top_examples(self, task_type: str, *, limit: int = 3) -> list[LearningExample]:
        """Return best examples for a task, sorted by learned quality score."""
        normalized_task = str(task_type or "").strip()
        if not normalized_task:
            return []
        max_items = max(1, int(limit))
        with self._lock:
            rows = [
                item
                for item in self._examples.values()
                if str(item.get("task_type", "")).strip() == normalized_task
            ]
        rows.sort(key=lambda item: float(item.get("quality_score", 0.0)), reverse=True)
        return [
            LearningExample(
                example_id=str(item["example_id"]),
                task_type=str(item["task_type"]),
                content=str(item.get("content", "")),
                quality_score=float(item.get("quality_score", 0.0)),
            )
            for item in rows[:max_items]
        ]

    def example_snapshot(self) -> dict[str, dict[str, Any]]:
        """Return a copy of tracked examples and their learned scores."""
        with self._lock:
            return {key: dict(value) for key, value in self._examples.items()}

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

    def current_version(self) -> str:
        """Return current autonomous VIRGINIE version."""
        return self._version_manager.current

    def review_and_improve(self, now_ts: float | None = None) -> dict[str, Any]:
        """Evaluate learning stats and autonomously tune/bump version via rules."""
        now = now_ts if now_ts is not None else datetime.utcnow().timestamp()
        if now - self._last_review_at < self.rules.min_review_interval_sec:
            return {
                "reviewed": False,
                "version": self.current_version(),
                "summary": "Review skipped due to min interval",
            }

        snap = self.action_snapshot()
        total_samples = int(sum(v["count"] for v in snap.values()))
        avg_profit = 0.0
        variance = 0.0
        if snap:
            avg_profit = sum(v["avg_profit"] for v in snap.values()) / len(snap)
            variance = sum(v["variance"] for v in snap.values()) / len(snap)

        improved = (
            total_samples >= self.rules.min_samples_for_revision
            and avg_profit >= self.rules.min_avg_profit_for_revision
            and variance <= self.rules.max_variance_for_revision
        )

        if improved:
            old = self.current_version()
            new = self._version_manager.bump_patch(
                f"Auto-tune: samples={total_samples}, avg={avg_profit:.2f}, var={variance:.2f}"
            )
            self._action_exploration_c = max(0.1, self._action_exploration_c * 0.98)
            summary = f"Version bump {old} -> {new} after successful review"
        else:
            self._action_exploration_c = min(1.5, self._action_exploration_c * 1.01)
            summary = (
                "No bump: thresholds not met "
                f"(samples={total_samples}, avg={avg_profit:.2f}, var={variance:.2f})"
            )

        self._last_review_at = now
        self._last_review_summary = summary
        return {
            "reviewed": True,
            "version": self.current_version(),
            "summary": summary,
            "total_samples": total_samples,
            "avg_profit": avg_profit,
            "variance": variance,
            "history": self._version_manager.history,
        }

    def review_status(self) -> dict[str, Any]:
        """Return latest review state without triggering a new review cycle."""
        return {
            "version": self.current_version(),
            "summary": self._last_review_summary,
            "history": self._version_manager.history,
            "last_review_at": self._last_review_at,
        }

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

    def __init__(
        self,
        *,
        failure_cooldown_sec: float = 60.0,
        failure_threshold: int = 3,
        time_fn: Callable[[], float] | None = None,
    ) -> None:
        self._agents: dict[str, VirginieAgent] = {}
        self._history: list[AgentResult] = []
        self._lock = threading.Lock()
        self._required_domains: set[str] = set()
        self._agent_task_counts: dict[str, int] = {}
        self._agent_stats: dict[str, dict[str, Any]] = {}
        self._failure_cooldown_sec = max(1.0, float(failure_cooldown_sec))
        self._failure_threshold = max(1, int(failure_threshold))
        self._time_fn = time_fn or time.time
        self._domain_aliases: dict[str, str] = {
            "ops": "operations",
            "deploy": "operations",
            "alerts": "notifications",
            "notify": "notifications",
            "msg": "notifications",
            "exec": "execution",
            "qa": "quality",
            "sec": "security",
            "gov": "governance",
            "alloc": "allocation",
        }

    @staticmethod
    def _normalize_domain(domain: str) -> str:
        normalized = str(domain or "").strip().lower().replace("_", " ").replace("-", " ")
        return " ".join(normalized.split())

    @staticmethod
    def _safe_text(value: Any, *, max_len: int = 300) -> str:
        text = str(value or "").strip()
        return text[:max_len]

    def register_agent(self, agent: VirginieAgent) -> None:
        """Register or replace an agent by name."""
        normalized_name = self._safe_text(agent.name, max_len=120)
        if not normalized_name:
            raise ValueError("Agent name must not be empty")
        normalized_domains = tuple(
            d
            for d in (
                self._domain_aliases.get(
                    self._normalize_domain(domain), self._normalize_domain(domain)
                )
                for domain in agent.domains
            )
            if d
        )
        normalized_agent = VirginieAgent(
            name=normalized_name,
            domains=normalized_domains,
            handler=agent.handler,
        )
        with self._lock:
            self._agents[normalized_agent.name] = normalized_agent
            self._agent_task_counts.setdefault(normalized_agent.name, 0)
            self._agent_stats.setdefault(
                normalized_agent.name,
                {
                    "assigned": 0,
                    "success": 0,
                    "failure": 0,
                    "consecutive_failure": 0,
                    "last_failure_ts": 0.0,
                    "last_error": None,
                },
            )

    def unregister_agent(self, agent_name: str) -> bool:
        """Remove an agent and related stats. Returns True when removed."""
        key = self._safe_text(agent_name, max_len=120)
        with self._lock:
            existed = key in self._agents
            self._agents.pop(key, None)
            self._agent_task_counts.pop(key, None)
            self._agent_stats.pop(key, None)
            return existed

    def set_required_domains(self, domains: list[str]) -> None:
        """Set mandatory domains that must be covered by at least one agent."""
        with self._lock:
            normalized = []
            for x in domains:
                d = self._normalize_domain(x)
                if not d:
                    continue
                normalized.append(self._domain_aliases.get(d, d))
            self._required_domains = set(normalized)

    def history(self, limit: int | None = None) -> list[AgentResult]:
        """Return newest-first execution history."""
        with self._lock:
            if limit is None or limit <= 0:
                return list(self._history)
            return list(self._history[: int(limit)])

    def clear_history(self) -> None:
        """Clear routing/execution history."""
        with self._lock:
            self._history.clear()

    def reset_agent_stats(self, agent_name: str | None = None) -> None:
        """Reset stats for one agent or all agents."""
        with self._lock:
            if agent_name:
                key = self._safe_text(agent_name, max_len=120)
                if key in self._agent_task_counts:
                    self._agent_task_counts[key] = 0
                if key in self._agent_stats:
                    self._agent_stats[key] = {
                        "assigned": 0,
                        "success": 0,
                        "failure": 0,
                        "consecutive_failure": 0,
                        "last_failure_ts": 0.0,
                        "last_error": None,
                    }
                return
            for name in list(self._agent_task_counts.keys()):
                self._agent_task_counts[name] = 0
            for name in list(self._agent_stats.keys()):
                self._agent_stats[name] = {
                    "assigned": 0,
                    "success": 0,
                    "failure": 0,
                    "consecutive_failure": 0,
                    "last_failure_ts": 0.0,
                    "last_error": None,
                }

    def missing_domains(self) -> list[str]:
        """Return required domains currently not covered by any registered agent."""
        with self._lock:
            covered = {domain for agent in self._agents.values() for domain in agent.domains}
            missing = sorted(self._required_domains - covered)
        return missing

    def coverage_report(self) -> dict[str, Any]:
        """Return domain coverage quality report for orchestrator governance."""
        missing = self.missing_domains()
        required_count = len(self._required_domains)
        covered_count = required_count - len(missing)
        coverage_pct = (covered_count / required_count * 100.0) if required_count > 0 else 100.0
        return {
            "required_domains": sorted(self._required_domains),
            "missing_domains": missing,
            "coverage_pct": round(coverage_pct, 1),
            "is_complete": len(missing) == 0,
        }

    def route_task(self, task: AgentTask) -> str | None:
        """Return best matching agent name for a task domain."""
        agent_name, _details = self._route_task_with_details(task)
        return agent_name

    def _route_task_with_details(self, task: AgentTask) -> tuple[str | None, dict[str, Any]]:
        """Return selected agent with routing diagnostics for observability."""
        task_domain = self._normalize_domain(task.domain)
        task_domain = self._domain_aliases.get(task_domain, task_domain)
        inferred: str | None = None
        with self._lock:
            matches = [a.name for a in self._agents.values() if task_domain in a.domains]
            if not matches:
                inferred = self._infer_domain(task)
                if inferred:
                    matches = [a.name for a in self._agents.values() if inferred in a.domains]
        if not matches:
            return None, {
                "domain_requested": task_domain,
                "domain_inferred": inferred,
                "matches": [],
                "cooldown_excluded": [],
            }
        with self._lock:
            cooldown_excluded = [name for name in matches if self._is_agent_in_cooldown(name)]
            available = [name for name in matches if name not in cooldown_excluded]
            candidates = available or matches
            ranked = sorted(
                candidates,
                key=lambda name: (
                    self._agent_failure_rate(name),
                    self._agent_task_counts.get(name, 0),
                    name,
                ),
            )
        return ranked[0], {
            "domain_requested": task_domain,
            "domain_inferred": inferred,
            "matches": matches,
            "cooldown_excluded": cooldown_excluded,
            "candidates": candidates,
            "ranked": ranked,
        }

    def execute(self, task: AgentTask) -> AgentResult:
        """Execute a task via its routed agent and store history."""
        agent_name, route_details = self._route_task_with_details(task)
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
            return AgentResult(
                agent_name=result.agent_name,
                task_id=result.task_id,
                success=result.success,
                summary=result.summary,
                data={**result.data, "routing": route_details},
            )

        with self._lock:
            agent = self._agents[agent_name]

        try:
            raw_result = agent.handler(task)
        except Exception as exc:
            raw_result = AgentResult(
                agent_name=agent_name,
                task_id=task.task_id,
                success=False,
                summary=f"Agent execution failed: {exc}",
                data={"error_type": type(exc).__name__},
            )
            raw_result = AgentResult(
                agent_name=raw_result.agent_name,
                task_id=raw_result.task_id,
                success=raw_result.success,
                summary=self._safe_text(raw_result.summary, max_len=240),
                data=raw_result.data,
            )
        result = AgentResult(
            agent_name=raw_result.agent_name,
            task_id=raw_result.task_id,
            success=raw_result.success,
            summary=raw_result.summary,
            data={**raw_result.data, "routing": route_details},
        )

        with self._lock:
            self._agent_task_counts[agent_name] = self._agent_task_counts.get(agent_name, 0) + 1
            stats = self._agent_stats.setdefault(
                agent_name,
                {
                    "assigned": 0,
                    "success": 0,
                    "failure": 0,
                    "consecutive_failure": 0,
                    "last_failure_ts": 0.0,
                    "last_error": None,
                },
            )
            stats["assigned"] += 1
            if result.success:
                stats["success"] += 1
                stats["consecutive_failure"] = 0
                stats["last_error"] = None
            else:
                stats["failure"] += 1
                stats["consecutive_failure"] = int(stats.get("consecutive_failure", 0)) + 1
                stats["last_failure_ts"] = float(self._time_fn())
                stats["last_error"] = result.summary
            self._history.insert(0, result)
            self._history = self._history[:200]
        return result

    def status(self) -> dict[str, Any]:
        """Return orchestrator metadata for backend/dashboard diagnostics."""
        with self._lock:
            last = self._history[0] if self._history else None
            covered = {domain for agent in self._agents.values() for domain in agent.domains}
            missing = sorted(self._required_domains - covered)
            required_count = len(self._required_domains)
            covered_count = required_count - len(missing)
            coverage_pct = (covered_count / required_count * 100.0) if required_count > 0 else 100.0
            return {
                "registered_agents": len(self._agents),
                "agent_names": sorted(self._agents.keys()),
                "domains": sorted({d for a in self._agents.values() for d in a.domains}),
                "agent_task_counts": dict(self._agent_task_counts),
                "agent_health": {
                    name: {
                        "assigned": int(stats.get("assigned", 0)),
                        "success": int(stats.get("success", 0)),
                        "failure": int(stats.get("failure", 0)),
                        "consecutive_failure": int(stats.get("consecutive_failure", 0)),
                        "failure_rate": round(self._agent_failure_rate(name), 3),
                        "cooldown_active": self._is_agent_in_cooldown(name),
                        "last_error": stats.get("last_error"),
                    }
                    for name, stats in self._agent_stats.items()
                },
                "history_size": len(self._history),
                "last_task_id": last.task_id if last else None,
                "last_agent": last.agent_name if last else None,
                "last_success": last.success if last else None,
                "last_summary": last.summary if last else None,
                "coverage_pct": round(coverage_pct, 1),
                "missing_domains": missing,
                "required_domains": sorted(self._required_domains),
                "coverage_complete": len(missing) == 0,
                "total_tasks": int(sum(self._agent_task_counts.values())),
                "total_success": int(
                    sum(int(s.get("success", 0)) for s in self._agent_stats.values())
                ),
                "total_failures": int(
                    sum(int(s.get("failure", 0)) for s in self._agent_stats.values())
                ),
                "failure_threshold": self._failure_threshold,
                "failure_cooldown_sec": self._failure_cooldown_sec,
                "updated_at": datetime.utcnow().isoformat(timespec="seconds"),
            }

    def _infer_domain(self, task: AgentTask) -> str | None:
        """Infer a likely domain from objective/payload keywords."""
        text = " ".join(
            [
                str(task.objective or ""),
                str(task.payload.get("reason", "")),
                str(task.payload.get("action", "")),
                str(task.payload.get("symbol", "")),
            ]
        ).lower()
        rules: list[tuple[str, tuple[str, ...]]] = [
            ("risk", ("risk", "limit", "drawdown", "volatility")),
            ("learning", ("learn", "feedback", "post-trade", "retrain")),
            ("trading", ("trade", "buy", "sell", "execution", "position")),
            ("notifications", ("notify", "alert", "chat", "message", "discord", "telegram")),
            ("quality", ("quality", "test", "qa", "validation")),
            ("operations", ("deploy", "ops", "restart", "health", "uptime")),
            ("portfolio", ("portfolio", "allocation", "rebalance", "target")),
            ("compliance", ("compliance", "policy", "audit", "governance")),
            ("planning", ("plan", "roadmap", "milestone", "product")),
        ]
        for domain, keywords in rules:
            if any(keyword in text for keyword in keywords):
                return domain
        return None

    def _agent_failure_rate(self, agent_name: str) -> float:
        stats = self._agent_stats.get(agent_name, {})
        assigned = int(stats.get("assigned", 0))
        if assigned <= 0:
            return 0.0
        failure = int(stats.get("failure", 0))
        return failure / assigned

    def _is_agent_in_cooldown(self, agent_name: str) -> bool:
        stats = self._agent_stats.get(agent_name, {})
        consecutive = int(stats.get("consecutive_failure", 0))
        if consecutive < self._failure_threshold:
            return False
        last_failure_ts = float(stats.get("last_failure_ts", 0.0) or 0.0)
        return (self._time_fn() - last_failure_ts) < self._failure_cooldown_sec


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

    def _notifications(task: AgentTask) -> AgentResult:
        return AgentResult(
            agent_name="notification-agent",
            task_id=task.task_id,
            success=True,
            summary=f"Notification dispatch prepared for: {task.objective}",
            data={"channel": task.payload.get("channel", "discord")},
        )

    def _trading(task: AgentTask) -> AgentResult:
        return AgentResult(
            agent_name="trading-agent",
            task_id=task.task_id,
            success=True,
            summary=f"Trading control workflow executed for: {task.objective}",
            data={"action": task.payload.get("action", "monitor")},
        )

    def _learning(task: AgentTask) -> AgentResult:
        return AgentResult(
            agent_name="learning-agent",
            task_id=task.task_id,
            success=True,
            summary=f"Learning loop update executed for: {task.objective}",
            data={"feedback": task.payload.get("feedback", "captured")},
        )

    def _risk(task: AgentTask) -> AgentResult:
        return AgentResult(
            agent_name="risk-agent",
            task_id=task.task_id,
            success=True,
            summary=f"Risk policy check executed for: {task.objective}",
            data={"risk_mode": task.payload.get("risk_mode", "balanced")},
        )

    def _portfolio(task: AgentTask) -> AgentResult:
        target_amount = float(task.payload.get("target_amount", 0) or 0)
        current_value = float(task.payload.get("portfolio_value", 0) or 0)
        gap_to_target = max(0.0, target_amount - current_value) if target_amount > 0 else 0.0
        has_goal = target_amount > 0
        is_paper_mode = bool(task.payload.get("paper_mode", False))
        min_buy_notional = float(task.payload.get("min_buy_notional", 0) or 0)
        min_sell_notional = float(task.payload.get("min_sell_notional", 0) or 0)
        min_trade_notional = max(min_buy_notional, min_sell_notional)
        constraints_known = min_trade_notional > 0
        if is_paper_mode:
            tradable_gap = gap_to_target > 0
        else:
            tradable_gap = (
                gap_to_target >= min_trade_notional if constraints_known else gap_to_target > 0
            )
        objective_text = (
            f"{task.objective} | Ziel={target_amount:.2f} USDT" if has_goal else task.objective
        )

        return AgentResult(
            agent_name="portfolio-agent",
            task_id=task.task_id,
            success=True,
            summary=(
                (
                    "Paper mode goal received; trading-agent assigned without exchange minimum checks"
                    if tradable_gap and is_paper_mode
                    else (
                        "Portfolio goal received; trading-agent assigned for fastest target pursuit"
                        if tradable_gap
                        else "Portfolio goal received but blocked by exchange minimum trade conditions"
                    )
                )
                if has_goal
                else f"Portfolio allocation review executed for: {task.objective}"
            ),
            data={
                "allocation_delta": task.payload.get("allocation_delta", 0),
                "goal_target_amount": round(target_amount, 2),
                "goal_current_value": round(current_value, 2),
                "goal_gap_amount": round(gap_to_target, 2),
                "exchange_min_buy_notional": round(min_buy_notional, 8),
                "exchange_min_sell_notional": round(min_sell_notional, 8),
                "exchange_constraints_known": constraints_known,
                "paper_mode": is_paper_mode,
                "exchange_constraints_enforced": not is_paper_mode,
                "goal_tradable_under_exchange_rules": tradable_gap,
                "delegate_to": "trading-agent" if has_goal and tradable_gap else None,
                "delegate_task": {
                    "domain": "trading",
                    "objective": objective_text,
                    "payload": {
                        "action": "reach_target_fast",
                        "autonomous_allocation": True,
                        "optimize_for_speed": True,
                        "respect_exchange_minimums": not is_paper_mode,
                        "paper_mode": is_paper_mode,
                        "target_amount": round(target_amount, 2),
                        "current_portfolio_value": round(current_value, 2),
                        "target_gap_amount": round(gap_to_target, 2),
                        "min_buy_notional": round(min_buy_notional, 8),
                        "min_sell_notional": round(min_sell_notional, 8),
                        "min_trade_notional": round(min_trade_notional, 8),
                    },
                }
                if has_goal and tradable_gap
                else None,
            },
        )

    def _compliance(task: AgentTask) -> AgentResult:
        return AgentResult(
            agent_name="compliance-agent",
            task_id=task.task_id,
            success=True,
            summary=f"Compliance validation executed for: {task.objective}",
            data={"policy": task.payload.get("policy", "default")},
        )

    return [
        VirginieAgent(name="planning-agent", domains=("planning", "product"), handler=_planning),
        VirginieAgent(name="ops-agent", domains=("operations", "deployment"), handler=_ops),
        VirginieAgent(
            name="quality-agent", domains=("quality", "testing", "security"), handler=_quality
        ),
        VirginieAgent(
            name="notification-agent",
            domains=("notifications", "alerts"),
            handler=_notifications,
        ),
        VirginieAgent(name="trading-agent", domains=("trading", "execution"), handler=_trading),
        VirginieAgent(name="learning-agent", domains=("learning", "feedback"), handler=_learning),
        VirginieAgent(name="risk-agent", domains=("risk", "limits"), handler=_risk),
        VirginieAgent(
            name="portfolio-agent",
            domains=("portfolio", "allocation"),
            handler=_portfolio,
        ),
        VirginieAgent(
            name="compliance-agent",
            domains=("compliance", "governance"),
            handler=_compliance,
        ),
    ]
