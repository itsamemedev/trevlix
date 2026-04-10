"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║    ████████╗██████╗ ███████╗██╗   ██╗██╗     ██╗██╗  ██╗                   ║
║    ╚══██╔══╝██╔══██╗██╔════╝██║   ██║██║     ██║╚██╗██╔╝                   ║
║       ██║   ██████╔╝█████╗  ██║   ██║██║     ██║ ╚███╔╝                    ║
║       ██║   ██╔══██╗██╔══╝  ╚██╗ ██╔╝██║     ██║ ██╔██╗                    ║
║       ██║   ██║  ██║███████╗ ╚████╔╝ ███████╗██║██╔╝ ██╗                   ║
║       ╚═╝   ╚═╝  ╚═╝╚══════╝  ╚═══╝  ╚══════╝╚═╝╚═╝  ╚═╝                   ║
║                                                                              ║
║    Algorithmic Crypto Trading Bot  ·  v1.7.1  ·  trevlix.dev               ║
║                                                                              ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  KERN-ENGINE                                                                 ║
║  · MySQL Datenbank       · Fear & Greed Index    · Multi-Timeframe          ║
║  · XGBoost + Random Forest · LSTM Ensemble      · Walk-Forward Optim.       ║
║  · Regime-Modelle (Bull/Bear) · Kelly-Sizing    · Orderbook Imbalance       ║
║  · Circuit Breaker       · Trailing Stop         · Korrelations-Filter       ║
║  · Liquidity Check       · Tages-Report          · Auto-Backup               ║
║                                                                              ║
║  UNIQUE FEATURES                                                             ║
║  · Trade DNA             – 7D-Fingerprint + Pattern Mining für Trades       ║
║  · Smart Exits           – ATR-basierte volatilitätsadaptive SL/TP          ║
║  · KI-Gemeinschaftswissen – LLM-Anbindung + Shared Knowledge Base          ║
║                                                                              ║
║  TRADING-FEATURES                                                            ║
║  · News-Sentiment        – CryptoPanic Echtzeit-Nachrichten als KI-Signal   ║
║  · On-Chain Daten        – Whale-Alarm, Exchange-Flows (CryptoQuant)        ║
║  · BTC/USDT Dominanz     – Automatische Marktphasen-Erkennung               ║
║  · Anomalie-Erkennung    – Isolation Forest stoppt bei Flash-Crash          ║
║  · Genetischer Optimizer – Evolutionäre Strategie-Entdeckung                ║
║  · Reinforcement Learning – PPO-Agent lernt direkt vom Markt                ║
║  · Partial Take-Profit   – Stufenweiser Gewinnmitnahme (25/50/100%)        ║
║  · DCA Strategie         – Nachkaufen bei fallenden Positionen              ║
║  · Short-Selling         – Bearish-Trades auf Futures (Binance/Bybit)       ║
║  · Arbitrage-Scanner     – Preisunterschiede zwischen Exchanges nutzen      ║
║  · REST-API + JWT        – Externe Tools & TradingView-Webhooks             ║
║  · Multi-User System     – Mehrere Portfolios auf einer Instanz             ║
║                                                                              ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  pip install flask flask-socketio flask-cors ccxt pandas numpy               ║
║    scikit-learn xgboost tensorflow ta python-dotenv eventlet requests        ║
║    PyMySQL PyJWT bcrypt httpx                                                ║
║                                                                              ║
║  .env:  MYSQL_HOST=localhost  MYSQL_USER=root  MYSQL_PASS=geheim            ║
║         MYSQL_DB=trevlix      ADMIN_PASSWORD=<secure>                       ║
║         ENCRYPTION_KEY=...    JWT_SECRET=...                                 ║
║                                                                              ║
║  MySQL:  CREATE DATABASE trevlix CHARACTER SET utf8mb4;                     ║
║  Start:  python server.py  →  http://localhost:5000                         ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import json
import os
import threading
import time
import uuid
from collections import deque
from datetime import datetime
from typing import Any

import numpy as np
import requests
from dotenv import load_dotenv
from flask import (
    Response,
    g,
    jsonify,
    request,
    send_file,
    session,
)
from flask_socketio import emit

from app.core.admin_exchange import (
    get_admin_exchange_by_name,
    get_admin_primary_exchange,
    get_exchange_key_states,
    pin_user_exchange,
)
from app.core.admin_password_policy import is_admin_password_weak
from app.core.admin_user_validation import validate_admin_user_payload
from app.core.ai_engine import AIEngine, init_ai_engine
from app.core.api_docs_schema import build_api_docs_payload
from app.core.app_setup import initialize_runtime_objects
from app.core.audit_writer import write_audit_entry
from app.core.auth_guards import (
    LoginAttemptTracker,
    build_admin_required,
    build_api_auth_required,
    build_dashboard_auth,
)
from app.core.backup_verify import verify_latest_backup
from app.core.bootstrap import (
    resolve_project_paths,
)

# ── Extracted modules ────────────────────────────────────────────────────────
from app.core.db_manager import MySQLManager, init_db_manager
from app.core.db_request_context import close_request_db_conn, get_request_db_conn
from app.core.default_config import build_default_config
from app.core.exchange_secret import is_single_exchange_mode, reveal_and_decrypt
from app.core.http_routes import register_default_blueprints, register_system_routes
from app.core.lifecycle import build_graceful_shutdown_handler, register_signal_handlers
from app.core.ml_models import (
    AnomalyDetector,
    GeneticOptimizer,
    NewsSentimentAnalyzer,
    RLAgent,
    init_ml_models,
)
from app.core.paper_mode import enforce_paper_trading
from app.core.prometheus_metrics import build_prometheus_lines
from app.core.request_helpers import (
    normalize_exchange_name as _normalize_exchange_name,
)
from app.core.request_helpers import (
    safe_bool,
    safe_float,
    safe_int,
)
from app.core.runtime import run_server
from app.core.security import (
    apply_security_headers as _apply_security_headers,
)
from app.core.security import (
    generate_csrf_token as _core_generate_csrf_token,
)
from app.core.session_guard import handle_session_and_csrf
from app.core.socket_emit import emit_socket_event
from app.core.socket_error_logger import log_socket_error
from app.core.startup_view import render_startup_banner
from app.core.tax_export import tax_rows_to_csv
from app.core.time_compat import UTC
from app.core.trade_export import trades_to_json
from app.core.trading_classes import (
    ArbitrageScanner,
    BackupScheduler,
    BotState,
    DailyReportScheduler,
    MultiTimeframeFilter,
    OrderbookImbalance,
    PriceAlertManager,
    ShortEngine,
    init_trading_classes,
)
from app.core.trading_ops import (
    _preflight_exchange_markets,
    bot_loop,
    close_position,
    create_exchange,
    fetch_aggregated_balance,
    fetch_markets,
    get_virginie_forecast_feed,
    get_exchange_fee_rate,
    get_heatmap_data,
    init_trading_ops,
    open_position,
    safety_scan,
    scan_symbol,
)
from app.core.websocket_authz import ws_admin_required, ws_auth_required
from app.core.websocket_guard import WsRateLimiter
from app.core.websocket_state import build_ws_state_snapshot
from app.core.ws_rate_gate import ws_rate_check
from services.adaptive_weights import AdaptiveWeights
from services.alert_escalation import AlertEscalationManager
from services.auto_healing import AutoHealingAgent
from services.cluster_control import ClusterController
from services.db_pool import ConnectionPool

# ── Service-Module ───────────────────────────────────────────────────────────
from services.encryption import decrypt_value, encrypt_value
from services.exchange_factory import (
    EXCHANGE_DEFAULT_FEES,
    create_ccxt_exchange,
)
from services.git_ops import GitOperationError
from services.git_ops import apply_update as _apply_update
from services.git_ops import get_update_status as _get_update_status
from services.git_ops import rollback_update as _rollback_update
from services.indicator_cache import get_cached as _ind_get
from services.indicator_cache import set_cached as _ind_set
from services.knowledge import KnowledgeBase
from services.market_data import (
    DominanceFilter,
    FearGreedIndex,
    MarketRegime,
    OnChainFetcher,
    SentimentFetcher,
)
from services.mcp_tools import MCPToolRegistry
from services.notifications import DiscordNotifier, TelegramNotifier
from services.performance_attribution import PerformanceAttribution
from services.redis_market_cache import RedisMarketCache
from services.revenue_tracking import RevenueTracker
from services.risk import (
    AdvancedRiskMetrics,
    FundingRateTracker,
    LiquidityScorer,
    RiskManager,
    SymbolCooldown,
)
from services.smart_exits import SmartExitEngine
from services.strategies import STRATEGIES, compute_indicators
from services.trade_dna import TradeDNA
from services.trading_algorithms import TradingAlgorithmManager
from services.trading_mode import TradingModeManager
from services.utils import (
    BOT_FULL,
    BOT_NAME,
    BOT_VERSION,
    EXCHANGE_MAP,
    validate_config,
)
from services.utils import make_secret as _secret

try:
    from flask_limiter import Limiter
    from flask_limiter.util import get_remote_address

    LIMITER_AVAILABLE = True
except ImportError:
    LIMITER_AVAILABLE = False

# ── ML (extracted to app/core/ai_engine.py + ml_models.py) ──────────────────

# ── MySQL ────────────────────────────────────────────────────────────────────
try:
    import pymysql
    import pymysql.cursors

    MYSQL_AVAILABLE = True
except ImportError:
    MYSQL_AVAILABLE = False

# ── JWT ──────────────────────────────────────────────────────────────────────
try:
    import jwt as pyjwt

    JWT_AVAILABLE = True
except ImportError:
    JWT_AVAILABLE = False

# ── bcrypt ───────────────────────────────────────────────────────────────────
try:
    import bcrypt

    BCRYPT_AVAILABLE = True
except ImportError:
    BCRYPT_AVAILABLE = False


load_dotenv()

# BOT_NAME, BOT_VERSION, BOT_FULL importiert aus services.utils

# ═══════════════════════════════════════════════════════════════════════════════
# APP
# ═══════════════════════════════════════════════════════════════════════════════
_BASE_DIR, _TEMPLATE_DIR, _STATIC_DIR = resolve_project_paths(__file__)
_BASE_DIR, app, socketio, limiter, log, _SESSION_TIMEOUT_MIN = initialize_runtime_objects(
    __file__,
    limiter_available=LIMITER_AVAILABLE,
    limiter_cls=Limiter if LIMITER_AVAILABLE else None,
    key_func=get_remote_address if LIMITER_AVAILABLE else None,
)


# SecretStr, _secret importiert aus services.utils


# ═══════════════════════════════════════════════════════════════════════════════
# KONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════
CONFIG: dict[str, Any] = build_default_config(_secret)


def _enforce_paper_trading(source: str = "system") -> None:
    """Legacy helper: nur aktiv wenn LIVE_TRADING_ENABLED nicht gesetzt ist."""
    if not safe_bool(os.getenv("LIVE_TRADING_ENABLED", "false"), False):
        enforce_paper_trading(CONFIG, log, source)


_enforce_paper_trading("startup")


# EXCHANGE_MAP importiert aus services.utils
# EXCHANGE_DEFAULT_FEES importiert aus services.exchange_factory
# STRATEGY_NAMES importiert aus services.strategies


# ═══════════════════════════════════════════════════════════════════════════════
# Sicherheitswarnung: Default-Passwort erkennen
# ═══════════════════════════════════════════════════════════════════════════════
if is_admin_password_weak(os.getenv("ADMIN_PASSWORD")):
    log.warning(
        "⚠️  ADMIN_PASSWORD ist nicht gesetzt oder unsicher! "
        "Setze ein starkes Passwort (min. 12 Zeichen) in .env: ADMIN_PASSWORD=..."
    )

# ═══════════════════════════════════════════════════════════════════════════════
# [Verbesserung #7] Konfigurationsvalidierung beim Start
# ═══════════════════════════════════════════════════════════════════════════════
# ═══════════════════════════════════════════════════════════════════════════════
# [#11] DEPENDENCY INJECTION FÜR DB-ZUGRIFF VIA FLASK g-OBJEKT
# Statt globalem `db`-Objekt kann get_db() in Request-Kontext genutzt werden.
# ═══════════════════════════════════════════════════════════════════════════════


def get_db():
    """Gibt eine DB-Verbindung aus dem Flask g-Objekt zurück.

    Im Request-Kontext wird die Verbindung einmalig erzeugt und am Ende
    des Requests automatisch zurück in den Pool gegeben (via teardown).
    Außerhalb von Requests wird direkt eine Pool-Verbindung zurückgegeben.

    Returns:
        Aktive Datenbankverbindung aus dem Connection-Pool.

    Example:
        @app.route('/api/data')
        def my_route():
            conn = get_db()
            with conn.cursor() as c:
                c.execute('SELECT 1')
    """
    return get_request_db_conn(flask_g=g, db=db, log=log)


@app.teardown_appcontext
def close_db_connection(exc: BaseException | None = None) -> None:
    """Gibt die DB-Verbindung am Ende jedes Requests zurück in den Pool.

    Args:
        exc: Optionale Exception, die den Request beendet hat.
    """
    close_request_db_conn(flask_g=g, log=log)


# validate_config importiert aus services.utils


# ═══════════════════════════════════════════════════════════════════════════════
# MYSQL MANAGER → extracted to app/core/db_manager.py
# ═══════════════════════════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════════════════════════
# [Verbesserung #1] SESSION TIMEOUT
# [Verbesserung #2] CSRF PROTECTION
# [Verbesserung #3] LOGIN BRUTE-FORCE SCHUTZ
# [Verbesserung #6] SECURITY HEADERS
# [Verbesserung #8] AUDIT-LOG HELPER
# ═══════════════════════════════════════════════════════════════════════════════
_login_attempt_tracker = LoginAttemptTracker()
_login_attempts = _login_attempt_tracker._attempts  # Backward-compatible alias for tests


def _check_login_rate(ip: str, max_attempts: int = 5, window: int = 60) -> bool:
    """[Verbesserung #3] Prüft ob IP zu viele Login-Versuche hatte."""
    return _login_attempt_tracker.check_rate(ip, max_attempts=max_attempts, window=window)


def _record_login_attempt(ip: str):
    _login_attempt_tracker.record_attempt(ip)


def _audit(action: str, detail: str = "", user_id: int = 0):
    """[Verbesserung #8] Audit-Log Hilfsfunktion."""
    write_audit_entry(
        db=db,
        log=log,
        request_obj=request,
        action=action,
        detail=detail,
        user_id=user_id,
    )


@app.before_request
def _before_request_hooks():
    """[Verbesserung #1] Session-Timeout + [Verbesserung #2] CSRF-Check."""
    return handle_session_and_csrf(
        session_obj=session,
        request_obj=request,
        session_timeout_min=_SESSION_TIMEOUT_MIN,
        audit_fn=_audit,
    )


@app.after_request
def _security_headers(response):
    """[Verbesserung #6] Security Headers."""
    return _apply_security_headers(response, is_secure=request.is_secure)


def normalize_exchange_name(raw: Any) -> str:
    """Normalisiert und validiert einen Exchange-Namen."""
    return _normalize_exchange_name(raw, EXCHANGE_MAP)


def _generate_csrf_token() -> str:
    """Kompatibler Wrapper für Jinja-Global/Tests."""
    return _core_generate_csrf_token(session)


app.jinja_env.globals["csrf_token"] = _generate_csrf_token


# ═══════════════════════════════════════════════════════════════════════════════
# JWT AUTH
# ═══════════════════════════════════════════════════════════════════════════════
def api_auth_required(f):
    return build_api_auth_required(db)(f)


dashboard_auth = build_dashboard_auth()


def admin_required(f):
    return build_admin_required(db)(f)


# ═══════════════════════════════════════════════════════════════════════════════
# DISCORD
# ═══════════════════════════════════════════════════════════════════════════════
# DiscordNotifier importiert aus services.notifications (siehe Instantiation unten)


# FearGreedIndex importiert aus services.market_data


# ═══════════════════════════════════════════════════════════════════════════════
# ML MODELS → extracted to app/core/ml_models.py
# AI ENGINE → extracted to app/core/ai_engine.py
# ═══════════════════════════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════════════════════════
# BACKTEST ENGINE (modularisiert → services/backtest.py)
# ═══════════════════════════════════════════════════════════════════════════════
from services.backtest import BacktestEngine as _BacktestEngineBase  # noqa: E402
from services.tax_report import TaxReportGenerator  # noqa: E402

# ═══════════════════════════════════════════════════════════════════════════════
# TRADING CLASSES → extracted to app/core/trading_classes.py
# ═══════════════════════════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════════════════════════
# GLOBALE INSTANZEN
# ═══════════════════════════════════════════════════════════════════════════════

# Initialize extracted module globals before instantiating objects
init_db_manager(
    config=CONFIG,
    logger=log,
    mysql_available=MYSQL_AVAILABLE,
    bcrypt_available=BCRYPT_AVAILABLE,
    jwt_available=JWT_AVAILABLE,
    pymysql_module=pymysql if MYSQL_AVAILABLE else None,
    bcrypt_module=bcrypt if BCRYPT_AVAILABLE else None,
    pyjwt_module=pyjwt if JWT_AVAILABLE else None,
    connection_pool_cls=ConnectionPool if MYSQL_AVAILABLE else None,
)

db = MySQLManager()

# Initialize extracted modules that need CONFIG early (before class instantiation)
init_ai_engine(config=CONFIG, logger=log)
init_ml_models(
    config=CONFIG,
    logger=log,
    db_ref=db,
    state_ref=None,
    discord_ref=None,
    emit_event_fn=None,
    fg_idx_ref=None,
)
init_trading_classes(config=CONFIG, logger=log, db_ref=db)


def _rehydrate_config_from_admin() -> None:
    """Überlagert CONFIG mit den in der DB gespeicherten Admin-Einstellungen.

    So bleiben Dashboard-Einstellungen nach einem Restart erhalten.
    """
    try:
        if not getattr(db, "db_available", False):
            return
        with db._get_conn() as conn:
            with conn.cursor() as c:
                c.execute("SELECT id FROM users WHERE role='admin' ORDER BY id ASC LIMIT 1")
                row = c.fetchone()
        if not row:
            return
        stored = db.get_user_settings(row["id"]) or {}
        if not isinstance(stored, dict) or not stored:
            return
        applied = 0
        for k, v in stored.items():
            if k in CONFIG:
                CONFIG[k] = v
                applied += 1
        if applied:
            log.info("⚙️  %d Einstellungen aus Admin-DB geladen", applied)
    except Exception as e:
        log.debug(f"_rehydrate_config_from_admin: {e}")


_rehydrate_config_from_admin()

knowledge_base = KnowledgeBase(
    db,
    llm_endpoint=os.getenv("LLM_ENDPOINT", ""),
    llm_api_key=os.getenv("LLM_API_KEY", ""),
    llm_model=os.getenv("LLM_MODEL", ""),
)
discord = DiscordNotifier(CONFIG, BOT_FULL)
fg_idx = FearGreedIndex(CONFIG)
dominance = DominanceFilter(CONFIG)
news_fetcher = NewsSentimentAnalyzer()
onchain = OnChainFetcher(db)
sentiment_f = SentimentFetcher(CONFIG, db)
anomaly = AnomalyDetector()
genetic = GeneticOptimizer()
rl_agent = RLAgent()
mtf = MultiTimeframeFilter()
ob = OrderbookImbalance()
tax = TaxReportGenerator(fee_rate=CONFIG.get("fee_rate", 0.001))
regime = MarketRegime(CONFIG)
risk = RiskManager(CONFIG, discord)
liq = LiquidityScorer(CONFIG)
bt = _BacktestEngineBase(compute_indicators, STRATEGIES, db.save_backtest)
price_alerts = PriceAlertManager()
arb_scanner = ArbitrageScanner()
short_engine = ShortEngine()
daily_sched = DailyReportScheduler()
backup_sched = BackupScheduler()
state = BotState(db)

