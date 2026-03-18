"""TREVLIX – Smart Exit Engine (Volatility-Adaptive SL/TP).

Ersetzt fixe SL/TP-Prozentsätze durch dynamische, volatilitätsbasierte
Stop-Loss- und Take-Profit-Level. Nutzt ATR, Marktregime und Signal-Stärke
für intelligentere Exits.

Kernlogik:
    SL = ATR × Regime-Multiplikator × Risiko-Faktor
    TP = ATR × Reward-Ratio × Signal-Stärke-Faktor

Regime-Anpassungen:
    - Bull: Enge Stops (1.2× ATR), großes TP → Trend reiten
    - Bear: Weite Stops (2.0× ATR), konservatives TP → Noise vermeiden
    - Range: Mittlere Stops (1.5× ATR), ausgewogenes TP
    - Crash: Sehr weite Stops (2.5× ATR) oder kein Trade

Volatility Squeeze Detection:
    Wenn Bollinger-Width unter Threshold fällt, wird ein Ausbruch erwartet.
    → Engere Stops, aber größeres TP-Potential.

Verwendung:
    from services.smart_exits import SmartExitEngine

    smart_exits = SmartExitEngine(config)
    sl, tp = smart_exits.compute(entry_price, scan_data, regime)
    new_sl, new_tp = smart_exits.adapt(position, current_price, scan_data, regime)
"""

import logging
import threading
from typing import Any

log = logging.getLogger("trevlix.smart_exits")

# ── Regime-spezifische Multiplikatoren ───────────────────────────────────────

_REGIME_SL_MULT: dict[str, float] = {
    "bull": 1.2,
    "bear": 2.0,
    "range": 1.5,
    "crash": 2.5,
}

_REGIME_TP_MULT: dict[str, float] = {
    "bull": 3.0,  # Trend reiten → 3:1 Reward-Ratio
    "bear": 1.5,  # Konservativ → 1.5:1
    "range": 2.0,  # Ausgewogen → 2:1
    "crash": 1.0,  # Minimal → 1:1 (fast kein TP)
}


