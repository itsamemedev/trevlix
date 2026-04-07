"""TREVLIX – Selbstlernende Kauf-/Verkaufsalgorithmen.

Stellt autonome Trading-Algorithmen bereit, die aus vergangenen Trades lernen
und eigenständige Kauf-/Verkaufsentscheidungen treffen.

Komponenten:
    BuyAlgorithm  – Erkennt optimale Einstiegspunkte anhand gelernter Muster
    SellAlgorithm – Optimiert Ausstiegszeitpunkte basierend auf Trade-Historie
    TradingAlgorithmManager – Orchestriert beide Algorithmen

Verwendung:
    from services.trading_algorithms import TradingAlgorithmManager
"""

import logging
import threading
from collections import deque
from datetime import datetime
from typing import Any

log = logging.getLogger("trevlix.trading_algorithms")


def _safe(val: object, default: float) -> float:
    """Return *val* as float, or *default* if None/NaN/invalid."""
    if val is None:
        return default
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


# ═══════════════════════════════════════════════════════════════════════════════
# KAUF-ALGORITHMUS (Selbstlernend)
# ═══════════════════════════════════════════════════════════════════════════════
class BuyAlgorithm:
    """Selbstlernender Kaufalgorithmus.

    Lernt aus vergangenen Trades, welche Marktbedingungen zu profitablen
    Einstiegen führen. Kombiniert drei Sub-Strategien:

    1. Momentum-Entry:  Erkennt Aufwärtsdynamik über Multi-Indikator-Bestätigung
    2. Mean-Reversion:  Findet überverkaufte Einstiege mit Erholungspotential
    3. Trend-Breakout:  Identifiziert Ausbrüche aus Konsolidierungsphasen

    Jede Sub-Strategie hat ein eigenes Gewicht, das anhand der historischen
    Performance dynamisch angepasst wird.
    """

    MIN_HISTORY = 5  # Mindestanzahl Trades bevor Gewichte adaptiert werden

    def __init__(self) -> None:
        self._lock = threading.Lock()
        # Sub-Strategie-Gewichte (starten gleichverteilt)
        self.weights: dict[str, float] = {
            "momentum": 1.0,
            "mean_reversion": 1.0,
            "trend_breakout": 1.0,
        }
        # Performance-Tracking pro Sub-Strategie
        self._wins: dict[str, int] = {k: 0 for k in self.weights}
        self._total: dict[str, int] = {k: 0 for k in self.weights}
        # PnL-Tracking pro Sub-Strategie (für Profit-Maximierung)
        self._pnl_sum: dict[str, float] = {k: 0.0 for k in self.weights}
        self._pnl_history: dict[str, list[float]] = {k: [] for k in self.weights}
        # Gelernte Schwellenwerte (werden durch Feedback optimiert)
        self.params: dict[str, float] = {
            "momentum_rsi_min": 45.0,
            "momentum_rsi_max": 70.0,
            "momentum_vol_min": 1.2,
            "momentum_ema_align_min": 0.4,
            "mr_rsi_max": 32.0,
            "mr_bb_pct_max": 0.15,
            "mr_stoch_max": 25.0,
            "breakout_vol_min": 1.8,
            "breakout_roc_min": 2.0,
            "breakout_bb_width_min": 0.02,
        }
        # Optimierungs-History: speichert Parameter-Snapshots + Ergebnis
        self._param_history: list[dict[str, Any]] = []
        self._trade_log: deque[dict[str, Any]] = deque(maxlen=500)
        self.total_signals = 0
        self.profitable_signals = 0
        self.total_pnl = 0.0
        self.avg_pnl = 0.0

    # ── Sub-Strategien ────────────────────────────────────────────────────────

    def _momentum_score(self, scan: dict[str, Any]) -> float:
        """Momentum-Entry: Aufwärtsdynamik über mehrere Indikatoren."""
        rsi = _safe(scan.get("rsi"), 50.0)
        vol_r = _safe(scan.get("vol_ratio"), 1.0)
        ema_align = _safe(scan.get("ema_alignment"), 0.0)
        macd_slope = _safe(scan.get("macd_hist_slope"), 0.0)
        roc10 = _safe(scan.get("roc10"), 0.0)

        score = 0.0
        p = self.params

        # RSI im Bullish-Bereich (nicht überkauft)
        if p["momentum_rsi_min"] <= rsi <= p["momentum_rsi_max"]:
            score += 0.3

        # Volumen über Durchschnitt
        if vol_r >= p["momentum_vol_min"]:
            score += min(0.25, (vol_r - p["momentum_vol_min"]) * 0.15)

        # EMA-Alignment bullisch
        if ema_align >= p["momentum_ema_align_min"]:
            score += 0.25

        # MACD-Histogram steigt
        if macd_slope > 0:
            score += min(0.1, macd_slope * 50)

        # Positiver Rate-of-Change
        if roc10 > 1.0:
            score += min(0.1, roc10 * 0.02)

        return min(1.0, score)

    def _mean_reversion_score(self, scan: dict[str, Any]) -> float:
        """Mean-Reversion: Überverkaufte Bedingungen mit Erholungspotential."""
        rsi = _safe(scan.get("rsi"), 50.0)
        bb_pct = _safe(scan.get("bb_pct"), 0.5)
        stoch_rsi = _safe(scan.get("stoch_rsi"), 50.0)
        price_vs_ema = _safe(scan.get("price_vs_ema21"), 0.0)
        macd_slope = _safe(scan.get("macd_hist_slope"), 0.0)

        score = 0.0
        p = self.params

        # RSI überverkauft
        if rsi <= p["mr_rsi_max"]:
            score += 0.35

        # Preis nahe unterer Bollinger-Band
        if bb_pct <= p["mr_bb_pct_max"]:
            score += 0.25

        # Stochastic RSI überverkauft
        if stoch_rsi <= p["mr_stoch_max"]:
            score += 0.2

        # Preis unter EMA21 (Erholung wahrscheinlich)
        if price_vs_ema < -0.01:
            score += min(0.1, abs(price_vs_ema) * 5)

        # MACD dreht nach oben (Erholungszeichen)
        if macd_slope > 0 and rsi < 40:
            score += 0.1

        return min(1.0, score)

    def _trend_breakout_score(self, scan: dict[str, Any]) -> float:
        """Trend-Breakout: Ausbruch aus enger Konsolidierung."""
        vol_r = _safe(scan.get("vol_ratio"), 1.0)
        roc10 = _safe(scan.get("roc10"), 0.0)
        bb_width = _safe(scan.get("bb_width"), 0.05)
        ema_align = _safe(scan.get("ema_alignment"), 0.0)
        atr_pct = _safe(scan.get("atr_pct"), 1.0)

        score = 0.0
        p = self.params

        # Volumen-Spike (Ausbruchsbestätigung)
        if vol_r >= p["breakout_vol_min"]:
            score += 0.3

        # Starker ROC (Preisausbruch)
        if roc10 >= p["breakout_roc_min"]:
            score += min(0.25, roc10 * 0.05)

        # Enge Bollinger-Bänder → Squeeze → Breakout-Potential
        if bb_width <= p["breakout_bb_width_min"]:
            score += 0.2

        # EMA-Alignment bullisch
        if ema_align > 0:
            score += 0.15

        # Erhöhte Volatilität (ATR steigt)
        if atr_pct > 1.5:
            score += min(0.1, atr_pct * 0.03)

        return min(1.0, score)

    # ── Hauptentscheidung ─────────────────────────────────────────────────────

    def evaluate(self, scan: dict[str, Any]) -> tuple[bool, float, str]:
        """Bewertet ob ein Kauf getätigt werden soll.

        Args:
            scan: Scan-Ergebnis aus scan_symbol() mit allen Indikatoren.

        Returns:
            Tuple (should_buy, confidence, reason).
        """
        with self._lock:
            w = dict(self.weights)

        m_score = self._momentum_score(scan)
        mr_score = self._mean_reversion_score(scan)
        tb_score = self._trend_breakout_score(scan)

        total_w = w["momentum"] + w["mean_reversion"] + w["trend_breakout"]
        if total_w <= 0:
            return False, 0.0, "Keine Gewichte"

        weighted = (
            m_score * w["momentum"]
            + mr_score * w["mean_reversion"]
            + tb_score * w["trend_breakout"]
        ) / total_w

        # Bestimme dominante Sub-Strategie für Logging
        scores = {"momentum": m_score, "mean_reversion": mr_score, "trend_breakout": tb_score}
        dominant = max(scores, key=scores.get)  # type: ignore[arg-type]
        dominant_labels = {
            "momentum": "Momentum",
            "mean_reversion": "Mean-Reversion",
            "trend_breakout": "Breakout",
        }

        # Schwellenwert: 0.35 = moderate Bestätigung erforderlich
        threshold = 0.35
        should_buy = weighted >= threshold

        reason = (
            f"BuyAlgo:{dominant_labels[dominant]} "
            f"({m_score:.0%}|{mr_score:.0%}|{tb_score:.0%}) → {weighted:.0%}"
        )

        return should_buy, round(weighted, 3), reason

    # ── Selbstlernen ──────────────────────────────────────────────────────────

    def record_result(
        self,
        scan: dict[str, Any],
        pnl: float,
        dominant_strategy: str = "",
    ) -> None:
        """Zeichnet Trade-Ergebnis auf und passt Gewichte an.

        Args:
            scan: Scan-Daten zum Zeitpunkt des Kaufs.
            pnl: Profit/Loss des abgeschlossenen Trades.
            dominant_strategy: Welche Sub-Strategie den Kauf ausgelöst hat.
        """
        won = pnl > 0
        with self._lock:
            self.total_signals += 1
            self.total_pnl += pnl
            self.avg_pnl = self.total_pnl / self.total_signals
            if won:
                self.profitable_signals += 1

            # Bestimme welche Sub-Strategien aktiv waren
            m_score = self._momentum_score(scan)
            mr_score = self._mean_reversion_score(scan)
            tb_score = self._trend_breakout_score(scan)

            active_strats = []
            if m_score >= 0.3:
                active_strats.append("momentum")
            if mr_score >= 0.3:
                active_strats.append("mean_reversion")
            if tb_score >= 0.3:
                active_strats.append("trend_breakout")

            if not active_strats:
                active_strats = ["momentum"]  # Fallback

            for strat in active_strats:
                self._total[strat] = self._total.get(strat, 0) + 1
                if won:
                    self._wins[strat] = self._wins.get(strat, 0) + 1
                # PnL-Tracking für Profit-Maximierung
                self._pnl_sum[strat] = self._pnl_sum.get(strat, 0.0) + pnl
                hist = self._pnl_history.get(strat, [])
                hist.append(pnl)
                if len(hist) > 100:
                    hist = hist[-100:]
                self._pnl_history[strat] = hist

            # Gewichte adaptieren (nach MIN_HISTORY Trades)
            total_trades = sum(self._total.values())
            if total_trades >= self.MIN_HISTORY:
                self._adapt_weights()

            # Parameter-Optimierung (alle 20 Trades)
            if total_trades > 0 and total_trades % 20 == 0:
                self._optimize_params(scan, pnl)

            self._trade_log.append(
                {
                    "time": datetime.now().strftime("%H:%M:%S"),
                    "won": won,
                    "pnl": round(pnl, 2),
                    "active": active_strats,
                    "scores": {
                        "m": round(m_score, 2),
                        "mr": round(mr_score, 2),
                        "tb": round(tb_score, 2),
                    },
                }
            )

    def _adapt_weights(self) -> None:
        """Passt Sub-Strategie-Gewichte PnL-gewichtet an.

        Kombiniert Win-Rate (40%) und durchschnittlichen Profit (60%)
        zu einem Gesamtscore. So werden Strategien bevorzugt, die nicht
        nur häufig gewinnen, sondern auch höheren Profit erzeugen.
        """
        avg_pnls = {}
        for strat in self.weights:
            total = self._total.get(strat, 0)
            if total < 3:
                continue
            wr = self._wins.get(strat, 0) / total
            # Durchschnittlicher PnL pro Trade für diese Strategie
            avg_pnl = self._pnl_sum.get(strat, 0.0) / total
            avg_pnls[strat] = avg_pnl
            # Normalisierter PnL-Score: sigmoid-artig auf [0, 1] abbilden
            # Positive PnL → Score > 0.5, negative → Score < 0.5
            pnl_score = 1.0 / (1.0 + 2.718 ** (-avg_pnl * 0.1))
            # Kombiniertes Gewicht: 40% Win-Rate + 60% PnL-Score
            combined = wr * 0.4 + pnl_score * 0.6
            self.weights[strat] = max(0.3, min(2.5, 0.3 + combined * 2.0))
        # Log-Ausgabe bei signifikanter Änderung
        if avg_pnls:
            best = max(avg_pnls, key=avg_pnls.get)  # type: ignore[arg-type]
            log.debug(
                f"[BUY-ALGO] Gewichte angepasst: beste Strategie={best} "
                f"(avg PnL={avg_pnls[best]:+.2f})"
            )

    def _optimize_params(self, scan: dict[str, Any], pnl: float) -> None:
        """Optimiert Schwellenwerte basierend auf PnL der letzten Trades.

        Verwendet zwei Signale:
        1. Win-Rate: Zu viele Verluste → strengere Einstiegsbedingungen
        2. Avg PnL: Negativer Durchschnitts-PnL → aggressivere Anpassung
        """
        recent = list(self._trade_log)[-20:]
        if len(recent) < 10:
            return

        wins = [t for t in recent if t["won"]]
        win_rate = len(wins) / len(recent) if recent else 0.5
        avg_recent_pnl = sum(t.get("pnl", 0) for t in recent) / len(recent)

        # Doppeltes Signal: Win-Rate + PnL-Richtung
        # Negativer PnL verstärkt die Anpassung
        if win_rate < 0.45 or avg_recent_pnl < -5:
            # Schlecht: Schwellen verschärfen
            pnl_factor = max(1.0, min(3.0, abs(avg_recent_pnl) / 20))
            adjustment = 0.02 * pnl_factor
        elif win_rate > 0.6 and avg_recent_pnl > 10:
            # Gut: Schwellen leicht lockern (mehr Trades zulassen)
            adjustment = -0.01
        else:
            adjustment = 0.0

        if abs(adjustment) > 0:
            self.params["momentum_rsi_min"] = max(
                35.0, min(55.0, self.params["momentum_rsi_min"] + adjustment * 100)
            )
            self.params["mr_rsi_max"] = max(
                25.0, min(40.0, self.params["mr_rsi_max"] - adjustment * 50)
            )
            self.params["breakout_vol_min"] = max(
                1.3, min(2.5, self.params["breakout_vol_min"] + adjustment * 5)
            )
            log.info(
                f"[BUY-ALGO] Parameter optimiert: WR={win_rate:.0%} "
                f"avgPnL={avg_recent_pnl:+.2f} adj={adjustment:+.3f}"
            )

        self._param_history.append(
            {
                "time": datetime.now().isoformat(),
                "win_rate": round(win_rate, 3),
                "avg_pnl": round(avg_recent_pnl, 2),
                "params": dict(self.params),
            }
        )
        # Limit history
        if len(self._param_history) > 50:
            self._param_history = self._param_history[-50:]

    def win_rate(self) -> float:
        """Aktuelle Gesamt-Win-Rate des Kaufalgorithmus."""
        if self.total_signals == 0:
            return 0.0
        return self.profitable_signals / self.total_signals

    def to_dict(self) -> dict[str, Any]:
        """Status-Dictionary für Dashboard."""
        with self._lock:
            sub_strats = []
            for name in self.weights:
                total = self._total.get(name, 0)
                wins = self._wins.get(name, 0)
                wr = wins / total if total > 0 else 0.0
                avg_pnl = self._pnl_sum.get(name, 0.0) / total if total > 0 else 0.0
                sub_strats.append(
                    {
                        "name": name,
                        "weight": round(self.weights[name], 2),
                        "win_rate": round(wr * 100, 1),
                        "avg_pnl": round(avg_pnl, 2),
                        "trades": total,
                    }
                )

            return {
                "enabled": True,
                "total_signals": self.total_signals,
                "profitable_signals": self.profitable_signals,
                "win_rate": round(self.win_rate() * 100, 1),
                "total_pnl": round(self.total_pnl, 2),
                "avg_pnl": round(self.avg_pnl, 2),
                "sub_strategies": sub_strats,
                "params": {k: round(v, 3) for k, v in self.params.items()},
                "recent_log": list(self._trade_log)[-10:],
            }