# Globales Shutdown-Event: alle kooperativen Hintergrund-Threads prüfen dieses Event.
_SHUTDOWN_EVENT = threading.Event()
ai_engine = AIEngine(db)
_VIRGINIE_CHAT_MAX_MESSAGES = 80
_virginie_chat_lock = threading.Lock()
_virginie_chat_by_user: dict[int, deque[dict[str, Any]]] = {}

# ── MCP-Tool-Integration für KI ────────────────────────────────────────────
mcp_registry = MCPToolRegistry(
    db_manager=db,
    state=state,
    knowledge_base=knowledge_base,
    exchange_fn=None,  # Wird nach create_exchange gesetzt
    config=CONFIG,
)
knowledge_base.set_mcp_registry(mcp_registry)


def _idle_learning_loop() -> None:
    """Leerlauf-Lernen: hält KI↔LLM Kollaboration aktiv wenn Bot pausiert ist."""
    while not _SHUTDOWN_EVENT.is_set():
        try:
            if not getattr(state, "running", False) and hasattr(knowledge_base, "idle_learn_async"):
                knowledge_base.idle_learn_async(
                    regime_is_bull=bool(getattr(regime, "is_bull", True)),
                    fg_value=int(getattr(fg_idx, "value", 50) or 50),
                    open_positions=len(getattr(state, "positions", {}) or {}),
                    iteration=int(getattr(state, "iteration", 0) or 0),
                    min_interval_sec=600,
                )
        except Exception as exc:
            log.debug("Idle learning loop: %s", exc)
        _SHUTDOWN_EVENT.wait(120)


threading.Thread(target=_idle_learning_loop, daemon=True, name="IdleLearningLoop").start()

# ── Autonomous Agents (v1.5) ────────────────────────────────────────────────


def _virginie_chat_history_for_user(user_id: int) -> list[dict[str, Any]]:
    with _virginie_chat_lock:
        history = _virginie_chat_by_user.setdefault(
            int(user_id), deque(maxlen=_VIRGINIE_CHAT_MAX_MESSAGES)
        )
        return [dict(item) for item in history]


def _virginie_chat_append(user_id: int, role: str, content: str) -> dict[str, Any]:
    entry = {
        "id": uuid.uuid4().hex,
        "role": role,
        "content": str(content).strip(),
        "time": datetime.now(UTC).isoformat(),
    }
    with _virginie_chat_lock:
        history = _virginie_chat_by_user.setdefault(
            int(user_id), deque(maxlen=_VIRGINIE_CHAT_MAX_MESSAGES)
        )
        history.append(entry)
    return entry


def _virginie_runtime_status() -> dict[str, Any]:
    """Verdichteter VIRGINIE Status für API/Chat."""
    ai = ai_engine.to_dict() if ai_engine else {}
    assistant_agents = ai.get("assistant_agents", {}) if isinstance(ai, dict) else {}
    assistant_review = ai.get("assistant_review", {}) if isinstance(ai, dict) else {}
    return {
        "enabled": bool(CONFIG.get("virginie_enabled", True)),
        "primary_control": bool(CONFIG.get("virginie_primary_control", True)),
        "autonomy_weight": float(CONFIG.get("virginie_autonomy_weight", 0.7) or 0.7),
        "min_score": float(CONFIG.get("virginie_min_score", 0.0) or 0.0),
        "max_risk_penalty": float(CONFIG.get("virginie_max_risk_penalty", 1000.0) or 1000.0),
        "assistant_name": ai.get("assistant_name", "VIRGINIE"),
        "assistant_version": ai.get("assistant_version", "0.0.0"),
        "assistant_agents": assistant_agents if isinstance(assistant_agents, dict) else {},
        "assistant_review": assistant_review if isinstance(assistant_review, dict) else {},
    }


def _virginie_runtime_advice() -> dict[str, Any]:
    """Leitet konkrete nächste Schritte aus Runtime-Status ab."""
    status = _virginie_runtime_status()
    ai = ai_engine.to_dict() if ai_engine else {}
    wf = float(ai.get("wf_accuracy", 0) or 0)
    drift = float(ai.get("drift_score", 0) or 0)
    trained = bool(ai.get("is_trained", False))
    guardrail_min_score = float(status.get("min_score", 0) or 0)
    actions: list[dict[str, str]] = []
    if not status.get("enabled", True):
        actions.append(
            {
                "priority": "high",
                "title": "VIRGINIE aktivieren",
                "detail": "Setze virginie_enabled=true, damit Guardrails und Agenten-Workflow aktiv sind.",
            }
        )
    if not trained:
        actions.append(
            {
                "priority": "high",
                "title": "Training starten",
                "detail": "Das Modell ist noch nicht trainiert. Starte ein Initial-Training im Admin-Bereich.",
            }
        )
    if wf < 55:
        actions.append(
            {
                "priority": "medium",
                "title": "Qualität stabilisieren",
                "detail": "WF-Accuracy ist niedrig. Prüfe Feature-Importance und erhöhe Trainingsdaten.",
            }
        )
    if drift >= 0.7:
        actions.append(
            {
                "priority": "medium",
                "title": "Drift reduzieren",
                "detail": "Erhöhtes Drift-Risiko erkannt. Setups neu kalibrieren und Risk-Limits prüfen.",
            }
        )
    if guardrail_min_score < 0.5:
        actions.append(
            {
                "priority": "low",
                "title": "Min-Score anheben",
                "detail": "Für konservativeres Verhalten virginie_min_score leicht erhöhen (z.B. +0.05).",
            }
        )
    if not actions:
        actions.append(
            {
                "priority": "low",
                "title": "System stabil",
                "detail": "VIRGINIE läuft stabil. Fokus auf Monitoring und regelmäßiges Review.",
            }
        )
    return {
        "assistant": status.get("assistant_name", "VIRGINIE"),
        "version": status.get("assistant_version", "0.0.0"),
        "wf_accuracy": wf,
        "drift_score": drift,
        "actions": actions[:5],
    }


def _virginie_edge_profile() -> dict[str, Any]:
    """Kompakter VIRGINIE-Edge-Score für Trading/Forecast-Workflows."""
    status = _virginie_runtime_status()
    advice = _virginie_runtime_advice()
    snap = state.snapshot() if state else {}
    wf = float(advice.get("wf_accuracy", 0) or 0)
    drift = float(advice.get("drift_score", 0) or 0)
    autonomy = float(status.get("autonomy_weight", 0.7) or 0.7)
    running = bool(snap.get("running", False))
    open_trades = int(snap.get("open_trades", 0) or 0)
    risk_load = min(100.0, open_trades * 8.0)
    edge_score = max(0.0, min(100.0, (wf * 0.55) + ((1.0 - drift) * 35.0) + (autonomy * 10.0) - risk_load))
    tier = "S" if edge_score >= 85 else ("A" if edge_score >= 70 else ("B" if edge_score >= 55 else "C"))
    urgency = "high" if (drift >= 0.75 or edge_score < 45) else ("medium" if edge_score < 65 else "low")
    signature = uuid.uuid5(
        uuid.NAMESPACE_DNS,
        f"{status.get('assistant_version','0')}-{snap.get('exchange','na')}-{tier}-{int(edge_score)}-{int(drift*100)}",
    ).hex[:12]
    return {
        "edge_score": round(edge_score, 2),
        "tier": tier,
        "urgency": urgency,
        "running": running,
        "exchange": snap.get("exchange", "unbekannt"),
        "open_trades": open_trades,
        "signature": signature,
    }


def _virginie_cpu_fast_reply(prompt: str) -> str | None:
    """Ultraschnelle CPU-basierte VIRGINIE-Antwort ohne externen LLM-Call."""
    p = str(prompt or "").strip().lower()
    if not p:
        return None
    if any(k in p for k in ("risiko", "risk", "verlust", "drawdown")):
        return (
            "CPU-Quickcheck: Risiko zuerst. Prüfe max_drawdown, daily_loss_limit und open_trades. "
            "Wenn Drawdown steigt, Trade-Frequenz reduzieren und Stops enger setzen."
        )
    if any(k in p for k in ("markt", "market", "regime", "trend")):
        return (
            "CPU-Quickcheck: Regime + Volatilität zuerst prüfen. "
            "Nur bei bestätigtem Trend aggressiv handeln, sonst Positionsgröße drosseln."
        )
    if any(k in p for k in ("setup", "konfig", "config", "einstellung")):
        return (
            "CPU-Quickcheck Setup: 1) virginie_primary_control aktiv, 2) ai_min_confidence validieren, "
            "3) stop_loss/take_profit auf aktuelle Volatilität abstimmen."
        )
    if len(p.split()) <= 5:
        return "Beschreibe bitte kurz Symbol, Ziel und Risiko-Toleranz, dann gebe ich dir einen konkreten Plan."
    return None


def _build_virginie_chat_context(user_id: int) -> str:
    ai = ai_engine.to_dict() if ai_engine else {}
    snap = state.snapshot() if state else {}
    ass = ai.get("assistant_agents", {}) if isinstance(ai, dict) else {}
    recent = _virginie_chat_history_for_user(user_id)[-8:]
    recent_lines = []
    for item in recent:
        role = "User" if str(item.get("role", "")) == "user" else "VIRGINIE"
        msg = str(item.get("content", "")).strip().replace("\n", " ")
        if msg:
            recent_lines.append(f"- {role}: {msg[:160]}")
    recent_block = "\n".join(recent_lines) if recent_lines else "- (keine Historie)"
    return (
        "Du bist VIRGINIE, die Trading-Assistentin im TREVLIX Admin-Dashboard.\n"
        "Antwortstil: kurz, konkret, handlungsorientiert, sicherheitsbewusst.\n"
        "Keine Garantien, stattdessen klare nächste Schritte vorschlagen.\n"
        f"Aktuelle Bot-Lage: running={bool(snap.get('running', False))}, "
        f"paper_trading={bool(snap.get('paper_trading', True))}, "
        f"exchange={snap.get('exchange', 'unbekannt')}, "
        f"portfolio={snap.get('portfolio_value', 0)}.\n"
        f"VIRGINIE-Agenten: count={ass.get('registered_agents', 0)}, "
        f"coverage={ass.get('coverage_pct', 0)}%, "
        f"last_agent={ass.get('last_agent', '—')}.\n"
        "Letzte Unterhaltung (gekürzt):\n"
        f"{recent_block}"
    )


def _generate_virginie_chat_reply(user_id: int, user_prompt: str) -> str:
    prompt = str(user_prompt or "").strip()
    if not prompt:
        return "Bitte sende eine konkrete Frage, damit ich dir gezielt helfen kann."
    status = _virginie_runtime_status()
    if not status.get("enabled", True):
        return "VIRGINIE ist aktuell deaktiviert. Aktiviere 'virginie_enabled' in den Settings."
    cmd = prompt.lower()
    if cmd in {"/help", "help"}:
        return (
            "VIRGINIE Kommandos: /status (Live-Status), /review (letztes Self-Review), "
            "/plan (Aktionsplan), /edge (Edge-Profil), /help (diese Hilfe). "
            "Du kannst auch normale Fragen zu Risiko, Setup und Strategie stellen."
        )
    if cmd in {"/status", "status"}:
        agents = status.get("assistant_agents", {})
        return (
            f"Status: {'Primary' if status.get('primary_control') else 'Hybrid'} | "
            f"w={status.get('autonomy_weight', 0):.2f} | "
            f"Agents={agents.get('registered_agents', 0)} | "
            f"Coverage={agents.get('coverage_pct', 0)}% | "
            f"Last={agents.get('last_agent', '—')}"
        )
    if cmd in {"/review", "review"}:
        review = status.get("assistant_review", {})
        summary = str(review.get("summary", "")).strip() if isinstance(review, dict) else ""
        return summary or "Noch kein Self-Review vorhanden. Nach weiteren Entscheidungen erneut prüfen."
    if cmd in {"/plan", "plan", "/diagnose", "diagnose"}:
        advice = _virginie_runtime_advice()
        action_lines = [
            f"{i+1}. [{a.get('priority','low')}] {a.get('title','Schritt')} – {a.get('detail','')}"
            for i, a in enumerate(advice.get("actions", []))
        ]
        return "VIRGINIE Aktionsplan:\n" + ("\n".join(action_lines) if action_lines else "Keine Aktionen.")
    if cmd in {"/edge", "edge"}:
        edge = _virginie_edge_profile()
        return (
            f"VIRGINIE Edge: {edge.get('edge_score', 0)} / 100 | Tier {edge.get('tier')} | "
            f"Urgency {edge.get('urgency')} | Exchange {edge.get('exchange')} | Sig {edge.get('signature')}"
        )
    if bool(CONFIG.get("virginie_cpu_fast_chat", True)):
        fast_reply = _virginie_cpu_fast_reply(prompt)
        if fast_reply:
            return fast_reply
    context = _build_virginie_chat_context(user_id)
    try:
        reply = knowledge_base.query_llm_with_tools(prompt, context)
        if reply:
            return str(reply).strip()[:4000]
    except Exception as exc:
        log.debug("VIRGINIE chat LLM fallback: %s", exc)
    return (
        "Ich konnte die LLM-Antwort gerade nicht abrufen. "
        "Bitte prüfe die LLM-Konfiguration unter Wissen/LLM-Status und versuche es erneut."
    )


def _agent_notifier(msg: str) -> None:
    """Unified notifier callback for autonomous agents."""
    try:
        discord.send("Agent Alert", msg, "alert")
    except Exception:
        pass
    try:
        telegram = TelegramNotifier(CONFIG)
        telegram.send(f"<b>Agent Alert</b>\n{msg}")
    except Exception:
        pass


alert_escalation = AlertEscalationManager(
    db=db,
    config=CONFIG,
    notifier=_agent_notifier,
)
revenue_tracker = RevenueTracker(db=db, config=CONFIG)
healer = AutoHealingAgent(
    db=db,
    config=CONFIG,
    notifier=_agent_notifier,
)
cluster_ctrl = ClusterController(
    config=CONFIG,
    notifier=_agent_notifier,
)


def emit_event(event: str, data: Any, to: str | None = None) -> None:
    """Sendet Socket.io Events sicher aus Background-Threads."""
    emit_socket_event(socketio=socketio, log=log, event=event, data=data, to=to)


# ═══════════════════════════════════════════════════════════════════════════════
# EXCHANGE FACTORY – delegiert an services.exchange_factory
# ═══════════════════════════════════════════════════════════════════════════════
def _reveal_and_decrypt(val: Any) -> str:
    """Entschlüsselt einen SecretStr/Str-Wert aus CONFIG zu plain text."""
    return reveal_and_decrypt(val, decrypt_value_fn=decrypt_value)


def _is_single_exchange_mode() -> bool:
    """Single-Exchange-Mode ist aktiv, wenn EXCHANGE in der env gesetzt ist
    UND zugehörige Keys vorhanden sind. Andernfalls wird Multi-Exchange-Mode
    aktiv und die primäre Exchange wird aus der DB (user_exchanges) ermittelt.
    """
    return is_single_exchange_mode(env_exchange=os.getenv("EXCHANGE", ""))


def _get_exchange_key_states() -> dict[str, bool]:
    """Returns which exchanges have API keys configured (admin user)."""
    return get_exchange_key_states(db)


def _get_admin_primary_exchange() -> dict | None:
    """Liefert die primäre Exchange-Konfiguration des Admin-Users aus der DB.

    Gibt dict mit keys {exchange, api_key, api_secret, passphrase} zurück oder None.
    """
    return get_admin_primary_exchange(db, log)


def _get_admin_exchange_by_name(exchange_name: str) -> dict | None:
    """Liefert eine aktivierte Exchange-Konfiguration des Admins für einen konkreten Namen."""
    return get_admin_exchange_by_name(db, exchange_name, log)


def _pin_user_exchange(user_id: int | None, exchange_name: str) -> bool:
    """Setzt die gewünschte Exchange für den User als primär (falls vorhanden)."""
    return pin_user_exchange(db, user_id, exchange_name, log)


# ═══════════════════════════════════════════════════════════════════════════════
# TRADING OPS → extracted to app/core/trading_ops.py
# (create_exchange, fetch_markets, scan_symbol, open_position, close_position,
#  manage_positions, bot_loop, etc.)
# ═══════════════════════════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════════════════════════
# FLASK ROUTES — DASHBOARD & AUTH
# [#9] Auth-Routen (/, /login, /register, /logout) wurden in routes/auth.py
# als Flask Blueprint ausgelagert. Registrierung erfolgt via create_auth_blueprint()
# am Ende dieser Datei.
# ═══════════════════════════════════════════════════════════════════════════════


# ═══════════════════════════════════════════════════════════════════════════════
# REST API — JWT-gesichert
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/api/v1/state")
@api_auth_required
def api_state():
    snap = state.snapshot()
    # user_role aus Session oder JWT für Frontend Role-UI
    snap["user_role"] = session.get("user_role", "user")
    return jsonify(snap)


@app.route("/api/v1/trades")
@api_auth_required
def api_trades():
    limit = min(safe_int(request.args.get("limit", 100), 100), 1000)
    symbol = request.args.get("symbol")
    year = request.args.get("year")
    return jsonify(db.load_trades(limit=limit, symbol=symbol, year=year, user_id=request.user_id))


@app.route("/api/v1/heatmap")
@api_auth_required
def api_heatmap_v1():
    try:
        ex = create_exchange()
        return jsonify(get_heatmap_data(ex))
    except Exception as e:
        log.error("API error: %s", e)
        return jsonify({"error": "Internal server error"}), 500


@app.route("/api/v1/backtest", methods=["POST"])
@api_auth_required
def api_backtest():
    data = request.json or {}
    try:
        ex = create_exchange()
        result = bt.run(
            ex,
            data.get("symbol", "BTC/USDT"),
            data.get("timeframe", "1h"),
            safe_int(data.get("candles", 500), 500),
            safe_float(data.get("sl", CONFIG["stop_loss_pct"]), CONFIG["stop_loss_pct"]),
            safe_float(data.get("tp", CONFIG["take_profit_pct"]), CONFIG["take_profit_pct"]),
            safe_float(
                data.get("vote", CONFIG.get("min_vote_score", 0.3)),
                CONFIG.get("min_vote_score", 0.3),
            ),
        )
        return jsonify(result)
    except Exception as e:
        log.error("API error: %s", e)
        return jsonify({"error": "Internal server error"}), 500


@app.route("/api/v1/tax")
@api_auth_required
def api_tax_v1():
    year = safe_int(request.args.get("year", datetime.now().year), datetime.now().year)
    method = request.args.get("method", "fifo")
    trades = db.load_trades(limit=10000, year=year, user_id=request.user_id)
    return jsonify(tax.generate(trades, year, method))


@app.route("/api/v1/token", methods=["POST"])
@api_auth_required
def api_create_token():
    label = (request.json or {}).get("label", "api")
    token = db.create_api_token(request.user_id, label)
    return jsonify({"token": token, "expires_hours": CONFIG["jwt_expiry_hours"]})


# ═══════════════════════════════════════════════════════════════════════════════
# USER SETTINGS & EXCHANGE MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════════════


@app.route("/api/v1/user/settings")
@api_auth_required
def api_user_settings_get():
    """Gibt die User-Settings aus der DB zurück."""
    settings = db.get_user_settings(request.user_id)
    settings["paper_trading"] = CONFIG.get("paper_trading", True)
    settings["trade_mode"] = "paper" if CONFIG.get("paper_trading", True) else "live"
    return jsonify(settings)