class SmartExitEngine:
    """Volatility-Adaptive Stop-Loss und Take-Profit Engine.

    Berechnet dynamische SL/TP-Level basierend auf ATR, Marktregime und
    Signal-Stärke. Passt bestehende Positionen laufend an.

    Args:
        config: CONFIG-Dict mit Trading-Parametern.
    """

    def __init__(self, config: dict[str, Any]) -> None:
        self._config = config
        self._lock = threading.Lock()
        self._adjustments: dict[str, dict[str, Any]] = {}  # symbol → letztes Exit-Update

    @property
    def enabled(self) -> bool:
        """Ob Smart Exits aktiviert sind."""
        return bool(self._config.get("use_smart_exits", False))

    def compute(
        self,
        entry_price: float,
        scan: dict[str, Any],
        regime: str,
    ) -> tuple[float, float]:
        """Berechnet initiale SL/TP-Level für eine neue Position.

        Args:
            entry_price: Einstiegspreis.
            scan: Scan-Ergebnis-Dict mit Indikatoren (atr14, atr_pct, bb_width, confidence).
            regime: Aktuelles Marktregime ('bull', 'bear', 'range', 'crash').

        Returns:
            Tuple (stop_loss_price, take_profit_price).
        """
        if not entry_price or entry_price <= 0:
            return 0.0, 0.0

        if not self.enabled:
            sl_pct = self._config.get("stop_loss_pct", 0.025)
            tp_pct = self._config.get("take_profit_pct", 0.060)
            return entry_price * (1 - sl_pct), entry_price * (1 + tp_pct)

        atr = scan.get("atr14", 0.0)
        atr_pct = scan.get("atr_pct", 1.0)
        bb_width = scan.get("bb_width", 0.05)
        confidence = scan.get("confidence", 0.5)

        # Fallback: wenn ATR nicht verfügbar, fixe Prozentsätze verwenden
        if atr <= 0 or atr_pct <= 0:
            sl_pct = self._config.get("stop_loss_pct", 0.025)
            tp_pct = self._config.get("take_profit_pct", 0.060)
            return entry_price * (1 - sl_pct), entry_price * (1 + tp_pct)

        # ── SL-Berechnung ────────────────────────────────────────────────
        base_mult = self._config.get("smart_exit_atr_sl_mult", 1.5)
        regime_mult = _REGIME_SL_MULT.get(regime, 1.5)
        sl_distance = atr * base_mult * regime_mult

        # Volatility Squeeze: engere Stops bei sehr niedriger Volatilität
        squeeze_threshold = self._config.get("smart_exit_squeeze_threshold", 0.03)
        if bb_width < squeeze_threshold:
            sl_distance *= 0.8  # 20% engere Stops bei Squeeze
            log.debug(f"Volatility Squeeze: BB-Width {bb_width:.4f} < {squeeze_threshold}")

        # SL begrenzen auf konfigurierbare Min/Max-Grenzen
        min_sl_pct = self._config.get("smart_exit_min_sl_pct", 0.01)  # Min. 1%
        max_sl_pct = self._config.get("smart_exit_max_sl_pct", 0.08)  # Max. 8%
        sl_pct = max(min_sl_pct, min(sl_distance / entry_price, max_sl_pct))
        sl = entry_price * (1 - sl_pct)

        # ── TP-Berechnung ────────────────────────────────────────────────
        base_reward = self._config.get("smart_exit_reward_ratio", 2.0)
        regime_reward = _REGIME_TP_MULT.get(regime, 2.0)

        # Signal-Stärke-Faktor: stärkere Signale → größeres TP
        signal_factor = 0.8 + (confidence * 0.4)  # 0.8-1.2x bei 0%-100% Konfidenz
        tp_distance = atr * base_reward * regime_reward * signal_factor

        # TP begrenzen
        min_tp_pct = self._config.get("smart_exit_min_tp_pct", 0.02)  # Min. 2%
        max_tp_pct = self._config.get("smart_exit_max_tp_pct", 0.15)  # Max. 15%
        tp_pct = max(min_tp_pct, min(tp_distance / entry_price, max_tp_pct))
        tp = entry_price * (1 + tp_pct)

        log.debug(
            f"SmartExit: regime={regime} atr={atr:.4f} "
            f"SL={sl:.4f} ({sl_pct * 100:.2f}%) TP={tp:.4f} ({tp_pct * 100:.2f}%)"
        )

        with self._lock:
            self._adjustments["_last_compute"] = {
                "regime": regime,
                "atr": round(atr, 4),
                "sl_pct": round(sl_pct * 100, 2),
                "tp_pct": round(tp_pct * 100, 2),
                "signal_factor": round(signal_factor, 3),
                "squeeze": bb_width < squeeze_threshold,
            }

        return sl, tp

    def adapt(
        self,
        symbol: str,
        pos: dict[str, Any],
        current_price: float,
        atr: float,
        regime: str,
    ) -> tuple[float | None, float | None]:
        """Passt SL/TP einer bestehenden Position dynamisch an.

        Wird in manage_positions() aufgerufen. Verschiebt SL/TP nur in
        günstige Richtung (SL nur nach oben, TP nur nach oben bei Trend).

        Args:
            symbol: Trading-Pair.
            pos: Positions-Dict aus state.positions.
            current_price: Aktueller Marktpreis.
            atr: Aktuelle ATR des Symbols.
            regime: Aktuelles Marktregime.

        Returns:
            Tuple (new_sl, new_tp) – None wenn keine Anpassung nötig.
        """
        if not self.enabled or atr <= 0:
            return None, None

        entry = pos.get("entry")
        if not entry or entry <= 0:
            return None, None
        current_sl = pos.get("sl", entry * 0.975)
        current_tp = pos.get("tp", entry * 1.06)
        pnl_pct = (current_price - entry) / entry

        new_sl = None
        new_tp = None

        # ── Dynamische SL-Anpassung ─────────────────────────────────────
        # Im Profit: SL enger nachziehen (regime-abhängig)
        if pnl_pct > 0.01:  # Min. 1% im Plus
            regime_mult = _REGIME_SL_MULT.get(regime, 1.5)
            trailing_distance = atr * regime_mult * 0.8  # Enger als Initial
            proposed_sl = current_price - trailing_distance
            if proposed_sl > current_sl:
                new_sl = proposed_sl
                log.debug(f"SmartExit adapt {symbol}: SL {current_sl:.4f} → {proposed_sl:.4f}")

        # ── Dynamische TP-Anpassung ──────────────────────────────────────
        # Im starken Profit: TP erweitern wenn Trend weiter stark
        if pnl_pct > 0.03 and regime == "bull":  # >3% Profit + Bullenmarkt
            regime_reward = _REGIME_TP_MULT.get(regime, 2.0)
            extended_tp = current_price + (atr * regime_reward * 1.2)
            if extended_tp > current_tp:
                new_tp = extended_tp
                log.debug(f"SmartExit adapt {symbol}: TP {current_tp:.4f} → {extended_tp:.4f}")

        if new_sl or new_tp:
            with self._lock:
                self._adjustments[symbol] = {
                    "regime": regime,
                    "atr": round(atr, 4),
                    "pnl_pct": round(pnl_pct * 100, 2),
                    "sl_moved": new_sl is not None,
                    "tp_moved": new_tp is not None,
                }

        return new_sl, new_tp

    def classify_regime_from_scan(self, scan: dict[str, Any]) -> str:
        """Klassifiziert das Marktregime anhand von Scan-Daten.

        Ergänzt die globale Bull/Bear-Erkennung um feingranulare Zustände.

        Args:
            scan: Scan-Ergebnis-Dict mit Indikatoren.

        Returns:
            Regime-String: 'bull', 'bear', 'range' oder 'crash'.
        """
        atr_pct = scan.get("atr_pct", 1.0)
        rsi = scan.get("rsi", 50)
        bb_width = scan.get("bb_width", 0.05)
        roc10 = scan.get("roc10", 0)

        # Crash-Erkennung: hohe Volatilität + starker Abwärts-Momentum
        if atr_pct > 3.0 and roc10 < -5:
            return "crash"

        # Range-Erkennung: niedrige Volatilität + RSI neutral
        if bb_width < 0.03 and 35 < rsi < 65:
            return "range"

        # Bull/Bear basierend auf Momentum
        if roc10 > 2 and rsi > 50:
            return "bull"
        elif roc10 < -2 and rsi < 50:
            return "bear"

        return "range"

    def to_dict(self) -> dict[str, Any]:
        """Dashboard-Serialisierung.

        Returns:
            Dict mit Engine-Status und letzten Anpassungen.
        """
        with self._lock:
            adj_copy = dict(self._adjustments)
        return {
            "enabled": self.enabled,
            "regime_multipliers": {
                "sl": dict(_REGIME_SL_MULT),
                "tp": dict(_REGIME_TP_MULT),
            },
            "config": {
                "atr_sl_mult": self._config.get("smart_exit_atr_sl_mult", 1.5),
                "reward_ratio": self._config.get("smart_exit_reward_ratio", 2.0),
                "min_sl_pct": self._config.get("smart_exit_min_sl_pct", 1.0),
                "max_sl_pct": self._config.get("smart_exit_max_sl_pct", 8.0),
                "squeeze_threshold": self._config.get("smart_exit_squeeze_threshold", 0.03),
            },
            "last_adjustments": adj_copy,
        }
