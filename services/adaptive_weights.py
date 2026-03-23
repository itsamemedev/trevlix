"""TREVLIX – Adaptive Strategy Weighting Engine.

Passt die Gewichte der 9 Voting-Strategien dynamisch an, basierend auf
ihrer jüngsten Performance. Strategien, die in der aktuellen Marktphase
gut performen, bekommen höheres Gewicht – schlechte werden heruntergestuft.

Einzigartig: Selbstlernende Strategie-Gewichtung mit Regime-Sensitivität
und Exponential Decay. Kein anderer Open-Source-Bot bietet diese Art
der automatischen Strategie-Optimierung in Echtzeit.

Kernlogik:
    1. Rolling-Window: Nur die letzten N Trades pro Strategie zählen
    2. Exponential Decay: Neuere Trades zählen exponentiell stärker
    3. Regime-Awareness: Separate Gewichte pro Marktregime
    4. Clamping: Gewichte zwischen 0.3x und 2.5x begrenzt
    5. Normalisierung: Durchschnittliches Gewicht bleibt bei 1.0

Verwendung:
    from services.adaptive_weights import AdaptiveWeights

    aw = AdaptiveWeights()
    aw.record_vote("EMA-Trend", won=True, regime="bull")
    weights = aw.get_weights(regime="bull")
"""

import logging
import threading
from collections import defaultdict
from datetime import datetime
from typing import Any

import numpy as np

log = logging.getLogger("trevlix.adaptive_weights")

# Default-Strategienamen (müssen mit STRATEGY_NAMES übereinstimmen)
_DEFAULT_STRATEGIES = [
    "EMA-Trend",
    "RSI-Stochastic",
    "MACD-Kreuzung",
    "Bollinger",
    "Volumen-Ausbruch",
    "OBV-Trend",
    "ROC-Momentum",
    "Ichimoku",
    "VWAP",
]


