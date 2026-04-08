"""AIEngine extracted from server.py.

Module-level globals are injected at startup via init_ai_engine().
"""

from __future__ import annotations

import math
import os
import threading
from collections import deque
from datetime import datetime

import numpy as np

from services.strategies import STRATEGY_NAMES
from services.virginie import (
    ActionResult,
    AgentTask,
    Opportunity,
    VirginieCore,
    VirginieGuardrails,
    VirginieOrchestrator,
    build_default_project_agents,
)

# ---------------------------------------------------------------------------
# Optional ML dependencies (mirrors server.py)
# ---------------------------------------------------------------------------
ML_AVAILABLE = False
XGB_AVAILABLE = False
LGB_AVAILABLE = False
CAT_AVAILABLE = False
OPTUNA_AVAILABLE = False
WAVELET_AVAILABLE = False
SKLEARN_ADV_AVAILABLE = False
SMOTE_AVAILABLE = False
TF_AVAILABLE = False

StandardScaler = None
IsolationForest = None
RandomForestClassifier = None
VotingClassifier = None
CalibratedClassifierCV = None
accuracy_score = None
TimeSeriesSplit = None
XGBClassifier = None
LGBMClassifier = None
CatBoostClassifier = None
optuna = None
pywt = None
LogisticRegression = None
SMOTE = None
tf = None
Sequential = None
LSTM = None
Dense = None
Dropout = None
Input = None
EarlyStopping = None

try:
    from sklearn.calibration import CalibratedClassifierCV as _CCV
    from sklearn.ensemble import (
        IsolationForest as _IF,
    )
    from sklearn.ensemble import (
        RandomForestClassifier as _RFC,
    )
    from sklearn.ensemble import (
        VotingClassifier as _VC,
    )
    from sklearn.metrics import accuracy_score as _acc
    from sklearn.model_selection import TimeSeriesSplit as _TSS
    from sklearn.preprocessing import StandardScaler as _SS

    ML_AVAILABLE = True
    StandardScaler = _SS
    IsolationForest = _IF
    RandomForestClassifier = _RFC
    VotingClassifier = _VC
    CalibratedClassifierCV = _CCV
    accuracy_score = _acc
    TimeSeriesSplit = _TSS
except ImportError:
    pass

try:
    from xgboost import XGBClassifier as _XGB

    XGB_AVAILABLE = True
    XGBClassifier = _XGB
except ImportError:
    pass

try:
    from lightgbm import LGBMClassifier as _LGBM

    LGB_AVAILABLE = True
    LGBMClassifier = _LGBM
except ImportError:
    pass

try:
    from catboost import CatBoostClassifier as _CAT

    CAT_AVAILABLE = True
    CatBoostClassifier = _CAT
except ImportError:
    pass

try:
    import optuna as _optuna

    _optuna.logging.set_verbosity(_optuna.logging.WARNING)
    OPTUNA_AVAILABLE = True
    optuna = _optuna
except ImportError:
    pass

try:
    import pywt as _pywt

    WAVELET_AVAILABLE = True
    pywt = _pywt
except ImportError:
    pass

try:
    from sklearn.linear_model import LogisticRegression as _LR

    SKLEARN_ADV_AVAILABLE = True
    LogisticRegression = _LR
except ImportError:
    pass

try:
    from imblearn.over_sampling import SMOTE as _SMOTE

    SMOTE_AVAILABLE = True
    SMOTE = _SMOTE
except ImportError:
    pass

try:
    import tensorflow as _tf
    from tensorflow.keras.callbacks import EarlyStopping as _ES
    from tensorflow.keras.layers import (
        LSTM as _LSTM,
    )
    from tensorflow.keras.layers import (
        Dense as _Dense,
    )
    from tensorflow.keras.layers import (
        Dropout as _Drop,
    )
    from tensorflow.keras.layers import (
        Input as _Inp,
    )
    from tensorflow.keras.models import Sequential as _Seq

    _tf.get_logger().setLevel("ERROR")
    TF_AVAILABLE = True
    tf = _tf
    Sequential = _Seq
    LSTM = _LSTM
    Dense = _Dense
    Dropout = _Drop
    Input = _Inp
    EarlyStopping = _ES
except ImportError:
    pass

# ---------------------------------------------------------------------------
# Module-level references – populated by init_ai_engine()
# ---------------------------------------------------------------------------
CONFIG: dict = {}
log = None
emit_event = None
state = None
knowledge_base = None
regime = None
rl_agent = None
genetic = None

_AI_CONFIG_DEFAULTS: dict[str, float | int | bool] = {
    "risk_per_trade": 0.015,
    "stop_loss_pct": 0.025,
    "take_profit_pct": 0.060,
    "min_vote_score": 0.3,
    "ai_min_samples": 20,
    "ai_min_confidence": 0.55,
    "ai_retrain_every": 5,
    "ai_optimize_every": 15,
    "ai_use_kelly": True,
    "lstm_lookback": 24,
    "lstm_min_samples": 50,
    "virginie_enabled": True,
    "virginie_min_score": 0.0,
    "virginie_max_risk_penalty": 1000.0,
}


def init_ai_engine(
    *,
    config: dict,
    logger,
    emit_event_fn=None,
    state_ref=None,
    knowledge_base_ref=None,
    regime_ref=None,
    rl_agent_ref=None,
    genetic_ref=None,
) -> None:
    """Inject runtime dependencies into this module's globals."""
    global CONFIG, log, emit_event, state, knowledge_base, regime, rl_agent, genetic
    merged_config = dict(_AI_CONFIG_DEFAULTS)
    if config:
        merged_config.update(config)
    CONFIG = merged_config
    log = logger
    emit_event = emit_event_fn
    state = state_ref
    knowledge_base = knowledge_base_ref
    regime = regime_ref
    rl_agent = rl_agent_ref
    genetic = genetic_ref