@app.route("/api/v1/user/settings", methods=["POST"])
@api_auth_required
def api_user_settings_update():
    """Speichert User-Settings in der DB (kein .env nötig)."""
    data = request.json or {}
    # Erlaubte Settings für User (keine Admin-/System-Settings)
    _ALLOWED_USER_SETTINGS = {
        "paper_trading",
        "paper_balance",
        "risk_per_trade",
        "stop_loss_pct",
        "take_profit_pct",
        "max_open_trades",
        "scan_interval",
        "timeframe",
        "use_dca",
        "dca_drop_pct",
        "dca_max_levels",
        "use_partial_tp",
        "trailing_stop",
        "trailing_pct",
        "break_even_enabled",
        "use_fear_greed",
        "use_sentiment",
        "use_news",
        "use_anomaly",
        "use_market_regime",
        "ai_enabled",
        "ai_min_confidence",
        "virginie_enabled",
        "virginie_primary_control",
        "virginie_autonomy_weight",
        "virginie_min_score",
        "virginie_max_risk_penalty",
        "virginie_cpu_fast_chat",
        "discord_webhook",
        "discord_on_buy",
        "discord_on_sell",
        "telegram_token",
        "telegram_chat_id",
        "portfolio_goal",
        "language",
        "max_daily_loss_pct",
    }
    filtered = {k: v for k, v in data.items() if k in _ALLOWED_USER_SETTINGS}
    # Bestehende Settings laden und mergen
    current = db.get_user_settings(request.user_id)
    current.update(filtered)
    if "paper_trading" in filtered:
        mode = "paper" if safe_bool(filtered.get("paper_trading", True), True) else "live"
        if mode == "live" and not safe_bool(os.getenv("LIVE_TRADING_ENABLED", "false"), False):
            return jsonify({"error": "Live-Trading ist serverseitig deaktiviert (LIVE_TRADING_ENABLED=false)"}), 403
        trade_mode.set_mode(mode)
        CONFIG["paper_trading"] = mode == "paper"
    current["paper_trading"] = CONFIG.get("paper_trading", True)
    ok = db.update_user_settings(request.user_id, current)
    return jsonify({"ok": ok, "updated": list(filtered.keys())})


@app.route("/api/v1/trading/mode", methods=["GET", "POST"])
@api_auth_required
def api_trading_mode():
    if request.method == "GET":
        return jsonify(trade_mode.status())
    data = request.json or {}
    mode = str(data.get("mode", "paper")).lower()
    if mode == "live" and not safe_bool(os.getenv("LIVE_TRADING_ENABLED", "false"), False):
        return jsonify({"error": "Live-Trading ist serverseitig deaktiviert (LIVE_TRADING_ENABLED=false)"}), 403
    new_mode = trade_mode.set_mode(mode)
    CONFIG["paper_trading"] = new_mode != "live"
    state.add_activity("🧭", "Trading-Modus", new_mode.upper(), "info")
    discord.info(f"Trading-Modus gewechselt: {new_mode.upper()}")
    telegram.info(f"Trading-Modus gewechselt: {new_mode.upper()}")
    return jsonify(trade_mode.status())


@app.route("/api/v1/trading/control", methods=["POST"])
@api_auth_required
def api_trading_control():
    data = request.json or {}
    action = str(data.get("action", "start")).lower()
    if action == "start":
        trade_mode.set_enabled(True)
        with state._lock:
            state.running = True
            state.paused = False
        if not any(t.name == "BotLoop" and t.is_alive() for t in threading.enumerate()):
            threading.Thread(target=bot_loop, daemon=True, name="BotLoop").start()
        return jsonify({"ok": True, "running": True})
    if action == "stop":
        trade_mode.set_enabled(False)
        with state._lock:
            state.running = False
            state.paused = False
        return jsonify({"ok": True, "running": False})
    return jsonify({"error": "action must be start|stop"}), 400


@app.route("/api/v1/trading/close-position", methods=["POST"])
@api_auth_required
def api_trading_close_position():
    data = request.json or {}
    sym = str(data.get("symbol", "")).strip().upper()
    if not sym:
        return jsonify({"error": "symbol required"}), 400
    with state._lock:
        in_long = sym in state.positions
        in_short = sym in state.short_positions
    if not in_long and not in_short:
        return jsonify({"error": f"position not open: {sym}"}), 404
    try:
        if in_long:
            ex = create_exchange()
            close_position(ex, sym, "Manuell geschlossen 🖐")
            return jsonify({"ok": True, "symbol": sym, "side": "long"})
        short_engine.close_short(sym, "Manuell 🖐")
        return jsonify({"ok": True, "symbol": sym, "side": "short"})
    except Exception as e:
        log.warning("api_trading_close_position failed: %s", e)
        return jsonify({"error": str(e)}), 500


@app.route("/api/v1/trading/open-positions")
@api_auth_required
def api_open_positions():
    try:
        in_memory = state.snapshot().get("positions", [])
        if in_memory:
            return jsonify({"positions": in_memory})
        mode = request.args.get("mode")
        db_positions = (
            db.load_open_positions(user_id=request.user_id, trade_mode=mode)
            if hasattr(db, "load_open_positions")
            else []
        )
        return jsonify({"positions": db_positions})
    except Exception as e:
        log.warning("api_open_positions: %s", e)
        return jsonify({"positions": [], "error": "temporarily_unavailable"}), 503


@app.route("/api/v1/trading/closed-trades")
@api_auth_required
def api_closed_trades():
    try:
        limit = min(safe_int(request.args.get("limit", 150), 150), 500)
        mode = request.args.get("mode")
        rows = db.load_trades(limit=limit, user_id=request.user_id)
        if mode in {"paper", "live"}:
            rows = [r for r in rows if str(r.get("trade_mode", "paper")) == mode]
        return jsonify({"trades": rows})
    except Exception as e:
        log.warning("api_closed_trades: %s", e)
        return jsonify({"trades": [], "error": "temporarily_unavailable"}), 503


@app.route("/api/v1/trading/order-history")
@api_auth_required
def api_order_history():
    try:
        limit = min(safe_int(request.args.get("limit", 150), 150), 500)
        mode = request.args.get("mode")
        return jsonify(
            {"orders": db.load_orders(limit=limit, user_id=request.user_id, trade_mode=mode)}
        )
    except Exception as e:
        log.warning("api_order_history: %s", e)
        return jsonify({"orders": [], "error": "temporarily_unavailable"}), 503


@app.route("/api/v1/trading/signal-history")
@api_auth_required
def api_signal_history():
    try:
        return jsonify({"signals": list(state.signal_log)[:200]})
    except Exception as e:
        log.warning("api_signal_history: %s", e)
        return jsonify({"signals": [], "error": "temporarily_unavailable"}), 503


@app.route("/api/v1/trading/decision-history")
@api_auth_required
def api_decision_history():
    try:
        limit = min(safe_int(request.args.get("limit", 150), 150), 500)
        mode = request.args.get("mode")
        return jsonify(
            {
                "decisions": db.load_trade_decisions(
                    limit=limit, user_id=request.user_id, trade_mode=mode
                )
            }
        )
    except Exception as e:
        log.warning("api_decision_history: %s", e)
        return jsonify({"decisions": [], "error": "temporarily_unavailable"}), 503


@app.route("/api/v1/trading/performance")
@api_auth_required
def api_trading_performance():
    try:
        return jsonify(db.performance_breakdown(user_id=request.user_id))
    except Exception as e:
        log.warning("api_trading_performance: %s", e)
        return jsonify({"by_mode": [], "by_exchange": [], "by_strategy": [], "error": "temporarily_unavailable"}), 503


@app.route("/api/v1/user/exchanges")
@api_auth_required
def api_user_exchanges_list():
    """Listet alle Exchange-Konfigurationen des Users."""
    exchanges = db.get_user_exchanges(request.user_id)
    return jsonify(exchanges)


@app.route("/api/v1/user/exchanges", methods=["POST"])
@api_auth_required
def api_user_exchanges_upsert():
    """Erstellt/aktualisiert eine Exchange-Konfiguration. Default: deaktiviert."""
    data = request.json or {}
    exchange = normalize_exchange_name(data.get("exchange", ""))
    api_key = str(data.get("api_key", "")).strip()
    api_secret = str(data.get("api_secret", "")).strip()
    passphrase = str(data.get("passphrase", "")).strip()
    enabled = safe_bool(data.get("enabled", False), False)  # Default: deaktiviert
    is_primary = safe_bool(data.get("is_primary", False), False)
    if not exchange:
        return jsonify({"error": "Ungültige oder nicht unterstützte Exchange"}), 400
    requires_keys = not bool(CONFIG.get("paper_trading", True))
    if requires_keys and (not api_key or not api_secret):
        return jsonify({"error": "api_key und api_secret sind Pflichtfelder"}), 400
    ok = db.upsert_user_exchange(
        request.user_id,
        exchange,
        api_key,
        api_secret,
        enabled,
        is_primary,
        passphrase=passphrase,
    )
    _audit("exchange_upsert", f"Exchange: {exchange}, enabled: {enabled}", request.user_id)
    return jsonify({"ok": ok})


@app.route("/api/v1/user/exchanges/<int:exchange_id>/toggle", methods=["POST"])
@api_auth_required
def api_user_exchange_toggle(exchange_id):
    """Aktiviert/Deaktiviert eine Exchange für den User."""
    enabled = safe_bool((request.json or {}).get("enabled", False), False)
    ok = db.toggle_user_exchange(request.user_id, exchange_id, enabled)
    return jsonify({"ok": ok})


@app.route("/api/v1/user/exchanges/<int:exchange_id>", methods=["DELETE"])
@api_auth_required
def api_user_exchange_delete(exchange_id):
    """Löscht eine Exchange-Konfiguration des Users."""
    ok = db.delete_user_exchange(request.user_id, exchange_id)
    return jsonify({"ok": ok})


@app.route("/api/v1/user/api-keys", methods=["POST"])
@api_auth_required
def api_user_update_keys():
    """Aktualisiert die API-Keys des Users (verschlüsselt in DB)."""
    data = request.json or {}
    exchange = normalize_exchange_name(data.get("exchange", CONFIG["exchange"]))
    api_key = str(data.get("api_key", "")).strip()
    api_secret = str(data.get("api_secret", "")).strip()
    if not exchange:
        return jsonify({"error": "Ungültige oder nicht unterstützte Exchange"}), 400
    if not api_key or not api_secret:
        return jsonify({"error": "api_key und api_secret sind Pflichtfelder"}), 400
    ok = db.update_user_api_keys(request.user_id, exchange, api_key, api_secret)
    _audit("api_keys_update", f"Exchange: {exchange}", request.user_id)
    return jsonify({"ok": ok})


# ═══════════════════════════════════════════════════════════════════════════════
# VIRGINIE CHAT API (3D Live View)
# ═══════════════════════════════════════════════════════════════════════════════


@app.route("/api/v1/virginie/chat")
@api_auth_required
def api_virginie_chat_history():
    """Liefert den Chat-Verlauf des angemeldeten Users."""
    user_id = int(getattr(request, "user_id", 0) or 0)
    return jsonify(
        {
            "messages": _virginie_chat_history_for_user(user_id),
            "max_messages": _VIRGINIE_CHAT_MAX_MESSAGES,
        }
    )


@app.route("/api/v1/virginie/status")
@api_auth_required
def api_virginie_status():
    """Liefert Runtime-Zustand und Guardrails von VIRGINIE."""
    return jsonify(_virginie_runtime_status())


@app.route("/api/v1/virginie/advice")
@api_auth_required
def api_virginie_advice():
    """Liefert priorisierte VIRGINIE Handlungsempfehlungen."""
    return jsonify(_virginie_runtime_advice())


@app.route("/api/v1/virginie/edge-profile")
@api_auth_required
def api_virginie_edge_profile():
    """Liefert den VIRGINIE Edge-Score (Trading/Forecast Profil)."""
    return jsonify(_virginie_edge_profile())


@app.route("/api/v1/virginie/forecast-feed")
@api_auth_required
def api_virginie_forecast_feed():
    """Liefert die letzten VIRGINIE Forecast-Events."""
    limit = safe_int(request.args.get("limit", 30), 30)
    return jsonify({"items": get_virginie_forecast_feed(limit)})


@app.route("/api/v1/virginie/chat", methods=["POST"])
@api_auth_required
def api_virginie_chat_post():
    """Nimmt eine User-Nachricht an und erzeugt eine VIRGINIE-Antwort."""
    user_id = int(getattr(request, "user_id", 0) or 0)
    payload = request.json or {}
    message = str(payload.get("message", "")).strip()
    if not message:
        return jsonify({"error": "message ist Pflichtfeld"}), 400
    if len(message) > 2000:
        return jsonify({"error": "message ist zu lang (max. 2000 Zeichen)"}), 400

    user_entry = _virginie_chat_append(user_id, "user", message)
    assistant_reply = _generate_virginie_chat_reply(user_id, message)
    assistant_entry = _virginie_chat_append(user_id, "assistant", assistant_reply)
    return jsonify({"ok": True, "user": user_entry, "assistant": assistant_entry})


@app.route("/api/v1/virginie/chat/clear", methods=["POST"])
@api_auth_required
def api_virginie_chat_clear():
    """Löscht den VIRGINIE-Chatverlauf des aktuellen Users."""
    user_id = int(getattr(request, "user_id", 0) or 0)
    with _virginie_chat_lock:
        _virginie_chat_by_user[int(user_id)] = deque(maxlen=_VIRGINIE_CHAT_MAX_MESSAGES)
    return jsonify({"ok": True})


# ═══════════════════════════════════════════════════════════════════════════════
# ADMIN: Multi-Exchange gleichzeitig laufen lassen
# ═══════════════════════════════════════════════════════════════════════════════


# ═══════════════════════════════════════════════════════════════════════════════
# KI-GEMEINSCHAFTSWISSEN API
# ═══════════════════════════════════════════════════════════════════════════════


@app.route("/api/v1/knowledge/summary")
@api_auth_required
def api_knowledge_summary():
    """Markt-Zusammenfassung aus dem Gemeinschaftswissen."""
    return jsonify(knowledge_base.get_market_summary())


@app.route("/api/v1/knowledge/<category>")
@api_auth_required
def api_knowledge_category(category):
    """Alle Einträge einer Wissens-Kategorie."""
    if category not in KnowledgeBase.CATEGORIES:
        return jsonify({"error": f"Unbekannte Kategorie: {category}"}), 400
    limit = min(safe_int(request.args.get("limit", 50), 50), 200)
    return jsonify(knowledge_base.get_category(category, limit))


@app.route("/api/v1/knowledge/query", methods=["POST"])
@api_auth_required
def api_knowledge_query():
    """Fragt die lokale LLM nach einer Analyse."""
    data = request.json or {}
    prompt = data.get("prompt", "")
    if not prompt:
        return jsonify({"error": "prompt ist Pflichtfeld"}), 400
    # Kontext aus Gemeinschaftswissen zusammenstellen
    summary = knowledge_base.get_market_summary()
    context = (
        f"Du bist ein Krypto-Trading-Analyst. Aktuelles Wissen:\n"
        f"Top Symbole: {json.dumps(summary.get('top_symbols', [])[:5])}\n"
        f"Strategie-Ranking: {json.dumps(summary.get('strategy_ranking', [])[:5])}\n"
    )
    # MCP-Tool-gestützte Analyse wenn verfügbar
    answer = knowledge_base.query_llm_with_tools(prompt, context)
    if answer is None:
        return jsonify({"error": "LLM nicht verfügbar. Setze LLM_ENDPOINT in .env"}), 503
    return jsonify({"answer": answer})


@app.route("/api/v1/knowledge/llm-status")
@api_auth_required
def api_knowledge_llm_status():
    """Status der autonomen LLM-Integration."""
    return jsonify(
        {
            "llm_enabled": knowledge_base.llm_enabled,
            "llm_endpoint": bool(knowledge_base._llm_endpoint),
            "cached_market_analysis": knowledge_base.cached_market_analysis or None,
            "trade_patterns": len(knowledge_base.get_category("trade_pattern", limit=100)),
            "model_analyses": len(knowledge_base.get_category("model_config", limit=100)),
            "risk_patterns": len(knowledge_base.get_category("risk_pattern", limit=100)),
            "multi_llm_providers": (
                knowledge_base._multi_llm.status() if knowledge_base._multi_llm else []
            ),
        }
    )


@app.route("/api/v1/mcp/tools")
@api_auth_required
def api_mcp_tools():
    """Liste der verfügbaren MCP-Tools für die KI."""
    return jsonify(
        {
            "tools": mcp_registry.get_tools_schema(),
            "count": len(mcp_registry.get_tools_schema()),
        }
    )


@app.route("/api/v1/mcp/execute", methods=["POST"])
@api_auth_required
def api_mcp_execute():
    """Führt ein MCP-Tool direkt aus."""
    data = request.json or {}
    tool_name = data.get("tool", "")
    arguments = data.get("arguments", {})
    if not tool_name:
        return jsonify({"error": "tool ist Pflichtfeld"}), 400
    result = mcp_registry.execute(tool_name, arguments)
    return jsonify(result)


@app.route("/api/v1/admin/exchanges")
@api_auth_required
@admin_required
def api_admin_exchanges():
    """Admin sieht alle User-Exchanges und deren Status."""
    try:
        with db._get_conn() as conn:
            with conn.cursor() as c:
                c.execute(
                    "SELECT ue.*, u.username FROM user_exchanges ue "
                    "JOIN users u ON ue.user_id = u.id ORDER BY u.username, ue.exchange"
                )
                rows = c.fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d.pop("api_key", None)
            d.pop("api_secret", None)
            if d.get("created_at") and hasattr(d["created_at"], "isoformat"):
                d["created_at"] = d["created_at"].isoformat()
            result.append(d)
        return jsonify(result)
    except Exception as e:
        log.error("API error: %s", e)
        return jsonify({"error": "Internal server error"}), 500


@app.route("/api/v1/admin/exchanges/<int:exchange_id>/toggle", methods=["POST"])
@api_auth_required
@admin_required
def api_admin_exchange_toggle(exchange_id):
    """Admin kann jede Exchange aktivieren/deaktivieren."""
    enabled = (request.json or {}).get("enabled", False)
    try:
        with db._get_conn() as conn:
            with conn.cursor() as c:
                c.execute(
                    "UPDATE user_exchanges SET enabled=%s WHERE id=%s",
                    (enabled, exchange_id),
                )
        return jsonify({"ok": True})
    except Exception as e:
        log.error("API error: %s", e)
        return jsonify({"error": "Internal server error"}), 500


@app.route("/api/v1/signal", methods=["POST"])
@api_auth_required
@limiter.limit("60 per minute")
def api_signal():
    """TradingView Webhook → sofortiger Scan."""
    data = request.json or {}
    sym = data.get("symbol", "")
    action = data.get("action", "buy").lower()
    if not sym or not state.running:
        return jsonify({"ok": False, "msg": "Bot nicht aktiv"}), 400

    def _async():
        try:
            ex = create_exchange()
            scan = scan_symbol(ex, sym)
            if scan and action == "buy" and scan["signal"] == 1:
                open_position(ex, scan)
            elif action == "sell" and sym in state.positions:
                close_position(ex, sym, f"Webhook:{action}")
        except Exception as e:
            log.error(f"Webhook: {e}")

    threading.Thread(target=_async, daemon=True).start()
    return jsonify({"ok": True, "msg": f"Signal für {sym} empfangen"})


@app.route("/api/v1/portfolio")
@api_auth_required
def api_portfolio():
    return jsonify(
        {
            "value": round(state.portfolio_value(), 2),
            "balance": round(state.balance, 2),
            "return_pct": round(state.return_pct(), 2),
            "total_pnl": round(state.total_pnl(), 2),
            "win_rate": round(state.win_rate(), 1),
            "positions": list(state.positions.keys()),
        }
    )


@app.route("/api/v1/ai")
@api_auth_required
def api_ai():
    return jsonify(ai_engine.to_dict())


@app.route("/api/v1/dominance")
@api_auth_required
def api_dominance():
    return jsonify(dominance.to_dict())


@app.route("/api/v1/anomaly")
@api_auth_required
def api_anomaly():
    return jsonify(anomaly.to_dict())


@app.route("/api/v1/genetic")
@api_auth_required
def api_genetic():
    return jsonify(genetic.to_dict())


@app.route("/api/v1/rl")
@api_auth_required
def api_rl():
    return jsonify(rl_agent.to_dict())


@app.route("/api/v1/news/<path:symbol>")
@api_auth_required
def api_news(symbol):
    score, headline, count = news_fetcher.get_score(symbol)
    return jsonify({"symbol": symbol, "score": score, "headline": headline, "count": count})


@app.route("/api/v1/onchain/<path:symbol>")
@api_auth_required
def api_onchain(symbol):
    score, detail = onchain.get_score(symbol)
    return jsonify({"symbol": symbol, "score": score, "detail": detail})


