"""
ML model classes extracted from server.py.

Module-level globals are injected at startup via init_ml_models().
"""

from __future__ import annotations

import random
import threading
from datetime import datetime

import numpy as np

from services.cryptopanic import CryptoPanicClient

# ---------------------------------------------------------------------------
# Optional ML dependencies
# ---------------------------------------------------------------------------
try:
    from sklearn.ensemble import IsolationForest
    from sklearn.preprocessing import StandardScaler

    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False

# ---------------------------------------------------------------------------
# Module-level references – populated by init_ml_models()
# ---------------------------------------------------------------------------
CONFIG: dict = {}
log = None
state = None
discord = None
emit_event = None
fg_idx = None
db = None


def init_ml_models(
    *,
    config: dict,
    logger,
    state_ref,
    discord_ref,
    emit_event_fn,
    fg_idx_ref,
    db_ref,
) -> None:
    """Inject runtime dependencies into this module's globals.

    Must be called once during application startup before any ML model
    instance is used.
    """
    global CONFIG, log, state, discord, emit_event, fg_idx, db
    CONFIG = config
    log = logger
    state = state_ref
    discord = discord_ref
    emit_event = emit_event_fn
    fg_idx = fg_idx_ref
    db = db_ref


# ═══════════════════════════════════════════════════════════════════════════════
# NEWS SENTIMENT (CryptoPanic API v2)
# ═══════════════════════════════════════════════════════════════════════════════
class NewsSentimentAnalyzer:
    """
    Wrapper für den CryptoPanic API v2 Service.
    Delegiert an services.cryptopanic.CryptoPanicClient.
    Score -1 bis +1: negativ=schlecht, positiv=bullish
    """

    def __init__(self):
        token = CONFIG.get("cryptopanic_token", "")
        plan = CONFIG.get("cryptopanic_plan", "free")
        self._client = CryptoPanicClient(token=token, plan=plan)

    def get_score(self, symbol: str) -> tuple[float, str, int]:
        """Returns (score, headline, article_count)"""
        return self._client.get_score(symbol, db=db)

    def prefetch_scores(self, symbols: list[str]) -> dict[str, tuple[float, str, int]]:
        """Batch-prefetch für mehrere Symbole (CryptoPanic-Limit-schonend)."""
        return self._client.prefetch_scores(symbols, db=db)


# ═══════════════════════════════════════════════════════════════════════════════
# ANOMALIE-ERKENNUNG (Isolation Forest)
# ═══════════════════════════════════════════════════════════════════════════════
class AnomalyDetector:
    """
    Erkennt ungewöhnliche Marktbedingungen (Flash-Crash, Spike).
    Trainiert auf Live-Preisdaten, pausiert Bot bei Anomalie.
    """

    def __init__(self):
        self.model = None
        self.scaler = StandardScaler() if ML_AVAILABLE else None
        self._data: list[list[float]] = []
        self._lock = threading.Lock()
        self.last_score = 0.0
        self.is_anomaly = False
        self.anomaly_symbol = ""
        self.anomaly_time = None
        self._last_trained = None

    def add_observation(self, price_chg: float, vol_ratio: float, rsi: float, atr_pct: float):
        """Add a new data point and trigger background training when ready."""
        with self._lock:
            self._data.append([price_chg, vol_ratio, rsi, atr_pct])
            if len(self._data) > 2000:
                self._data = self._data[-2000:]
            if len(self._data) >= 200 and (
                self._last_trained is None
                or (datetime.now() - self._last_trained).total_seconds() > 3600
            ):
                threading.Thread(target=self._train, daemon=True).start()

    def _train(self):
        if not ML_AVAILABLE:
            return
        try:
            with self._lock:
                X = np.array(self._data[-500:], dtype=np.float32)
            # Training außerhalb des Locks (kann lange dauern)
            # Verwende lokale Kopie des Scalers um Race-Condition zu vermeiden
            local_scaler = StandardScaler()
            X_s = local_scaler.fit_transform(X)
            new_model = IsolationForest(
                contamination=CONFIG["anomaly_contamination"],
                n_estimators=100,
                random_state=42,
                n_jobs=-1,
            )
            new_model.fit(X_s)
            # Atomare Zuweisung unter Lock → kein Zustand zwischen altem und neuem Modell
            with self._lock:
                self.scaler = local_scaler
                self.model = new_model
                self._last_trained = datetime.now()
        except Exception as e:
            log.debug(f"Anomalie-Training: {e}")

    def check(
        self, symbol: str, price_chg: float, vol_ratio: float, rsi: float, atr_pct: float
    ) -> tuple[bool, float]:
        """Returns (is_anomaly, score). Score < -0.5 = Anomalie."""
        if not CONFIG.get("use_anomaly") or self.model is None:
            return False, 0.0
        try:
            # Modell + Scaler atomar lesen um Race-Condition mit _train() zu vermeiden
            with self._lock:
                model_snap = self.model
                scaler_snap = self.scaler
            X = np.array([[price_chg, vol_ratio, rsi, atr_pct]], dtype=np.float32)
            X_s = scaler_snap.transform(X)
            score = float(model_snap.score_samples(X_s)[0])  # je negativer, desto anormaler
            is_anom = score < -0.6
            self.last_score = score
            if is_anom and not self.is_anomaly:
                self.is_anomaly = True
                self.anomaly_symbol = symbol
                self.anomaly_time = datetime.now()
                discord.anomaly_detected(symbol, score)
                log.warning(f"🚨 Anomalie bei {symbol}: Score={score:.3f}")
                if state:
                    state.add_activity(
                        "🚨", f"Anomalie: {symbol}", f"Score:{score:.3f} → Bot pausiert", "error"
                    )
            elif not is_anom and self.is_anomaly:
                self.is_anomaly = False
                log.info("✅ Anomalie aufgelöst")
            return is_anom, score
        except Exception:
            return False, 0.0

    def to_dict(self) -> dict:
        """Return a serialisable summary of the detector's current state."""
        return {
            "enabled": CONFIG.get("use_anomaly", True),
            "trained": self.model is not None,
            "is_anomaly": self.is_anomaly,
            "last_score": round(self.last_score, 3),
            "anomaly_symbol": self.anomaly_symbol,
            "samples": len(self._data),
        }