# ═══════════════════════════════════════════════════════════════════════════════
# VERKAUF-ALGORITHMUS (Selbstlernend)
# ═══════════════════════════════════════════════════════════════════════════════
class SellAlgorithm:
    """Selbstlernender Verkaufsalgorithmus.

    Lernt aus vergangenen Trades, wann der optimale Ausstiegszeitpunkt ist.
    Kombiniert mehrere Exit-Strategien:

    1. Momentum-Reversal:  Erkennt Trendumkehr über Indikator-Divergenz
    2. Profit-Protection:  Dynamische Gewinnabsicherung basierend auf Volatilität
    3. Time-Decay:         Haltedauer-Analyse (zu lange offene Positionen)
    4. Pattern-Exit:       Gelernte Muster die auf Kursrückgang hindeuten
    """

    MIN_HISTORY = 5

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.weights: dict[str, float] = {
            "momentum_reversal": 1.0,
            "profit_protection": 1.0,
            "time_decay": 1.0,
            "pattern_exit": 1.0,
        }
        self._wins: dict[str, int] = {k: 0 for k in self.weights}
        self._total: dict[str, int] = {k: 0 for k in self.weights}
        self._pnl_sum: dict[str, float] = {k: 0.0 for k in self.weights}
        self._pnl_history: dict[str, list[float]] = {k: [] for k in self.weights}
        self.params: dict[str, float] = {
            "reversal_rsi_max": 72.0,
            "reversal_stoch_max": 80.0,
            "reversal_macd_slope_min": -0.001,
            "profit_trail_pct": 0.025,
            "profit_min_gain_pct": 0.015,
            "time_max_hours": 72.0,
            "time_decay_factor": 0.1,
            "pattern_bb_pct_max": 0.92,
            "pattern_vol_drop_min": 0.6,
            "pattern_ema_cross_weight": 0.3,
        }
        self._param_history: list[dict[str, Any]] = []
        self._trade_log: deque[dict[str, Any]] = deque(maxlen=500)
        # Tracking: Optimale Exit-Zeitpunkte aus vergangenen Trades
        self._optimal_exits: deque[dict[str, Any]] = deque(maxlen=200)
        self.total_signals = 0
        self.improved_exits = 0  # Exits die besser waren als SL/TP allein
        self.total_pnl = 0.0
        self.saved_pnl = 0.0  # Geschätzter PnL-Vorteil durch Algo-Exits

    # ── Sub-Strategien ────────────────────────────────────────────────────────

    def _momentum_reversal_score(self, scan: dict[str, Any], pos: dict[str, Any]) -> float:
        """Erkennt Momentum-Umkehr: Indikatoren drehen ins Negative."""
        rsi = _safe(scan.get("rsi"), 50.0)
        stoch_rsi = _safe(scan.get("stoch_rsi"), 50.0)
        macd_slope = _safe(scan.get("macd_hist_slope"), 0.0)
        ema_align = _safe(scan.get("ema_alignment"), 0.0)

        score = 0.0
        p = self.params

        # RSI überkauft
        if rsi >= p["reversal_rsi_max"]:
            score += 0.3

        # Stochastic RSI überkauft
        if stoch_rsi >= p["reversal_stoch_max"]:
            score += 0.25

        # MACD-Histogram fällt
        if macd_slope < p["reversal_macd_slope_min"]:
            score += 0.25

        # EMA-Alignment dreht bärisch
        if ema_align < 0:
            score += 0.2

        return min(1.0, score)

    def _profit_protection_score(self, scan: dict[str, Any], pos: dict[str, Any]) -> float:
        """Dynamische Gewinnabsicherung basierend auf unrealisiertem Gewinn."""
        entry = _safe(pos.get("entry"), 0)
        price = _safe(scan.get("price"), entry)
        highest = _safe(pos.get("highest"), price)
        atr_pct = _safe(scan.get("atr_pct"), 1.0)

        if entry <= 0 or price <= 0:
            return 0.0

        gain_pct = (price - entry) / entry
        drop_from_high = (highest - price) / highest if highest > 0 else 0.0

        score = 0.0
        p = self.params

        # Gewinn vorhanden und Preis fällt vom Hoch
        if gain_pct >= p["profit_min_gain_pct"]:
            # Dynamischer Trail basierend auf ATR
            trail_pct = p["profit_trail_pct"] * max(0.5, min(2.0, atr_pct))
            if drop_from_high >= trail_pct:
                score += 0.5

            # Je höher der Gewinn, desto aggressiver absichern
            if gain_pct > 0.04 and drop_from_high > trail_pct * 0.7:
                score += 0.3

        # Starker Rückgang vom Hoch (unabhängig vom Gesamtgewinn)
        if drop_from_high > 0.05:
            score += 0.2

        return min(1.0, score)

    def _time_decay_score(self, scan: dict[str, Any], pos: dict[str, Any]) -> float:
        """Zeitbasierte Exit-Bewertung: zu lange offene Positionen."""
        opened = pos.get("opened", "")
        if not opened:
            return 0.0

        try:
            open_dt = datetime.fromisoformat(opened)
            hours_open = (datetime.now() - open_dt).total_seconds() / 3600
        except (ValueError, TypeError):
            return 0.0

        p = self.params
        score = 0.0

        # Haltedauer überschritten
        if hours_open >= p["time_max_hours"]:
            score += 0.4

        # Zunehmender Druck nach halber Maximalzeit
        if hours_open >= p["time_max_hours"] * 0.5:
            time_ratio = hours_open / p["time_max_hours"]
            score += min(0.3, time_ratio * p["time_decay_factor"])

        # Lange Haltedauer + kein signifikanter Gewinn = schlechtes Zeichen
        entry = _safe(pos.get("entry"), 0)
        price = _safe(scan.get("price"), entry)
        if entry > 0 and price > 0:
            gain_pct = (price - entry) / entry
            if hours_open > 24 and gain_pct < 0.005:
                score += 0.3

        return min(1.0, score)

    def _pattern_exit_score(self, scan: dict[str, Any], pos: dict[str, Any]) -> float:
        """Musterbasierter Exit: Gelernte Muster die auf Rückgang hindeuten."""
        bb_pct = _safe(scan.get("bb_pct"), 0.5)
        vol_r = _safe(scan.get("vol_ratio"), 1.0)
        roc10 = _safe(scan.get("roc10"), 0.0)
        ema_align = _safe(scan.get("ema_alignment"), 0.0)

        score = 0.0
        p = self.params

        # Preis nahe oberer Bollinger-Band (potentielle Umkehr)
        if bb_pct >= p["pattern_bb_pct_max"]:
            score += 0.25

        # Volumen sinkt (Trend verliert Kraft)
        if vol_r <= p["pattern_vol_drop_min"]:
            score += 0.2

        # Negativer Rate-of-Change (Momentum erschöpft)
        if roc10 < -1.0:
            score += min(0.25, abs(roc10) * 0.05)

        # EMA-Crossover bärisch
        if ema_align < 0:
            score += p["pattern_ema_cross_weight"]

        return min(1.0, score)

    # ── Hauptentscheidung ─────────────────────────────────────────────────────

    def evaluate(
        self,
        scan: dict[str, Any],
        pos: dict[str, Any],
    ) -> tuple[bool, float, str]:
        """Bewertet ob eine Position geschlossen werden soll.

        Args:
            scan: Aktuelle Marktdaten aus scan_symbol().
            pos: Positionsdaten (entry, highest, opened, etc.).

        Returns:
            Tuple (should_sell, confidence, reason).
        """
        with self._lock:
            w = dict(self.weights)

        mr_score = self._momentum_reversal_score(scan, pos)
        pp_score = self._profit_protection_score(scan, pos)
        td_score = self._time_decay_score(scan, pos)
        pe_score = self._pattern_exit_score(scan, pos)

        total_w = sum(w.values())
        if total_w <= 0:
            return False, 0.0, "Keine Gewichte"

        weighted = (
            mr_score * w["momentum_reversal"]
            + pp_score * w["profit_protection"]
            + td_score * w["time_decay"]
            + pe_score * w["pattern_exit"]
        ) / total_w

        # Bestimme dominante Sub-Strategie
        scores = {
            "momentum_reversal": mr_score,
            "profit_protection": pp_score,
            "time_decay": td_score,
            "pattern_exit": pe_score,
        }
        dominant = max(scores, key=scores.get)  # type: ignore[arg-type]
        dominant_labels = {
            "momentum_reversal": "Reversal",
            "profit_protection": "ProfitGuard",
            "time_decay": "TimeDecay",
            "pattern_exit": "Pattern",
        }

        # Schwellenwert: 0.40 = moderate Bestätigung
        threshold = 0.40
        should_sell = weighted >= threshold

        reason = (
            f"SellAlgo:{dominant_labels[dominant]} "
            f"({mr_score:.0%}|{pp_score:.0%}|{td_score:.0%}|{pe_score:.0%})"
        )

        return should_sell, round(weighted, 3), reason

    # ── Selbstlernen ──────────────────────────────────────────────────────────

    def record_result(
        self,
        scan: dict[str, Any],
        pos: dict[str, Any],
        pnl: float,
        exit_reason: str,
    ) -> None:
        """Zeichnet Exit-Ergebnis auf und optimiert Gewichte/Parameter.

        Args:
            scan: Marktdaten zum Zeitpunkt des Verkaufs.
            pos: Positionsdaten.
            pnl: Profit/Loss.
            exit_reason: Grund des Verkaufs (SL, TP, SellAlgo, etc.).
        """
        was_algo_exit = "SellAlgo" in exit_reason
        won = pnl > 0

        with self._lock:
            self.total_signals += 1
            self.total_pnl += pnl
            if was_algo_exit and won:
                self.improved_exits += 1
            # Schätze PnL-Vorteil: Algo-Exits vs SL/TP-Exits
            if was_algo_exit and won:
                self.saved_pnl += max(0, pnl * 0.3)  # ~30% konservative Schätzung

            # Bestimme welche Sub-Strategien aktiv waren
            mr_score = self._momentum_reversal_score(scan, pos)
            pp_score = self._profit_protection_score(scan, pos)
            td_score = self._time_decay_score(scan, pos)
            pe_score = self._pattern_exit_score(scan, pos)

            active_strats = []
            if mr_score >= 0.3:
                active_strats.append("momentum_reversal")
            if pp_score >= 0.3:
                active_strats.append("profit_protection")
            if td_score >= 0.3:
                active_strats.append("time_decay")
            if pe_score >= 0.3:
                active_strats.append("pattern_exit")

            if not active_strats:
                active_strats = ["pattern_exit"]

            for strat in active_strats:
                self._total[strat] = self._total.get(strat, 0) + 1
                if won:
                    self._wins[strat] = self._wins.get(strat, 0) + 1
                self._pnl_sum[strat] = self._pnl_sum.get(strat, 0.0) + pnl
                hist = self._pnl_history.get(strat, [])
                hist.append(pnl)
                if len(hist) > 100:
                    hist = hist[-100:]
                self._pnl_history[strat] = hist

            total_trades = sum(self._total.values())
            if total_trades >= self.MIN_HISTORY:
                self._adapt_weights()

            if total_trades > 0 and total_trades % 20 == 0:
                self._optimize_params()

            self._trade_log.append(
                {
                    "time": datetime.now().strftime("%H:%M:%S"),
                    "won": won,
                    "pnl": round(pnl, 2),
                    "algo_exit": was_algo_exit,
                    "reason": exit_reason[:50],
                    "active": active_strats,
                }
            )

    def _adapt_weights(self) -> None:
        """Passt Sub-Strategie-Gewichte PnL-gewichtet an (Profit-Maximierung)."""
        for strat in self.weights:
            total = self._total.get(strat, 0)
            if total < 3:
                continue
            wr = self._wins.get(strat, 0) / total
            avg_pnl = self._pnl_sum.get(strat, 0.0) / total
            pnl_score = 1.0 / (1.0 + 2.718 ** (-avg_pnl * 0.1))
            combined = wr * 0.4 + pnl_score * 0.6
            self.weights[strat] = max(0.3, min(2.5, 0.3 + combined * 2.0))

    def _optimize_params(self) -> None:
        """Optimiert Schwellenwerte basierend auf PnL der letzten Algo-Exits."""
        recent = list(self._trade_log)[-20:]
        if len(recent) < 10:
            return

        algo_exits = [t for t in recent if t.get("algo_exit")]
        if not algo_exits:
            return

        win_rate = sum(1 for t in algo_exits if t["won"]) / len(algo_exits)
        avg_pnl = sum(t.get("pnl", 0) for t in algo_exits) / len(algo_exits)

        # PnL-basierte Anpassung: schlechter PnL → konservativere Exits
        if win_rate < 0.45 or avg_pnl < -5:
            pnl_factor = max(1.0, min(3.0, abs(avg_pnl) / 20))
            adjustment = 0.02 * pnl_factor
        elif win_rate > 0.6 and avg_pnl > 5:
            adjustment = -0.01
        else:
            adjustment = 0.0

        if abs(adjustment) > 0:
            self.params["reversal_rsi_max"] = max(
                65.0, min(80.0, self.params["reversal_rsi_max"] + adjustment * 100)
            )
            self.params["time_max_hours"] = max(
                24.0, min(120.0, self.params["time_max_hours"] + adjustment * 500)
            )
            self.params["profit_trail_pct"] = max(
                0.01, min(0.05, self.params["profit_trail_pct"] + adjustment)
            )
            log.info(
                f"[SELL-ALGO] Parameter optimiert: WR={win_rate:.0%} "
                f"avgPnL={avg_pnl:+.2f} adj={adjustment:+.3f}"
            )

        self._param_history.append(
            {
                "time": datetime.now().isoformat(),
                "win_rate": round(win_rate, 3),
                "avg_pnl": round(avg_pnl, 2),
                "params": dict(self.params),
            }
        )
        if len(self._param_history) > 50:
            self._param_history = self._param_history[-50:]

    def to_dict(self) -> dict[str, Any]:
        """Status-Dictionary für Dashboard."""
        with self._lock:
            sub_strats = []
            for name in self.weights:
                total = self._total.get(name, 0)
                wins = self._wins.get(name, 0)
                wr = wins / total if total > 0 else 0.0
                avg_pnl = self._pnl_sum.get(name, 0.0) / total if total > 0 else 0.0
                sub_strats.append(
                    {
                        "name": name,
                        "weight": round(self.weights[name], 2),
                        "win_rate": round(wr * 100, 1),
                        "avg_pnl": round(avg_pnl, 2),
                        "trades": total,
                    }
                )

            return {
                "enabled": True,
                "total_signals": self.total_signals,
                "improved_exits": self.improved_exits,
                "total_pnl": round(self.total_pnl, 2),
                "saved_pnl": round(self.saved_pnl, 2),
                "sub_strategies": sub_strats,
                "params": {k: round(v, 3) for k, v in self.params.items()},
                "recent_log": list(self._trade_log)[-10:],
            }