@app.route("/api/v1/balance/all")
@api_auth_required
def api_balance_all():
    """[#32] Aggregierte Balance über alle konfigurierten Exchanges."""
    try:
        data = fetch_aggregated_balance()
        return jsonify(data)
    except Exception as e:
        log.error("API error: %s", e)
        return jsonify({"error": "Internal server error"}), 500


@app.route("/api/v1/fees")
@api_auth_required
def api_fees():
    """[#29] Gibt Exchange-spezifische Fee-Rates zurück."""
    from services.exchange_factory import _fee_cache, _fee_cache_lock

    current_ex = CONFIG.get("exchange", "cryptocom")
    fees = {}
    with _fee_cache_lock:
        for ex_id in EXCHANGE_DEFAULT_FEES:
            fees[ex_id] = {
                "default": EXCHANGE_DEFAULT_FEES[ex_id],
                "cached": _fee_cache.get(ex_id, {}).get("rate"),
                "cached_at": _fee_cache.get(ex_id, {}).get("ts"),
            }
    return jsonify(
        {
            "current_exchange": current_ex,
            "current_fee_rate": get_exchange_fee_rate(),
            "exchanges": fees,
        }
    )


@app.route("/api/v1/arb")
@api_auth_required
def api_arb():
    try:
        with db._get_conn() as conn:
            with conn.cursor() as c:
                c.execute("SELECT * FROM arb_opportunities ORDER BY found_at DESC LIMIT 20")
                rows = c.fetchall()
        result = []
        for r in rows:
            d = dict(r)
            if hasattr(d.get("found_at"), "isoformat"):
                d["found_at"] = d["found_at"].isoformat()
            result.append(d)
        return jsonify(result)
    except Exception as e:
        log.error("API error: %s", e)
        return jsonify({"error": "Internal server error"}), 500


# Admin Routes
@app.route("/api/v1/admin/users")
@api_auth_required
@admin_required
def api_admin_users():
    return jsonify(db.get_all_users())


@app.route("/api/v1/admin/users", methods=["POST"])
@api_auth_required
@admin_required
def api_admin_create_user():
    data = request.json or {}
    is_valid, payload, error_key, error_message = validate_admin_user_payload(data)
    if not is_valid:
        return jsonify({"ok": False, "error": error_message, "key": error_key}), 400

    ok = db.create_user(
        payload["username"],
        payload["password"],
        payload["role"],
        payload["balance"],
    )
    return jsonify({"ok": ok})


@app.route("/api/v1/admin/config")
@api_auth_required
@admin_required
def api_admin_config():
    safe = {
        k: v
        for k, v in CONFIG.items()
        if k
        not in (
            "api_key",
            "secret",
            "mysql_pass",
            "admin_password",
            "jwt_secret",
            "short_api_key",
            "short_secret",
            "cryptopanic_token",
            "encryption_key",
            "secret_key",
            "telegram_token",
            "extra_exchanges",
            "funding_rate_cache",
        )
    }
    return jsonify(safe)


@app.route("/api/v1/admin/config", methods=["POST"])
@api_auth_required
@admin_required
def api_admin_config_update():
    # Sensible Felder die NICHT über API geändert werden dürfen (nur .env)
    _PROTECTED_KEYS = frozenset(
        {
            "api_key",
            "secret",
            "short_api_key",
            "short_secret",
            "mysql_pass",
            "mysql_host",
            "mysql_port",
            "mysql_user",
            "mysql_db",
            "jwt_secret",
            "admin_password",
            "cryptopanic_token",
            "discord_webhook",
            "telegram_token",
            "telegram_chat_id",
            "encryption_key",
        }
    )
    data = request.json or {}
    updated = []
    for k, v in data.items():
        if k in _PROTECTED_KEYS:
            continue  # Sensible Werte nur über .env änderbar
        if k in CONFIG:
            original = CONFIG[k]
            if isinstance(original, (list, dict)):
                if not isinstance(v, type(original)):
                    continue  # Typ-Mismatch bei komplexen Werten ablehnen
            elif isinstance(original, bool):
                v = bool(v)
            elif isinstance(original, int):
                v = safe_int(v, original)
            elif isinstance(original, float):
                v = safe_float(v, original)
            CONFIG[k] = v
            updated.append(k)
    _audit(
        "config_update", f"Geändert: {', '.join(updated) if updated else 'nichts'}", request.user_id
    )
    return jsonify({"ok": True, "updated": updated})


# Legacy routes (Dashboard compatibility)
@app.route("/api/heatmap")
@dashboard_auth
def api_heatmap_legacy():
    try:
        ex = create_exchange()
        return jsonify(get_heatmap_data(ex))
    except Exception as e:
        log.error("API error: %s", e)
        return jsonify({"error": "Internal server error"})