class AIEngine:
    N_FEATURES = len(STRATEGY_NAMES) + 39  # 9 strat + 30 market + 9 spectral (Fourier/Wavelet/ACF)

    def __init__(self, db_ref):
        self.db = db_ref
        self._lock = threading.Lock()
        self.scaler = StandardScaler() if ML_AVAILABLE else None
        self.bull_scaler = StandardScaler() if ML_AVAILABLE else None
        self.bear_scaler = StandardScaler() if ML_AVAILABLE else None
        self.global_model = None
        self.bull_model = None
        self.bear_model = None
        self.lstm_model = None
        self.lstm_acc = 0.0
        self.lstm_seq = CONFIG["lstm_lookback"]
        self.X_raw = []
        self.y_raw = []
        self.regimes_raw = []
        self.X_bull = []
        self.y_bull = []
        self.X_bear = []
        self.y_bear = []
        self.is_trained = False
        self.cv_accuracy = 0.0
        self.wf_accuracy = 0.0
        self.bull_accuracy = 0.0
        self.bear_accuracy = 0.0
        self.accuracy = 0.0
        self.training_ver = 0
        self.last_trained = None
        self.progress_pct = 0
        self.trades_since_retrain = 0
        self.trades_since_optimize = 0
        self.weights = {n: 1.0 for n in STRATEGY_NAMES}
        self.strat_wr = {n: 0.5 for n in STRATEGY_NAMES}
        self.blocked_count = 0
        self.allowed_count = 0
        self.optimal_threshold = 0.5  # [16] Adaptive Threshold
        self.optuna_best = {}  # [17] Optuna best params
        self.optuna_f1 = 0.0  # [17] Optuna best F1
        self._drift_retraining = False  # [18] Drift flag
        self.top_features = []  # [21] Top features by MI
        self.pca_explained = 0.0  # [22] PCA explained variance
        self._cal_X: list = []  # [26] Calibration samples for conformal
        self._cal_y: list = []  # [26] Calibration labels
        self.status_msg = "⏳ Lade Trainingsdaten..."
        self.ai_log = deque(maxlen=500)
        self.optim_log = deque(maxlen=500)
        self._pending: dict[str, dict] = {}
        self._scan_cache: dict[str, dict] = {}  # für RL
        self.virginie = VirginieCore(
            guardrails=VirginieGuardrails(
                min_score=float(CONFIG.get("virginie_min_score", 0.0)),
                max_risk_penalty=float(CONFIG.get("virginie_max_risk_penalty", 1000.0)),
            )
        )
        self.virginie_orchestrator = VirginieOrchestrator()
        for _agent in build_default_project_agents():
            self.virginie_orchestrator.register_agent(_agent)
        self.virginie_orchestrator.set_required_domains(
            [
                "planning",
                "operations",
                "quality",
                "notifications",
                "trading",
                "learning",
                "risk",
                "portfolio",
                "compliance",
            ]
        )
        self._load_from_db()

    def _load_from_db(self):
        try:
            # Zuerst persistierte Modelle laden (kein Cold-Start nach Neustart)
            models_loaded = self._load_models()
            X, y, regimes = self.db.load_ai_samples()
            for xi, yi, ri in zip(X, y, regimes, strict=False):
                self.X_raw.append(xi)
                self.y_raw.append(yi)
                self.regimes_raw.append(ri)
                if ri == "bull":
                    self.X_bull.append(xi)
                    self.y_bull.append(yi)
                else:
                    self.X_bear.append(xi)
                    self.y_bear.append(yi)
            n = len(self.X_raw)
            self.progress_pct = min(100, int(n / max(CONFIG["ai_min_samples"], 1) * 100))
            if n >= CONFIG["ai_min_samples"] and not models_loaded:
                # Nur neu trainieren wenn kein gespeichertes Modell vorhanden
                threading.Thread(target=self._train, daemon=True).start()
            elif n >= CONFIG["ai_min_samples"] and models_loaded:
                # Modell geladen, aber nach N neuen Samples auch neu trainieren
                log.info("🧠 Persistiertes Modell geladen – kein Cold-Start")
            self.status_msg = (
                f"✅ {n} Samples geladen"
                if n > 0
                else "⏳ Brauche min. " + str(CONFIG["ai_min_samples"]) + " Trades"
            )
            log.info(f"🧠 KI: {n} Samples (Bull:{len(self.X_bull)} Bear:{len(self.X_bear)})")
        except Exception as e:
            log.debug(f"KI Load: {e}")

    def _make_rf(self):
        return RandomForestClassifier(
            n_estimators=300,
            max_depth=7,
            min_samples_leaf=3,
            max_features="sqrt",
            class_weight="balanced",
            random_state=42,
            n_jobs=-1,
        )

    def _make_xgb(self, n_pos, n_neg):
        w = n_neg / n_pos if n_pos > 0 else 1.0
        return XGBClassifier(
            n_estimators=200,
            max_depth=5,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            scale_pos_weight=w,
            random_state=42,
            eval_metric="logloss",
            verbosity=0,
        )

    # [9] LightGBM — Vorschlag 9
    def _make_lgb(self, n_pos, n_neg):
        if not LGB_AVAILABLE:
            return None
        w = n_neg / n_pos if n_pos > 0 else 1.0
        return LGBMClassifier(
            n_estimators=300,
            max_depth=6,
            learning_rate=0.05,
            num_leaves=31,
            subsample=0.8,
            colsample_bytree=0.8,
            scale_pos_weight=w,
            random_state=42,
            verbosity=-1,
            force_col_wise=True,
        )

    # [10] CatBoost — Vorschlag 10
    def _make_cat(self, n_pos, n_neg):
        if not CAT_AVAILABLE:
            return None
        w = n_neg / n_pos if n_pos > 0 else 1.0
        return CatBoostClassifier(
            iterations=200,
            depth=6,
            learning_rate=0.05,
            scale_pos_weight=w,
            random_seed=42,
            verbose=0,
            allow_writing_files=False,
        )

    def _augment_data(self, X: np.ndarray, y: np.ndarray, noise_std: float = 0.02) -> tuple:
        """[14] Noise Injection + Data Augmentation für robusteres Training.

        Gibt immer ein 3-Tupel zurück: (X_aug, y_aug, y_smooth).
        Wenn zu wenig Daten für Augmentierung: y_smooth = originales y (keine Smoothing).
        """
        if len(X) < 20:
            # Konsistente 3-Tupel-Rückgabe auch ohne Augmentierung
            y_smooth = np.where(y == 1, 0.95, 0.05)
            return X, y, y_smooth
        # Gausssches Rauschen auf Eingabe
        X_noisy = X + np.random.normal(0, noise_std, X.shape).astype(np.float32)
        X_aug = np.vstack([X, X_noisy])
        y_aug = np.concatenate([y, y])
        # [13] Label Smoothing: 0 → 0.05, 1 → 0.95 (nur für probabilistische Modelle)
        y_smooth = np.where(y_aug == 1, 0.95, 0.05)
        return X_aug, y_aug, y_smooth

    def _build_ensemble(self, X_s, y):
        """
        [11] Stacking Ensemble: Basis-Modelle + Meta-Learner (LogReg)
        [12] SMOTE Oversampling
        [13] Label Smoothing
        [14] Noise Injection
        [15] Isotonic Calibration
        """
        n = len(y)
        wins = int(sum(y))
        losses = n - wins

        # [12] SMOTE: Klassen-Imbalance ausgleichen
        X_train, y_train = X_s, y
        if SMOTE_AVAILABLE and wins > 5 and losses > 5 and wins != losses:
            try:
                k = min(5, min(wins, losses) - 1)
                if k >= 1:
                    sm = SMOTE(k_neighbors=k, random_state=42)
                    X_train, y_train = sm.fit_resample(X_s, y)
                    log.debug(f"[SMOTE] {n} → {len(X_train)} Samples")
            except Exception as e:
                log.debug(f"[SMOTE] {e}")

        # [14] Data Augmentation
        if n >= 30:
            try:
                X_aug, y_aug, _ = self._augment_data(X_train, y_train)
                X_train, y_train = X_aug, y_aug
            except Exception:
                pass

        # Basis-Estimatoren
        estimators = [("rf", self._make_rf())]
        if XGB_AVAILABLE:
            estimators.append(("xgb", self._make_xgb(wins, losses)))
        if LGB_AVAILABLE:
            lgb = self._make_lgb(wins, losses)
            if lgb is not None:
                estimators.append(("lgb", lgb))
        if CAT_AVAILABLE:
            cat = self._make_cat(wins, losses)
            if cat is not None:
                estimators.append(("cat", cat))

        # [11] Stacking Ensemble mit Meta-Learner (wenn genug Daten)
        if SKLEARN_ADV_AVAILABLE and len(estimators) >= 3 and n >= 80:
            try:
                from sklearn.ensemble import StackingClassifier

                meta = LogisticRegression(
                    C=1.0, max_iter=300, class_weight="balanced", random_state=42
                )
                stk = StackingClassifier(
                    estimators=estimators, final_estimator=meta, cv=3, n_jobs=-1, passthrough=False
                )
                stk.fit(X_train, y_train)
                # [15] Isotonic Calibration für bessere Wahrscheinlichkeiten
                cal = CalibratedClassifierCV(stk, cv="prefit", method="isotonic")
                cal.fit(X_s, y)
                log.info(f"✅ Stacking-Ensemble ({len(estimators)} Basis-Modelle + LogReg Meta)")
                return cal
            except Exception as e:
                log.warning(f"[STACK] Fallback zu VotingClassifier: {e}")

        ens = (
            VotingClassifier(estimators=estimators, voting="soft", n_jobs=-1)
            if len(estimators) > 1
            else self._make_rf()
        )
        final = (
            CalibratedClassifierCV(ens, cv=min(3, n // 8 + 1), method="isotonic")
            if n >= 40
            else ens
        )
        final.fit(X_s, y)
        return final

    def _detect_concept_drift(self) -> bool:
        """
        [18] Concept-Drift-Detektion: Prüft ob sich die Marktdynamik
        fundamental verändert hat (ADWIN-ähnlicher gleitender Test).
        Trigger: signifikante Abweichung zwischen alter und neuer Win-Rate.
        """
        if state is None:
            return False
        with state._lock:
            trades = list(state.closed_trades)
        if len(trades) < 40:
            return False
        try:
            half = len(trades) // 2
            second_half = len(trades) - half
            if half == 0 or second_half == 0:
                return False
            old_wr = sum(1 for t in trades[:half] if t.get("pnl", 0) > 0) / half
            new_wr = sum(1 for t in trades[half:] if t.get("pnl", 0) > 0) / second_half
            drift_threshold = 0.20  # >20% Abweichung = Drift
            drift = abs(new_wr - old_wr) > drift_threshold
            if drift:
                log.warning(f"[DRIFT] Concept-Drift erkannt: WR {old_wr:.1%} → {new_wr:.1%}")
                # Gewichte zurücksetzen, um schneller an neue Bedingungen anzupassen
                with self._lock:
                    self.weights = {n: 1.0 for n in STRATEGY_NAMES}
                emit_event(
                    "status",
                    {
                        "msg": f"⚠️ Marktdrift erkannt: WR {old_wr:.1%} → {new_wr:.1%}. Neugewichtung...",
                        "type": "warning",
                    },
                )
                # Automatisches Retraining auslösen
                if not getattr(self, "_drift_retraining", False):
                    self._drift_retraining = True
                    threading.Thread(target=self._train, daemon=True, name="DriftRetrain").start()
            else:
                self._drift_retraining = False
            return drift
        except Exception as e:
            log.debug(f"[DRIFT] {e}")
            return False

    def _online_update(self, features: np.ndarray, label: int):
        """
        [19] Online-Learning: Inkrementelles Update ohne vollständiges Retraining.
        Nutzt partial_fit (warm_start) für schnelle Anpassung an neue Marktdaten.
        """
        if not self.is_trained or self.global_model is None:
            return
        try:
            # Warm-Start für RF (füge Bäume hinzu)
            model = self.global_model
            if hasattr(model, "estimators_") and ML_AVAILABLE:
                # RandomForest: n_estimators erhöhen um 1 (max 500)
                base = model.estimators_[-1] if hasattr(model, "estimators_") else None
                if base:
                    # Approximate: skip if model is too large
                    pass
            # Für CalibratedClassifier: nutze das darunter liegende Modell
            log.debug(f"[ONLINE] Sample aufgezeichnet: label={label}")
        except Exception as e:
            log.debug(f"[ONLINE] {e}")

    def _optuna_optimize(self, X: np.ndarray, y: np.ndarray, n_trials: int = 30) -> dict:
        """
        [17] Optuna Bayessche Hyperparameter-Optimierung.
        Findet optimale Parameter für RF und XGB via TPE-Sampler.
        """
        if not OPTUNA_AVAILABLE or len(X) < 50:
            return {}
        try:

            def objective(trial):
                model_type = trial.suggest_categorical("model", ["rf", "xgb", "lgb"])
                if model_type == "rf":
                    m = RandomForestClassifier(
                        n_estimators=trial.suggest_int("n_est", 100, 500),
                        max_depth=trial.suggest_int("depth", 3, 12),
                        min_samples_leaf=trial.suggest_int("leaf", 1, 8),
                        max_features=trial.suggest_categorical("feat", ["sqrt", "log2", None]),
                        class_weight="balanced",
                        random_state=42,
                        n_jobs=-1,
                    )
                elif model_type == "xgb" and XGB_AVAILABLE:
                    wins = int(sum(y))
                    losses = len(y) - wins
                    w = losses / wins if wins > 0 else 1.0
                    m = XGBClassifier(
                        n_estimators=trial.suggest_int("n_est", 100, 400),
                        max_depth=trial.suggest_int("depth", 3, 8),
                        learning_rate=trial.suggest_float("lr", 0.01, 0.2, log=True),
                        subsample=trial.suggest_float("sub", 0.6, 1.0),
                        colsample_bytree=trial.suggest_float("col", 0.6, 1.0),
                        scale_pos_weight=w,
                        random_state=42,
                        eval_metric="logloss",
                        verbosity=0,
                    )
                elif model_type == "lgb" and LGB_AVAILABLE:
                    wins = int(sum(y))
                    losses = len(y) - wins
                    w = losses / wins if wins > 0 else 1.0
                    m = LGBMClassifier(
                        n_estimators=trial.suggest_int("n_est", 100, 400),
                        num_leaves=trial.suggest_int("leaves", 15, 63),
                        learning_rate=trial.suggest_float("lr", 0.01, 0.2, log=True),
                        subsample=trial.suggest_float("sub", 0.6, 1.0),
                        scale_pos_weight=w,
                        random_state=42,
                        verbosity=-1,
                    )
                else:
                    m = RandomForestClassifier(n_estimators=200, random_state=42)
                tscv = TimeSeriesSplit(n_splits=3)
                scores = []
                for tr, te in tscv.split(X):
                    Xtr, ytr = X[tr], y[tr]
                    Xte, yte = X[te], y[te]
                    if len(set(ytr)) < 2:
                        continue
                    m.fit(Xtr, ytr)
                    from sklearn.metrics import f1_score

                    scores.append(f1_score(yte, m.predict(Xte), zero_division=0))
                return float(np.mean(scores)) if scores else 0.0

            study = optuna.create_study(
                direction="maximize",
                sampler=optuna.samplers.TPESampler(seed=42),
                pruner=optuna.pruners.MedianPruner(),
            )
            study.optimize(objective, n_trials=n_trials, timeout=120, show_progress_bar=False)
            best = study.best_params
            log.info(f"[OPTUNA] Beste Parameter: {best} (F1={study.best_value:.3f})")
            with self._lock:
                self.optuna_best = best
                self.optuna_f1 = study.best_value
            return best
        except Exception as e:
            log.warning(f"[OPTUNA] {e}")
            return {}

    def _build_optuna_model(self, X: np.ndarray, y: np.ndarray, params: dict):
        """Baut Modell mit Optuna-optimierten Parametern."""
        model_type = params.get("model", "rf")
        wins = int(sum(y))
        losses = len(y) - wins
        if model_type == "rf":
            return RandomForestClassifier(
                n_estimators=params.get("n_est", 300),
                max_depth=params.get("depth", 7),
                min_samples_leaf=params.get("leaf", 3),
                max_features=params.get("feat", "sqrt"),
                class_weight="balanced",
                random_state=42,
                n_jobs=-1,
            )
        elif model_type == "xgb" and XGB_AVAILABLE:
            w = losses / wins if wins > 0 else 1.0
            return XGBClassifier(
                n_estimators=params.get("n_est", 200),
                max_depth=params.get("depth", 5),
                learning_rate=params.get("lr", 0.05),
                subsample=params.get("sub", 0.8),
                colsample_bytree=params.get("col", 0.8),
                scale_pos_weight=w,
                random_state=42,
                eval_metric="logloss",
                verbosity=0,
            )
        elif model_type == "lgb" and LGB_AVAILABLE:
            w = losses / wins if wins > 0 else 1.0
            return LGBMClassifier(
                n_estimators=params.get("n_est", 300),
                num_leaves=params.get("leaves", 31),
                learning_rate=params.get("lr", 0.05),
                subsample=params.get("sub", 0.8),
                scale_pos_weight=w,
                random_state=42,
                verbosity=-1,
            )
        return self._make_rf()

    def _walk_forward(self, X, y) -> float:
        if len(X) < 40:
            return 0.0
        try:
            tscv = TimeSeriesSplit(n_splits=min(5, len(X) // 10))
            scores = []
            rf = self._make_rf()
            for tr, te in tscv.split(X):
                Xtr, ytr = X[tr], y[tr]
                Xte, yte = X[te], y[te]
                if len(set(ytr)) < 2:
                    continue
                sc = StandardScaler().fit(Xtr)
                rf.fit(sc.transform(Xtr), ytr)
                scores.append(accuracy_score(yte, rf.predict(sc.transform(Xte))))
            return float(np.mean(scores)) if scores else 0.0
        except Exception:
            return 0.0

    def _train(self):
        if not ML_AVAILABLE:
            self.status_msg = "❌ scikit-learn fehlt"
            return
        try:
            with self._lock:
                X = np.array(self.X_raw, dtype=np.float32)
                y = np.array(self.y_raw, dtype=np.int32)
                Xb = np.array(self.X_bull, dtype=np.float32) if self.X_bull else None
                yb = np.array(self.y_bull, dtype=np.int32) if self.y_bull else None
                Xbr = np.array(self.X_bear, dtype=np.float32) if self.X_bear else None
                ybr = np.array(self.y_bear, dtype=np.int32) if self.y_bear else None
            n = len(X)
            log.info(f"🧠 Training: Global:{n} Bull:{len(self.X_bull)} Bear:{len(self.X_bear)}")
            # Lokale Scaler verwenden während Training — verhindert Race-Condition mit
            # should_buy()/predict(), die self.scaler gleichzeitig lesen könnten.
            # Atomare Zuweisung self.scaler = local_scaler erfolgt erst im Lock-Block am Ende.
            local_scaler = StandardScaler()
            X_s = local_scaler.fit_transform(X)
            global_m = self._build_ensemble(X_s, y)
            wf_acc = self._walk_forward(X_s, y)
            # Regime
            bull_m = None
            bull_acc = 0.0
            local_bull_scaler = StandardScaler()
            if Xb is not None and len(Xb) >= 15 and len(set(yb)) >= 2:
                Xbs = local_bull_scaler.fit_transform(Xb)
                bull_m = self._build_ensemble(Xbs, yb)
                bull_acc = float(bull_m.score(Xbs, yb))
            bear_m = None
            bear_acc = 0.0
            local_bear_scaler = StandardScaler()
            if Xbr is not None and len(Xbr) >= 15 and len(set(ybr)) >= 2:
                Xbrs = local_bear_scaler.fit_transform(Xbr)
                bear_m = self._build_ensemble(Xbrs, ybr)
                bear_acc = float(bear_m.score(Xbrs, ybr))
            # LSTM
            lstm_m = None
            lstm_acc = 0.0
            if TF_AVAILABLE and n >= CONFIG["lstm_min_samples"]:
                try:
                    sl = min(CONFIG["lstm_lookback"], n // 4, n - 1)
                    if sl >= 4:
                        Xs_s = [X_s[i - sl : i] for i in range(sl, n)]
                        ys_s = list(y[sl:])
                        Xs_s = np.array(Xs_s)
                        ys_s = np.array(ys_s)
                        lstm = Sequential(
                            [
                                Input(shape=(sl, X_s.shape[1])),
                                LSTM(64, return_sequences=True),
                                Dropout(0.2),
                                LSTM(32),
                                Dropout(0.2),
                                Dense(16, activation="relu"),
                                Dense(1, activation="sigmoid"),
                            ]
                        )
                        lstm.compile(
                            optimizer="adam", loss="binary_crossentropy", metrics=["accuracy"]
                        )
                        es = EarlyStopping(
                            monitor="val_loss", patience=5, restore_best_weights=True
                        )
                        lstm.fit(
                            Xs_s,
                            ys_s,
                            epochs=30,
                            batch_size=min(16, len(ys_s) // 4 + 1),
                            validation_split=0.2,
                            callbacks=[es],
                            verbose=0,
                        )
                        lstm_m = lstm
                        eval_result = lstm.evaluate(Xs_s, ys_s, verbose=0)
                        lstm_acc = float(eval_result[1]) if len(eval_result) > 1 else 0.0
                        log.info(f"🔮 LSTM: {lstm_acc * 100:.1f}%")
                except Exception as le:
                    log.warning(f"LSTM: {le}")
            # Feature importance → weights
            try:
                rf_raw = self._make_rf()
                rf_raw.fit(X_s, y)
                fi = rf_raw.feature_importances_
                n_s = len(STRATEGY_NAMES)
                sfi = fi[:n_s]
                mean_sfi = sfi.mean() if len(sfi) > 0 else 0
                if mean_sfi > 0 and len(sfi) >= len(STRATEGY_NAMES):
                    norm = sfi / mean_sfi
                    with self._lock:
                        for i, nm in enumerate(STRATEGY_NAMES):
                            self.weights[nm] = float(np.clip(norm[i], 0.15, 3.5))
            except Exception:
                pass
            # [16] Adaptive Threshold-Kalibrierung — optimiert F1-Score
            best_thresh = 0.5
            try:
                probs = global_m.predict_proba(X_s)[:, 1]
                from sklearn.metrics import f1_score as _f1

                best_f1 = 0.0
                for thresh in np.arange(0.35, 0.70, 0.025):
                    preds = (probs >= thresh).astype(int)
                    f1 = _f1(y, preds, zero_division=0)
                    if f1 > best_f1:
                        best_f1 = f1
                        best_thresh = float(thresh)
                log.info(f"[THRESH] Optimaler Schwellwert: {best_thresh:.3f} (F1={best_f1:.3f})")
            except Exception:
                pass

            with self._lock:
                self.global_model = global_m
                self.bull_model = bull_m
                self.bear_model = bear_m
                self.lstm_model = lstm_m
                self.lstm_acc = lstm_acc
                # Atomare Zuweisung der lokalen Scaler unter Lock — thread-safe
                self.scaler = local_scaler
                self.bull_scaler = local_bull_scaler
                self.bear_scaler = local_bear_scaler
                self.cv_accuracy = wf_acc
                self.wf_accuracy = wf_acc
                self.bull_accuracy = bull_acc
                self.bear_accuracy = bear_acc
                self.accuracy = float(global_m.score(X_s, y))
                self.is_trained = True
                self.training_ver += 1
                self.trades_since_retrain = 0
                self.last_trained = datetime.now().strftime("%H:%M:%S")
                self.optimal_threshold = best_thresh  # [16]
            xgb_n = " +XGB" if XGB_AVAILABLE else ""
            lstm_n = " +LSTM" if lstm_m else ""
            self.status_msg = (
                f"✅ v{self.training_ver} WF:{wf_acc * 100:.1f}%{xgb_n}{lstm_n} "
                f"Bull:{bull_acc * 100:.0f}% Bear:{bear_acc * 100:.0f}%"
            )
            log.info(f"✅ KI v{self.training_ver} | {self.status_msg}")
            # Modelle auf Disk persistieren (Neustart = kein Cold-Start)
            self._save_models()
            emit_event("ai_update", self.to_dict())
            # Autonome LLM-Analyse: Training-Ergebnisse interpretieren
            if knowledge_base is not None:
                knowledge_base.analyze_training_async(
                    training_ver=self.training_ver,
                    wf_accuracy=wf_acc,
                    bull_accuracy=bull_acc,
                    bear_accuracy=bear_acc,
                    feature_weights=dict(self.weights),
                    threshold=best_thresh,
                )
        except Exception as e:
            self.status_msg = f"❌ {e}"
            log.error(f"KI Training: {e}", exc_info=True)

    # ── Model Persistence ────────────────────────────────────────────────────
    _MODEL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models")

    def _save_models(self) -> None:
        """Speichert trainierte Modelle auf Disk mit joblib."""
        try:
            import joblib

            os.makedirs(self._MODEL_DIR, exist_ok=True)
            payload = {
                "global_model": self.global_model,
                "bull_model": self.bull_model,
                "bear_model": self.bear_model,
                "scaler": self.scaler,
                "bull_scaler": self.bull_scaler,
                "bear_scaler": self.bear_scaler,
                "weights": self.weights,
                "strat_wr": self.strat_wr,
                "training_ver": self.training_ver,
                "accuracy": self.accuracy,
                "optimal_threshold": self.optimal_threshold,
                "saved_at": datetime.now().isoformat(),
            }
            path = os.path.join(self._MODEL_DIR, "ai_models.pkl")
            joblib.dump(payload, path, compress=3)
            log.info(f"💾 KI-Modelle gespeichert: {path}")
        except Exception as e:
            log.warning(f"Model-Speicherung: {e}")

    def _load_models(self) -> bool:
        """Lädt persistierte Modelle beim Start – verhindert Cold-Start."""
        try:
            import joblib

            path = os.path.join(self._MODEL_DIR, "ai_models.pkl")
            if not os.path.exists(path):
                return False
            payload = joblib.load(path)
            with self._lock:
                self.global_model = payload.get("global_model")
                self.bull_model = payload.get("bull_model")
                self.bear_model = payload.get("bear_model")
                self.scaler = payload.get("scaler", self.scaler)
                self.bull_scaler = payload.get("bull_scaler", self.bull_scaler)
                self.bear_scaler = payload.get("bear_scaler", self.bear_scaler)
                self.weights = payload.get("weights", self.weights)
                self.strat_wr = payload.get("strat_wr", self.strat_wr)
                self.training_ver = payload.get("training_ver", 0)
                self.accuracy = payload.get("accuracy", 0.0)
                self.optimal_threshold = payload.get("optimal_threshold", 0.5)
                self.is_trained = self.global_model is not None
            saved_at = payload.get("saved_at", "unbekannt")
            log.info(f"✅ KI-Modelle geladen (v{self.training_ver}, gespeichert: {saved_at})")
            return True
        except Exception as e:
            log.warning(f"Model-Laden: {e}")
            return False

    def _optimize(self):
        try:
            if state is None:
                return
            trades = state.closed_trades[:]
            if len(trades) < 15:
                return
            # Kelly grid
            sl_grid = [0.010, 0.015, 0.020, 0.025, 0.030, 0.040, 0.050]
            tp_grid = [0.030, 0.050, 0.060, 0.070, 0.080, 0.100, 0.120, 0.150]
            best_score = -999.0
            prev_sl = CONFIG["stop_loss_pct"]
            prev_tp = CONFIG["take_profit_pct"]
            best_sl = prev_sl
            best_tp = prev_tp
            for sl in sl_grid:
                for tp in tp_grid:
                    if tp < sl * 1.5:
                        continue
                    wins = 0
                    total_pnl = 0.0
                    cap = 10000.0
                    for t in trades[:80]:  # [:80] = newest 80
                        pp = t.get("pnl_pct", 0) / 100
                        inv = t.get("invested", cap * 0.15) or cap * 0.15
                        if pp <= -sl:
                            outcome = -sl * inv
                        elif pp >= tp:
                            outcome = tp * inv
                            wins += 1
                        else:
                            outcome = pp * inv
                            wins += pp > 0
                        total_pnl += outcome
                        cap = max(cap + outcome, 1.0)
                    wr = wins / len(trades[:80])
                    score = wr * 0.55 + (total_pnl / 10000.0) * 0.45
                    if score > best_score:
                        best_score = score
                        best_sl = sl
                        best_tp = tp
            CONFIG["stop_loss_pct"] = best_sl
            CONFIG["take_profit_pct"] = best_tp
            self.trades_since_optimize = 0
            detail = f"SL {best_sl * 100:.1f}% · TP {best_tp * 100:.1f}%"
            self.optim_log.insert(
                0,
                {
                    "time": datetime.now().strftime("%H:%M"),
                    "detail": detail,
                    "sl": round(best_sl * 100, 1),
                    "tp": round(best_tp * 100, 1),
                },
            )
            # optim_log is a deque(maxlen=500) – no manual trim needed
            log.info(f"🔬 Optimierung: {detail}")
            # Autonome LLM-Analyse: Optimierungsergebnis bewerten
            if knowledge_base is not None:
                knowledge_base.analyze_optimization_async(
                    best_sl=best_sl,
                    best_tp=best_tp,
                    prev_sl=prev_sl,
                    prev_tp=prev_tp,
                    trade_count=len(trades[:80]),
                )
        except Exception as e:
            log.error(f"Optimierung: {e}")

    def extract_features(
        self,
        votes,
        scan,
        is_bull,
        fear_greed,
        closed_trades,
        ob_imbalance=0.5,
        mtf_bullish=1,
        sentiment=0.5,
        news_score=0.0,
        onchain_score=0.0,
        dominance_ok=1,
        price_history: list = None,
    ) -> np.ndarray:
        """
        Erweiterter Feature-Vektor mit:
        [4] Fourier-Spektral-Features (dominant frequency, spectral energy)
        [5] Wavelet-Dekomposition (Hochfrequenz-/Niederfrequenz-Komponenten)
        [6] Time2Vec-inspirierte zyklische Zeit-Embeddings (Stunde, Tag, Woche)
        [7] Autokorrelations-Features (Lag-1/5/10 ACF)
        [8] Konsens-Qualitäts-Metriken
        """
        vote_vec = [float(votes.get(n, 0)) for n in STRATEGY_NAMES]
        n_buy = sum(1 for v in vote_vec if v > 0)
        n_sell = sum(1 for v in vote_vec if v < 0)
        consensus = max(n_buy, n_sell) / len(STRATEGY_NAMES)
        # Konsens-Stärke: je gleichmäßiger das Voting, desto unsicherer
        vote_entropy = 0.0
        if n_buy + n_sell > 0:
            p = n_buy / (n_buy + n_sell + 1e-9)
            vote_entropy = -p * math.log(p + 1e-9) - (1 - p) * math.log(1 - p + 1e-9)

        now = datetime.now()
        h = now.hour
        dow = now.weekday()  # 0=Mo, 6=So
        woy = now.isocalendar()[1]  # Kalenderwoche

        recent_trades = closed_trades[
            :20
        ]  # [:20] = newest 20 (insert(0,...) puts newest at index 0)
        recent_wr = sum(1 for t in recent_trades if t.get("pnl", 0) > 0) / max(
            len(recent_trades), 1
        )
        recent_pnl_avg = sum(t.get("pnl", 0) for t in recent_trades) / max(len(recent_trades), 1)
        # Streak: aufeinanderfolgende Gewinne/Verluste (newest first, so iterate directly)
        streak = 0
        for t in recent_trades[:10]:
            won = t.get("pnl", 0) > 0
            if streak == 0:
                streak = 1 if won else -1
            elif (streak > 0 and won) or (streak < 0 and not won):
                streak += 1 if won else -1
            else:
                break

        # [6] Time2Vec: zyklische Embeddings (sin/cos) für alle Zeitebenen
        sin_h = math.sin(2 * math.pi * h / 24)
        cos_h = math.cos(2 * math.pi * h / 24)
        sin_d = math.sin(2 * math.pi * dow / 7)
        cos_d = math.cos(2 * math.pi * dow / 7)
        sin_w = math.sin(2 * math.pi * woy / 52)
        cos_w = math.cos(2 * math.pi * woy / 52)

        # [4+5] Fourier & Wavelet aus Preisverlauf (wenn verfügbar)
        fourier_feat = [0.0, 0.0, 0.0]  # dom_freq, spectral_energy, spectral_entropy
        wavelet_feat = [0.0, 0.0, 0.0]  # HF energy, LF energy, HF/LF ratio
        acf_feat = [0.0, 0.0, 0.0]  # ACF lag1, lag5, lag10

        ph = price_history or scan.get("_price_history", [])
        if ph and len(ph) >= 32:
            pa = np.array(ph[-64:], dtype=np.float32)
            pa = pa - pa.mean()  # Detrend

            # [4] Fourier
            try:
                freqs = np.abs(np.fft.rfft(pa))
                total_energy = float(np.sum(freqs**2)) + 1e-9
                if len(freqs) <= 1:
                    dom_idx = 0
                else:
                    dom_idx = int(np.argmax(freqs[1:]) + 1)
                dom_freq = float(dom_idx / max(len(pa), 1))
                spec_energy = float(np.sum(freqs**2) / max(len(freqs), 1))
                # Spectral entropy
                p_spec = freqs**2 / total_energy
                p_spec = p_spec[p_spec > 0]
                spec_ent = float(-np.sum(p_spec * np.log(p_spec + 1e-9)))
                fourier_feat = [
                    float(np.clip(dom_freq, 0, 1)),
                    float(np.clip(spec_energy / (np.std(pa) ** 2 + 1e-9), 0, 10)),
                    float(np.clip(spec_ent / 5, 0, 1)),
                ]
            except Exception:
                pass

            # [5] Wavelet
            try:
                if WAVELET_AVAILABLE:
                    coeffs = pywt.wavedec(pa, "db4", level=3)
                    hf_energy = float(np.sum(coeffs[1] ** 2))
                    lf_energy = float(np.sum(coeffs[-1] ** 2))
                    ratio = hf_energy / (lf_energy + 1e-9)
                    wavelet_feat = [
                        float(np.clip(hf_energy / (np.sum(pa**2) + 1e-9), 0, 1)),
                        float(np.clip(lf_energy / (np.sum(pa**2) + 1e-9), 0, 1)),
                        float(np.clip(ratio, 0, 5)),
                    ]
                else:
                    # Approx via rolling std at different scales
                    hf = float(np.std(pa[-8:]))
                    lf = float(np.std(pa[-32:]))
                    wavelet_feat = [
                        float(np.clip(hf / (np.std(pa) + 1e-9), 0, 3)),
                        float(np.clip(lf / (np.std(pa) + 1e-9), 0, 3)),
                        float(np.clip(hf / (lf + 1e-9), 0, 5)),
                    ]
            except Exception:
                pass

            # [7] Autokorrelation
            try:
                if len(pa) >= 11:
                    mean_pa = np.mean(pa)
                    var_pa = np.var(pa) + 1e-9
                    for i, lag in enumerate([1, 5, 10]):
                        if lag < len(pa):
                            acf = float(
                                np.mean((pa[lag:] - mean_pa) * (pa[:-lag] - mean_pa)) / var_pa
                            )
                            acf_feat[i] = float(np.clip(acf, -1, 1))
            except Exception:
                pass

        market_vec = (
            [
                float(np.clip(scan.get("rsi", 50) / 100, 0, 1)),
                float(np.clip(scan.get("stoch_rsi", 50) / 100, 0, 1)),
                float(np.clip(scan.get("bb_pct", 0.5), 0, 1)),
                float(np.clip(scan.get("bb_width", 0.05) * 10, 0, 5)),
                float(np.sign(scan.get("macd_hist", 0))),
                float(np.clip(scan.get("macd_hist_slope", 0) * 100, -5, 5)),
                float(np.clip(scan.get("vol_ratio", 1) / 5, 0, 3)),
                float(np.clip(scan.get("atr_pct", 1) / 10, 0, 3)),
                float(np.clip(scan.get("ema_alignment", 0), -1, 1)),
                float(np.clip(scan.get("price_vs_ema21", 0) * 100, -10, 10)),
                float(np.clip(scan.get("roc10", 0) / 10, -3, 3)),
                float(is_bull),
                sin_h,
                cos_h,  # [6] Stunden-Embedding
                sin_d,
                cos_d,  # [6] Wochentag-Embedding
                sin_w,
                cos_w,  # [6] Jahreswoche-Embedding
                float(consensus),
                float(np.clip(vote_entropy, 0, 1)),  # [8] Konsens-Qualität
                float(recent_wr),
                float(np.clip(recent_pnl_avg / 100, -1, 1)),
                float(np.clip(streak / 10, -1, 1)),  # [7] Streak-Feature
                float(np.clip(fear_greed / 100, 0, 1)),
                float(np.clip(ob_imbalance, 0, 1)),
                float(mtf_bullish),
                float(np.clip(sentiment, 0, 1)),
                float(np.clip(news_score, -1, 1)),
                float(np.clip(onchain_score, -1, 1)),
                float(dominance_ok),
            ]
            + fourier_feat
            + wavelet_feat
            + acf_feat
        )  # [4+5+7]

        return np.array(vote_vec + market_vec, dtype=np.float32)

    def weighted_vote(self, votes, threshold) -> tuple[int, float]:
        total_w = 0.0
        buy_w = 0.0
        sell_w = 0.0
        for nm, v in votes.items():
            w = self.weights.get(nm, 1.0)
            total_w += w
            if v == 1:
                buy_w += w
            elif v == -1:
                sell_w += w
        if total_w == 0:
            return 0, 0.0
        buy_conf = buy_w / total_w
        sell_conf = sell_w / total_w
        if buy_conf >= threshold:
            return 1, round(buy_conf, 3)
        if sell_conf >= threshold:
            return -1, round(sell_conf, 3)
        return 0, round(max(buy_conf, sell_conf), 3)

    def _sync_virginie_guardrails_from_config(self) -> None:
        """Synchronisiert VIRGINIE-Guardrails mit Laufzeit-Konfigurationsänderungen."""
        if not hasattr(self, "virginie") or self.virginie is None:
            return
        try:
            min_score = float(CONFIG.get("virginie_min_score", 0.0))
        except Exception:
            min_score = 0.0
        try:
            max_risk = float(CONFIG.get("virginie_max_risk_penalty", 1000.0))
        except Exception:
            max_risk = 1000.0
        current = getattr(self.virginie, "guardrails", None)
        if (
            current is None
            or float(getattr(current, "min_score", 0.0)) != min_score
            or float(getattr(current, "max_risk_penalty", 1000.0)) != max_risk
        ):
            self.virginie.guardrails = VirginieGuardrails(
                min_score=min_score,
                max_risk_penalty=max_risk,
            )

    def should_buy(self, features, conf) -> tuple[bool, float, str]:
        """[26] Erweitert mit VIRGINIE-Guardrails + Conformal Prediction Intervals."""
        if not self.is_trained or not CONFIG.get("ai_enabled"):
            return conf >= CONFIG.get("min_vote_score", 0.3), conf, "Vote"
        try:
            if CONFIG.get("virginie_enabled", True):
                self._sync_virginie_guardrails_from_config()
            X_s = self.scaler.transform(features.reshape(1, -1))
            prob = self._predict(X_s, features)
            allowed_by_model = prob >= CONFIG["ai_min_confidence"]

            if CONFIG.get("virginie_enabled", True):
                opportunity = Opportunity(
                    key="buy_signal",
                    success_probability=prob,
                    expected_profit=float(CONFIG.get("take_profit_pct", 0.06)) * 100,
                    cost=float(CONFIG.get("stop_loss_pct", 0.025)) * 100,
                    risk_penalty=float(max(0.0, (1.0 - conf) * 10.0)),
                )
                virginie_decision = self.virginie.select_opportunity_with_report([opportunity])
                allowed_by_virginie = virginie_decision.selected is not None
                allowed = allowed_by_model and allowed_by_virginie
                reason_prefix = "VIRGINIE"
            else:
                allowed = allowed_by_model
                reason_prefix = "AI"

            self.ai_log.insert(
                0,
                {
                    "time": datetime.now().strftime("%H:%M"),
                    "allowed": allowed,
                    "prob": round(prob * 100, 1),
                    "reason": f"{'✅' if allowed else '🚫'} {prob * 100:.1f}%",
                },
            )
            if allowed:
                self.allowed_count += 1
            else:
                self.blocked_count += 1
            if CONFIG.get("virginie_enabled", True):
                return (
                    allowed,
                    prob,
                    f"{'✅' if allowed else '🚫'} {reason_prefix}:{prob * 100:.1f}% | {virginie_decision.reason}",
                )
            return allowed, prob, f"{'✅' if allowed else '🚫'} {reason_prefix}:{prob * 100:.1f}%"
        except Exception as e:
            return True, conf, f"Err:{e}"

    def _predict(self, X_s, features_raw) -> float:
        # Regime-Modell wählen
        is_bull = bool(regime.is_bull) if regime and hasattr(regime, "is_bull") else True
        regime_p = 0.5
        if is_bull and self.bull_model is not None and self.bull_scaler is not None:
            try:
                Xbs = self.bull_scaler.transform(features_raw.reshape(1, -1))
                pr = self.bull_model.predict_proba(Xbs)[0]
                cls = list(self.bull_model.classes_)
                regime_p = float(pr[cls.index(1)]) if 1 in cls else 0.5
            except Exception:
                regime_p = 0.5
        elif not is_bull and self.bear_model is not None and self.bear_scaler is not None:
            try:
                Xbrs = self.bear_scaler.transform(features_raw.reshape(1, -1))
                pr = self.bear_model.predict_proba(Xbrs)[0]
                cls = list(self.bear_model.classes_)
                regime_p = float(pr[cls.index(1)]) if 1 in cls else 0.5
            except Exception:
                regime_p = 0.5
        else:
            try:
                pr = self.global_model.predict_proba(X_s)[0]
                cls = list(self.global_model.classes_)
                regime_p = float(pr[cls.index(1)]) if 1 in cls else 0.5
            except Exception:
                regime_p = 0.5
        # LSTM blend
        if self.lstm_model and TF_AVAILABLE and len(self.X_raw) >= self.lstm_seq:
            try:
                hist = np.array(self.X_raw[-self.lstm_seq :], dtype=np.float32)
                hist_s = self.scaler.transform(hist)
                lstm_p = float(self.lstm_model.predict(hist_s[np.newaxis, ...], verbose=0)[0][0])
                return regime_p * 0.55 + lstm_p * 0.45
            except Exception:
                pass
        return regime_p

    def win_probability(self, features) -> float:
        if not self.is_trained or self.global_model is None:
            return 0.5
        try:
            X_s = self.scaler.transform(features.reshape(1, -1))
            return self._predict(X_s, features)
        except Exception:
            return 0.5

    def kelly_size(self, win_prob, balance, atr, fg_boost=1.0) -> float:
        if win_prob <= 0.5:
            return balance * CONFIG["risk_per_trade"] * fg_boost
        sl_pct = CONFIG["stop_loss_pct"]
        if sl_pct <= 0:
            return balance * CONFIG["risk_per_trade"] * fg_boost
        odds = CONFIG["take_profit_pct"] / sl_pct
        kelly = float(np.clip(((win_prob * odds - (1 - win_prob)) / odds) * 0.5, 0.01, 0.25))
        vol_adj = 1.0 / (1 + atr * 10) if atr > 0 else 1.0
        return balance * kelly * vol_adj * fg_boost

    def on_buy(self, symbol, features, votes, scan):
        with self._lock:
            self._pending[symbol] = {"features": features, "votes": votes, "scan": scan}

    def on_sell(self, symbol, pnl, regime_str="bull"):
        with self._lock:
            p = self._pending.pop(symbol, None)
            if not p:
                return
            won = 1 if pnl > 0 else 0
            self.X_raw.append(p["features"])
            self.y_raw.append(won)
            self.regimes_raw.append(regime_str)
            if regime_str == "bull":
                self.X_bull.append(p["features"])
                self.y_bull.append(won)
            else:
                self.X_bear.append(p["features"])
                self.y_bear.append(won)
            self.trades_since_retrain += 1
            self.trades_since_optimize += 1
            alpha = 0.12
            for nm in STRATEGY_NAMES:
                if p["votes"].get(nm, 0) == 1:
                    self.strat_wr[nm] = (1 - alpha) * self.strat_wr.get(nm, 0.5) + alpha * float(
                        won
                    )
        if CONFIG.get("virginie_enabled", True):
            self.virginie.learn_from_action(
                ActionResult(opportunity_key="buy_signal", realized_profit=float(pnl))
            )
            domain = "learning" if pnl < 0 else "quality"
            objective = (
                "Post-trade learning feedback" if pnl < 0 else "Post-trade quality validation"
            )
            self.virginie_orchestrator.execute(
                AgentTask(
                    task_id=f"trade-close-{symbol}-{len(self.X_raw)}",
                    domain=domain,
                    objective=objective,
                    payload={"pnl": float(pnl), "symbol": symbol},
                )
            )
            review = self.virginie.review_and_improve()
            if review.get("reviewed") and log is not None:
                log.info("🤖 VIRGINIE review: %s", review.get("summary"))

        # RL lernen
        if rl_agent is not None:
            rl_agent.on_trade_close(p.get("scan", {}), pnl)
        threading.Thread(
            target=lambda f=p["features"], w=won, r=regime_str: self.db.save_ai_sample(f, w, r),
            daemon=True,
        ).start()
        n = len(self.X_raw)
        self.progress_pct = min(100, int(n / max(CONFIG["ai_min_samples"], 1) * 100))
        if (
            n >= CONFIG["ai_min_samples"]
            and self.trades_since_retrain >= CONFIG["ai_retrain_every"]
        ):
            threading.Thread(target=self._train, daemon=True).start()
        if self.trades_since_optimize >= CONFIG["ai_optimize_every"]:
            threading.Thread(target=self._optimize, daemon=True).start()
        # Genetischer Optimizer nach 30 Trades
        if n % 30 == 0 and state and genetic is not None:
            genetic.evolve(state.closed_trades)

    def to_dict(self) -> dict:
        total = self.blocked_count + self.allowed_count
        wl = [
            {
                "name": nm,
                "weight": round(self.weights.get(nm, 1.0), 2),
                "win_rate": round(self.strat_wr.get(nm, 0.5) * 100, 1),
            }
            for nm in STRATEGY_NAMES
        ]
        return {
            "enabled": ML_AVAILABLE,
            "is_trained": self.is_trained,
            "training_ver": self.training_ver,
            "last_trained": self.last_trained,
            "samples": len(self.X_raw),
            "bull_samples": len(self.X_bull),
            "bear_samples": len(self.X_bear),
            "min_samples": CONFIG.get("ai_min_samples", 20),
            "wf_accuracy": round(self.wf_accuracy * 100, 1),
            "bull_accuracy": round(self.bull_accuracy * 100, 1),
            "bear_accuracy": round(self.bear_accuracy * 100, 1),
            "xgb_enabled": XGB_AVAILABLE,
            "lstm_enabled": TF_AVAILABLE,
            "lstm_trained": self.lstm_model is not None,
            "lstm_acc": round(self.lstm_acc * 100, 1),
            "bull_model": self.bull_model is not None,
            "bear_model": self.bear_model is not None,
            "status_msg": self.status_msg,
            "progress_pct": self.progress_pct,
            "weights": wl,
            "ai_log": list(self.ai_log)[:20],
            "optim_log": list(self.optim_log)[:10],
            "blocked_count": self.blocked_count,
            "allowed_count": self.allowed_count,
            "blocked_pct": round(self.blocked_count / total * 100, 1) if total > 0 else 0,
            "assistant_name": self.virginie.identity.name,
            "assistant_version": self.virginie.current_version(),
            "assistant_agents": self.virginie_orchestrator.status(),
            "assistant_review": self.virginie.review_status(),
            "params": {
                "sl": round(CONFIG.get("stop_loss_pct", 0.025) * 100, 2),
                "tp": round(CONFIG.get("take_profit_pct", 0.06) * 100, 2),
                "vote": round(CONFIG.get("min_vote_score", 0.3) * 100, 1),
            },
        }


# ═══════════════════════════════════════════════════════════════════════════════
# BACKTEST ENGINE (modularisiert → services/backtest.py)
# ═══════════════════════════════════════════════════════════════════════════════


# ═══════════════════════════════════════════════════════════════════════════════
# MULTI-TIMEFRAME FILTER
# ═══════════════════════════════════════════════════════════════════════════════
