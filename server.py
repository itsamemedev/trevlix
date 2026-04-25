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
║                                                                              ║
║  TRADING-FEATURES                                                            ║
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
    get_json_body,
    safe_bool,
    safe_float,
    safe_int,
)
from app.core.request_helpers import (
    normalize_exchange_name as _normalize_exchange_name,
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
import app.core.trading_ops as _trading_ops_mod
from app.core.trading_ops import (
    _preflight_exchange_markets,
    bot_loop,
    close_position,
    create_exchange,
    fetch_aggregated_balance,
    fetch_markets,
    get_exchange_fee_rate,
    get_heatmap_data,
    get_virginie_forecast_feed,
    get_virginie_forecast_quality,
    get_virginie_forecast_stats,
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
    """Force paper-trading mode if PAPER_TRADING=true is explicitly set."""
    if safe_bool(os.getenv("PAPER_TRADING", "false"), False):
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


@app.errorhandler(404)
def _handle_404(_e):
    """JSON-safe 404 response for API, HTML for browser."""
    if request.path.startswith("/api/"):
        return jsonify({"error": "not_found"}), 404
    return "Not Found", 404


@app.errorhandler(405)
def _handle_405(_e):
    if request.path.startswith("/api/"):
        return jsonify({"error": "method_not_allowed"}), 405
    return "Method Not Allowed", 405


@app.errorhandler(500)
def _handle_500(e):
    """Catch-all 500 handler – never leak exception details to clients."""
    try:
        log.error("Unhandled 500 on %s: %s", request.path, e)
    except Exception:
        pass
    if request.path.startswith("/api/"):
        return jsonify({"error": "internal_server_error"}), 500
    return "Internal Server Error", 500


@app.errorhandler(Exception)
def _handle_unexpected(e):
    """Fallback for uncaught exceptions – prevents stack-trace leakage."""
    from werkzeug.exceptions import HTTPException

    if isinstance(e, HTTPException):
        return e
    try:
        log.exception("Unhandled exception on %s", request.path)
    except Exception:
        pass
    if request.path.startswith("/api/"):
        return jsonify({"error": "internal_server_error"}), 500
    return "Internal Server Error", 500


def normalize_exchange_name(raw: Any) -> str:
    """Normalisiert und validiert einen Exchange-Namen."""
    return _normalize_exchange_name(raw, EXCHANGE_MAP)


def _generate_csrf_token() -> str:
    """Kompatibler Wrapper für Jinja-Global/Tests."""
    return _core_generate_csrf_token(session)


app.jinja_env.globals["csrf_token"] = _generate_csrf_token
app.jinja_env.globals["bot_version"] = BOT_VERSION
app.jinja_env.globals["bot_name"] = BOT_NAME


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
    edge_score = max(
        0.0, min(100.0, (wf * 0.55) + ((1.0 - drift) * 35.0) + (autonomy * 10.0) - risk_load)
    )
    tier = (
        "S"
        if edge_score >= 85
        else ("A" if edge_score >= 70 else ("B" if edge_score >= 55 else "C"))
    )
    urgency = (
        "high" if (drift >= 0.75 or edge_score < 45) else ("medium" if edge_score < 65 else "low")
    )
    signature = uuid.uuid5(
        uuid.NAMESPACE_DNS,
        f"{status.get('assistant_version', '0')}-{snap.get('exchange', 'na')}-{tier}-{int(edge_score)}-{int(drift * 100)}",
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
        return (
            summary
            or "Noch kein Self-Review vorhanden. Nach weiteren Entscheidungen erneut prüfen."
        )
    if cmd in {"/plan", "plan", "/diagnose", "diagnose"}:
        advice = _virginie_runtime_advice()
        action_lines = [
            f"{i + 1}. [{a.get('priority', 'low')}] {a.get('title', 'Schritt')} – {a.get('detail', '')}"
            for i, a in enumerate(advice.get("actions", []))
        ]
        return "VIRGINIE Aktionsplan:\n" + (
            "\n".join(action_lines) if action_lines else "Keine Aktionen."
        )
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
    except Exception as exc:
        log.debug("Agent-Notifier Discord fehlgeschlagen: %s", exc)
    try:
        telegram = TelegramNotifier(CONFIG)
        telegram.send(f"<b>Agent Alert</b>\n{msg}")
    except Exception as exc:
        log.debug("Agent-Notifier Telegram fehlgeschlagen: %s", exc)


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

# LLM ↔ Agenten-Bridge: MCP-Registry erhält Live-Referenzen auf Orchestrator
# und Ops-Agenten, damit die LLM über query_llm_with_tools() direkt
# Agenten-Tasks ausführen kann (execute_agent_task, healing_status, ...).
try:
    mcp_registry.set_agent_refs(
        virginie_orchestrator=getattr(ai_engine, "virginie_orchestrator", None),
        healer=healer,
        alert_escalation=alert_escalation,
        cluster_ctrl=cluster_ctrl,
    )
except Exception as exc:  # noqa: BLE001
    log.warning("MCP-Registry Agent-Bindung fehlgeschlagen: %s", exc)


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


# ═══════════════════════════════════════════════════════════════════════════════
# KI-GEMEINSCHAFTSWISSEN API
# ═══════════════════════════════════════════════════════════════════════════════


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


@app.route("/api/v1/pine-script")
@dashboard_auth
def api_pine_script():
    """Liefert die aktuelle Trevlix-Strategie als TradingView Pine Script v5.

    Verwendet die Live-CONFIG-Werte (SL/TP/Trailing/Break-Even), damit das
    exportierte Skript mit der Bot-Konfiguration übereinstimmt.
    """
    symbol = str(request.args.get("symbol", "BTCUSDT")).upper().replace("/", "")
    sl_pct = float(CONFIG.get("stop_loss_pct", 0.02)) * 100
    tp_pct = float(CONFIG.get("take_profit_pct", 0.05)) * 100
    trailing_pct = float(CONFIG.get("trailing_pct", 0.015)) * 100
    be_trigger = float(CONFIG.get("break_even_trigger", 0.015)) * 100
    be_buffer = float(CONFIG.get("break_even_buffer", 0.001)) * 100
    min_conf = float(CONFIG.get("ai_min_confidence", 0.55)) * 100
    script = f"""//@version=5
// TREVLIX Strategy Export – automatisch generiert
// Symbol: {symbol}
strategy("TREVLIX {symbol}", overlay=true, initial_capital=10000,
         default_qty_type=strategy.percent_of_equity, default_qty_value=10,
         pyramiding=0, commission_type=strategy.commission.percent, commission_value=0.1)

// ── Parameter (aus Live-Config) ────────────────────────────────────────
slPct       = input.float({sl_pct:.2f}, "Stop-Loss %",   step=0.1) / 100
tpPct       = input.float({tp_pct:.2f}, "Take-Profit %", step=0.1) / 100
trailPct    = input.float({trailing_pct:.2f}, "Trailing %",    step=0.1) / 100
beTrigger   = input.float({be_trigger:.2f}, "Break-Even Trigger %", step=0.1) / 100
beBuffer    = input.float({be_buffer:.3f}, "Break-Even Buffer %",  step=0.01) / 100
aiMinConf   = input.float({min_conf:.0f}, "Min. Konfidenz %", step=5) / 100

// ── Indikatoren (Trevlix-Kerngewichte) ─────────────────────────────────
rsiVal  = ta.rsi(close, 14)
emaFast = ta.ema(close, 21)
emaSlow = ta.ema(close, 50)
[macdLine, signalLine, _hist] = ta.macd(close, 12, 26, 9)
bbBasis = ta.sma(close, 20)
bbDev   = 2 * ta.stdev(close, 20)
bbUpper = bbBasis + bbDev
bbLower = bbBasis - bbDev

// ── Signal-Score (vereinfachte Trevlix-Voting-Logik) ───────────────────
score =  (rsiVal < 35 ? 1 : 0)
       + (emaFast > emaSlow ? 1 : 0)
       + (macdLine > signalLine ? 1 : 0)
       + (close < bbLower ? 1 : 0)
confidence = score / 4.0

longCond  = confidence >= aiMinConf and strategy.position_size == 0
exitCond  = rsiVal > 70 or close < emaSlow

// ── Entries / Exits ────────────────────────────────────────────────────
if longCond
    strategy.entry("Long", strategy.long)

if strategy.position_size > 0
    entry = strategy.position_avg_price
    slLvl = entry * (1 - slPct)
    tpLvl = entry * (1 + tpPct)
    // Break-Even Stop anheben
    if close >= entry * (1 + beTrigger)
        slLvl := entry * (1 + beBuffer)
    strategy.exit("Exit", "Long", stop=slLvl, limit=tpLvl, trail_points=close * trailPct, trail_offset=close * trailPct)
    if exitCond
        strategy.close("Long", comment="Signal")

plot(emaFast, "EMA 21", color=color.new(color.yellow, 0))
plot(emaSlow, "EMA 50", color=color.new(color.orange, 0))
plot(bbUpper, "BB Upper", color=color.new(color.gray, 70))
plot(bbLower, "BB Lower", color=color.new(color.gray, 70))
"""
    return Response(
        script,
        mimetype="text/plain",
        headers={
            "Content-Disposition": f"attachment;filename=trevlix_{symbol.lower()}.pine",
        },
    )


@app.route("/api/backtest/history")
@dashboard_auth
def api_backtest_history():
    return jsonify(db.get_recent_backtests(10))


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


# ── [Verbesserung #48] Prometheus-kompatible Metriken ─────────────────────────


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

    # Apply user's stored paper_trading preference — overrides global default so
    # individual users can switch to live mode even when admin set paper globally.
    try:
        user_settings = db.get_user_settings(user_id) or {}
        if "paper_trading" in user_settings:
            desired_paper = bool(user_settings["paper_trading"])
            if CONFIG.get("paper_trading") != desired_paper:
                CONFIG["paper_trading"] = desired_paper
                trade_mode.set_mode("paper" if desired_paper else "live")
                log.debug("User %s paper_trading=%s aus Settings geladen", user_id, desired_paper)
    except Exception as _pt_exc:
        log.debug("paper_trading aus Settings laden fehlgeschlagen: %s", _pt_exc)

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
    snap["llm"] = _get_llm_header_status()
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
    snap["llm"] = _get_llm_header_status()
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
    raw_uid = getattr(request, "user_id", None) or session.get("user_id")
    if not raw_uid:
        emit("virginie_chat_error", {"error": "Nicht authentifiziert."})
        return
    user_id = int(raw_uid)
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
    _valid = {
        "cryptocom",
        "binance",
        "bybit",
        "okx",
        "kucoin",
        "kraken",
        "huobi",
        "coinbase",
        "bitget",
        "mexc",
        "gateio",
    }
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
def on_update_config(data: dict | None = None):
    data = data or {}
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
        "use_market_regime",
        "arb_min_spread_pct",
        "arb_scan_limit",
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
        "break_even_trigger",
        "break_even_buffer",
        "partial_tp_pct",
        "use_grid",
        "use_rl",
        "use_lstm",
        # Exchange selection – allowed for all authenticated users
        "exchange",
        "timeframe",
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
        "break_even_trigger",
        "break_even_buffer",
        "partial_tp_pct",
        "portfolio_goal",
        "arb_min_spread_pct",
    }
    _int_keys = {
        "max_open_trades",
        "scan_interval",
        "circuit_breaker_losses",
        "circuit_breaker_min",
        "dca_max_levels",
        "lstm_lookback",
        "discord_report_hour",
        "arb_scan_limit",
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
        "bitget",
        "mexc",
        "gateio",
    }
    updated: dict[str, Any] = {}
    for k, v in data.items():
        if k not in allowed:
            continue
        if k == "paper_trading":
            desired_paper = bool(v)
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
        if k == "timeframe":
            tf = str(v).strip().lower()
            if tf in {"1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "8h", "12h", "1d"}:
                CONFIG["timeframe"] = tf
                updated["timeframe"] = tf
            continue
        if k in _numeric_keys:
            v = safe_float(v, CONFIG.get(k, 0.0))
            if v < 0:
                continue  # Reject negative numeric values
        elif k in _int_keys:
            v = safe_int(v, CONFIG.get(k, 0))
            if v < 0:
                continue  # Reject negative int values
        elif isinstance(CONFIG.get(k), bool):
            v = bool(v)
        # Sanity: reject unreasonable values for critical keys
        if k == "max_open_trades" and (v < 1 or v > 100):
            continue
        if k == "stop_loss_pct" and (v <= 0 or v > 50):
            continue
        if k == "take_profit_pct" and (v <= 0 or v > 500):
            continue
        if k == "scan_interval" and (v < 5 or v > 3600):
            continue
        if k == "risk_per_trade" and (v <= 0 or v > 0.5):
            continue
        CONFIG[k] = v
        updated[k] = v
    # Persistenz: Admin-Settings in der DB speichern, damit sie einen Restart überleben.
    persist_failed = False
    try:
        uid = getattr(request, "user_id", session.get("user_id"))
        if uid and updated:
            current = db.get_user_settings(uid) or {}
            current.update(updated)
            current["paper_trading"] = CONFIG.get("paper_trading", True)
            db.update_user_settings(uid, current)
    except Exception as e:
        persist_failed = True
        log.warning(f"update_config persist failed: {e}")
    if not updated:
        emit(
            "status",
            {
                "msg": "⚠️ Keine gültigen Einstellungen übermittelt",
                "key": "ws_settings_none",
                "type": "warning",
            },
        )
    elif persist_failed:
        emit(
            "status",
            {
                "msg": "⚠️ Einstellungen aktiv, Persistenz fehlgeschlagen",
                "key": "ws_settings_persist_failed",
                "type": "warning",
            },
        )
    else:
        emit(
            "status",
            {
                "msg": "✅ Einstellungen gespeichert",
                "key": "ws_settings_saved",
                "type": "success",
            },
        )
    emit("update", state.snapshot(), broadcast=True)


@socketio.on("save_api_keys")
def on_save_keys(data: dict | None = None):
    data = data or {}
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
def on_update_discord(data: dict | None = None):
    data = data or {}
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


def _run_ai_job(target, name: str, done_key: str, done_msg: str) -> None:
    """Run an AI background job and broadcast a completion / error status."""
    try:
        target()
        emit_event(
            "status",
            {"msg": done_msg, "key": done_key, "type": "success"},
        )
    except Exception as e:
        log.warning(f"{name} failed: {e}")
        emit_event(
            "status",
            {
                "msg": f"❌ {name} fehlgeschlagen: {e}",
                "key": f"{done_key}_failed",
                "type": "error",
            },
        )


@socketio.on("force_train")
def on_force_train():
    if not _ws_admin_required():
        return
    emit("status", {"msg": "🧠 KI-Training gestartet...", "key": "ws_ai_training", "type": "info"})
    threading.Thread(
        target=_run_ai_job,
        args=(ai_engine._train, "KI-Training", "ws_ai_training_done", "✅ KI-Training fertig"),
        daemon=True,
    ).start()


@socketio.on("force_optimize")
def on_force_optimize():
    if not _ws_admin_required():
        return
    emit("status", {"msg": "🔬 Optimierung läuft...", "key": "ws_ai_optimizing", "type": "info"})
    threading.Thread(
        target=_run_ai_job,
        args=(
            ai_engine._optimize,
            "Optimierung",
            "ws_ai_optimizing_done",
            "✅ Optimierung fertig",
        ),
        daemon=True,
    ).start()


@socketio.on("force_genetic")
def on_force_genetic():
    if not _ws_admin_required():
        return
    emit(
        "status",
        {"msg": "🧬 Genetischer Optimizer gestartet...", "key": "ws_ai_genetic", "type": "info"},
    )
    trades = list(state.closed_trades)
    threading.Thread(
        target=_run_ai_job,
        args=(
            lambda: genetic.evolve(trades),
            "Genetischer Optimizer",
            "ws_ai_genetic_done",
            "✅ Genetischer Optimizer fertig",
        ),
        daemon=True,
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
def on_close_position(data: dict | None = None):
    data = data or {}
    if not _ws_auth_required():
        return
    if not _ws_rate_check("close_position", min_interval=2.0):
        emit(
            "status",
            {"msg": "⏳ Zu schnell – bitte warten", "key": "ws_rate_limit", "type": "warning"},
        )
        return
    sym = str(data.get("symbol", "") or "").strip()
    if not sym:
        emit(
            "status",
            {
                "msg": "❌ Kein Symbol übergeben",
                "key": "ws_close_no_symbol",
                "type": "error",
            },
        )
        return
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
    else:
        emit(
            "status",
            {
                "msg": f"⚠️ Keine offene Position für {sym}",
                "key": "ws_close_no_position",
                "type": "warning",
            },
        )


@socketio.on("run_backtest")
def on_run_backtest(data: dict | None = None):
    data = data or {}
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
def on_add_alert(data: dict | None = None):
    data = data or {}
    if not _ws_auth_required():
        return
    uid = session.get("user_id")
    if not uid:
        emit("auth_error", {"msg": "Nicht authentifiziert"})
        return
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
def on_delete_alert(data: dict | None = None):
    data = data or {}
    if not _ws_auth_required():
        return
    uid = session.get("user_id")
    # Scope to current user unless session user is admin (user_id=1 by policy)
    # so a non-admin cannot delete alerts owned by someone else.
    is_admin = bool(session.get("is_admin")) or uid == 1
    db.delete_alert(safe_int(data.get("id", 0), 0), user_id=None if is_admin else uid)
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
        opps = arb_scanner.scan(list(state.markets))
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
def on_admin_create_user(data: dict | None = None):
    data = data or {}
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


# ════════════════════════════════════════════════════════════════════════════════
# GRID TRADING ENGINE (modularisiert → services/grid_trading.py)
# ════════════════════════════════════════════════════════════════════════════════
from services.grid_trading import GridTradingEngine  # noqa: E402

grid_engine = GridTradingEngine()


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
def on_undo_close(data: dict | None = None):
    data = data or {}
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
def on_start_exchange(data: dict | None = None):
    data = data or {}
    if not _ws_auth_required():
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
def on_stop_exchange(data: dict | None = None):
    data = data or {}
    if not _ws_auth_required():
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
def on_save_exchange_keys(data: dict | None = None):
    data = data or {}
    if not _ws_auth_required():
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
    if not ok:
        log.warning("Exchange-Keys DB-Speicherung fehlgeschlagen für %s", ex_name)
    # Zusätzlich in CONFIG für sofortige Nutzung im laufenden Prozess spiegeln
    if "extra_exchanges" not in CONFIG:
        CONFIG["extra_exchanges"] = {}
    CONFIG["extra_exchanges"][ex_name] = {
        "api_key": encrypt_value(api_key),
        "secret": encrypt_value(secret),
        "passphrase": encrypt_value(passphrase) if passphrase else "",
    }
    # Balance-Cache invalidieren, damit der nächste /api/v1/exchanges-Aufruf
    # die frisch hinterlegten Keys verwendet statt einen veralteten Snapshot.
    if uid:
        try:
            from routes.api.market import invalidate_balance_cache

            invalidate_balance_cache(uid, ex_name)
        except Exception:  # pragma: no cover – Cache-Invalidierung ist best-effort
            pass
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
def on_close_exchange_position(data: dict | None = None):
    data = data or {}
    if not _ws_admin_required():
        return
    if not _ws_rate_check("close_exchange_position", min_interval=2.0):
        emit(
            "status",
            {"msg": "⏳ Zu schnell – bitte warten", "key": "ws_rate_limit", "type": "warning"},
        )
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
        with state._lock:
            pos = state.positions.get(symbol)
            amount = pos.get("qty", 0) if pos else 0
        if amount > 0:
            try:
                order = ex.create_market_sell_order(symbol, amount)
                log.info(
                    "Exchange-Position geschlossen: %s auf %s (qty=%.6f, order=%s)",
                    symbol,
                    ex_name,
                    amount,
                    (order or {}).get("id", "?"),
                )
            except Exception as sell_err:
                log.error("Sell-Order fehlgeschlagen: %s %s: %s", symbol, ex_name, sell_err)
                emit(
                    "status",
                    {
                        "msg": f"❌ Order fehlgeschlagen: {sell_err}",
                        "key": "ws_close_error",
                        "type": "error",
                    },
                )
                return
        elif amount <= 0:
            log.warning("close_exchange_position: Keine offene Menge für %s", symbol)
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
        log.error("close_exchange_position fehlgeschlagen: %s %s: %s", symbol, ex_name, e)
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


def _get_llm_header_status() -> dict[str, Any]:
    """Günstige LLM-Status-Ermittlung für den Header-Chip (keine Netzwerk-Calls)."""
    llm_endpoint = CONFIG.get("llm_endpoint", "") or getattr(knowledge_base, "_llm_endpoint", "")
    llm_model = CONFIG.get("llm_model", "—") or getattr(knowledge_base, "_llm_model", "—")
    out: dict[str, Any] = {
        "endpoint": llm_endpoint or "—",
        "model": llm_model,
        "provider": "—",
        "status": "⚪ Nicht konfiguriert",
    }
    if llm_endpoint:
        out["provider"] = _derive_llm_provider_name(llm_endpoint)
        out["status"] = "✅ Konfiguriert"
    try:
        multi_llm = getattr(knowledge_base, "_multi_llm", None)
        if multi_llm:
            provider_stats = multi_llm.status()
            if provider_stats:
                active_ok = [p for p in provider_stats if p.get("available")]
                if not llm_endpoint:
                    out["endpoint"] = "multi-provider"
                if out["model"] in ("", "—"):
                    out["model"] = ", ".join(p.get("name", "?") for p in provider_stats[:3])
                primary = (active_ok or provider_stats)[0]
                out["provider"] = str(primary.get("name", "—")).title()
                out["status"] = (
                    f"✅ {len(active_ok)}/{len(provider_stats)} Provider online"
                    if active_ok
                    else "❌ Alle Provider offline"
                )
    except Exception as e:
        log.debug("LLM header status failed: %s", e)
    return out


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
                active_ok = [p for p in provider_stats if p.get("available")]
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
            "is_trained": ai_dict.get("is_trained", False),
            "training_ver": ai_dict.get("training_version", 0),
            "status_msg": ai_dict.get("status_msg", ""),
            "progress_pct": ai_dict.get("progress_pct", 0),
            "wf_accuracy": ai_dict.get("wf_accuracy", 0),
            "bull_accuracy": ai_dict.get("bull_accuracy", 0),
            "bear_accuracy": ai_dict.get("bear_accuracy", 0),
            "samples": ai_dict.get("samples", 0),
            "bull_samples": ai_dict.get("bull_samples", 0),
            "bear_samples": ai_dict.get("bear_samples", 0),
            "allowed_count": ai_dict.get("allowed_count", 0),
            "blocked_count": ai_dict.get("blocked_count", 0),
            "weights": ai_dict.get("weights", []),
            "ai_log": ai_dict.get("ai_log", []),
            "trained": ai_dict.get("is_trained", False),
            "accuracy": f"{ai_dict.get('accuracy', 0) * 100:.1f}%",
            "cv_accuracy": f"{ai_dict.get('cv_accuracy', 0) * 100:.1f}%",
            "predictions": ai_dict.get("predictions_made", 0),
            "correct": ai_dict.get("predictions_correct", 0),
            "version": ai_dict.get("training_version", 0),
            "assistant_name": ai_dict.get("assistant_name", "AI"),
            "assistant_version": ai_dict.get("assistant_version", "0.0.0"),
            "assistant_examples": ai_dict.get("assistant_examples", {}),
            "assistant_agents": ai_dict.get("assistant_agents", {}),
            "assistant_review": ai_dict.get("assistant_review", {}),
            "assistant_primary_control": ai_dict.get("assistant_primary_control", False),
            "assistant_autonomy_weight": ai_dict.get("assistant_autonomy_weight", 0.7),
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
        "expected_return": round((float(p50) - start_value) / start_value * 100, 2)
        if start_value > 0
        else 0.0,
    }


# ════════════════════════════════════════════════════════════════════════════════
# TELEGRAM BOT NOTIFIER (Verbesserung 5)
# ════════════════════════════════════════════════════════════════════════════════


# TelegramNotifier bereits oben aus services.notifications importiert
telegram = TelegramNotifier(CONFIG, BOT_FULL)


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
funding_tracker = FundingRateTracker(CONFIG)
adv_risk = AdvancedRiskMetrics()

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


# ═══════════════════════════════════════════════════════════════════════════════
# AUTONOMOUS AGENT API ENDPOINTS (v1.5)
# ═══════════════════════════════════════════════════════════════════════════════


# ── Auto-Healing Agent ──────────────────────────────────────────────────────


# ── Revenue Tracking Agent ──────────────────────────────────────────────────


# ── Multi-Server Cluster Control Agent ──────────────────────────────────────


# ── Alert Escalation ────────────────────────────────────────────────────────


# ═══════════════════════════════════════════════════════════════════════════════
# Fehlende API-Endpunkte (vom Dashboard referenziert)
# ═══════════════════════════════════════════════════════════════════════════════


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
# (Muss vor der AppDeps-Konstruktion definiert sein, da AppDeps
#  ``_maybe_auto_start_bot`` als Callback übergibt.)
# ═══════════════════════════════════════════════════════════════════════════════
_AUTO_START = os.getenv("AUTO_START", "true").lower() in ("true", "1", "yes")


def _has_any_configured_exchange() -> bool:
    """Prüft, ob mindestens ein aktivierter Exchange mit API-Keys vorhanden ist.

    Im Paper-Trading-Modus ist keine Exchange-Konfiguration erforderlich –
    dann immer True. Im Live-Modus: mindestens ein User-Exchange in der DB
    mit ``enabled=1`` und vorhandenem ``api_key``, oder Legacy-ENV-Keys.
    """
    if CONFIG.get("paper_trading", True):
        return True
    # Legacy Single-Exchange-ENV (API_KEY/API_SECRET) – zählt als konfiguriert.
    legacy_key = (os.getenv("API_KEY") or "").strip()
    legacy_secret = (os.getenv("API_SECRET") or "").strip()
    if legacy_key and legacy_secret:
        return True
    try:
        with db._get_conn() as conn:
            with conn.cursor() as c:
                c.execute(
                    "SELECT COUNT(*) AS n FROM user_exchanges "
                    "WHERE enabled=1 AND api_key IS NOT NULL AND api_key!=''"
                )
                row = c.fetchone() or {}
                return int(row.get("n", 0) or 0) > 0
    except Exception as e:  # noqa: BLE001
        log.debug(f"_has_any_configured_exchange: {e}")
        return False


def _maybe_auto_start_bot() -> bool:
    """Startet den Bot-Loop, wenn AUTO_START aktiv ist, der Bot noch nicht
    läuft und mindestens eine Exchange konfiguriert ist.

    Gibt True zurück, wenn der Bot in diesem Aufruf gestartet wurde.
    """
    if not _AUTO_START:
        return False
    if not _has_any_configured_exchange():
        return False
    # Start atomar unter state._lock prüfen und setzen, damit parallele
    # HTTP-Calls nicht zwei Bot-Loops gleichzeitig starten.
    with state._lock:
        if getattr(state, "running", False):
            return False
        state.running = True
        state.paused = False
    threading.Thread(target=bot_loop, daemon=True, name="BotLoop").start()
    log.info("🚀 Bot auto-gestartet (Exchange konfiguriert)")
    state.add_activity(
        "🚀",
        "Auto-Start",
        f"v{BOT_VERSION} · {CONFIG.get('exchange', '—').upper()}",
        "success",
    )
    return True


# ── API-Blueprint-Registrierung ────────────────────────────────────────────
from routes.api.deps import AppDeps
from routes.api.trading import create_trading_blueprint
from routes.api.admin import create_admin_blueprint
from routes.api.ai import create_ai_blueprint
from routes.api.system import create_system_blueprint
from routes.api.market import create_market_blueprint

_api_deps = AppDeps(
    config=CONFIG,
    state=state,
    db=db,
    log=log,
    api_auth_required=api_auth_required,
    admin_required=admin_required,
    get_json_body=get_json_body,
    safe_int=safe_int,
    safe_float=safe_float,
    safe_bool=safe_bool,
    create_exchange=create_exchange,
    close_position=close_position,
    open_position=open_position,
    fetch_markets=fetch_markets,
    scan_symbol=scan_symbol,
    get_exchange_fee_rate=get_exchange_fee_rate,
    get_heatmap_data=get_heatmap_data,
    fetch_aggregated_balance=fetch_aggregated_balance,
    safety_scan=safety_scan,
    trading_ops_mod=_trading_ops_mod,
    bot_version=BOT_VERSION,
    bot_name=BOT_NAME,
    bot_full=BOT_FULL,
    ai_engine=ai_engine,
    backtest=bt,
    tax_report=tax,
    trade_mode=trade_mode,
    knowledge=knowledge_base,
    mcp_tools=mcp_registry,
    risk_mgr=risk,
    adv_risk=adv_risk,
    revenue=revenue_tracker,
    cluster_ctrl=cluster_ctrl,
    alert_escalation=alert_escalation,
    healer=healer,
    perf_attribution=perf_attribution,
    trade_dna=trade_dna,
    trading_algos=trading_algos,
    smart_exits=smart_exits,
    grid_engine=grid_engine,
    arb_scanner=arb_scanner,
    short_engine=short_engine,
    dominance=dominance,
    anomaly=anomaly,
    genetic=genetic,
    rl_agent=rl_agent,
    news_fetcher=news_fetcher,
    onchain=onchain,
    fg_idx=fg_idx,
    sentiment_f=sentiment_f,
    funding_tracker=funding_tracker,
    adaptive_weights=adaptive_weights,
    symbol_cooldown=symbol_cooldown,
    liq=liq,
    ob=ob,
    discord=discord,
    telegram=telegram,
    price_alerts=price_alerts,
    emit_event=emit_event,
    limiter=limiter,
    exchange_default_fees=EXCHANGE_DEFAULT_FEES,
    exchange_map={},
    get_virginie_forecast_feed=get_virginie_forecast_feed,
    get_virginie_forecast_quality=get_virginie_forecast_quality,
    get_virginie_forecast_stats=get_virginie_forecast_stats,
    audit_fn=_audit,
    db_audit_fn=db_audit,
    build_prometheus_lines=build_prometheus_lines,
    build_ws_state_snapshot=build_ws_state_snapshot,
    trades_to_json=trades_to_json,
    tax_rows_to_csv=tax_rows_to_csv,
    verify_latest_backup=verify_latest_backup,
    apply_update=_apply_update,
    get_update_status=_get_update_status,
    rollback_update=_rollback_update,
    reveal_and_decrypt=_reveal_and_decrypt,
    is_single_exchange_mode=_is_single_exchange_mode,
    get_admin_exchange_by_name=_get_admin_exchange_by_name,
    get_admin_primary_exchange=_get_admin_primary_exchange,
    get_exchange_key_states=_get_exchange_key_states,
    pin_user_exchange=_pin_user_exchange,
    normalize_exchange_name=normalize_exchange_name,
    validate_admin_user_payload=validate_admin_user_payload,
    is_admin_password_weak=is_admin_password_weak,
    get_llm_header_status_fn=_get_llm_header_status,
    maybe_auto_start_bot_fn=_maybe_auto_start_bot,
    set_env_var_fn=_set_env_var,
    bot_loop_fn=bot_loop,
)

app.register_blueprint(create_trading_blueprint(_api_deps))
app.register_blueprint(create_admin_blueprint(_api_deps))
app.register_blueprint(create_ai_blueprint(_api_deps))
app.register_blueprint(create_system_blueprint(_api_deps))
app.register_blueprint(create_market_blueprint(_api_deps))

# ── Observability wiring (request-ID, metrics middleware, health checks) ──
try:
    from app.core.observability_setup import (
        install_http_metrics_middleware,
        register_default_health_checks,
        register_default_metrics,
    )
    from services.request_context import (
        install_flask_request_id,
        install_log_filter,
    )

    install_log_filter(log)
    install_flask_request_id(app)
    register_default_metrics()
    install_http_metrics_middleware(app)
    register_default_health_checks(
        db=db,
        exchange_manager=None,
        llm_provider=None,
        healer=healer,
    )
except Exception as _obs_exc:  # noqa: BLE001 - observability must not block startup
    log.warning("observability wiring failed: %s", _obs_exc)

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
        has_configured_exchanges=_has_any_configured_exchange,
        db=db,
    )