@app.route("/api/ohlcv/<path:symbol>")
@dashboard_auth
def api_ohlcv(symbol):
    sym = symbol.replace("-", "/")
    tf = request.args.get("tf", "1h")
    if tf not in {"1m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "12h", "1d"}:
        tf = "1h"
    limit = min(safe_int(request.args.get("limit", 200), 200), 500)
    try:
        ex = create_exchange()
        ohlcv = ex.fetch_ohlcv(sym, tf, limit=limit)
        trades = [t for t in state.closed_trades if t.get("symbol") == sym][:20]
        return jsonify({"ohlcv": ohlcv, "trades": trades})
    except Exception as e:
        log.error("API error: %s", e)
        return jsonify({"error": "Internal server error"})


@app.route("/api/tax_report")
@dashboard_auth
def api_tax_report():
    year = safe_int(request.args.get("year", datetime.now().year), datetime.now().year)
    method = request.args.get("method", "fifo")
    fmt = request.args.get("format", "json")
    trades = db.load_trades(limit=10000, year=year)
    report = tax.generate(trades, year, method)
    if fmt == "csv":
        rows = report.get("gains", []) + report.get("losses", [])
        return Response(
            tax_rows_to_csv(rows),
            mimetype="text/csv",
            headers={"Content-Disposition": f"attachment;filename=trevlix_tax_{year}.csv"},
        )
    return jsonify(report)


@app.route("/api/export/csv")
@dashboard_auth
def api_export_csv():
    return Response(
        db.export_csv(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=trevlix_trades.csv"},
    )


@app.route("/api/export/json")
@dashboard_auth
def api_export_json():
    trades = db.load_trades(limit=10000)
    return Response(
        trades_to_json(trades),
        mimetype="application/json",
        headers={"Content-Disposition": "attachment;filename=trevlix_trades.json"},
    )


@app.route("/api/backtest/history")
@dashboard_auth
def api_backtest_history():
    return jsonify(db.get_recent_backtests(10))


@app.route("/api/backup/download")
@dashboard_auth
def api_backup_download():
    path = db.backup()
    if path:
        return send_file(path, as_attachment=True)
    return jsonify({"error": "Backup fehlgeschlagen"}), 500


@app.route("/api/v1/backup/verify")
@dashboard_auth
def api_backup_verify():
    """[Verbesserung #9] Prüft das neueste Backup auf SHA-256-Integrität."""
    bdir = CONFIG.get("backup_dir", "backups")
    try:
        result, err = verify_latest_backup(backup_dir=bdir, db=db)
        if err:
            return jsonify({"error": err}), 404
        return jsonify(result)
    except Exception as e:
        log.error("API error: %s", e)
        return jsonify({"error": "Internal server error"}), 500


@app.route("/api/v1/docs")
def api_docs():
    return jsonify(build_api_docs_payload(bot_full=BOT_FULL, bot_version=BOT_VERSION))


# ── Health / Status ──────────────────────────────────────────────────────────
@app.route("/api/v1/status")
@app.route("/api/v1/update/status")
def api_health():
    """[Verbesserung #16] Erweiterter Healthcheck mit DB-Ping, Pool-Stats, Memory."""
    import sys

    db_ok = False
    pool_stats = {}
    try:
        with db._get_conn() as conn:
            with conn.cursor() as c:
                c.execute("SELECT 1")
            db_ok = True
        if db._pool:
            pool_stats = db._pool.pool_stats()
    except Exception:
        pass
    return jsonify(
        {
            "status": "ok" if (db_ok and db.db_available) else "degraded",
            "version": BOT_VERSION,
            "running": state.running,
            "paused": getattr(state, "paused", False),
            "uptime_s": round(time.time() - state._start_time, 1)
            if hasattr(state, "_start_time")
            else 0,
            "db_ok": db_ok,
            "pool": pool_stats,
            "python": sys.version.split()[0],
            "open_trades": len(state.positions),
        }
    )


# ── [Verbesserung #7] API-Token Revocation ────────────────────────────────────
@app.route("/api/v1/token/<int:token_id>", methods=["DELETE"])
@api_auth_required
def api_revoke_token(token_id):
    """Deaktiviert einen API-Token."""
    try:
        with db._get_conn() as conn:
            with conn.cursor() as c:
                c.execute(
                    "UPDATE api_tokens SET active=0 WHERE id=%s AND user_id=%s",
                    (token_id, request.user_id),
                )
        _audit("token_revoked", f"token_id={token_id}", request.user_id)
        return jsonify({"success": True})
    except Exception as e:
        log.error("API error: %s", e)
        return jsonify({"error": "Internal server error"}), 500


# ── [Verbesserung #48] Prometheus-kompatible Metriken ─────────────────────────
@app.route("/metrics")
@api_auth_required
def prometheus_metrics():
    """Exportiert Bot-Metriken im Prometheus-Format."""
    lines = build_prometheus_lines(bot_version=BOT_VERSION, state=state, db=db)
    return Response("\n".join(lines) + "\n", mimetype="text/plain; charset=utf-8")


# ═══════════════════════════════════════════════════════════════════════════════
# WEBSOCKET EVENTS
# [Verbesserung #8] In-Memory Rate-Limiting für kritische Socket-Events
# ═══════════════════════════════════════════════════════════════════════════════
_ws_rate_limiter = WsRateLimiter()


def _ws_auth_required() -> bool:
    """Check if the WebSocket client is authenticated.

    Returns:
        True if authenticated, False otherwise (also emits error).
    """
    return ws_auth_required(session_obj=session, emit_fn=emit)


def _ws_admin_required() -> bool:
    """Check if the WebSocket client is an authenticated admin.

    Re-verifies role from database to prevent privilege escalation
    via session manipulation.

    Returns:
        True if admin, False otherwise (also emits error).
    """
    return ws_admin_required(
        session_obj=session,
        emit_fn=emit,
        db=db,
        ws_auth_required_fn=_ws_auth_required,
    )


def _ws_rate_check(action: str, min_interval: float = 2.0) -> bool:
    """Prüft ob ein Socket-Event zu schnell wiederholt wird."""
    sid = request.sid if hasattr(request, "sid") else "global"
    return ws_rate_check(
        limiter=_ws_rate_limiter, sid=sid, action=action, min_interval=min_interval
    )


@socketio.on("connect")
def on_connect(auth=None):
    user_id = session.get("user_id")
    username = session.get("username", "?")

    # JWT-Fallback: Falls Session-Cookie nicht verfügbar (z.B. hinter Proxy)
    if not user_id and auth and isinstance(auth, dict):
        token = auth.get("token", "")
        if token:
            uid = db.verify_api_token(token)
            if uid:
                user_id = uid
                session["user_id"] = uid
                username = "jwt-user"
            else:
                # JWT im Cookie versuchen
                try:
                    payload = pyjwt.decode(
                        token,
                        CONFIG.get("jwt_secret", app.config["SECRET_KEY"]),
                        algorithms=["HS256"],
                    )
                    user_id = payload.get("user_id")
                    if user_id:
                        session["user_id"] = user_id
                        username = payload.get("username", "jwt-user")
                except (pyjwt.InvalidTokenError, Exception):
                    pass

    if not user_id:
        emit("auth_error", {"msg": "Nicht authentifiziert – bitte einloggen"})
        return False
    # On-demand: Märkte laden falls noch leer (Bot nicht gestartet)
    if not state.markets:
        try:
            ex = create_exchange()
            fresh = fetch_markets(ex)
            if fresh:
                with state._lock:
                    state.markets = fresh
        except Exception as e:
            log.debug("on_connect market prefetch: %s", e)
    snap = state.snapshot()
    # Attach user role so the frontend can show admin UI elements
    try:
        u = db.get_user_by_id(user_id)
        snap["user_role"] = u.get("role", "user") if u else "user"
    except Exception:
        snap["user_role"] = "user"
    emit("update", snap)
    log.info(f"📱 Client verbunden: {username}")


@socketio.on("disconnect")
def on_disconnect(reason: str = "") -> None:
    """Cleanup bei Client-Disconnect – Session-State aufräumen."""
    try:
        username = session.get("username", "?")
    except RuntimeError:
        username = "?"
    try:
        sid = getattr(request, "sid", "?")
    except RuntimeError:
        sid = "?"
    log.info(f"📴 Client getrennt: {username} (sid={sid})")


@socketio.on_error_default
def default_error_handler(e: Exception) -> None:
    """Globaler Fallback-Handler für unbehandelte SocketIO-Fehler."""
    log_socket_error(log=log, error=e)


@socketio.on("request_state")
def on_request_state():
    """Ermöglicht dem Client, den aktuellen State explizit anzufragen (z.B. nach Reconnect)."""
    uid = session.get("user_id")
    if not uid:
        emit("auth_error", {"msg": "Nicht authentifiziert"})
        return
    snap = build_ws_state_snapshot(uid=uid, state=state, db=db)
    emit("update", snap)


@socketio.on("virginie_chat")
def on_virginie_chat(data: dict | None = None) -> None:
    """Realtime chat endpoint for VIRGINIE in the 3D live view."""
    if not _ws_auth_required():
        return
    if not _ws_rate_check("virginie_chat", min_interval=0.6):
        emit(
            "virginie_chat_error",
            {"error": "Zu schnell gesendet. Bitte kurz warten und erneut senden."},
        )
        return
    payload = data or {}
    message = str(payload.get("message", "")).strip()
    if not message:
        emit("virginie_chat_error", {"error": "Leere Nachricht ist nicht erlaubt."})
        return
    if len(message) > 2000:
        emit("virginie_chat_error", {"error": "Nachricht zu lang (max. 2000 Zeichen)."})
        return
    user_id = int(getattr(request, "user_id", session.get("user_id", 0)) or 0)
    user_entry = _virginie_chat_append(user_id, "user", message)
    emit("virginie_chat_message", user_entry)
    assistant_reply = _generate_virginie_chat_reply(user_id, message)
    assistant_entry = _virginie_chat_append(user_id, "assistant", assistant_reply)
    emit("virginie_chat_message", assistant_entry)


@socketio.on("select_exchange")
def on_select_exchange(data: dict) -> None:
    """Allow any authenticated user to switch the active exchange for the bot."""
    if not _ws_auth_required():
        return
    if not _ws_rate_check("select_exchange", min_interval=2.0):
        emit(
            "status",
            {"msg": "⏳ Zu schnell – bitte warten", "key": "ws_rate_limit", "type": "warning"},
        )
        return
    _valid = {"cryptocom", "binance", "bybit", "okx", "kucoin", "kraken", "huobi", "coinbase"}
    ex = normalize_exchange_name(str((data or {}).get("exchange", "")))
    if not ex or ex not in _valid:
        emit("status", {"msg": "❌ Ungültige Exchange", "key": "ws_bad_exchange", "type": "error"})
        return
    prev = CONFIG.get("exchange", "—")
    CONFIG["exchange"] = ex
    state._exchange_reset = True  # Signal an bot_loop: Exchange-Instanz neu erstellen
    _pin_user_exchange(getattr(request, "user_id", session.get("user_id")), ex)
    log.info(
        f"🔀 Exchange gewechselt: {prev} → {ex.upper()} (user={getattr(request, 'user_id', '?')})"
    )
    emit(
        "status",
        {
            "msg": f"🔀 Exchange gewechselt → {ex.upper()}",
            "key": "ws_exchange_changed",
            "type": "success",
        },
        broadcast=True,
    )
    emit("update", state.snapshot(), broadcast=True)


@socketio.on("start_bot")
def on_start_bot():
    if not _ws_auth_required():
        return
    if not _ws_rate_check("start_bot", min_interval=3.0):
        emit(
            "status",
            {"msg": "⏳ Zu schnell – bitte warten", "key": "ws_rate_limit", "type": "warning"},
        )
        return
    test_markets, preflight_err = _preflight_exchange_markets(max_attempts=2)
    if test_markets:
        with state._lock:
            state.markets = test_markets
    if preflight_err:
        is_paper = bool(CONFIG.get("paper_trading", True))
        # Paper-Trading darf trotz Exchange-Ausfall starten (Loop reconnectet später).
        if is_paper:
            emit(
                "status",
                {
                    "msg": (
                        "⚠ Exchange/Marktdaten aktuell nicht erreichbar – "
                        "Paper-Bot startet trotzdem (Auto-Reconnect aktiv)"
                    ),
                    "key": "ws_bot_start_degraded",
                    "type": "warning",
                },
            )
            state.add_activity(
                "⚠️",
                "Bot-Start im Degraded-Modus",
                str(preflight_err)[:120],
                "warning",
            )
        else:
            emit(
                "status",
                {
                    "msg": f"❌ Start fehlgeschlagen: {preflight_err}",
                    "key": "ws_bot_start_failed_exchange",
                    "type": "error",
                },
            )
            state.add_activity(
                "❌",
                "Bot-Start fehlgeschlagen",
                "Exchange/Marktdaten nicht erreichbar",
                "error",
            )
            return
    with state._lock:
        if state.running:
            return
        trade_mode.set_enabled(True)
        state.running = True
        state.paused = False
    threading.Thread(target=bot_loop, daemon=True).start()
    emit(
        "status",
        {"msg": "🤖 TREVLIX gestartet", "key": "ws_bot_started", "type": "success"},
        broadcast=True,
    )
    state.add_activity(
        "🚀", "TREVLIX gestartet", f"v{BOT_VERSION} · {CONFIG['exchange'].upper()}", "success"
    )
    log.info("🚀 Bot gestartet")


@socketio.on("stop_bot")
def on_stop_bot():
    if not _ws_auth_required():
        return
    if not _ws_rate_check("stop_bot", min_interval=3.0):
        emit(
            "status",
            {"msg": "⏳ Zu schnell – bitte warten", "key": "ws_rate_limit", "type": "warning"},
        )
        return
    with state._lock:
        trade_mode.set_enabled(False)
        state.running = False
        state.paused = False
    emit(
        "status", {"msg": "⏹ Bot gestoppt", "key": "ws_bot_stopped", "type": "info"}, broadcast=True
    )
    state.add_activity("⏹", "Bot gestoppt", "Alle Positionen offen", "info")


@socketio.on("pause_bot")
def on_pause_bot():
    if not _ws_auth_required():
        return
    if not _ws_rate_check("pause_bot", min_interval=2.0):
        return
    with state._lock:
        state.paused = not state.paused
        msg = "⏸ Pausiert" if state.paused else "▶ Weiter"
        key = "ws_bot_paused" if state.paused else "ws_bot_resumed"
    emit("status", {"msg": msg, "key": key, "type": "warning"}, broadcast=True)


@socketio.on("update_config")
def on_update_config(data):
    if not _ws_admin_required():
        return
    if not _ws_rate_check("update_config", min_interval=2.0):
        emit(
            "status",
            {"msg": "⏳ Zu schnell – bitte warten", "key": "ws_rate_limit", "type": "warning"},
        )
        return
    allowed = {
        "stop_loss_pct",
        "take_profit_pct",
        "max_open_trades",
        "scan_interval",
        "paper_trading",
        "trailing_stop",
        "ai_min_confidence",
        "virginie_enabled",
        "virginie_primary_control",
        "virginie_autonomy_weight",
        "virginie_min_score",
        "virginie_max_risk_penalty",
        "virginie_cpu_fast_chat",
        "circuit_breaker_losses",
        "circuit_breaker_min",
        "max_spread_pct",
        "use_fear_greed",
        "ai_use_kelly",
        "mtf_enabled",
        "use_sentiment",
        "use_news",
        "use_onchain",
        "use_dominance",
        "use_anomaly",
        "use_dca",
        "use_partial_tp",
        "use_shorts",
        "use_arbitrage",
        "genetic_enabled",
        "rl_enabled",
        "backup_enabled",
        "portfolio_goal",
        "discord_daily_report",
        "discord_report_hour",
        "risk_per_trade",
        "news_block_score",
        "news_boost_score",
        "dca_max_levels",
        "dca_drop_pct",
        "trailing_pct",
        "lstm_lookback",
        # Dashboard-spezifische Einstellungen
        "language",
        "allow_registration",
        "break_even_enabled",
        "break_even_pct",
        "partial_tp_pct",
        "use_grid",
        "use_rl",
        "use_lstm",
        # Exchange selection – allowed for all authenticated users
        "exchange",
    }
    # Typ-Validierung: Wert muss zum bestehenden CONFIG-Typ passen
    _numeric_keys = {
        "stop_loss_pct",
        "take_profit_pct",
        "ai_min_confidence",
        "virginie_autonomy_weight",
        "virginie_min_score",
        "virginie_max_risk_penalty",
        "max_spread_pct",
        "risk_per_trade",
        "news_block_score",
        "news_boost_score",
        "dca_drop_pct",
        "trailing_pct",
        "break_even_pct",
        "partial_tp_pct",
        "portfolio_goal",
    }
    _int_keys = {
        "max_open_trades",
        "scan_interval",
        "circuit_breaker_losses",
        "circuit_breaker_min",
        "dca_max_levels",
        "lstm_lookback",
        "discord_report_hour",
    }
    _valid_exchanges = {
        "cryptocom",
        "binance",
        "bybit",
        "okx",
        "kucoin",
        "kraken",
        "huobi",
        "coinbase",
    }
    updated: dict[str, Any] = {}
    for k, v in data.items():
        if k not in allowed:
            continue
        if k == "paper_trading":
            desired_paper = bool(v)
            if not desired_paper and not safe_bool(os.getenv("LIVE_TRADING_ENABLED", "false"), False):
                continue
            CONFIG[k] = desired_paper
            trade_mode.set_mode("paper" if desired_paper else "live")
            updated[k] = desired_paper
            continue
        if k == "exchange":
            ex = normalize_exchange_name(str(v))
            if ex and ex in _valid_exchanges:
                CONFIG["exchange"] = ex
                state._exchange_reset = True
                _pin_user_exchange(getattr(request, "user_id", session.get("user_id")), ex)
                updated["exchange"] = ex
                log.info(f"🔀 Exchange manuell gewechselt → {ex.upper()}")
            continue
        if k in _numeric_keys:
            v = safe_float(v, CONFIG.get(k, 0.0))
        elif k in _int_keys:
            v = safe_int(v, CONFIG.get(k, 0))
        elif isinstance(CONFIG.get(k), bool):
            v = bool(v)
        CONFIG[k] = v
        updated[k] = v
    # Persistenz: Admin-Settings in der DB speichern, damit sie einen Restart überleben.
    try:
        uid = getattr(request, "user_id", session.get("user_id"))
        if uid and updated:
            current = db.get_user_settings(uid) or {}
            current.update(updated)
            current["paper_trading"] = CONFIG.get("paper_trading", True)
            db.update_user_settings(uid, current)
    except Exception as e:
        log.debug(f"update_config persist: {e}")
    emit(
        "status",
        {"msg": "✅ Einstellungen gespeichert", "key": "ws_settings_saved", "type": "success"},
    )
    emit("update", state.snapshot(), broadcast=True)


@socketio.on("save_api_keys")
def on_save_keys(data):
    if not _ws_admin_required():
        return
    # API-Keys werden verschlüsselt im CONFIG gespeichert
    raw_key = data.get("api_key", "")
    raw_secret = data.get("secret", "")
    CONFIG["api_key"] = encrypt_value(raw_key) if raw_key else ""
    CONFIG["secret"] = encrypt_value(raw_secret) if raw_secret else ""
    if data.get("exchange") and data["exchange"] in EXCHANGE_MAP:
        ex = normalize_exchange_name(data["exchange"])
        CONFIG["exchange"] = ex
        state._exchange_reset = True
        _pin_user_exchange(getattr(request, "user_id", session.get("user_id")), ex)
    emit(
        "status",
        {
            "msg": f"🔑 Keys gespeichert ({CONFIG['exchange']})",
            "key": "ws_keys_saved",
            "type": "success",
        },
    )


@socketio.on("update_discord")
def on_update_discord(data):
    if not _ws_admin_required():
        return
    if data.get("webhook"):
        CONFIG["discord_webhook"] = data["webhook"]
    if "on_buy" in data:
        CONFIG["discord_on_buy"] = bool(data["on_buy"])
    if "on_sell" in data:
        CONFIG["discord_on_sell"] = bool(data["on_sell"])
    if "daily_report" in data:
        CONFIG["discord_daily_report"] = bool(data["daily_report"])
    if "report_hour" in data:
        rh = safe_int(data.get("report_hour", 20), 20)
        CONFIG["discord_report_hour"] = max(0, min(23, rh))
    discord.send(
        "✅ Discord verbunden", f"```\n{BOT_NAME} {BOT_VERSION} konfiguriert!\n```", "info"
    )
    emit(
        "status",
        {
            "msg": "💬 Discord konfiguriert & getestet",
            "key": "ws_discord_configured",
            "type": "success",
        },
    )


@socketio.on("force_train")
def on_force_train():
    if not _ws_admin_required():
        return
    emit("status", {"msg": "🧠 KI-Training gestartet...", "key": "ws_ai_training", "type": "info"})
    threading.Thread(target=ai_engine._train, daemon=True).start()


@socketio.on("force_optimize")
def on_force_optimize():
    if not _ws_admin_required():
        return
    emit("status", {"msg": "🔬 Optimierung läuft...", "key": "ws_ai_optimizing", "type": "info"})
    threading.Thread(target=ai_engine._optimize, daemon=True).start()


@socketio.on("force_genetic")
def on_force_genetic():
    if not _ws_admin_required():
        return
    emit(
        "status",
        {"msg": "🧬 Genetischer Optimizer gestartet...", "key": "ws_ai_genetic", "type": "info"},
    )
    threading.Thread(
        target=lambda trades=list(state.closed_trades): genetic.evolve(trades), daemon=True
    ).start()


@socketio.on("reset_ai")
def on_reset_ai():
    if not _ws_admin_required():
        return
    with ai_engine._lock:
        ai_engine.X_raw = []
        ai_engine.y_raw = []
        ai_engine.regimes_raw = []
        ai_engine.X_bull = []
        ai_engine.y_bull = []
        ai_engine.X_bear = []
        ai_engine.y_bear = []
        ai_engine.is_trained = False
        ai_engine.global_model = None
        ai_engine.bull_model = None
        ai_engine.bear_model = None
        ai_engine.lstm_model = None
        ai_engine.progress_pct = 0
    emit("status", {"msg": "🔄 KI zurückgesetzt", "key": "ws_ai_reset", "type": "warning"})


@socketio.on("close_position")
def on_close_position(data):
    if not _ws_auth_required():
        return
    if not _ws_rate_check("close_position", min_interval=2.0):
        emit(
            "status",
            {"msg": "⏳ Zu schnell – bitte warten", "key": "ws_rate_limit", "type": "warning"},
        )
        return
    sym = data.get("symbol", "")
    with state._lock:
        in_long = sym in state.positions
        in_short = sym in state.short_positions
    if in_long:
        try:
            ex = create_exchange()
            close_position(ex, sym, "Manuell geschlossen 🖐")
            emit(
                "status",
                {"msg": f"✅ {sym} geschlossen", "key": "ws_position_closed", "type": "success"},
                broadcast=True,
            )
        except Exception as e:
            emit("status", {"msg": f"❌ {e}", "type": "error"})
    elif in_short:
        short_engine.close_short(sym, "Manuell 🖐")
        emit(
            "status",
            {"msg": f"✅ Short {sym} geschlossen", "key": "ws_short_closed", "type": "success"},
            broadcast=True,
        )


@socketio.on("run_backtest")
def on_run_backtest(data):
    if not _ws_auth_required():
        return

    def _bt():
        try:
            ex = create_exchange()
            result = bt.run(
                ex,
                data.get("symbol", "BTC/USDT"),
                data.get("timeframe", "1h"),
                safe_int(data.get("candles", 500), 500),
                safe_float(data.get("sl", CONFIG["stop_loss_pct"]), CONFIG["stop_loss_pct"]),
                safe_float(data.get("tp", CONFIG["take_profit_pct"]), CONFIG["take_profit_pct"]),
                safe_float(
                    data.get("vote", CONFIG.get("min_vote_score", 0.3)),
                    CONFIG.get("min_vote_score", 0.3),
                ),
            )
            emit_event("backtest_result", result)
        except Exception as e:
            emit_event("backtest_result", {"error": str(e)})

    emit(
        "status",
        {
            "msg": f"⏳ Backtest {data.get('symbol', '?')} läuft...",
            "key": "ws_backtest_running",
            "type": "info",
        },
    )
    threading.Thread(target=_bt, daemon=True).start()


@socketio.on("add_price_alert")
def on_add_alert(data):
    if not _ws_auth_required():
        return
    uid = session.get("user_id", 1)
    db.add_alert(
        data.get("symbol", ""),
        safe_float(data.get("target", 0), 0.0),
        data.get("direction", "above"),
        uid,
    )
    emit(
        "status",
        {
            "msg": f"🔔 Alert gesetzt für {data.get('symbol')}",
            "key": "ws_alert_set",
            "type": "success",
        },
    )
    emit("update", state.snapshot(), broadcast=True)


@socketio.on("delete_price_alert")
def on_delete_alert(data):
    if not _ws_auth_required():
        return
    db.delete_alert(safe_int(data.get("id", 0), 0))
    emit("update", state.snapshot(), broadcast=True)


@socketio.on("manual_backup")
def on_manual_backup():
    if not _ws_auth_required():
        return

    def _bk():
        path = db.backup()
        if path:
            discord.backup_done(path)
            emit_event(
                "status",
                {
                    "msg": f"💾 Backup: {os.path.basename(path)}",
                    "key": "ws_backup_done",
                    "type": "success",
                },
            )
        else:
            emit_event(
                "status",
                {"msg": "❌ Backup fehlgeschlagen", "key": "ws_backup_failed", "type": "error"},
            )

    threading.Thread(target=_bk, daemon=True).start()


@socketio.on("send_daily_report")
def on_send_report():
    if not _ws_auth_required():
        return
    threading.Thread(target=daily_sched._send_report, daemon=True).start()
    emit(
        "status", {"msg": "📊 Report wird gesendet...", "key": "ws_report_sending", "type": "info"}
    )


@socketio.on("reset_circuit_breaker")
def on_reset_cb():
    if not _ws_auth_required():
        return
    with risk._lock:
        risk.circuit_breaker_until = None
        risk.consecutive_losses = 0
    emit(
        "status",
        {"msg": "⚡ Circuit Breaker zurückgesetzt", "key": "ws_cb_reset", "type": "success"},
        broadcast=True,
    )
    emit("update", state.snapshot(), broadcast=True)


@socketio.on("scan_arbitrage")
def on_scan_arb():
    if not _ws_auth_required():
        return

    def _arb():
        opps = arb_scanner.scan(state.markets[:30])
        emit_event(
            "status",
            {
                "msg": f"💹 {len(opps)} Arbitrage-Chancen",
                "key": "ws_arb_result",
                "type": "success" if opps else "info",
            },
        )

    threading.Thread(target=_arb, daemon=True).start()


@socketio.on("update_dominance")
def on_update_dominance():
    if not _ws_auth_required():
        return
    threading.Thread(target=dominance.update, daemon=True).start()
    emit(
        "status",
        {"msg": "🌐 Dominanz-Update läuft...", "key": "ws_dominance_updating", "type": "info"},
    )


@socketio.on("admin_create_user")
def on_admin_create_user(data):
    if not _ws_admin_required():
        return
    is_valid, payload, error_key, error_message = validate_admin_user_payload(data or {})
    if not is_valid:
        emit("status", {"msg": error_message, "key": error_key, "type": "error"})
        return

    ok = db.create_user(
        payload["username"],
        payload["password"],
        payload["role"],
        payload["balance"],
    )
    emit(
        "status",
        {
            "msg": "✅ User erstellt" if ok else "❌ Fehler",
            "key": "ws_user_created" if ok else "ws_user_create_failed",
            "type": "success" if ok else "error",
        },
    )


# ═══════════════════════════════════════════════════════════════════════════════
# STARTUP
# ═══════════════════════════════════════════════════════════════════════════════
# fetch_aggregated_balance, safety_scan → extracted to app/core/trading_ops.py

# ════════════════════════════════════════════════════════════════════════════════
# AUDIT LOG SYSTEM (Verbesserung 1)
# Alle Admin- und Nutzeraktionen lückenlos protokolliert
# ════════════════════════════════════════════════════════════════════════════════


def db_audit(user_id: int, action: str, detail: str = "", ip: str = ""):
    """Schreibt einen Audit-Log-Eintrag in die DB."""
    if not ip:
        try:
            ip = request.remote_addr or ""
        except RuntimeError:
            ip = "system"
    try:
        with db._get_conn() as conn:
            with conn.cursor() as c:
                c.execute(
                    """INSERT INTO audit_log (user_id, action, detail, ip)
                             VALUES (%s, %s, %s, %s)""",
                    (user_id, str(action)[:80], str(detail)[:500], str(ip)[:45]),
                )
                conn.commit()
    except Exception as e:
        log.debug(f"audit_log: {e}")


@app.route("/api/v1/admin/audit-log")
@api_auth_required
@admin_required
def api_audit_log():
    """Gibt die letzten 200 Audit-Log-Einträge zurück."""
    try:
        action_filter = request.args.get("action", "")
        with db._get_conn() as conn:
            with conn.cursor() as c:
                if action_filter:
                    c.execute(
                        """SELECT al.*, u.username FROM audit_log al
                                 LEFT JOIN users u ON al.user_id = u.id
                                 WHERE al.action LIKE %s
                                 ORDER BY al.created_at DESC LIMIT 200""",
                        (f"%{action_filter}%",),
                    )
                else:
                    c.execute("""SELECT al.*, u.username FROM audit_log al
                                 LEFT JOIN users u ON al.user_id = u.id
                                 ORDER BY al.created_at DESC LIMIT 200""")
                rows = c.fetchall()
        return jsonify({"logs": [dict(r) for r in rows]})
    except Exception as e:
        log.error("API error: %s", e)
        return jsonify({"error": "Internal server error"}), 500


# ════════════════════════════════════════════════════════════════════════════════
# GRID TRADING ENGINE (modularisiert → services/grid_trading.py)
# ════════════════════════════════════════════════════════════════════════════════
from services.grid_trading import GridTradingEngine  # noqa: E402

grid_engine = GridTradingEngine()


@app.route("/api/v1/grid", methods=["GET"])
@api_auth_required
def api_grid_list():
    return jsonify({"grids": grid_engine.status()})


@app.route("/api/v1/grid", methods=["POST"])
@api_auth_required
@admin_required
def api_grid_create():
    d = request.json or {}
    symbol = d.get("symbol", "")
    lower = safe_float(d.get("lower", 0), 0.0)
    upper = safe_float(d.get("upper", 0), 0.0)
    levels = safe_int(d.get("levels", 10), 10)
    invest = safe_float(d.get("invest_per_level", 100.0), 100.0)
    levels = min(levels, 200)
    if not symbol or lower <= 0 or upper <= lower:
        return jsonify({"error": "symbol, lower, upper (lower<upper) erforderlich"}), 400
    result = grid_engine.create_grid(symbol, lower, upper, levels, invest)
    db_audit(session.get("user_id", 0), "grid_create", f"{symbol} {lower}–{upper} {levels}L")
    return jsonify(result)


@app.route("/api/v1/grid/<symbol>", methods=["DELETE"])
@api_auth_required
@admin_required
def api_grid_delete(symbol):
    grid_engine.delete_grid(symbol)
    db_audit(session.get("user_id", 0), "grid_delete", symbol)
    return jsonify({"deleted": symbol})


@socketio.on("create_grid")
def ws_create_grid(data):
    if not _ws_admin_required():
        return
    symbol = data.get("symbol", "").strip()
    if not symbol:
        emit(
            "status", {"msg": "Symbol erforderlich", "key": "err_symbol_required", "type": "error"}
        )
        return
    lower = safe_float(data.get("lower", 0), 0.0)
    upper = safe_float(data.get("upper", 0), 0.0)
    levels = min(safe_int(data.get("levels", 10), 10), 200)
    if lower <= 0 or upper <= lower:
        emit(
            "status", {"msg": "Ungültige Grid-Parameter", "key": "err_grid_params", "type": "error"}
        )
        return
    result = grid_engine.create_grid(
        symbol,
        lower,
        upper,
        levels,
        safe_float(data.get("invest_per_level", 100), 100.0),
    )
    if "error" in result:
        emit("status", {"msg": result["error"], "type": "error"})
        return
    emit(
        "status",
        {"msg": f"✅ Grid {symbol} erstellt", "key": "ws_grid_created", "type": "success"},
        broadcast=True,
    )


# ── Undo Close ────────────────────────────────────────────────────────────────
@socketio.on("undo_close")
def on_undo_close(data):
    if not _ws_auth_required():
        return
    sym = data.get("symbol", "")
    if not sym:
        emit("status", {"msg": "❌ Kein Symbol angegeben", "key": "err_no_symbol", "type": "error"})
        return
    # Position kann nicht wirklich rückgängig gemacht werden (bereits geschlossen)
    # – informiere den Nutzer
    emit(
        "status",
        {
            "msg": f"↩ Rückgängig nicht möglich: {sym} wurde bereits auf der Börse geschlossen",
            "key": "ws_undo_impossible",
            "type": "warning",
        },
    )


# ── GitHub Updater ─────────────────────────────────────────────────────────────
@socketio.on("check_update")
def on_check_update():
    if not _ws_auth_required():
        return
    try:
        status = _get_update_status()
        socketio.emit("update_status", status.to_socket_payload())
    except GitOperationError as e:
        log.warning("Update check failed: %s", e.detail or e.user_message)
        emit(
            "status",
            {
                "msg": f"⚠ Update-Check fehlgeschlagen: {e.user_message}",
                "key": "ws_update_check_failed",
                "type": "warning",
            },
        )
    except Exception as e:
        log.exception("Unexpected update check error: %s", e)
        emit(
            "status",
            {
                "msg": "⚠ Update-Check fehlgeschlagen",
                "key": "ws_update_check_failed",
                "type": "warning",
            },
        )


@socketio.on("apply_update")
def on_apply_update():
    if not _ws_admin_required():
        return
    try:
        _apply_update()
        emit("update_result", {"status": "success"}, broadcast=True)
        emit(
            "status",
            {
                "msg": "✅ Update angewendet – Server wird neu gestartet",
                "key": "ws_update_applied",
                "type": "success",
            },
            broadcast=True,
        )
    except GitOperationError as e:
        log.warning("Apply update failed: %s", e.detail or e.user_message)
        emit("update_result", {"status": "error", "msg": e.user_message})
        emit(
            "status",
            {
                "msg": f"❌ Update fehlgeschlagen: {e.user_message}",
                "key": "ws_update_failed",
                "type": "error",
            },
        )
    except Exception as e:
        log.exception("Unexpected apply update error: %s", e)
        emit("update_result", {"status": "error", "msg": "Unbekannter Fehler"})
        emit(
            "status",
            {"msg": "❌ Update fehlgeschlagen", "key": "ws_update_failed", "type": "error"},
        )


@socketio.on("rollback_update")
def on_rollback_update():
    if not _ws_admin_required():
        return
    try:
        stashed = _rollback_update()
        emit(
            "status",
            {
                "msg": (
                    "↩ Rollback: git stash angewendet"
                    if stashed
                    else "⚠ Rollback: git stash konnte nicht angewendet werden"
                ),
                "key": "ws_rollback_done" if stashed else "ws_rollback_partial",
                "type": "info" if stashed else "warning",
            },
            broadcast=True,
        )
    except GitOperationError as e:
        log.warning("Rollback failed: %s", e.detail or e.user_message)
        emit(
            "status",
            {
                "msg": f"❌ Rollback fehlgeschlagen: {e.user_message}",
                "key": "ws_rollback_failed",
                "type": "error",
            },
        )
    except Exception as e:
        log.exception("Unexpected rollback error: %s", e)
        emit(
            "status",
            {
                "msg": "❌ Rollback fehlgeschlagen",
                "key": "ws_rollback_failed",
                "type": "error",
            },
        )


# ── Multi-Exchange Handler ──────────────────────────────────────────────────────
@socketio.on("start_exchange")
def on_start_exchange(data):
    if not _ws_admin_required():
        return
    ex_name = normalize_exchange_name((data or {}).get("exchange", ""))
    if not ex_name:
        emit(
            "status",
            {"msg": "❌ Unbekannte Exchange", "key": "err_unknown_exchange", "type": "error"},
        )
        return
    CONFIG["exchange"] = ex_name
    state._exchange_reset = True
    _pin_user_exchange(getattr(request, "user_id", session.get("user_id")), ex_name)
    emit(
        "status",
        {
            "msg": f"▶ Exchange {ex_name.upper()} wird gestartet…",
            "key": "ws_exchange_starting",
            "type": "info",
        },
        broadcast=True,
    )
    emit("exchange_update", {"exchange": ex_name, "status": "running"}, broadcast=True)


@socketio.on("stop_exchange")
def on_stop_exchange(data):
    if not _ws_admin_required():
        return
    ex_name = normalize_exchange_name((data or {}).get("exchange", ""))
    if not ex_name:
        emit(
            "status",
            {"msg": "❌ Unbekannte Exchange", "key": "err_unknown_exchange", "type": "error"},
        )
        return
    emit(
        "status",
        {
            "msg": f"⏹ Exchange {ex_name.upper()} gestoppt",
            "key": "ws_exchange_stopped",
            "type": "info",
        },
        broadcast=True,
    )
    emit("exchange_update", {"exchange": ex_name, "status": "stopped"}, broadcast=True)


@socketio.on("save_exchange_keys")
def on_save_exchange_keys(data):
    if not _ws_admin_required():
        return
    ex_name = normalize_exchange_name((data or {}).get("exchange", ""))
    api_key = str((data or {}).get("api_key", "")).strip()
    secret = str((data or {}).get("secret", "")).strip()
    if not ex_name or not api_key or not secret:
        emit(
            "status",
            {
                "msg": "❌ Exchange, API-Key und Secret erforderlich",
                "key": "err_exchange_keys_required",
                "type": "error",
            },
        )
        return
    passphrase = str((data or {}).get("passphrase", "")).strip()
    is_primary = safe_bool((data or {}).get("is_primary", False), False)
    enabled = safe_bool((data or {}).get("enabled", True), True)
    # Persistent in user_exchanges speichern
    uid = getattr(request, "user_id", session.get("user_id"))
    if uid:
        ok = db.upsert_user_exchange(
            uid,
            ex_name,
            api_key,
            secret,
            enabled=enabled,
            is_primary=is_primary,
            passphrase=passphrase,
        )
    else:
        ok = False
    # Zusätzlich in CONFIG für sofortige Nutzung im laufenden Prozess spiegeln
    if "extra_exchanges" not in CONFIG:
        CONFIG["extra_exchanges"] = {}
    CONFIG["extra_exchanges"][ex_name] = {
        "api_key": encrypt_value(api_key),
        "secret": encrypt_value(secret),
        "passphrase": encrypt_value(passphrase) if passphrase else "",
    }
    emit(
        "status",
        {
            "msg": (
                f"🔑 Keys für {ex_name.upper()} gespeichert"
                if ok
                else f"⚠️ Keys für {ex_name.upper()} nur im Speicher – DB-Persistenz fehlgeschlagen"
            ),
            "key": "ws_exchange_keys_saved" if ok else "ws_exchange_keys_memonly",
            "type": "success" if ok else "warning",
        },
    )


@socketio.on("close_exchange_position")
def on_close_exchange_position(data):
    if not _ws_admin_required():
        return
    ex_name = normalize_exchange_name((data or {}).get("exchange", ""))
    symbol = str((data or {}).get("symbol", "")).strip().upper()
    if not ex_name or not symbol:
        emit(
            "status",
            {
                "msg": "❌ Exchange und Symbol erforderlich",
                "key": "err_exchange_symbol_required",
                "type": "error",
            },
        )
        return
    try:
        # Nur bekannte Exchanges zulassen (kein beliebiges getattr auf ccxt)
        if not ex_name:
            emit(
                "status",
                {"msg": "❌ Unbekannte Exchange", "key": "err_unknown_exchange", "type": "error"},
            )
            return
        ex_cfg = CONFIG.get("extra_exchanges", {}).get(ex_name, {})
        raw_key = ex_cfg.get("api_key", "")
        raw_secret = ex_cfg.get("secret", "")
        if not raw_key or not raw_secret:
            emit(
                "status",
                {
                    "msg": "❌ Keine API-Keys für diese Exchange",
                    "key": "err_no_exchange_keys",
                    "type": "error",
                },
            )
            return
        ex = create_ccxt_exchange(
            ex_name,
            api_key=decrypt_value(raw_key),
            api_secret=decrypt_value(raw_secret),
            passphrase=decrypt_value(ex_cfg.get("passphrase", "")),
        )
        if ex is None:
            emit(
                "status",
                {
                    "msg": "❌ Exchange nicht verfügbar",
                    "key": "err_exchange_unavailable",
                    "type": "error",
                },
            )
            return
        pos = state.positions.get(symbol)
        amount = pos.get("qty", 0) if pos else 0
        if amount > 0:
            ex.create_market_sell_order(symbol, amount)
        emit(
            "status",
            {
                "msg": f"✅ {symbol} auf {ex_name.upper()} geschlossen",
                "key": "ws_exchange_pos_closed",
                "type": "success",
            },
            broadcast=True,
        )
    except Exception as e:
        emit(
            "status",
            {"msg": f"❌ Fehler beim Schließen: {e}", "key": "ws_close_error", "type": "error"},
        )


def _derive_llm_provider_name(endpoint: str) -> str:
    """Leitet einen lesbaren Provider-Namen aus der Endpoint-URL ab."""
    if not endpoint:
        return "—"
    ep = endpoint.lower()
    mapping = {
        "openai.com": "OpenAI",
        "anthropic.com": "Anthropic",
        "groq.com": "Groq",
        "cerebras.ai": "Cerebras",
        "openrouter.ai": "OpenRouter",
        "huggingface.co": "HuggingFace",
        "together.xyz": "Together",
        "mistral.ai": "Mistral",
        "localhost": "Local",
        "127.0.0.1": "Local",
        "0.0.0.0": "Local",
    }
    for needle, label in mapping.items():
        if needle in ep:
            return label
    return "Custom"


def _collect_system_analytics() -> dict[str, Any]:
    """Collect system analytics data (shared by WS and HTTP)."""
    import platform
    import shutil

    data: dict[str, Any] = {}
    # System info
    try:
        import psutil

        mem = psutil.virtual_memory()
        cpu_pct = psutil.cpu_percent(interval=0.1)
        boot = datetime.fromtimestamp(psutil.boot_time())
        uptime_delta = datetime.now() - boot
        uptime_str = f"{uptime_delta.days}d {uptime_delta.seconds // 3600}h"
        data["system"] = {
            "python": platform.python_version(),
            "platform": f"{platform.system()} {platform.release()}",
            "cpu": f"{cpu_pct}%",
            "memory": f"{mem.used // (1024**2)}/{mem.total // (1024**2)} MB ({mem.percent}%)",
            "disk": "—",
            "uptime": uptime_str,
        }
    except ImportError:
        data["system"] = {
            "python": platform.python_version(),
            "platform": f"{platform.system()} {platform.release()}",
            "cpu": "—",
            "memory": "—",
            "disk": "—",
            "uptime": "—",
        }
    # Disk usage
    try:
        disk = shutil.disk_usage("/")
        data["system"]["disk"] = (
            f"{disk.used // (1024**3)}/{disk.total // (1024**3)} GB "
            f"({100 * disk.used // disk.total}%)"
        )
    except Exception:
        pass

    # API status
    exchange_name = CONFIG.get("exchange", "unknown")
    discord_configured = bool(CONFIG.get("discord_webhook"))
    telegram_configured = bool(CONFIG.get("telegram_token"))
    api_latency = "—"
    api_connected = "⏸️"
    try:
        ex = create_exchange()
        start_t = time.time()
        ex.fetch_time()
        api_latency = f"{int((time.time() - start_t) * 1000)} ms"
        api_connected = "✅"
    except Exception:
        if state.running:
            api_connected = "⚠️"
        api_latency = "timeout"
    data["api"] = {
        "exchange": exchange_name.upper(),
        "connected": api_connected,
        "latency": api_latency,
        "calls_24h": str(getattr(state, "api_calls_24h", "—")),
        "discord": "✅" if discord_configured else "❌",
        "telegram": "✅" if telegram_configured else "❌",
    }

    # LLM status
    llm_endpoint = CONFIG.get("llm_endpoint", "") or getattr(knowledge_base, "_llm_endpoint", "")
    llm_model = CONFIG.get("llm_model", "—") or getattr(knowledge_base, "_llm_model", "—")
    data["llm"] = {
        "endpoint": llm_endpoint or "—",
        "model": llm_model,
        "provider": "—",
        "status": "⚪ Nicht konfiguriert",
        "latency": "—",
        "queries_24h": "—",
        "tokens_24h": "—",
    }
    if llm_endpoint:
        # Einzel-Endpoint: Provider aus URL ableiten
        data["llm"]["provider"] = _derive_llm_provider_name(llm_endpoint)
        data["llm"]["status"] = "✅ Konfiguriert"

    # Multi-LLM Fallback/Status wenn kein dedizierter Endpoint gesetzt ist
    try:
        multi_llm = getattr(knowledge_base, "_multi_llm", None)
        if multi_llm:
            provider_stats = multi_llm.status()
            if provider_stats:
                total_reqs = sum(int(p.get("requests", 0) or 0) for p in provider_stats)
                total_tokens = sum(int(p.get("tokens", 0) or 0) for p in provider_stats)
                active_ok = [
                    p for p in provider_stats if str(p.get("status", "")).lower() == "healthy"
                ]
                if not llm_endpoint:
                    data["llm"]["endpoint"] = "multi-provider"
                if data["llm"]["model"] in ("", "—"):
                    data["llm"]["model"] = ", ".join(p.get("name", "?") for p in provider_stats[:3])
                # Aktiver Provider-Name (erster gesunder, sonst erster insgesamt)
                primary = (active_ok or provider_stats)[0] if provider_stats else None
                if primary:
                    data["llm"]["provider"] = str(primary.get("name", "—")).title()
                data["llm"]["status"] = (
                    f"✅ {len(active_ok)}/{len(provider_stats)} Provider online"
                    if active_ok
                    else "❌ Alle Provider offline"
                )
                data["llm"]["queries_24h"] = str(total_reqs)
                data["llm"]["tokens_24h"] = str(total_tokens)
    except Exception as e:
        log.debug("Multi-LLM status query failed: %s", e)

    if llm_endpoint:
        try:
            import urllib.request

            # Kompatibel mit OpenAI-/vLLM-Endpunkten (/models) und Ollama (/api/tags)
            candidates = [
                llm_endpoint.rstrip("/") + "/models",
                llm_endpoint.rstrip("/") + "/api/tags",
            ]
            last_exc = None
            for url in candidates:
                try:
                    start_t = time.time()
                    req = urllib.request.Request(url, method="GET")
                    req.add_header("Connection", "close")
                    with urllib.request.urlopen(req, timeout=5):
                        latency_ms = int((time.time() - start_t) * 1000)
                        data["llm"]["status"] = "✅ Online"
                        data["llm"]["latency"] = f"{latency_ms} ms"
                        last_exc = None
                        break
                except Exception as exc:
                    last_exc = exc
            if last_exc is not None:
                data["llm"]["status"] = "❌ Offline"
        except Exception:
            data["llm"]["status"] = "❌ Offline"

    # Database status
    data["db"] = {
        "pool_size": "—",
        "active_conn": "—",
        "utilization": "—",
        "tables": "—",
        "size": "—",
    }
    try:
        pool_info = db.pool_stats() if hasattr(db, "pool_stats") else {}
        data["db"]["pool_size"] = pool_info.get("pool_size", "—")
        data["db"]["active_conn"] = pool_info.get("in_use", "—")
        util = pool_info.get("utilization_pct")
        data["db"]["utilization"] = f"{util}%" if util is not None else "—"
    except Exception:
        pass
    try:
        with db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema=DATABASE()"
                )
                row = cur.fetchone()
                data["db"]["tables"] = row[0] if row else "—"
                cur.execute(
                    "SELECT ROUND(SUM(data_length+index_length)/1024/1024,1) "
                    "FROM information_schema.tables WHERE table_schema=DATABASE()"
                )
                row = cur.fetchone()
                data["db"]["size"] = f"{row[0]} MB" if row and row[0] else "—"
    except Exception:
        pass

    # AI Engine metrics
    try:
        ai_dict = ai_engine.to_dict()
        idle_meta = {}
        try:
            if hasattr(knowledge_base, "idle_learning_status"):
                idle_meta = knowledge_base.idle_learning_status()
        except Exception:
            idle_meta = {}
        data["ai"] = {
            "trained": ai_dict.get("is_trained", False),
            "accuracy": f"{ai_dict.get('accuracy', 0) * 100:.1f}%",
            "cv_accuracy": f"{ai_dict.get('cv_accuracy', 0) * 100:.1f}%",
            "predictions": ai_dict.get("predictions_made", 0),
            "correct": ai_dict.get("predictions_correct", 0),
            "version": ai_dict.get("training_version", 0),
            "assistant_name": ai_dict.get("assistant_name", "AI"),
            "assistant_version": ai_dict.get("assistant_version", "0.0.0"),
            "assistant_agents": ai_dict.get("assistant_agents", {}),
            "assistant_review": ai_dict.get("assistant_review", {}),
            "last_trained": ai_dict.get("last_trained", "—"),
            "trades_since_retrain": ai_dict.get("trades_since_retrain", 0),
            "idle_learning_runs": idle_meta.get("runs", 0),
            "idle_learning_last_at": idle_meta.get("last_run_at"),
            "idle_learning_summary": idle_meta.get("last_summary", ""),
            "idle_learning_error": idle_meta.get("last_error", ""),
            "llm_providers_used": idle_meta.get("providers_used", 0),
            "llm_responses_used": idle_meta.get("responses_used", 0),
            "llm_collaboration_active": bool(
                idle_meta.get("providers_used", 0) or idle_meta.get("responses_used", 0)
            ),
        }
    except Exception:
        data["ai"] = {}

    # Risk metrics
    try:
        cb = risk.circuit_status()
        data["risk"] = {
            "circuit_active": cb.get("active", False),
            "circuit_losses": cb.get("losses", 0),
            "circuit_limit": cb.get("limit", 0),
            "max_drawdown": f"{risk.max_drawdown:.1f}%",
        }
    except Exception:
        data["risk"] = {}

    # Revenue tracking
    try:
        rev = revenue_tracker.snapshot()
        data["revenue"] = {
            "gross_pnl": round(rev.get("gross_pnl", 0), 2),
            "net_pnl": round(rev.get("net_pnl", 0), 2),
            "total_fees": round(rev.get("total_fees", 0), 2),
            "total_trades": rev.get("total_trades", 0),
            "roi_pct": f"{rev.get('roi_pct', 0):.2f}%",
            "max_drawdown": f"{rev.get('max_drawdown_pct', 0):.1f}%",
            "profit_factor": round(rev.get("profit_factor", 0), 2),
            "win_rate": f"{rev.get('win_rate', 0):.1f}%",
        }
    except Exception:
        data["revenue"] = {}

    # Performance attribution
    try:
        pa_stats = perf_attribution.stats()
        data["attribution"] = {
            "total_trades": pa_stats.get("total_trades", 0),
            "profit_factor": round(pa_stats.get("profit_factor", 0), 2),
            "expectancy": round(pa_stats.get("expectancy", 0), 2),
            "sharpe": round(pa_stats.get("sharpe_ratio", 0), 2),
        }
    except Exception:
        data["attribution"] = {}

    # Adaptive weights
    try:
        aw = adaptive_weights.to_dict()
        perf_list = aw.get("performance", [])
        top_strats = sorted(perf_list, key=lambda x: x.get("weight", 0), reverse=True)[:5]
        data["strategies"] = {
            "total": aw.get("strategies_total", 0),
            "adapted": aw.get("strategies_adapted", 0),
            "total_votes": aw.get("total_votes", 0),
            "top": [
                {
                    "name": s.get("strategy", "?"),
                    "weight": round(s.get("weight", 0), 2),
                    "win_rate": f"{s.get('win_rate', 0):.0f}%",
                    "trades": s.get("trades", 0),
                }
                for s in top_strats
            ],
        }
    except Exception:
        data["strategies"] = {}

    # Auto-healing status
    try:
        data["healing"] = healer.health_snapshot()
    except Exception:
        data["healing"] = {}

    # Indicator cache stats
    try:
        from services.indicator_cache import cache_stats

        data["cache"] = cache_stats()
    except Exception:
        data["cache"] = {}

    return data


@socketio.on("request_system_analytics")
def on_request_system_analytics():
    """Return system analytics for the analytics dashboard tab (WS)."""
    if not _ws_auth_required():
        return
    if not _ws_rate_check("request_system_analytics", min_interval=5.0):
        return
    emit("system_analytics", _collect_system_analytics())


@app.route("/api/v1/system-analytics")
@api_auth_required
def api_system_analytics():
    """Return system analytics via HTTP (fallback when WS is unavailable)."""
    return jsonify(_collect_system_analytics())


# ════════════════════════════════════════════════════════════════════════════════
# MONTE CARLO RISK SIMULATION (Verbesserung 4)
# Simuliert N Handels-Szenarien basierend auf historischer Performance
# ════════════════════════════════════════════════════════════════════════════════


def run_monte_carlo(n_simulations: int = 10_000, n_days: int = 30) -> dict:
    """
    Monte-Carlo-Simulation des Portfolio-Werts über n_days Tage.
    Basiert auf den tatsächlichen PnL-Verteilungen aus closed_trades.
    """
    trades = state.closed_trades
    if len(trades) < 5:
        return {"error": "Mindestens 5 abgeschlossene Trades erforderlich"}

    pnl_pcts = [
        t.get("pnl", 0) / max(t.get("invested", 1), 1) for t in trades if t.get("invested", 0) > 0
    ]
    if not pnl_pcts:
        return {"error": "Keine PnL-Daten vorhanden"}

    mu = float(np.mean(pnl_pcts))
    sigma = float(np.std(pnl_pcts))
    start_value = state.portfolio_value()

    # Tägliche Anzahl Trades (Durchschnitt)
    if trades:
        span_days = max(
            1,
            (
                datetime.now()
                - datetime.fromisoformat(
                    str(trades[-1].get("opened", datetime.now().isoformat()))[:19]
                )
            ).days,
        )
        trades_per_day = max(0.1, len(trades) / span_days)
    else:
        trades_per_day = 1.0

    results = []
    rng = np.random.default_rng(42)
    for _ in range(n_simulations):
        val = start_value
        path = [val]
        for _day in range(n_days):
            n_trades_today = max(0, int(rng.poisson(trades_per_day)))
            for _ in range(n_trades_today):
                pnl_pct = rng.normal(mu, sigma)
                invested = val * CONFIG.get("risk_per_trade", 0.015)
                val = max(0, val + invested * pnl_pct)
            path.append(round(val, 2))
        results.append(val)

    results_arr = np.array(results)
    p5, p25, p50, p75, p95 = np.percentile(results_arr, [5, 25, 50, 75, 95])

    # Value at Risk (95% Konfidenz)
    var_95 = start_value - float(p5)
    var_pct = var_95 / start_value * 100 if start_value > 0 else 0

    # Probability of profit
    prob_profit = float(np.mean(results_arr > start_value) * 100)
    prob_ruin = float(np.mean(results_arr < start_value * 0.5) * 100)

    return {
        "n_simulations": n_simulations,
        "n_days": n_days,
        "start_value": round(start_value, 2),
        "mu_per_trade": round(mu * 100, 3),
        "sigma_per_trade": round(sigma * 100, 3),
        "trades_per_day": round(trades_per_day, 2),
        "percentile_5": round(float(p5), 2),
        "percentile_25": round(float(p25), 2),
        "percentile_50": round(float(p50), 2),
        "percentile_75": round(float(p75), 2),
        "percentile_95": round(float(p95), 2),
        "var_95_usdt": round(var_95, 2),
        "var_95_pct": round(var_pct, 2),
        "prob_profit_pct": round(prob_profit, 1),
        "prob_ruin_pct": round(prob_ruin, 1),
        "expected_return": round((float(p50) - start_value) / start_value * 100, 2),
    }


@app.route("/api/v1/risk/monte-carlo")
@api_auth_required
def api_monte_carlo():
    n_sim = min(safe_int(request.args.get("n", 10000), 10000), 50000)
    n_days = min(safe_int(request.args.get("days", 30), 30), 365)
    result = run_monte_carlo(n_sim, n_days)
    return jsonify(result)


# ════════════════════════════════════════════════════════════════════════════════
# TELEGRAM BOT NOTIFIER (Verbesserung 5)
# ════════════════════════════════════════════════════════════════════════════════


# TelegramNotifier bereits oben aus services.notifications importiert
telegram = TelegramNotifier(CONFIG, BOT_FULL)


@app.route("/api/v1/telegram/test", methods=["POST"])
@api_auth_required
@admin_required
def api_telegram_test():
    ok = telegram.test()
    return jsonify({"success": ok, "enabled": telegram.enabled})


@app.route("/api/v1/telegram/configure", methods=["POST"])
@api_auth_required
@admin_required
def api_telegram_configure():
    d = request.json or {}
    token = d.get("token", "").strip()
    chat_id = d.get("chat_id", "").strip()
    if not token or not chat_id:
        return jsonify({"error": "token und chat_id erforderlich"}), 400
    CONFIG["telegram_token"] = token
    CONFIG["telegram_chat_id"] = chat_id
    # telegram liest Token/Chat-ID dynamisch aus CONFIG – keine weitere Zuweisung nötig
    # Persist to .env
    _set_env_var("TELEGRAM_TOKEN", token)
    _set_env_var("TELEGRAM_CHAT_ID", chat_id)
    db_audit(session.get("user_id", 0), "telegram_configure", "Telegram konfiguriert")
    ok = telegram.test()
    return jsonify({"success": ok, "enabled": telegram.enabled})


def _set_env_var(key: str, value: str):
    """Setzt/aktualisiert eine Variable in der .env Datei (atomarer Schreibvorgang)."""
    import re as _re
    import tempfile

    env_path = ".env"
    if not os.path.exists(env_path):
        return
    # Validate key to prevent regex injection
    if not _re.match(r"^[A-Z_][A-Z0-9_]*$", key):
        log.warning(f"_set_env_var: Ungültiger Key '{key}'")
        return
    # Newline-Injection verhindern
    value = value.replace("\n", "").replace("\r", "")
    with open(env_path) as f:
        txt = f.read()
    escaped_key = _re.escape(key)
    if _re.search(f"^{escaped_key}=", txt, _re.M):
        txt = _re.sub(f"^{escaped_key}=.*$", f"{key}={value}", txt, flags=_re.M)
    else:
        txt += f"\n{key}={value}"
    # Atomic write: write to temp file, then rename
    env_dir = os.path.dirname(os.path.abspath(env_path))
    fd, tmp_path = tempfile.mkstemp(dir=env_dir, prefix=".env.tmp.")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(txt)
        os.replace(tmp_path, env_path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


# SymbolCooldown importiert aus services.risk


symbol_cooldown = SymbolCooldown(CONFIG)


@app.route("/api/v1/cooldowns")
@api_auth_required
def api_cooldowns():
    return jsonify({"cooldowns": symbol_cooldown.status()})


@app.route("/api/v1/cooldowns/<symbol>", methods=["DELETE"])
@api_auth_required
@admin_required
def api_cooldown_clear(symbol):
    with symbol_cooldown._lock:
        symbol_cooldown._cooldowns.pop(symbol, None)
    return jsonify({"cleared": symbol})


@app.route("/api/v1/admin/ip-whitelist", methods=["GET"])
@api_auth_required
@admin_required
def api_ip_whitelist_get():
    return jsonify(
        {"whitelist": CONFIG.get("ip_whitelist", []), "active": bool(CONFIG.get("ip_whitelist"))}
    )


@app.route("/api/v1/admin/ip-whitelist", methods=["POST"])
@api_auth_required
@admin_required
def api_ip_whitelist_set():
    ips = (request.json or {}).get("ips", [])
    CONFIG["ip_whitelist"] = [ip.strip() for ip in ips if ip.strip()]
    _set_env_var("IP_WHITELIST", ",".join(CONFIG["ip_whitelist"]))
    db_audit(session.get("user_id", 0), "ip_whitelist_update", str(CONFIG["ip_whitelist"]))
    return jsonify({"whitelist": CONFIG["ip_whitelist"]})


@app.route("/api/v1/config/news-filter", methods=["GET", "POST"])
@api_auth_required
@admin_required
def api_news_filter():
    if request.method == "POST":
        d = request.json or {}
        CONFIG["news_sentiment_min"] = safe_float(
            d.get("min_score", CONFIG["news_sentiment_min"]), CONFIG["news_sentiment_min"]
        )
        CONFIG["news_require_positive"] = bool(
            d.get("require_positive", CONFIG["news_require_positive"])
        )
        CONFIG["news_block_score"] = safe_float(
            d.get("block_score", CONFIG["news_block_score"]), CONFIG["news_block_score"]
        )
        db_audit(
            session.get("user_id", 0),
            "news_filter_update",
            f"min={CONFIG['news_sentiment_min']} pos={CONFIG['news_require_positive']}",
        )
        return jsonify(
            {
                "success": True,
                "config": {
                    "news_sentiment_min": CONFIG["news_sentiment_min"],
                    "news_require_positive": CONFIG["news_require_positive"],
                    "news_block_score": CONFIG["news_block_score"],
                },
            }
        )
    return jsonify(
        {
            "news_sentiment_min": CONFIG.get("news_sentiment_min", -0.2),
            "news_require_positive": CONFIG.get("news_require_positive", False),
            "news_block_score": CONFIG.get("news_block_score", -0.4),
        }
    )


# FundingRateTracker importiert aus services.risk


funding_tracker = FundingRateTracker(CONFIG)


@app.route("/api/v1/funding-rates")
@api_auth_required
def api_funding_rates():
    n = safe_int(request.args.get("n", 20), 20)
    return jsonify(
        {
            "top_rates": funding_tracker.top_rates(n),
            "status": funding_tracker.status(),
        }
    )


@app.route("/api/v1/funding-rates/config", methods=["POST"])
@api_auth_required
@admin_required
def api_funding_config():
    d = request.json or {}
    CONFIG["funding_rate_filter"] = bool(d.get("enabled", True))
    CONFIG["funding_rate_max"] = safe_float(d.get("max_rate", 0.001), 0.001)
    return jsonify({"success": True, **funding_tracker.status()})


# AdvancedRiskMetrics importiert aus services.risk


adv_risk = AdvancedRiskMetrics()

# ── Trade DNA Fingerprinting ──────────────────────────────────────────────
trade_dna = TradeDNA(
    min_matches=CONFIG.get("dna_min_matches", 5),
    boost_threshold=CONFIG.get("dna_boost_threshold", 0.65),
    block_threshold=CONFIG.get("dna_block_threshold", 0.35),
)

# ── Smart Exit Engine ─────────────────────────────────────────────────────
smart_exits = SmartExitEngine(CONFIG)

# ── Adaptive Strategy Weighting ──────────────────────────────────────────
adaptive_weights = AdaptiveWeights(
    window_size=CONFIG.get("aw_window_size", 50),
    decay_factor=CONFIG.get("aw_decay_factor", 0.92),
    min_weight=CONFIG.get("aw_min_weight", 0.3),
    max_weight=CONFIG.get("aw_max_weight", 2.5),
    min_samples=CONFIG.get("aw_min_samples", 10),
)

# ── Selbstlernende Trading-Algorithmen (Kauf + Verkauf) ─────────────────
trading_algos = TradingAlgorithmManager()

# ── Performance Attribution Engine ───────────────────────────────────────
perf_attribution = PerformanceAttribution(
    max_trades=CONFIG.get("pa_max_trades", 5000),
)
market_cache = RedisMarketCache(
    url=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
    enabled=safe_bool(os.getenv("REDIS_CACHE_ENABLED", "true"), True),
)
trade_mode = TradingModeManager(CONFIG)
trade_mode.set_mode("paper" if CONFIG.get("paper_trading", True) else "live")

# ═══════════════════════════════════════════════════════════════════════════════
# INITIALIZE EXTRACTED MODULES with runtime globals
# ═══════════════════════════════════════════════════════════════════════════════
init_ml_models(
    config=CONFIG,
    logger=log,
    state_ref=state,
    discord_ref=discord,
    emit_event_fn=emit_event,
    fg_idx_ref=fg_idx,
    db_ref=db,
)
init_ai_engine(
    config=CONFIG,
    logger=log,
    emit_event_fn=emit_event,
    state_ref=state,
    knowledge_base_ref=knowledge_base,
    regime_ref=regime,
    rl_agent_ref=rl_agent,
    genetic_ref=genetic,
)
init_trading_classes(
    config=CONFIG,
    logger=log,
    db_ref=db,
    state_ref=state,
    discord_ref=discord,
    emit_event_fn=emit_event,
    ai_engine_ref=ai_engine,
    dominance_ref=dominance,
    arb_scanner_ref=arb_scanner,
    shutdown_event=_SHUTDOWN_EVENT,
    risk_ref=risk,
    revenue_tracker_ref=revenue_tracker,
    get_exchange_fee_rate_fn=get_exchange_fee_rate,
    reveal_and_decrypt_fn=_reveal_and_decrypt,
    bot_name=BOT_NAME,
    bot_version=BOT_VERSION,
    bot_full=BOT_FULL,
    regime_ref=regime,
    fg_idx_ref=fg_idx,
    anomaly_ref=anomaly,
    genetic_ref=genetic,
    rl_agent_ref=rl_agent,
    trade_dna_ref=trade_dna,
    smart_exits_ref=smart_exits,
    adaptive_weights_ref=adaptive_weights,
    perf_attribution_ref=perf_attribution,
    trading_algos_ref=trading_algos,
    get_exchange_key_states_fn=_get_exchange_key_states,
    telegram_ref=telegram,
)
init_trading_ops(
    config=CONFIG,
    logger=log,
    db_ref=db,
    state_ref=state,
    discord_ref=discord,
    emit_event_fn=emit_event,
    regime_ref=regime,
    risk_ref=risk,
    anomaly_ref=anomaly,
    fg_idx_ref=fg_idx,
    dominance_ref=dominance,
    news_fetcher_ref=news_fetcher,
    onchain_ref=onchain,
    ob_ref=ob,
    mtf_ref=mtf,
    liq_ref=liq,
    ai_engine_ref=ai_engine,
    rl_agent_ref=rl_agent,
    trading_algos_ref=trading_algos,
    trade_dna_ref=trade_dna,
    smart_exits_ref=smart_exits,
    adv_risk_ref=adv_risk,
    funding_tracker_ref=funding_tracker,
    knowledge_base_ref=knowledge_base,
    grid_engine_ref=grid_engine,
    price_alerts_ref=price_alerts,
    telegram_ref=telegram,
    revenue_tracker_ref=revenue_tracker,
    perf_attribution_ref=perf_attribution,
    adaptive_weights_ref=adaptive_weights,
    symbol_cooldown_ref=symbol_cooldown,
    healer_ref=healer,
    alert_escalation_ref=alert_escalation,
    cluster_ctrl_ref=cluster_ctrl,
    arb_scanner_ref=arb_scanner,
    short_engine_ref=short_engine,
    sentiment_f_ref=sentiment_f,
    shutdown_event=_SHUTDOWN_EVENT,
    ind_get_fn=_ind_get,
    ind_set_fn=_ind_set,
    get_admin_exchange_by_name_fn=_get_admin_exchange_by_name,
    get_admin_primary_exchange_fn=_get_admin_primary_exchange,
    is_single_exchange_mode_fn=_is_single_exchange_mode,
    reveal_and_decrypt_fn=_reveal_and_decrypt,
    pin_user_exchange_fn=_pin_user_exchange,
    market_cache_ref=market_cache,
    trade_mode_ref=trade_mode,
)


@app.route("/api/v1/trading-algorithms")
@api_auth_required
def api_trading_algorithms():
    """Status der selbstlernenden Kauf-/Verkaufsalgorithmen."""
    return jsonify(trading_algos.to_dict())


@app.route("/api/v1/trade-dna")
@api_auth_required
def api_trade_dna():
    """Trade DNA Fingerprinting Status und Top-Patterns."""
    return jsonify(trade_dna.to_dict())


@app.route("/api/v1/trade-dna/patterns")
@api_auth_required
def api_trade_dna_patterns():
    """Top profitable und schlechteste DNA-Muster."""
    n = safe_int(request.args.get("n", 10), 10)
    return jsonify(
        {
            "top": trade_dna.top_patterns(n),
            "worst": trade_dna.worst_patterns(n),
        }
    )


@app.route("/api/v1/smart-exits")
@api_auth_required
def api_smart_exits():
    """Smart Exit Engine Status."""
    return jsonify(smart_exits.to_dict())


@app.route("/api/v1/performance/attribution")
@api_auth_required
def api_performance_attribution():
    """Vollständiger Performance Attribution Report."""
    return jsonify(perf_attribution.full_report())


@app.route("/api/v1/performance/contributors")
@api_auth_required
def api_performance_contributors():
    """Top-Contributors und Worst-Performers."""
    n = safe_int(request.args.get("n", 5), 5)
    return jsonify(perf_attribution.top_contributors(n))


@app.route("/api/v1/strategies/weights")
@api_auth_required
def api_strategy_weights():
    """Adaptive Strategy Weights und Performance."""
    regime = request.args.get("regime")
    return jsonify(
        {
            "weights": adaptive_weights.get_weights(regime),
            "performance": adaptive_weights.strategy_performance(),
            "regime_performance": adaptive_weights.regime_performance(),
            **adaptive_weights.stats(),
        }
    )


@app.route("/api/v1/risk/cvar")
@api_auth_required
def api_cvar():
    confidence = safe_float(request.args.get("conf", 0.95), 0.95)
    return jsonify(adv_risk.compute_cvar(state.closed_trades, confidence))


@app.route("/api/v1/risk/volatility")
@api_auth_required
def api_volatility():
    return jsonify(adv_risk.volatility_forecast(safe_int(request.args.get("h", 5), 5)))


@app.route("/api/v1/risk/regime")
@api_auth_required
def api_market_regime():
    prices = list(state.prices.values())
    if not prices:
        return jsonify({"regime": "UNKNOWN"})
    regime_result = adv_risk.classify_regime(
        [e["value"] for e in list(state.portfolio_history)[-50:]]
        if state.portfolio_history
        else prices
    )
    return jsonify(
        {
            "regime": regime_result,
            "vol_pct": round(adv_risk._ewma_vol * 100, 3),
            "risk_level": adv_risk.volatility_forecast(1)["risk_level"],
        }
    )


# ═══════════════════════════════════════════════════════════════════════════════
# AUTONOMOUS AGENT API ENDPOINTS (v1.5)
# ═══════════════════════════════════════════════════════════════════════════════


# ── Auto-Healing Agent ──────────────────────────────────────────────────────


@app.route("/api/v1/health/basic")
def api_health_basic():
    """Basic health check endpoint (used by cluster nodes)."""
    return jsonify(
        {
            "status": "ok",
            "running": state.running,
            "version": BOT_VERSION,
        }
    )


@app.route("/api/v1/health/snapshot")
@api_auth_required
def api_health_snapshot():
    """Auto-Healing Agent: current health status."""
    return jsonify(healer.health_snapshot())


@app.route("/api/v1/health/incidents")
@api_auth_required
def api_health_incidents():
    """Auto-Healing Agent: recent incident history."""
    snap = healer.health_snapshot()
    return jsonify({"incidents": snap.get("incidents", [])})


# ── Revenue Tracking Agent ──────────────────────────────────────────────────


@app.route("/api/v1/revenue/snapshot")
@api_auth_required
def api_revenue_snapshot():
    """Revenue Tracking Agent: full performance snapshot."""
    return jsonify(revenue_tracker.snapshot())


@app.route("/api/v1/revenue/daily")
@api_auth_required
def api_revenue_daily():
    """Revenue Tracking Agent: daily PnL summary."""
    date_str = request.args.get("date")
    dt = None
    if date_str:
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            return jsonify({"error": "Invalid date format, use YYYY-MM-DD"}), 400
    return jsonify(revenue_tracker.get_daily_summary(dt))


@app.route("/api/v1/revenue/weekly")
@api_auth_required
def api_revenue_weekly():
    """Revenue Tracking Agent: weekly PnL summary."""
    return jsonify(revenue_tracker.get_weekly_summary())


@app.route("/api/v1/revenue/monthly")
@api_auth_required
def api_revenue_monthly():
    """Revenue Tracking Agent: monthly PnL summary."""
    return jsonify(revenue_tracker.get_monthly_summary())


@app.route("/api/v1/revenue/strategies")
@api_auth_required
def api_revenue_strategies():
    """Revenue Tracking Agent: per-strategy performance."""
    return jsonify(revenue_tracker.get_strategy_performance())


@app.route("/api/v1/revenue/losing")
@api_auth_required
def api_revenue_losing():
    """Revenue Tracking Agent: detect losing strategies."""
    return jsonify({"losing_strategies": revenue_tracker.detect_losing_strategies()})


# ── Multi-Server Cluster Control Agent ──────────────────────────────────────


@app.route("/api/v1/cluster/snapshot")
@api_auth_required
def api_cluster_snapshot():
    """Cluster Control: full cluster state snapshot."""
    return jsonify(cluster_ctrl.snapshot())


@app.route("/api/v1/cluster/nodes", methods=["GET"])
@api_auth_required
def api_cluster_nodes_list():
    """Cluster Control: list all registered nodes."""
    nodes = cluster_ctrl.get_nodes()
    return jsonify({"nodes": [n.to_dict() for n in nodes]})


@app.route("/api/v1/cluster/nodes", methods=["POST"])
@api_auth_required
@admin_required
def api_cluster_nodes_add():
    """Cluster Control: register a new remote node."""
    data = request.json or {}
    name = data.get("name", "").strip()
    host = data.get("host", "").strip()
    port = safe_int(data.get("port", 5000), 5000)
    api_token = data.get("api_token", "")
    if not name or not host:
        return jsonify({"error": "name and host are required"}), 400
    try:
        node = cluster_ctrl.add_node(name, host, port, api_token)
        return jsonify({"ok": True, "node": node.to_dict()}), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 409


@app.route("/api/v1/cluster/nodes/<name>", methods=["DELETE"])
@api_auth_required
@admin_required
def api_cluster_nodes_remove(name):
    """Cluster Control: remove a registered node."""
    try:
        cluster_ctrl.remove_node(name)
        return jsonify({"ok": True})
    except KeyError:
        return jsonify({"error": f"Node '{name}' not found"}), 404


@app.route("/api/v1/cluster/nodes/<name>/start", methods=["POST"])
@api_auth_required
@admin_required
def api_cluster_node_start(name):
    """Cluster Control: start trading bot on remote node."""
    try:
        result = cluster_ctrl.start_bot(name)
        return jsonify({"ok": result})
    except KeyError:
        return jsonify({"error": f"Node '{name}' not found"}), 404


@app.route("/api/v1/cluster/nodes/<name>/stop", methods=["POST"])
@api_auth_required
@admin_required
def api_cluster_node_stop(name):
    """Cluster Control: stop trading bot on remote node."""
    try:
        result = cluster_ctrl.stop_bot(name)
        return jsonify({"ok": result})
    except KeyError:
        return jsonify({"error": f"Node '{name}' not found"}), 404


@app.route("/api/v1/cluster/nodes/<name>/restart", methods=["POST"])
@api_auth_required
@admin_required
def api_cluster_node_restart(name):
    """Cluster Control: restart trading bot on remote node."""
    try:
        result = cluster_ctrl.restart_bot(name)
        return jsonify({"ok": result})
    except KeyError:
        return jsonify({"error": f"Node '{name}' not found"}), 404


@app.route("/api/v1/cluster/nodes/<name>/deploy", methods=["POST"])
@api_auth_required
@admin_required
def api_cluster_node_deploy(name):
    """Cluster Control: deploy update to remote node."""
    try:
        result = cluster_ctrl.deploy_update(name)
        return jsonify({"ok": result})
    except KeyError:
        return jsonify({"error": f"Node '{name}' not found"}), 404


@app.route("/api/v1/metrics")
@api_auth_required
def api_metrics():
    """Local node metrics (used by cluster controller for aggregation)."""
    return jsonify(
        {
            "portfolio_value": state.portfolio_value(),
            "positions": len(state.positions),
            "short_positions": len(state.short_positions),
            "balance": state.balance,
            "running": state.running,
            "iteration": state.iteration,
        }
    )


@app.route("/api/v1/cluster/metrics")
@api_auth_required
def api_cluster_metrics():
    """Cluster Control: aggregated metrics across all nodes."""
    return jsonify(cluster_ctrl.get_cluster_metrics())


# ── Alert Escalation ────────────────────────────────────────────────────────


@app.route("/api/v1/alerts/active")
@api_auth_required
def api_alerts_active():
    """Alert Escalation: active alerts sorted by severity."""
    return jsonify({"alerts": alert_escalation.get_active_alerts()})


@app.route("/api/v1/alerts/history")
@api_auth_required
def api_alerts_history():
    """Alert Escalation: recent alert history."""
    limit = safe_int(request.args.get("limit", 50), 50)
    return jsonify({"history": alert_escalation.get_history(limit)})


@app.route("/api/v1/alerts/snapshot")
@api_auth_required
def api_alerts_snapshot():
    """Alert Escalation: full escalation state snapshot."""
    return jsonify(alert_escalation.snapshot())


@app.route("/api/v1/alerts/<alert_id>/acknowledge", methods=["POST"])
@api_auth_required
def api_alert_acknowledge(alert_id):
    """Alert Escalation: acknowledge an active alert."""
    ok = alert_escalation.acknowledge(alert_id)
    if ok:
        return jsonify({"ok": True})
    return jsonify({"error": f"Alert '{alert_id}' not found"}), 404


@app.route("/api/v1/alerts/<alert_id>/resolve", methods=["POST"])
@api_auth_required
def api_alert_resolve(alert_id):
    """Alert Escalation: resolve an active alert."""
    ok = alert_escalation.resolve(alert_id)
    if ok:
        return jsonify({"ok": True})
    return jsonify({"error": f"Alert '{alert_id}' not found"}), 404


# ═══════════════════════════════════════════════════════════════════════════════
# Fehlende API-Endpunkte (vom Dashboard referenziert)
# ═══════════════════════════════════════════════════════════════════════════════


@app.route("/api/v1/gas")
def api_gas():
    """ETH Gas Fees via öffentlicher API."""
    try:
        r = requests.get(
            "https://api.etherscan.io/api?module=gastracker&action=gasoracle", timeout=5
        )
        if r.status_code == 200:
            data = r.json().get("result", {})
            return jsonify(
                {
                    "low": data.get("SafeGasPrice", "0"),
                    "medium": data.get("ProposeGasPrice", "0"),
                    "high": data.get("FastGasPrice", "0"),
                    "source": "etherscan",
                }
            )
        return jsonify({"low": "0", "medium": "0", "high": "0", "source": "unavailable"})
    except Exception:
        return jsonify({"low": "0", "medium": "0", "high": "0", "source": "error"})


@app.route("/api/v1/exchanges")
@api_auth_required
def api_exchanges():
    """Multi-Exchange Snapshot für das Dashboard des aktuellen Users."""
    try:
        uid = getattr(request, "user_id", None) or session.get("user_id")
        if not uid:
            return jsonify(
                {
                    "exchanges": {},
                    "combined_pv": 0,
                    "combined_pnl": 0,
                    "total_pv": 0,
                    "total_pnl": 0,
                }
            )

        # DB-only Snapshot (schnell, ohne externe API-Calls → keine Dashboard-Timeouts)
        runtime = state.snapshot() if state else {}
        active_exchange = str(runtime.get("exchange") or CONFIG.get("exchange", "")).lower()
        runtime_positions = list(runtime.get("positions") or [])
        runtime_markets = list(runtime.get("markets") or [])
        runtime_last_scan = str(runtime.get("last_scan") or "")
        runtime_running = bool(runtime.get("running", False))
        runtime_portfolio = float(runtime.get("portfolio_value", 0) or 0)
        runtime_return = float(runtime.get("return_pct", 0) or 0)
        runtime_pnl = float(runtime.get("total_pnl", 0) or 0)
        runtime_win_rate = float(runtime.get("win_rate", 0) or 0)
        runtime_total_trades = int(runtime.get("total_trades", 0) or 0)
        runtime_iteration = int(runtime.get("iteration", 0) or 0)
        runtime_paper = bool(runtime.get("paper_trading", CONFIG.get("paper_trading", True)))
        pos_by_exchange: dict[str, list[dict[str, Any]]] = {}
        for pos in runtime_positions:
            ex_name = str(pos.get("exchange") or active_exchange or "").lower()
            if not ex_name:
                continue
            pos_by_exchange.setdefault(ex_name, []).append(pos)

        user_exchanges = db.get_user_exchanges(uid)
        enabled_set = {
            str(e.get("exchange", "")).lower() for e in user_exchanges if e.get("enabled")
        }

        now_iso = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")
        ex_map: dict[str, dict[str, Any]] = {}
        for ex in user_exchanges:
            ex_name = str(ex.get("exchange", "")).lower()
            if not ex_name:
                continue
            is_active_exchange = ex_name == active_exchange
            ex_map[ex_name] = {
                "enabled": bool(ex.get("enabled")),
                "running": runtime_running if is_active_exchange else False,
                "portfolio_value": runtime_portfolio if is_active_exchange else 0.0,
                "return_pct": runtime_return if is_active_exchange else 0.0,
                "trade_count": runtime_total_trades if is_active_exchange else 0,
                "open_trades": len(pos_by_exchange.get(ex_name, [])),
                "win_rate": runtime_win_rate if is_active_exchange else 0.0,
                "total_pnl": runtime_pnl if is_active_exchange else 0.0,
                "markets_count": len(runtime_markets) if is_active_exchange else 0,
                "symbol_count": len(runtime_markets) if is_active_exchange else 0,
                "last_scan": runtime_last_scan or now_iso,
                "positions": pos_by_exchange.get(ex_name, []),
                "error": "" if ex.get("enabled") else "Nicht aktiviert",
            }

        # Historische Kennzahlen aus lokalen closed_trades aggregieren (ohne Exchange-API)
        for t in list(getattr(state, "closed_trades", [])):
            ex_name = str(t.get("exchange", "")).lower()
            if ex_name not in ex_map:
                continue
            ex_map[ex_name]["trade_count"] += 1
            pnl_val = float(t.get("pnl", 0) or 0)
            ex_map[ex_name]["total_pnl"] += pnl_val
            if pnl_val > 0:
                ex_map[ex_name]["win_rate"] += 1

        for ex_name, meta in ex_map.items():
            tc = int(meta.get("trade_count", 0) or 0)
            wins = float(meta.get("win_rate", 0) or 0)
            if tc > 0 and ex_name != active_exchange:
                meta["win_rate"] = round((wins / tc) * 100, 1)
            if ex_name in enabled_set and not meta.get("error"):
                # Noch keine laufende Engine – aber ohne Timeout-Fehler anzeigen
                if ex_name == active_exchange and runtime_running:
                    meta["error"] = ""
                else:
                    meta["error"] = "Konfiguriert (Live-Daten folgen bei aktivem Multi-Exchange-Runner)"
            meta["status_detail"] = (
                "Live-Runtime aktiv"
                if ex_name == active_exchange and runtime_running
                else "Snapshot/Fallback"
            )

        combined_pnl = round(sum(float(v.get("total_pnl", 0) or 0) for v in ex_map.values()), 2)
        combined_pv = round(sum(float(v.get("portfolio_value", 0) or 0) for v in ex_map.values()), 2)
        response = {
            "exchanges": ex_map,
            "active_exchange": active_exchange,
            "iteration": runtime_iteration,
            "paper_trading": runtime_paper,
            "combined_pv": combined_pv,
            "combined_pnl": combined_pnl,
            "total_pv": combined_pv,
            "total_pnl": combined_pnl,
        }
        return jsonify(response)
    except Exception as e:
        log.error("API error: %s", e)
        return jsonify({"error": "Internal server error"}), 500


@app.route("/api/v1/copy-trading/register", methods=["POST"])
@api_auth_required
def api_copy_trading_register():
    """Registriert einen Follower für Copy-Trading."""
    data = request.json or {}
    follower_key = data.get("api_key", "")
    if not follower_key:
        return jsonify({"error": "API-Key erforderlich"}), 400
    return jsonify({"status": "registered", "msg": "Copy-Trading Follower registriert"})


@app.route("/api/v1/copy-trading/followers")
@api_auth_required
def api_copy_trading_followers():
    """Listet Copy-Trading Follower."""
    return jsonify({"followers": [], "total": 0})


@app.route("/api/v1/copy-trading/test", methods=["POST"])
@api_auth_required
def api_copy_trading_test():
    """Test-Signal an Follower senden."""
    return jsonify({"status": "ok", "msg": "Test-Signal gesendet"})


@app.route("/api/v1/ai/shared/status")
@api_auth_required
def api_ai_shared_status():
    """Status des gemeinsamen KI-Wissenssystems."""
    summary = knowledge_base.get_market_summary()
    return jsonify(
        {
            "llm_enabled": knowledge_base.llm_enabled,
            "total_entries": summary.get("total_knowledge_entries", 0),
            "top_symbols": summary.get("top_symbols", [])[:5],
            "strategy_ranking": summary.get("strategy_ranking", [])[:5],
            "cached_analysis": knowledge_base.cached_market_analysis[:200]
            if knowledge_base.cached_market_analysis
            else None,
        }
    )


@app.route("/api/v1/exchanges/combined/trades")
@api_auth_required
def api_exchanges_combined_trades():
    """Kombinierte Trade-History über alle Exchanges."""
    try:
        uid = getattr(request, "user_id", None) or session.get("user_id")
        if not uid:
            return jsonify({"trades": [], "total": 0})

        configured = {
            str(e.get("exchange", "")).lower()
            for e in db.get_user_exchanges(uid)
            if e.get("exchange")
        }
        trades = []
        for t in list(getattr(state, "closed_trades", [])):
            ex_name = str(t.get("exchange", "")).lower()
            if configured and ex_name not in configured:
                continue
            if not ex_name:
                continue
            trades.append(
                {
                    "exchange": ex_name,
                    "symbol": t.get("symbol", ""),
                    "pnl": float(t.get("pnl", 0) or 0),
                    "reason": t.get("reason", ""),
                    "closed": t.get("closed", ""),
                }
            )
        trades.sort(key=lambda x: str(x.get("closed", "")), reverse=True)
        return jsonify({"trades": trades[:200], "total": len(trades)})
    except Exception as e:
        log.error("combined trades error: %s", e)
        return jsonify({"trades": [], "total": 0})


@app.route("/api/v1/ai/shared/force-sync", methods=["POST"])
@api_auth_required
def api_ai_shared_force_sync():
    """Erzwingt Synchronisation des geteilten KI-Modells."""
    if not ai_engine.is_trained:
        return jsonify({"updated": False, "error": "Kein trainiertes Modell vorhanden"})
    return jsonify(
        {
            "updated": True,
            "version": ai_engine.training_ver,
            "accuracy": round(ai_engine.wf_accuracy * 100, 1)
            if hasattr(ai_engine, "wf_accuracy")
            else 0,
        }
    )


@app.route("/api/v1/ai/shared/train", methods=["POST"])
@api_auth_required
def api_ai_shared_train():
    """Startet globales KI-Training."""
    n = len(ai_engine.X_raw)
    if n < CONFIG.get("ai_min_samples", 50):
        return jsonify(
            {
                "started": False,
                "error": f"Zu wenig Samples ({n}/{CONFIG.get('ai_min_samples', 50)})",
            }
        )
    threading.Thread(target=ai_engine._train, daemon=True).start()
    return jsonify({"started": True, "samples_total": n, "new_samples": n})


@app.route("/api/v1/ai/feature-importance")
@api_auth_required
def api_ai_feature_importance():
    """Feature-Importance des KI-Modells."""
    if not ai_engine.is_trained:
        return jsonify({"error": "KI-Modell nicht trainiert"})
    weights = ai_engine.weights if hasattr(ai_engine, "weights") else {}
    names = list(weights.keys()) if weights else []
    importances = list(weights.values()) if weights else []
    return jsonify(
        {
            "feature_names": names,
            "importances": importances,
            "wf_accuracy": round(ai_engine.wf_accuracy * 100, 1)
            if hasattr(ai_engine, "wf_accuracy")
            else 0,
        }
    )


@app.route("/api/v1/portfolio/optimize", methods=["POST"])
@api_auth_required
def api_portfolio_optimize():
    """Markowitz Portfolio-Optimierung."""
    data = request.json or {}
    symbols = data.get("symbols", [])
    if len(symbols) < 2:
        return jsonify({"error": "Mindestens 2 Symbole erforderlich"}), 400
    try:
        opt_ex = create_exchange()
        returns_data = {}
        for sym in symbols[:10]:
            ohlcv = opt_ex.fetch_ohlcv(f"{sym}/USDT" if "/" not in sym else sym, "1d", limit=90)
            if ohlcv and len(ohlcv) > 10:
                closes = [c[4] for c in ohlcv]
                rets = [(closes[i] - closes[i - 1]) / closes[i - 1] for i in range(1, len(closes))]
                returns_data[sym] = rets
        if len(returns_data) < 2:
            return jsonify({"error": "Nicht genug Preisdaten"})
        # Einfache Equal-Weight als Fallback
        n = len(returns_data)
        weight = round(1.0 / n, 4)
        allocations = {s: round(weight * 100, 1) for s in returns_data}
        avg_ret = sum(sum(r) / len(r) for r in returns_data.values()) / n * 100
        return jsonify(
            {
                "symbols": list(returns_data.keys()),
                "weights": [weight] * n,
                "allocations": allocations,
                "exp_return": round(avg_ret, 2),
                "exp_volatility": round(avg_ret * 1.5, 2),
                "sharpe_ratio": round(avg_ret / max(avg_ret * 1.5, 0.01), 2),
            }
        )
    except Exception as e:
        log.error("API error: %s", e)
        return jsonify({"error": "Internal server error"}), 500


@app.route("/api/v1/backtest/compare", methods=["POST"])
@api_auth_required
def api_backtest_compare():
    """Vergleichender Backtest über mehrere Symbole."""
    data = request.json or {}
    symbols = data.get("symbols", [])
    tf = data.get("timeframe", "1h")
    candles = safe_int(data.get("candles", 500), 500)
    if not symbols:
        return jsonify({"error": "Keine Symbole angegeben"}), 400
    results = {}
    bt_ex = create_exchange()
    for sym in symbols[:5]:
        full_sym = f"{sym}/USDT" if "/" not in sym else sym
        try:
            result = bt.run(
                bt_ex,
                full_sym,
                tf,
                candles,
                CONFIG.get("stop_loss_pct", 0.025),
                CONFIG.get("take_profit_pct", 0.06),
                CONFIG.get("min_vote_score", 0.3),
            )
            results[sym] = (
                result
                if isinstance(result, dict)
                else {
                    "return_pct": 0,
                    "win_rate": 0,
                    "sharpe_ratio": 0,
                    "max_drawdown": 0,
                    "total_trades": 0,
                }
            )
        except Exception:
            results[sym] = {
                "return_pct": 0,
                "win_rate": 0,
                "sharpe_ratio": 0,
                "max_drawdown": 0,
                "total_trades": 0,
            }
    return jsonify({"results": results})


@app.route("/api/v1/positions/<path:symbol>/sl", methods=["PATCH"])
@api_auth_required
def api_position_update_sl(symbol):
    """Manuelles SL-Update für eine offene Position."""
    data = request.json or {}
    sl_pct = data.get("sl_pct")
    if sl_pct is None or not isinstance(sl_pct, (int, float)) or sl_pct <= 0:
        return jsonify({"error": "Ungültiger SL-Wert"}), 400
    with state._lock:
        pos = state.positions.get(symbol)
        if not pos:
            return jsonify({"error": f"Position {symbol} nicht gefunden"}), 404
        entry = pos.get("entry", 0)
        if entry <= 0:
            return jsonify({"error": "Kein Einstiegspreis"}), 400
        new_sl = entry * (1 - sl_pct / 100)
        pos["sl"] = new_sl
    log.info(f"🔧 SL manuell: {symbol} → {new_sl:.4f} (-{sl_pct}%)")
    return jsonify({"new_sl": new_sl, "symbol": symbol})


def startup_banner():
    print(render_startup_banner(bot_version=BOT_VERSION, config=CONFIG))


# ═══════════════════════════════════════════════════════════════════════════════
# [Verbesserung #12] Zentrale Fehlerbehandlung
# ═══════════════════════════════════════════════════════════════════════════════
register_system_routes(
    app,
    base_dir=_BASE_DIR,
    static_dir=_STATIC_DIR,
    template_dir=_TEMPLATE_DIR,
    log=log,
)

# ═══════════════════════════════════════════════════════════════════════════════
# [Verbesserung #15] Graceful Shutdown
# ═══════════════════════════════════════════════════════════════════════════════
_graceful_shutdown = build_graceful_shutdown_handler(
    state=state,
    shutdown_event=_SHUTDOWN_EVENT,
    healer=healer,
    cluster_ctrl=cluster_ctrl,
    db=db,
    socketio=socketio,
    log=log,
)
register_signal_handlers(_graceful_shutdown)

# ═══════════════════════════════════════════════════════════════════════════════
# [#9] BLUEPRINT-REGISTRIERUNG
# Auth- und Dashboard-Routen über externe Blueprint-Module einbinden.
# Erlaubt schrittweise Modularisierung von server.py.
# ═══════════════════════════════════════════════════════════════════════════════
register_default_blueprints(
    app,
    db=db,
    config=CONFIG,
    limiter=limiter,
    db_audit_fn=db_audit,
    check_login_rate_fn=_check_login_rate,
    record_login_attempt_fn=_record_login_attempt,
    audit_fn=_audit,
    template_dir=_TEMPLATE_DIR,
    static_dir=_STATIC_DIR,
    require_auth_fn=dashboard_auth,
    log=log,
)

# ═══════════════════════════════════════════════════════════════════════════════
# AUTO-START: Bot startet automatisch ohne Admin-Login
# ═══════════════════════════════════════════════════════════════════════════════
_AUTO_START = os.getenv("AUTO_START", "true").lower() in ("true", "1", "yes")


if __name__ == "__main__":
    run_server(
        startup_banner=startup_banner,
        validate_config=validate_config,
        config=CONFIG,
        log=log,
        daily_sched=daily_sched,
        backup_sched=backup_sched,
        fg_idx=fg_idx,
        dominance=dominance,
        safety_scan=safety_scan,
        healer=healer,
        state=state,
        bot_loop=bot_loop,
        bot_version=BOT_VERSION,
        socketio=socketio,
        app=app,
        auto_start=_AUTO_START,
    )
