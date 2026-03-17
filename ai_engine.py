"""
╔══════════════════════════════════════════════════════════════════╗
║   TREVLIX AI ENGINE  –  Selbstlernende Gewinnoptimierung         ║
║                                                                  ║
║  HINWEIS: Dieses Modul ist ein eigenständiges Referenz-Modul.   ║
║  server.py importiert es NICHT – server.py hat eine eigene,     ║
║  erweiterte AIEngine-Klasse mit 9 Strategien (inkl. Ichimoku    ║
║  und VWAP), Fourier/Wavelet-Features und Bull/Bear-Regimen.     ║
║                                                                  ║
╠══════════════════════════════════════════════════════════════════╣
║                                                                  ║
║  Wie es funktioniert:                                            ║
║                                                                  ║
║  1. LERNEN: Jeder abgeschlossene Trade wird analysiert.          ║
║     Der Bot speichert alle Marktbedingungen beim Kaufzeitpunkt   ║
║     und ob der Trade gewonnen oder verloren hat.                 ║
║                                                                  ║
║  2. MODELL: Ein Random Forest (Ensemble aus 200 Entscheidungs-   ║
║     bäumen) lernt welche Signal-Kombinationen zum Gewinn führen. ║
║     Ab 20 Trades wird das Modell trainiert.                      ║
║                                                                  ║
║  3. GEWICHTUNG: Die 7 Strategien bekommen dynamische Gewichte    ║
║     basierend auf ihrer Vorhersagekraft (Feature Importance).    ║
║     Schlechte Strategien werden automatisch abgewertet.          ║
║                                                                  ║
║  4. FILTER: Vor jedem Kauf berechnet die KI eine                 ║
║     Gewinnwahrscheinlichkeit. Trades unter 55% werden blockiert. ║
║                                                                  ║
║  5. KELLY: Positionsgrößen werden mathematisch optimal nach      ║
║     dem Kelly-Kriterium berechnet (nicht zu viel, nicht zu wenig)║
║                                                                  ║
║  6. OPTIMIERUNG: Alle 15 Trades sucht der Bot automatisch die    ║
║     besten SL/TP-Werte auf den letzten Trades.                  ║
║                                                                  ║
╚══════════════════════════════════════════════════════════════════╝
"""

import logging
import math
import threading
from datetime import datetime
from typing import Any

import numpy as np

try:
    from sklearn.calibration import CalibratedClassifierCV
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.model_selection import cross_val_score
    from sklearn.preprocessing import StandardScaler

    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False
    print("⚠️  scikit-learn fehlt! pip install scikit-learn")

log = logging.getLogger("AIEngine")

# ═══════════════════════════════════════════════════════════════
# FEATURE-NAMEN (muss mit extract_features übereinstimmen)
# ═══════════════════════════════════════════════════════════════

# WICHTIG: Diese Liste muss mit STRATEGY_NAMES in server.py übereinstimmen.
# server.py ist die primäre Quelle. Diese Datei (ai_engine.py) wird von
# server.py NICHT importiert – server.py definiert seine eigene AIEngine-Klasse.
# ai_engine.py dient nur als eigenständiges Referenz-Modul.
STRATEGY_NAMES = [
    "EMA-Trend",
    "RSI-Stochastic",
    "MACD-Kreuzung",
    "Bollinger",
    "Volumen-Ausbruch",
    "OBV-Trend",
    "ROC-Momentum",
    "Ichimoku",  # neu in v1.1.0
    "VWAP",  # neu in v1.1.0
]

FEATURE_NAMES = STRATEGY_NAMES + [
    "rsi_norm",  # RSI / 100
    "stoch_rsi_norm",  # Stochastic RSI / 100
    "bb_pct",  # Position in Bollinger Band (0=unten, 1=oben)
    "bb_width_norm",  # Bollinger Band Breite (normalisiert)
    "macd_hist_sign",  # Vorzeichen MACD-Histogram
    "macd_hist_slope",  # Steigung MACD-Histogram
    "vol_ratio_norm",  # Volumen-Verhältnis / 5
    "atr_pct_norm",  # ATR als % / 10
    "ema_alignment",  # 1=ema8>21>50>200, -1=umgekehrt, 0=neutral
    "price_vs_ema21",  # (Preis - EMA21) / EMA21
    "roc10_norm",  # Rate of Change / 10
    "bull_market",  # 1=Bullish, 0=Bearish
    "hour_sin",  # Tageszeit (Sinus-Kodierung)
    "hour_cos",  # Tageszeit (Kosinus-Kodierung)
    "vote_consensus",  # Anteil aller Strategien die gleich stimmen
    "recent_win_rate",  # Win-Rate der letzten 10 Trades
]