# ═══════════════════════════════════════════════════════════════════════════════
# GENETISCHER STRATEGIE-OPTIMIZER
# ═══════════════════════════════════════════════════════════════════════════════
class GeneticOptimizer:
    """
    Evolutionärer Algorithmus der tausende Parameter-Kombinationen testet.
    Genome = {sl, tp, vote, strats, indicators}
    """

    def __init__(self):
        self.best_genome: dict | None = None
        self.best_fitness = 0.0
        self.generation = 0
        self.running = False
        self._lock = threading.Lock()
        self.history: list[dict] = []

    def _random_genome(self) -> dict:
        return {
            "sl": round(random.uniform(0.01, 0.06), 3),
            "tp": round(random.uniform(0.03, 0.15), 3),
            "vote": round(random.uniform(0.45, 0.75), 2),
            "rsi_buy": random.randint(25, 45),
            "rsi_sell": random.randint(55, 75),
            "ema_fast": random.choice([5, 8, 10, 12, 21]),
            "ema_slow": random.choice([21, 34, 50, 55]),
            "vol_mult": round(random.uniform(1.2, 3.0), 1),
            "bb_std": round(random.uniform(1.5, 2.5), 1),
        }

    def _mutate(self, genome: dict, rate: float = 0.3) -> dict:
        g = dict(genome)
        if random.random() < rate:
            g["sl"] = max(0.005, g["sl"] + random.gauss(0, 0.005))
        if random.random() < rate:
            g["tp"] = max(0.02, g["tp"] + random.gauss(0, 0.01))
        if random.random() < rate:
            g["vote"] = float(np.clip(g["vote"] + random.gauss(0, 0.05), 0.4, 0.85))
        if random.random() < rate:
            g["rsi_buy"] = max(20, min(45, g["rsi_buy"] + random.randint(-5, 5)))
        if random.random() < rate:
            g["rsi_sell"] = max(55, min(80, g["rsi_sell"] + random.randint(-5, 5)))
        if random.random() < rate:
            g["vol_mult"] = max(1.0, g["vol_mult"] + random.gauss(0, 0.2))
        g["sl"] = round(float(np.clip(g["sl"], 0.005, 0.08)), 3)
        g["tp"] = round(float(np.clip(g["tp"], 0.02, 0.20)), 3)
        if g["tp"] < g["sl"] * 1.5:
            g["tp"] = round(g["sl"] * 2, 3)
        return g

    def _crossover(self, g1: dict, g2: dict) -> dict:
        child = {}
        for k in g1:
            child[k] = g1[k] if random.random() < 0.5 else g2[k]
        return child

    def _fitness(self, genome: dict, trades: list[dict]) -> float:
        """Berechnet Fitness eines Genoms auf historischen Trades."""
        if not trades:
            return 0.0
        wins = 0
        losses = 0
        total_pnl = 0.0
        for t in trades[:100]:  # [:100] = newest 100 (insert(0,...) puts newest at index 0)
            pp = (t.get("pnl_pct") or 0) / 100
            inv = t.get("invested") or 100
            if pp <= -genome["sl"]:
                total_pnl -= genome["sl"] * inv
                losses += 1
            elif pp >= genome["tp"]:
                total_pnl += genome["tp"] * inv
                wins += 1
            else:
                total_pnl += pp * inv
                if pp > 0:
                    wins += 1
                else:
                    losses += 1
        n = wins + losses
        if n < 5:
            return 0.0
        wr = wins / n
        pf = (wr * genome["tp"]) / max((1 - wr) * genome["sl"], 0.001)
        return float(wr * 0.5 + min(pf, 5) / 5 * 0.3 + min(total_pnl / 10000, 1) * 0.2)

    def evolve(self, trades: list[dict]):
        """Start an evolutionary optimisation run in a background thread."""
        if not CONFIG.get("genetic_enabled"):
            return
        if len(trades) < 20:
            return
        with self._lock:
            if self.running:
                return
            self.running = True
        threading.Thread(target=self._run, args=(trades,), daemon=True).start()

    def _run(self, trades: list[dict]):
        try:
            pop_size = CONFIG["genetic_population"]
            n_gen = CONFIG["genetic_generations"]
            # Initialpopulation
            population = [self._random_genome() for _ in range(pop_size)]
            # Bestes aus Config als Seed
            population[0] = {
                "sl": CONFIG["stop_loss_pct"],
                "tp": CONFIG["take_profit_pct"],
                "vote": CONFIG.get("min_vote_score", 0.3),
                "rsi_buy": 35,
                "rsi_sell": 65,
                "ema_fast": 8,
                "ema_slow": 21,
                "vol_mult": 2.0,
                "bb_std": 2.0,
            }
            for gen in range(n_gen):
                fitness_scores = [(g, self._fitness(g, trades)) for g in population]
                fitness_scores.sort(key=lambda x: x[1], reverse=True)
                best_g, best_f = fitness_scores[0]
                # Speichere best
                with self._lock:
                    if best_f > self.best_fitness:
                        self.best_fitness = best_f
                        self.best_genome = best_g
                        self.generation = gen + 1
                        self.history.insert(
                            0, {"gen": gen + 1, "fitness": round(best_f, 4), "genome": best_g}
                        )
                        self.history = self.history[:20]
                # Eliten
                elite_n = max(2, pop_size // 5)
                elites = [g for g, _ in fitness_scores[:elite_n]]
                # Neue Generation
                new_pop = elites[:]
                while len(new_pop) < pop_size:
                    p1 = random.choice(elites)
                    p2 = random.choice(elites)
                    child = self._crossover(p1, p2)
                    child = self._mutate(child)
                    new_pop.append(child)
                population = new_pop
                if gen % 5 == 4:
                    db.save_genetic(gen + 1, best_f, best_g)
                    log.info(
                        f"🧬 Gen {gen + 1}: Fitness={best_f:.4f} SL={best_g['sl'] * 100:.1f}% TP={best_g['tp'] * 100:.1f}%"
                    )
                emit_event(
                    "genetic_update",
                    {"gen": gen + 1, "fitness": round(best_f, 4), "best": best_g, "total": n_gen},
                )
            # Bestes Genome in Config übernehmen
            if self.best_genome:
                CONFIG["stop_loss_pct"] = self.best_genome["sl"]
                CONFIG["take_profit_pct"] = self.best_genome["tp"]
                CONFIG["min_vote_score"] = self.best_genome["vote"]
                log.info(
                    f"✅ Genetik abgeschlossen: SL={self.best_genome['sl'] * 100:.1f}% TP={self.best_genome['tp'] * 100:.1f}%"
                )
                discord.genetic_result(self.generation, self.best_fitness, self.best_genome)
                if state:
                    state.add_activity(
                        "🧬",
                        "Genetischer Optimizer",
                        f"SL:{self.best_genome['sl'] * 100:.1f}% TP:{self.best_genome['tp'] * 100:.1f}% Fitness:{self.best_fitness:.3f}",
                        "success",
                    )
        except Exception as e:
            log.error(f"Genetik: {e}")
        finally:
            with self._lock:
                self.running = False

    def to_dict(self) -> dict:
        """Return a serialisable summary of the optimiser's current state."""
        with self._lock:
            return {
                "enabled": CONFIG.get("genetic_enabled", True),
                "running": self.running,
                "generation": self.generation,
                "best_fitness": round(self.best_fitness, 4),
                "best_genome": self.best_genome,
                "history": self.history[:10],
            }


# ═══════════════════════════════════════════════════════════════════════════════
# REINFORCEMENT LEARNING AGENT (Q-Learning / Tabular PPO vereinfacht)
# ═══════════════════════════════════════════════════════════════════════════════
class RLAgent:
    """
    Einfacher Q-Learning Agent der aus Trade-Ergebnissen lernt.
    State:  [rsi_bucket, trend, fg_bucket, news_bucket, ob_bucket]
    Actions: 0=nichts, 1=kaufen, 2=verkaufen
    """

    ACTIONS = [0, 1, 2]  # hold, buy, sell

    def __init__(self):
        self.q_table: dict[str, list[float]] = {}
        self.alpha = 0.1  # Lernrate
        self.gamma = 0.9  # Diskontierung
        self.epsilon = 0.3  # Exploration
        self.epsilon_min = 0.05
        self.epsilon_decay = 0.995
        self.episodes = 0
        self.total_reward = 0.0
        self.is_trained = False
        self._lock = threading.Lock()
        self._replay: list[dict] = []

    def _state_key(self, rsi: float, trend: int, fg: int, news: float, ob: float) -> str:
        rsi_b = int(rsi // 10) * 10  # 0,10,20,...,90
        fg_b = int(fg // 20) * 20  # 0,20,40,60,80
        news_b = 1 if news > 0.2 else (-1 if news < -0.2 else 0)
        ob_b = 1 if ob > 0.6 else (-1 if ob < 0.4 else 0)
        return f"{rsi_b}_{trend}_{fg_b}_{news_b}_{ob_b}"

    def _get_q(self, state: str) -> list[float]:
        if state not in self.q_table:
            self.q_table[state] = [0.0, 0.0, 0.0]
        return self.q_table[state]

    def act(self, rsi: float, trend: int, fg: int, news: float, ob: float) -> int:
        """Select an action using epsilon-greedy policy."""
        if not CONFIG.get("rl_enabled") or not self.is_trained:
            return 1  # Default: kaufen (wird von anderen Filtern kontrolliert)
        state = self._state_key(rsi, trend, fg, news, ob)
        with self._lock:
            if random.random() < self.epsilon:
                return random.choice(self.ACTIONS)
            q = self._get_q(state)
            return int(np.argmax(q))

    def learn(
        self,
        rsi: float,
        trend: int,
        fg: int,
        news: float,
        ob: float,
        action: int,
        reward: float,
        next_rsi: float,
        next_trend: int,
    ):
        """Update the Q-table with a single (s, a, r, s') transition."""
        if not CONFIG.get("rl_enabled"):
            return
        state = self._state_key(rsi, trend, fg, news, ob)
        next_state = self._state_key(next_rsi, next_trend, fg, news, ob)
        with self._lock:
            q = self._get_q(state)
            q_next = self._get_q(next_state)
            # Q-Update
            q[action] += self.alpha * (reward + self.gamma * max(q_next) - q[action])
            self.epsilon = max(self.epsilon_min, self.epsilon * self.epsilon_decay)
            self.episodes += 1
            self.total_reward += reward
            if self.episodes >= CONFIG.get("rl_min_episodes", 100):
                self.is_trained = True
            self._replay.append({"state": state, "action": action, "reward": reward})
            self._replay = self._replay[-1000:]

    def on_trade_close(self, entry_scan: dict, pnl: float):
        """Lernt aus abgeschlossenem Trade."""
        if not entry_scan:
            return
        reward = float(np.clip(pnl / 100, -2.0, 2.0))  # Normalisierte Belohnung
        rsi = entry_scan.get("rsi", 50)
        trend = 1 if entry_scan.get("ema_alignment", 0) > 0 else -1
        fg = fg_idx.value if fg_idx else 50
        news = entry_scan.get("news_score", 0)
        ob = entry_scan.get("ob_ratio", 0.5)
        self.learn(rsi, trend, fg, news, ob, 1, reward, rsi, trend)

    def to_dict(self) -> dict:
        """Return a serialisable summary of the agent's current state."""
        return {
            "enabled": CONFIG.get("rl_enabled", True),
            "is_trained": self.is_trained,
            "episodes": self.episodes,
            "total_reward": round(self.total_reward, 2),
            "epsilon": round(self.epsilon, 3),
            "q_states": len(self.q_table),
            "min_episodes": CONFIG.get("rl_min_episodes", 100),
        }