# ═══════════════════════════════════════════════════════════════════════════════
# TRADING ALGORITHM MANAGER
# ═══════════════════════════════════════════════════════════════════════════════
class TradingAlgorithmManager:
    """Orchestriert Kauf- und Verkaufsalgorithmen.

    Stellt eine zentrale Schnittstelle für den Bot-Loop bereit und
    verwaltet den Gesamtstatus der Algorithmen.
    """

    def __init__(self) -> None:
        self.buy_algo = BuyAlgorithm()
        self.sell_algo = SellAlgorithm()
        self._active = True
        log.info("🧠 Trading-Algorithmen initialisiert (Kauf + Verkauf)")

    @property
    def is_configured(self) -> bool:
        """True wenn beide Algorithmen einsatzbereit sind."""
        return self._active

    def evaluate_buy(self, scan: dict[str, Any]) -> tuple[bool, float, str]:
        """Prüft ob ein Kauf getätigt werden soll.

        Args:
            scan: Scan-Ergebnis mit allen Marktindikatoren.

        Returns:
            (should_buy, confidence, reason)
        """
        if not self._active:
            return False, 0.0, "Algorithmen deaktiviert"
        return self.buy_algo.evaluate(scan)

    def evaluate_sell(
        self,
        scan: dict[str, Any],
        pos: dict[str, Any],
    ) -> tuple[bool, float, str]:
        """Prüft ob eine Position geschlossen werden soll.

        Args:
            scan: Aktuelle Marktdaten.
            pos: Positionsdaten.

        Returns:
            (should_sell, confidence, reason)
        """
        if not self._active:
            return False, 0.0, "Algorithmen deaktiviert"
        return self.sell_algo.evaluate(scan, pos)

    def record_buy_result(
        self,
        scan: dict[str, Any],
        pnl: float,
    ) -> None:
        """Meldet das Ergebnis eines Kaufs zurück für Selbstlernen."""
        self.buy_algo.record_result(scan, pnl)

    def record_sell_result(
        self,
        scan: dict[str, Any],
        pos: dict[str, Any],
        pnl: float,
        exit_reason: str,
    ) -> None:
        """Meldet das Ergebnis eines Verkaufs zurück für Selbstlernen."""
        self.sell_algo.record_result(scan, pos, pnl, exit_reason)

    def to_dict(self) -> dict[str, Any]:
        """Gesamtstatus für Dashboard und API."""
        buy_dict = self.buy_algo.to_dict()
        sell_dict = self.sell_algo.to_dict()

        total_buy = buy_dict.get("total_signals", 0)
        total_sell = sell_dict.get("total_signals", 0)

        return {
            "configured": self.is_configured,
            "active": self._active,
            "buy_algorithm": buy_dict,
            "sell_algorithm": sell_dict,
            "total_trades": total_buy + total_sell,
            "buy_win_rate": buy_dict.get("win_rate", 0),
            "status_msg": self._status_msg(total_buy, total_sell),
        }

    def _status_msg(self, total_buy: int, total_sell: int) -> str:
        """Generiert Statusnachricht für Dashboard."""
        if total_buy == 0 and total_sell == 0:
            return "✅ Konfiguriert – Sammle Daten..."
        buy_wr = self.buy_algo.win_rate() * 100
        return f"✅ Aktiv | {total_buy} Käufe ({buy_wr:.0f}% WR) | {total_sell} Exits"