class AdaptiveWeights:
    """Self-Learning Strategy Weight Engine.

    Verfolgt die Performance jeder Strategie über ein Rolling-Window
    und berechnet optimale Gewichte mit Exponential Decay.

    Args:
        window_size: Anzahl der letzten Trades pro Strategie für die Gewichtung.
        decay_factor: Exponential Decay (0.9 = neuere Trades 10% stärker pro Schritt).
        min_weight: Minimales Gewicht (verhindert vollständiges Abschalten).
        max_weight: Maximales Gewicht (verhindert Überkonzentration).
        min_samples: Mindestanzahl Trades bevor Anpassung greift.
        strategies: Liste der Strategienamen.
    """

    def __init__(
        self,
        window_size: int = 50,
        decay_factor: float = 0.92,
        min_weight: float = 0.3,
        max_weight: float = 2.5,
        min_samples: int = 10,
        strategies: list[str] | None = None,
    ) -> None:
        self._window = window_size
        self._decay = decay_factor
        self._min_w = min_weight
        self._max_w = max_weight
        self._min_samples = min_samples
        self._strategies = strategies or list(_DEFAULT_STRATEGIES)
        self._lock = threading.Lock()

        # Global: strategy → [list of (won: bool, timestamp)]
        self._global_history: dict[str, list[tuple[bool, float]]] = defaultdict(list)

        # Regime-spezifisch: regime → strategy → [list of (won: bool, timestamp)]
        self._regime_history: dict[str, dict[str, list[tuple[bool, float]]]] = defaultdict(
            lambda: defaultdict(list)
        )

        # Cached Gewichte (wird bei jedem record_vote aktualisiert)
        self._cached_global: dict[str, float] = {s: 1.0 for s in self._strategies}
        self._cached_regime: dict[str, dict[str, float]] = {}

    def record_vote(
        self,
        strategy: str,
        won: bool,
        regime: str = "unknown",
        pnl: float | None = None,
    ) -> None:
        """Zeichnet das Ergebnis eines Strategy-Votes auf.

        Args:
            strategy: Name der Strategie (z.B. 'EMA-Trend').
            won: True wenn der Trade profitabel war.
            regime: Marktregime zum Zeitpunkt des Trades.
            pnl: Optionaler PnL-Wert (für zukünftige PnL-gewichtete Berechnung).
        """
        now = datetime.now().timestamp()

        with self._lock:
            # Global
            h = self._global_history[strategy]
            h.append((won, now))
            if len(h) > self._window:
                self._global_history[strategy] = h[-self._window :]

            # Regime-spezifisch
            rh = self._regime_history[regime][strategy]
            rh.append((won, now))
            if len(rh) > self._window:
                self._regime_history[regime][strategy] = rh[-self._window :]

            # Gewichte direkt unter Lock neu berechnen (verhindert Race Condition)
            self._recalculate_unlocked()

    def get_weights(self, regime: str | None = None) -> dict[str, float]:
        """Gibt die aktuellen Strategie-Gewichte zurück.

        Args:
            regime: Wenn angegeben, werden regime-spezifische Gewichte
                    mit den globalen Gewichten gemischt (70/30).

        Returns:
            Dict {strategy_name: weight} mit normalisierten Gewichten.
        """
        with self._lock:
            if regime and regime in self._cached_regime:
                # Mische global (30%) + regime-spezifisch (70%)
                global_w = dict(self._cached_global)
                regime_w = dict(self._cached_regime[regime])
                merged = {}
                for s in self._strategies:
                    g = global_w.get(s, 1.0)
                    r = regime_w.get(s, 1.0)
                    merged[s] = round(0.3 * g + 0.7 * r, 3)
                return merged
            return dict(self._cached_global)

    def _recalculate(self) -> None:
        """Berechnet alle Gewichte neu (thread-safe)."""
        with self._lock:
            self._recalculate_unlocked()

    def _recalculate_unlocked(self) -> None:
        """Berechnet alle Gewichte neu (muss unter self._lock aufgerufen werden)."""
        # Global
        self._cached_global = self._compute_weights(self._global_history)

        # Pro Regime – Snapshot der Keys um RuntimeError bei dict-Änderung zu vermeiden
        for regime in list(self._regime_history.keys()):
            strat_history = self._regime_history.get(regime)
            if strat_history:
                self._cached_regime[regime] = self._compute_weights(strat_history)

    def _compute_weights(self, history: dict[str, list[tuple[bool, float]]]) -> dict[str, float]:
        """Berechnet Gewichte aus einer History mit Exponential Decay.

        Returns:
            Dict {strategy: weight} – normalisiert auf Durchschnitt 1.0.
        """
        raw_scores: dict[str, float] = {}

        for strategy in self._strategies:
            records = history.get(strategy, [])
            if len(records) < self._min_samples:
                raw_scores[strategy] = 1.0
                continue

            # Exponential Decay: neuere Trades zählen stärker
            n = len(records)
            weights = np.array([self._decay ** (n - 1 - i) for i in range(n)])
            outcomes = np.array([1.0 if won else 0.0 for won, _ in records])

            weight_sum = np.sum(weights)
            weighted_wr = float(np.sum(weights * outcomes) / weight_sum) if weight_sum > 0 else 0.5

            # Score: Win-Rate von 0.5 (Baseline) abweichen
            # 60% WR → 1.25x, 40% WR → 0.75x, 70% WR → 1.5x
            score = 0.5 + (weighted_wr - 0.5) * 2.5
            score = max(self._min_w, min(score, self._max_w))
            raw_scores[strategy] = score

        # Normalisierung: Durchschnitt soll 1.0 bleiben
        values = list(raw_scores.values())
        avg = sum(values) / len(values) if values else 1.0
        if avg > 0:
            normalized = {s: round(v / avg, 3) for s, v in raw_scores.items()}
        else:
            normalized = {s: 1.0 for s in self._strategies}

        # Nochmal clampen nach Normalisierung
        return {s: round(max(self._min_w, min(w, self._max_w)), 3) for s, w in normalized.items()}

    def strategy_performance(self) -> list[dict[str, Any]]:
        """Gibt die Performance-Übersicht aller Strategien zurück.

        Returns:
            Sortierte Liste mit Strategie-Performance (WR, Trades, Gewicht).
        """
        result = []
        with self._lock:
            weights = dict(self._cached_global)
            for strategy in self._strategies:
                records = self._global_history.get(strategy, [])
                total = len(records)
                wins = sum(1 for won, _ in records if won)
                wr = (wins / total * 100) if total > 0 else 0
                result.append(
                    {
                        "strategy": strategy,
                        "weight": weights.get(strategy, 1.0),
                        "trades": total,
                        "wins": wins,
                        "losses": total - wins,
                        "win_rate": round(wr, 1),
                        "adapted": total >= self._min_samples,
                    }
                )
        result.sort(key=lambda x: x["weight"], reverse=True)
        return result

    def regime_performance(self) -> dict[str, list[dict[str, Any]]]:
        """Gibt die Regime-spezifische Performance zurück.

        Returns:
            Dict {regime: [strategy_performances]}.
        """
        result: dict[str, list[dict[str, Any]]] = {}
        with self._lock:
            for regime, strat_history in self._regime_history.items():
                regime_weights = self._cached_regime.get(regime, {})
                regime_list = []
                for strategy in self._strategies:
                    records = strat_history.get(strategy, [])
                    total = len(records)
                    wins = sum(1 for won, _ in records if won)
                    wr = (wins / total * 100) if total > 0 else 0
                    regime_list.append(
                        {
                            "strategy": strategy,
                            "weight": regime_weights.get(strategy, 1.0),
                            "trades": total,
                            "win_rate": round(wr, 1),
                        }
                    )
                regime_list.sort(key=lambda x: x["weight"], reverse=True)
                result[regime] = regime_list
        return result

    def load_from_trades(self, closed_trades: list[dict[str, Any]]) -> int:
        """Lädt historische Trades für die Gewichts-Kalibrierung.

        Args:
            closed_trades: Liste abgeschlossener Trades.

        Returns:
            Anzahl geladener Trades.
        """
        count = 0
        for trade in closed_trades:
            reason = trade.get("reason", "")
            regime = trade.get("regime", "unknown")
            won = trade.get("pnl", 0) > 0

            # Versuche die dominierende Strategie aus dem Reason zu extrahieren
            strategy = self._extract_strategy(reason)
            if strategy:
                self.record_vote(strategy, won=won, regime=regime)
                count += 1
        log.info(f"Adaptive Weights: {count} historische Votes geladen")
        return count

    def _extract_strategy(self, reason: str) -> str | None:
        """Extrahiert den Strategienamen aus dem Trade-Reason.

        Args:
            reason: Trade-Grund-String (z.B. 'EMA-Trend+MACD-Kreuzung').

        Returns:
            Erster passender Strategiename oder None.
        """
        for s in self._strategies:
            if s in reason:
                return s
        return None

    def stats(self) -> dict[str, Any]:
        """Kurzstatistiken für Dashboard."""
        with self._lock:
            total = sum(len(h) for h in self._global_history.values())
            n_adapted = sum(1 for h in self._global_history.values() if len(h) >= self._min_samples)
            regimes = list(self._regime_history.keys())

        return {
            "total_votes": total,
            "strategies_adapted": n_adapted,
            "strategies_total": len(self._strategies),
            "regimes_tracked": regimes,
            "window_size": self._window,
            "decay_factor": self._decay,
        }

    def to_dict(self) -> dict[str, Any]:
        """Serialisierung für Dashboard/API."""
        return {
            "enabled": True,
            "weights": self.get_weights(),
            "performance": self.strategy_performance(),
            **self.stats(),
        }