# ═══════════════════════════════════════════════════════════════
# HAUPT-KI-ENGINE
# ═══════════════════════════════════════════════════════════════


class AIEngine:
    """
    Selbstlernende KI-Engine für maximierte Gewinnquote.

    Lernt kontinuierlich aus jedem Trade und verbessert:
    - Vorhersagegenauigkeit (welche Signale führen wirklich zu Gewinnen)
    - Strategie-Gewichtung (welche der 7 Strategien ist gerade zuverlässig)
    - Positionsgrößen (Kelly-Kriterium)
    - SL/TP-Parameter (automatische Optimierung)
    """

    def __init__(self, config: dict, state_ref):
        self.config = config
        self.state_ref = state_ref  # Referenz auf BotState für Trade-History
        self._lock = threading.Lock()

        # ── Modell ──────────────────────────────────────────────
        self.model: Any | None = None
        self.scaler = StandardScaler() if ML_AVAILABLE else None
        self.is_trained = False
        self.accuracy = 0.0
        self.cv_accuracy = 0.0
        self.min_samples = 20  # Mindest-Trades für erstes Training
        self.retrain_every = 5  # Neu trainieren alle N Trades
        self.trades_since_retrain = 0
        self.last_trained = None
        self.training_version = 0

        # ── Trainingsdaten ──────────────────────────────────────
        self.X_raw: list[np.ndarray] = []  # Feature-Vektoren
        self.y_raw: list[int] = []  # Labels: 1=Gewinn, 0=Verlust
        # Zugehörige Feature-Vektoren zu noch offenen Positionen
        self._pending_features: dict[str, np.ndarray] = {}

        # ── Strategie-Gewichte ──────────────────────────────────
        # Starten alle bei 1.0 (gleichwertig)
        # Werden nach Training auf [0.3, 3.0] skaliert
        self.strategy_weights: dict[str, float] = {n: 1.0 for n in STRATEGY_NAMES}
        self.strategy_win_rates: dict[str, float] = {n: 0.0 for n in STRATEGY_NAMES}

        # ── Vorhersage-Tracking ─────────────────────────────────
        self.predictions_made = 0
        self.predictions_correct = 0
        self._pending_predictions: dict[str, float] = {}

        # ── Parameter-Optimierung ───────────────────────────────
        self.optimize_every = 15  # Optimierung alle N Trades
        self.trades_since_optimize = 0
        self.last_optimization = None
        self.optimization_log: list[dict] = []

        # ── KI-Status für Dashboard ─────────────────────────────
        self.status_msg = "Sammle Trainingsdaten..."
        self.ai_decisions: list[dict] = []  # Log aller KI-Entscheidungen

    # ═══════════════════════════════════════════════════════════
    # FEATURE EXTRAKTION
    # ═══════════════════════════════════════════════════════════

    def extract_features(
        self, scan_result: dict, votes: dict, is_bull: bool, recent_trades: list
    ) -> np.ndarray:
        """
        Wandelt einen Scan-Ergebnisdatensatz in einen Feature-Vektor um.
        Dieser Vektor ist das "Gedächtnis" der KI für jeden Trade.
        """
        # 1. Strategie-Stimmen (7 Features: -1, 0, 1)
        vote_features = [float(votes.get(n, 0)) for n in STRATEGY_NAMES]

        # Konsens berechnen
        buys = sum(1 for v in vote_features if v > 0)
        sells = sum(1 for v in vote_features if v < 0)
        consensus = max(buys, sells) / len(STRATEGY_NAMES) if STRATEGY_NAMES else 0

        # 2. Marktbedingungen
        rsi = scan_result.get("rsi", 50)
        stoch = scan_result.get("stoch_rsi", 50)
        bb_pct = scan_result.get("bb_pct", 0.5)
        bb_wid = scan_result.get("bb_width", 0.05)
        vol_r = scan_result.get("vol_ratio", 1.0)
        atr_pct = scan_result.get("atr_pct", 1.0)
        macd_h = scan_result.get("macd_hist", 0)
        macd_sl = scan_result.get("macd_hist_slope", 0)
        ema_al = scan_result.get("ema_alignment", 0)
        pve21 = scan_result.get("price_vs_ema21", 0)
        roc10 = scan_result.get("roc10", 0)

        # 3. Tageszeit (Sinus/Kosinus kodiert → Periodizität)
        h = datetime.now().hour
        hour_sin = math.sin(2 * math.pi * h / 24)
        hour_cos = math.cos(2 * math.pi * h / 24)

        # 4. Letzte Win-Rate (gleitend, letzte 10 Trades)
        recent_wins = [t for t in recent_trades[-10:] if t.get("pnl", 0) > 0]
        recent_wr = len(recent_wins) / 10 if len(recent_trades) >= 10 else 0.5

        market_features = [
            rsi / 100.0,
            stoch / 100.0,
            float(np.clip(bb_pct, 0, 1)),
            float(np.clip(bb_wid * 10, 0, 5)),
            float(np.sign(macd_h)),
            float(np.clip(macd_sl * 100, -5, 5)),
            float(np.clip(vol_r / 5.0, 0, 3)),
            float(np.clip(atr_pct / 10.0, 0, 3)),
            float(np.clip(ema_al, -1, 1)),
            float(np.clip(pve21 * 100, -10, 10)),
            float(np.clip(roc10 / 10.0, -3, 3)),
            float(is_bull),
            float(hour_sin),
            float(hour_cos),
            float(consensus),
            float(recent_wr),
        ]

        vec = np.array(vote_features + market_features, dtype=np.float32)
        return vec

    # ═══════════════════════════════════════════════════════════
    # TRADE-ERGEBNIS VERARBEITEN
    # ═══════════════════════════════════════════════════════════

    def register_trade_open(self, symbol: str, features: np.ndarray):
        """Speichert Features beim Kauf für späteres Training."""
        with self._lock:
            self._pending_features[symbol] = features
            # Win-Probability für spätere Accuracy-Berechnung speichern
            if self.is_trained and self.model is not None and ML_AVAILABLE:
                try:
                    X_scaled = self.scaler.transform(features.reshape(1, -1))
                    proba = self.model.predict_proba(X_scaled)[0]
                    classes = list(self.model.classes_)
                    win_idx = classes.index(1) if 1 in classes else -1
                    self._pending_predictions[symbol] = (
                        float(proba[win_idx]) if win_idx >= 0 else 0.5
                    )
                except Exception:
                    pass

    def register_trade_close(self, symbol: str, pnl: float, votes: dict):
        """
        Wird nach jedem Verkauf aufgerufen.
        Fügt das Ergebnis den Trainingsdaten hinzu und triggert Retraining.
        """
        with self._lock:
            features = self._pending_features.pop(symbol, None)
            if features is None:
                return

            won = pnl > 0
            self.X_raw.append(features)
            self.y_raw.append(1 if won else 0)
            self.trades_since_retrain += 1
            self.trades_since_optimize += 1

            # Vorhersage-Accuracy tracken
            pred = self._pending_predictions.pop(symbol, None)
            if pred is not None:
                self.predictions_made += 1
                predicted_win = pred >= 0.5
                if predicted_win == won:
                    self.predictions_correct += 1

            # Individuelle Win-Rates der Strategien aktualisieren
            self._update_strategy_win_rates(votes, won)

            # Entscheidung unter Lock treffen, Ausführung außerhalb
            should_train = (
                len(self.X_raw) >= self.min_samples
                and self.trades_since_retrain >= self.retrain_every
            )
            should_optimize = self.trades_since_optimize >= self.optimize_every

        # Training/Optimierung außerhalb des Locks ausführen
        if should_train:
            self._train_model()

        if should_optimize:
            self._optimize_parameters()

    def _update_strategy_win_rates(self, votes: dict, won: bool):
        """
        Aktualisiert die individuelle Erfolgsrate jeder Strategie.
        Exponentiell gleitend (neuere Trades werden stärker gewichtet).
        """
        alpha = 0.1  # Lernrate
        for name in STRATEGY_NAMES:
            v = votes.get(name, 0)
            if v == 1:  # Strategie hat Kauf empfohlen
                old = self.strategy_win_rates.get(name, 0.5)
                self.strategy_win_rates[name] = (1 - alpha) * old + alpha * float(won)

    # ═══════════════════════════════════════════════════════════
    # MODELL TRAINING
    # ═══════════════════════════════════════════════════════════

    def _train_model(self):
        """
        Trainiert den Random Forest auf allen bisher gesammelten Trades.
        Benutzt Cross-Validation für realistische Genauigkeitsschätzung.
        """
        if not ML_AVAILABLE:
            return

        try:
            # Snapshot der Trainingsdaten unter Lock
            with self._lock:
                X = np.array(self.X_raw, dtype=np.float32)
                y = np.array(self.y_raw, dtype=np.int32)
            n = len(X)

            log.info(
                f"🧠 KI Training gestartet | {n} Trades | "
                f"Klassen: {sum(y)} Gewinner / {n - sum(y)} Verlierer"
            )

            # Scaler neu fitten
            X_scaled = self.scaler.fit_transform(X)

            # Random Forest – robust, schnell, interpretierbar
            rf = RandomForestClassifier(
                n_estimators=200,
                max_depth=6,
                min_samples_leaf=3,
                min_samples_split=5,
                max_features="sqrt",
                class_weight="balanced",  # Ungleichgewicht ausgleichen
                bootstrap=True,
                random_state=42,
                n_jobs=-1,
            )

            # Wahrscheinlichkeits-Kalibrierung für zuverlässige Prozente
            if n >= 40:
                self.model = CalibratedClassifierCV(rf, cv=3, method="isotonic")
            else:
                self.model = rf

            self.model.fit(X_scaled, y)

            # Genauigkeit messen
            self.accuracy = float(self.model.score(X_scaled, y))
            if n >= 30:
                base_rf = RandomForestClassifier(
                    n_estimators=100,
                    max_depth=6,
                    class_weight="balanced",
                    random_state=42,
                    n_jobs=-1,
                )
                cv_scores = cross_val_score(
                    base_rf, X_scaled, y, cv=min(5, n // 5), scoring="accuracy"
                )
                self.cv_accuracy = float(cv_scores.mean())
            else:
                self.cv_accuracy = self.accuracy * 0.9  # Konservative Schätzung

            # Feature Importance → Strategie-Gewichte aktualisieren
            self._update_strategy_weights()

            # Versionierung (unter Lock aktualisieren)
            with self._lock:
                self.is_trained = True
                self.training_version += 1
                self.trades_since_retrain = 0
                self.last_trained = datetime.now().strftime("%H:%M:%S")

            msg = (
                f"KI Modell v{self.training_version} trainiert | "
                f"Genauigkeit: {self.cv_accuracy * 100:.1f}% | "
                f"{n} Trades"
            )
            self.status_msg = msg
            log.info(f"✅ {msg}")

        except Exception as e:
            log.error(f"KI Training Fehler: {e}", exc_info=True)
            self.status_msg = f"Training fehlgeschlagen: {e}"

    def _update_strategy_weights(self):
        """
        Leitet aus Feature-Importance die Strategie-Gewichte ab.
        Wichtige Strategien bekommen höhere Gewichte (max 3x, min 0.2x).
        """
        try:
            # Feature Importances aus dem Random Forest extrahieren
            base_model = (
                getattr(self.model, "base_estimator", None)
                or getattr(self.model, "estimator", None)
                or self.model
            )
            if hasattr(base_model, "feature_importances_"):
                importances = base_model.feature_importances_
            elif hasattr(self.model, "feature_importances_"):
                importances = self.model.feature_importances_
            else:
                return

            n_strats = len(STRATEGY_NAMES)
            strat_importances = importances[:n_strats]

            if strat_importances.sum() == 0:
                return

            # Normalisieren auf Summe = n_strats (Durchschnitt bleibt 1.0)
            norm = (
                strat_importances / strat_importances.mean()
                if strat_importances.mean() > 0
                else strat_importances
            )
            # Clampen: jede Strategie bekommt mindestens 20% und maximal 300% Gewicht
            for i, name in enumerate(STRATEGY_NAMES):
                self.strategy_weights[name] = float(np.clip(norm[i], 0.2, 3.0))

            top = sorted(self.strategy_weights.items(), key=lambda x: x[1], reverse=True)
            log.info("🎛️  Strategie-Gewichte: " + " | ".join(f"{n}={w:.2f}" for n, w in top[:3]))
        except Exception as e:
            log.debug(f"Gewicht-Update Fehler: {e}")

    # ═══════════════════════════════════════════════════════════
    # VORHERSAGE
    # ═══════════════════════════════════════════════════════════

    def predict_win_probability(self, features: np.ndarray) -> float:
        """
        Gibt Gewinnwahrscheinlichkeit für einen potenziellen Trade zurück.
        Ohne trainiertes Modell: konservatives 0.5 (keine Meinung).
        """
        with self._lock:
            if not self.is_trained or self.model is None or not ML_AVAILABLE:
                return 0.5
            model = self.model
            scaler = self.scaler
            classes = list(model.classes_)

        try:
            X_scaled = scaler.transform(features.reshape(1, -1))
            proba = model.predict_proba(X_scaled)[0]
            # Klasse 1 = Gewinn
            if 1 not in classes:
                return 0.5
            win_idx = classes.index(1)
            win_prob = float(proba[win_idx])

            self.predictions_made += 1
            return win_prob
        except Exception as e:
            log.debug(f"Vorhersage-Fehler: {e}")
            return 0.5

    def should_buy(self, features: np.ndarray, confidence: float) -> tuple[bool, float, str]:
        """
        Entscheidet ob ein Kauf stattfinden soll.
        Returns: (erlaubt, ai_score, grund)
        """
        win_prob = self.predict_win_probability(features)

        if not self.is_trained:
            # Noch kein Modell: nur Voting-Konfidenz nutzen
            return True, confidence, "Sammle noch Daten"

        # Kombinierter Score: 60% KI-Wahrscheinlichkeit + 40% Voting-Konfidenz
        ai_score = win_prob * 0.6 + confidence * 0.4

        threshold = 0.55  # Mindest-Score für Kauf

        if ai_score >= threshold:
            grund = f"KI: {win_prob * 100:.0f}% Gewinnchance"
            self._log_decision("✅", "Kauf erlaubt", f"Score: {ai_score * 100:.0f}%", ai_score)
            return True, ai_score, grund
        else:
            grund = f"KI blockiert (Score: {ai_score * 100:.0f}% < {threshold * 100:.0f}%)"
            self._log_decision("🚫", "Kauf blockiert", grund, ai_score)
            return False, ai_score, grund

    def _log_decision(self, icon: str, title: str, detail: str, score: float):
        """Loggt KI-Entscheidung für Dashboard."""
        self.ai_decisions.insert(
            0,
            {
                "time": datetime.now().strftime("%H:%M:%S"),
                "icon": icon,
                "title": title,
                "detail": detail,
                "score": round(score * 100, 1),
            },
        )
        self.ai_decisions = self.ai_decisions[:30]

    # ═══════════════════════════════════════════════════════════
    # GEWICHTETES VOTING
    # ═══════════════════════════════════════════════════════════

    def weighted_vote(self, votes: dict, threshold: float) -> tuple[int, float]:
        """
        Führt gewichtetes Voting durch.
        Strategien die historisch besser abschneiden haben mehr Einfluss.
        """
        weighted_buy = weighted_sell = total_w = 0.0

        for name in STRATEGY_NAMES:
            v = votes.get(name, 0)
            w = self.strategy_weights.get(name, 1.0)
            total_w += w
            if v == 1:
                weighted_buy += w
            elif v == -1:
                weighted_sell += w

        if total_w == 0:
            return 0, 0.0

        buy_score = weighted_buy / total_w
        sell_score = weighted_sell / total_w

        if buy_score >= threshold:
            return 1, round(buy_score, 3)
        if sell_score >= threshold:
            return -1, round(sell_score, 3)
        return 0, round(max(buy_score, sell_score), 3)

    # ═══════════════════════════════════════════════════════════
    # KELLY-POSITIONSGRÖSSE
    # ═══════════════════════════════════════════════════════════

    def kelly_position_size(
        self, win_prob: float, balance: float, price: float, atr: float
    ) -> float:
        """
        Berechnet optimale Positionsgröße nach dem Kelly-Kriterium.

        Formel: f* = (b·p - q) / b
        b = TP/SL Verhältnis (Reward/Risk)
        p = Gewinnwahrscheinlichkeit
        q = Verlustwahrscheinlichkeit = 1-p

        Wir nutzen "Half Kelly" für mehr Sicherheit.
        """
        sl = self.config.get("stop_loss_pct", 0.025)
        tp = self.config.get("take_profit_pct", 0.06)
        b = tp / sl if sl > 0 else 2.4
        p = max(0.1, min(0.9, win_prob))  # Clampen für Stabilität
        q = 1.0 - p

        kelly_f = (b * p - q) / b
        kelly_f = max(0.0, kelly_f)
        half_kelly = kelly_f * 0.5  # Konservativ: Half Kelly

        # Maximale Positionsgröße aus Config
        max_pct = self.config.get("max_position_pct", 0.20)
        invest = balance * min(half_kelly, max_pct, 0.95)

        # Fallback auf ATR-basierte Berechnung wenn Kelly zu klein
        if invest < 2.0:
            risk_amount = balance * self.config.get("risk_per_trade", 0.015)
            stop_dist = atr if atr > 0 else price * sl
            invest = min(risk_amount / stop_dist * price, balance * max_pct) if stop_dist > 0 else 0

        return max(0.0, invest)

    # ═══════════════════════════════════════════════════════════
    # PARAMETER OPTIMIERUNG
    # ═══════════════════════════════════════════════════════════

    def _optimize_parameters(self):
        """
        Grid-Search über SL/TP-Kombinationen auf den letzten Trades.
        Findet die Parameter die historisch die beste Gewinnquote + PnL liefern.
        """
        trades = getattr(self.state_ref, "closed_trades", [])
        if len(trades) < 15:
            return

        recent = trades[-60:]  # Letzte 60 Trades als Basis
        log.info(f"🔬 KI-Optimierung startet auf {len(recent)} Trades...")

        # Suchraum
        sl_vals = [0.012, 0.015, 0.02, 0.025, 0.03, 0.035, 0.04, 0.05]
        tp_vals = [0.03, 0.04, 0.05, 0.06, 0.07, 0.08, 0.10, 0.12, 0.15]

        best_score = -999.0
        best_sl = self.config.get("stop_loss_pct", 0.025)
        best_tp = self.config.get("take_profit_pct", 0.06)
        results = []

        for sl in sl_vals:
            for tp in tp_vals:
                if tp < sl * 1.5:  # Risk/Reward muss mindestens 1.5:1 sein
                    continue

                sim_wins = 0
                sim_pnl = 0.0
                sim_cap = 10000.0

                for t in recent:
                    pnl_pct = t.get("pnl_pct", 0) / 100
                    invested = t.get("invested", sim_cap * 0.15) or sim_cap * 0.15

                    # Simuliere was mit diesem SL/TP passiert wäre
                    if pnl_pct <= -sl:
                        outcome = -sl * invested
                    elif pnl_pct >= tp:
                        outcome = tp * invested
                        sim_wins += 1
                    else:
                        outcome = pnl_pct * invested
                        if pnl_pct > 0:
                            sim_wins += 1

                    sim_pnl += outcome
                    sim_cap = max(sim_cap + outcome, 1.0)

                n = len(recent)
                win_rate = sim_wins / n
                avg_pnl = sim_pnl / n
                # Score = Kombination aus Win-Rate und Gesamt-PnL (normalisiert)
                score = win_rate * 0.6 + (sim_pnl / 10000.0) * 0.4

                results.append((sl, tp, win_rate, avg_pnl, score))
                if score > best_score:
                    best_score = score
                    best_sl = sl
                    best_tp = tp

        # Nur anwenden wenn Verbesserung signifikant (> 0.5% Änderung)
        cur_sl = self.config.get("stop_loss_pct", 0.025)
        cur_tp = self.config.get("take_profit_pct", 0.06)
        sl_diff = abs(best_sl - cur_sl)
        tp_diff = abs(best_tp - cur_tp)

        changed = False
        if sl_diff > 0.003 or tp_diff > 0.005:
            self.config["stop_loss_pct"] = best_sl
            self.config["take_profit_pct"] = best_tp
            changed = True

        # Auch min_vote_score optimieren
        if hasattr(self.state_ref, "closed_trades"):
            self._optimize_vote_threshold(recent)

        # Log-Eintrag
        msg = (
            f"SL: {cur_sl * 100:.1f}%→{best_sl * 100:.1f}% | "
            f"TP: {cur_tp * 100:.1f}%→{best_tp * 100:.1f}%"
        )
        status = "✅ Optimiert" if changed else "✔️ Keine Änderung nötig"
        entry = {
            "time": datetime.now().strftime("%H:%M:%S"),
            "icon": "🔬",
            "title": f"Optimierung #{len(self.optimization_log) + 1}",
            "detail": f"{status} | {msg}",
            "score": round(best_score * 100, 1),
            "sl": round(best_sl * 100, 2),
            "tp": round(best_tp * 100, 2),
            "changed": changed,
        }
        self.optimization_log.insert(0, entry)
        self.optimization_log = self.optimization_log[:20]
        self.trades_since_optimize = 0
        self.last_optimization = datetime.now().strftime("%H:%M:%S")

        if changed:
            log.info(f"🔬 KI optimiert Parameter: {msg}")
        else:
            log.info("🔬 KI: Aktuelle Parameter bereits optimal")

    def _optimize_vote_threshold(self, trades: list):
        """Optimiert den Min-Vote-Score Schwellenwert."""
        thresholds = [0.43, 0.50, 0.57, 0.60, 0.64, 0.71, 0.86]
        best_score = -1.0
        best_wr = 0.0
        best_t = self.config.get("min_vote_score", 0.6)

        for t in thresholds:
            # Simuliere nur Trades die über diesem Threshold waren
            filtered = [tr for tr in trades if tr.get("confidence", 0) >= t]
            if len(filtered) < 5:
                continue
            wr = sum(1 for tr in filtered if tr.get("pnl", 0) > 0) / len(filtered)
            # Bestrafe kleine Stichproben um Überanpassung zu vermeiden
            score = wr - 1.0 / math.sqrt(len(filtered))
            if score > best_score:
                best_score = score
                best_wr = wr
                best_t = t

        if abs(best_t - self.config.get("min_vote_score", 0.6)) > 0.05:
            self.config["min_vote_score"] = best_t
            log.info(
                f"🎯 Voting-Schwellenwert optimiert: {best_t * 100:.0f}%"
                f" (erwartete Win-Rate: {best_wr * 100:.1f}%)"
            )

    # ═══════════════════════════════════════════════════════════
    # DASHBOARD-DATEN
    # ═══════════════════════════════════════════════════════════

    def to_dict(self) -> dict:
        """Alle KI-Daten für das Dashboard."""
        # Feature Importances
        importances = []
        try:
            base = (
                getattr(self.model, "base_estimator", None)
                or getattr(self.model, "estimator", None)
                or self.model
            )
            if self.is_trained and base and hasattr(base, "feature_importances_"):
                fi = base.feature_importances_
                for i, name in enumerate(FEATURE_NAMES):
                    if i < len(fi):
                        importances.append(
                            {
                                "name": name,
                                "importance": round(float(fi[i]) * 100, 2),
                                "is_strategy": i < len(STRATEGY_NAMES),
                            }
                        )
                importances.sort(key=lambda x: x["importance"], reverse=True)
        except Exception:
            pass

        # Strategie-Gewichte mit Win-Rates
        weights = []
        for name in STRATEGY_NAMES:
            weights.append(
                {
                    "name": name,
                    "weight": round(self.strategy_weights.get(name, 1.0), 3),
                    "win_rate": round(self.strategy_win_rates.get(name, 0.5) * 100, 1),
                }
            )
        weights.sort(key=lambda x: x["weight"], reverse=True)

        # Vorhersage-Präzision
        pred_acc = (
            self.predictions_correct / self.predictions_made * 100
            if self.predictions_made > 0
            else 0
        )

        samples_needed = max(0, self.min_samples - len(self.X_raw))

        return {
            "enabled": ML_AVAILABLE,
            "is_trained": self.is_trained,
            "status_msg": self.status_msg,
            "accuracy": round(self.accuracy * 100, 1),
            "cv_accuracy": round(self.cv_accuracy * 100, 1),
            "samples": len(self.X_raw),
            "min_samples": self.min_samples,
            "samples_needed": samples_needed,
            "training_version": self.training_version,
            "last_trained": self.last_trained,
            "last_optimization": self.last_optimization,
            "strategy_weights": weights,
            "feature_importances": importances[:15],
            "optimization_log": self.optimization_log[:10],
            "ai_decisions": self.ai_decisions[:15],
            "predictions_made": self.predictions_made,
            "pred_accuracy": round(pred_acc, 1),
            "current_params": {
                "sl": round(self.config.get("stop_loss_pct", 0.025) * 100, 2),
                "tp": round(self.config.get("take_profit_pct", 0.06) * 100, 2),
                "vote_score": round(self.config.get("min_vote_score", 0.6) * 100, 1),
            },
            "progress_pct": min(100, int(len(self.X_raw) / self.min_samples * 100)),
        }
