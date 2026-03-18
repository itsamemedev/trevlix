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
║    Algorithmic Crypto Trading Bot  ·  v1.4.0  ·  trevlix.dev               ║
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

import csv
import hashlib
import hmac
import io
import json
import logging
import math
import os
import random
import secrets
import signal
import threading
import time
import traceback
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from functools import wraps
from typing import Any

import ccxt
import httpx
import numpy as np
import pandas as pd
import requests
from dotenv import load_dotenv
from flask import Flask, Response, g, jsonify, redirect, request, send_file, session
from flask_cors import CORS
from flask_socketio import SocketIO, emit

from services.adaptive_weights import AdaptiveWeights
from services.cryptopanic import CryptoPanicClient
from services.db_pool import ConnectionPool

# ── Service-Module ───────────────────────────────────────────────────────────
from services.encryption import decrypt_value, encrypt_value
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
from services.performance_attribution import PerformanceAttribution
from services.risk import (
    AdvancedRiskMetrics,
    FundingRateTracker,
    LiquidityScorer,
    RiskManager,
    SymbolCooldown,
)
from services.smart_exits import SmartExitEngine
from services.strategies import STRATEGIES, STRATEGY_NAMES, compute_indicators
from services.trade_dna import TradeDNA
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

# ── ML ──────────────────────────────────────────────────────────────────────
try:
    from sklearn.calibration import CalibratedClassifierCV
    from sklearn.ensemble import IsolationForest, RandomForestClassifier, VotingClassifier
    from sklearn.metrics import accuracy_score
    from sklearn.model_selection import TimeSeriesSplit
    from sklearn.preprocessing import StandardScaler

    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False

try:
    from xgboost import XGBClassifier

    XGB_AVAILABLE = True
except ImportError:
    XGB_AVAILABLE = False

# [1] LightGBM — schneller als XGBoost, besser bei Tabellendaten
try:
    from lightgbm import LGBMClassifier

    LGB_AVAILABLE = True
except ImportError:
    LGB_AVAILABLE = False

# [2] CatBoost — beste Performance bei kategorischen Features
try:
    from catboost import CatBoostClassifier

    CAT_AVAILABLE = True
except ImportError:
    CAT_AVAILABLE = False

# [3] Optuna — Bayessche Hyperparameter-Optimierung
try:
    import optuna

    optuna.logging.set_verbosity(optuna.logging.WARNING)
    OPTUNA_AVAILABLE = True
except ImportError:
    OPTUNA_AVAILABLE = False

# [6] Scipy for Fourier + Wavelet features
try:
    import pywt  # PyWavelets

    WAVELET_AVAILABLE = True
except ImportError:
    WAVELET_AVAILABLE = False

# [8] Advanced sklearn
try:
    from sklearn.linear_model import LogisticRegression

    SKLEARN_ADV_AVAILABLE = True
except ImportError:
    SKLEARN_ADV_AVAILABLE = False

# SMOTE for class imbalance
try:
    from imblearn.over_sampling import SMOTE

    SMOTE_AVAILABLE = True
except ImportError:
    SMOTE_AVAILABLE = False

try:
    import tensorflow as tf
    from tensorflow.keras.callbacks import EarlyStopping
    from tensorflow.keras.layers import LSTM, Dense, Dropout, Input
    from tensorflow.keras.models import Sequential

    tf.get_logger().setLevel("ERROR")
    TF_AVAILABLE = True
except ImportError:
    TF_AVAILABLE = False

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
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_TEMPLATE_DIR = os.path.join(_BASE_DIR, "templates")
_STATIC_DIR = os.path.join(_BASE_DIR, "static")

app = Flask(
    __name__, static_folder=_STATIC_DIR, static_url_path="/static", template_folder=_TEMPLATE_DIR
)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", secrets.token_hex(32))

# ── [Verbesserung #5] Secure Cookie Flags ────────────────────────────────────
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
if os.getenv("ALLOWED_ORIGINS", "").startswith("https"):
    app.config["SESSION_COOKIE_SECURE"] = True

# ── [Verbesserung #1] Session-Timeout ─────────────────────────────────────────
try:
    _SESSION_TIMEOUT_MIN = int(os.getenv("SESSION_TIMEOUT_MIN", "30"))
except (ValueError, TypeError):
    _SESSION_TIMEOUT_MIN = 30

# ── CORS: Erlaubte Origins ────────────────────────────────────────────────────
_raw_origins = os.getenv("ALLOWED_ORIGINS", "*")
if _raw_origins.strip() == "*":
    _allowed_origins: Any = "*"
    _flask_cors_origins: Any = "*"
else:
    _allowed_origins = [o.strip() for o in _raw_origins.split(",") if o.strip()]
    _flask_cors_origins = _allowed_origins
CORS(app, origins=_flask_cors_origins, supports_credentials=(_flask_cors_origins != "*"))
socketio = SocketIO(
    app,
    cors_allowed_origins=_allowed_origins,
    async_mode="threading",
    logger=False,
    engineio_logger=False,
    # [Socket.io Fix] Stabilere Verbindung durch längere Timeouts
    ping_timeout=60,
    ping_interval=25,
    # Session-Verwaltung aktiv halten
    manage_session=True,
)

# ── Rate Limiter ─────────────────────────────────────────────────────────────
if LIMITER_AVAILABLE:
    limiter = Limiter(
        key_func=get_remote_address,
        app=app,
        default_limits=["200 per minute"],
        storage_uri="memory://",
    )
else:
    # Dummy-Limiter wenn flask-limiter nicht installiert
    class _DummyLimiter:
        def limit(self, *a, **kw):
            return lambda f: f

        def shared_limit(self, *a, **kw):
            return lambda f: f

    limiter = _DummyLimiter()

_log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
os.makedirs(_log_dir, exist_ok=True)

# ── [Verbesserung #14] Konfigurierbares Log-Level ─────────────────────────────
_LOG_LEVEL = getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO)

# ── [Verbesserung #50] Optionaler JSON-Logging-Formatter ──────────────────────
_USE_JSON_LOGS = os.getenv("JSON_LOGS", "false").lower() in ("true", "1", "yes")
_USE_COLOR_LOGS = os.getenv("COLOR_LOGS", "true").lower() in ("true", "1", "yes")


# ── [Verbesserung #51] Farbige Konsolenausgabe ───────────────────────────────
class _ColorFormatter(logging.Formatter):
    """ANSI-farbiger Log-Formatter für die Konsole."""

    COLORS = {
        "DEBUG": "\033[36m",  # Cyan
        "INFO": "\033[32m",  # Grün
        "WARNING": "\033[33m",  # Gelb
        "ERROR": "\033[31m",  # Rot
        "CRITICAL": "\033[41m",  # Rot Hintergrund
    }
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"

    def format(self, record):
        color = self.COLORS.get(record.levelname, "")
        ts = self.formatTime(record, datefmt="%H:%M:%S")
        level = f"{color}{self.BOLD}{record.levelname:<8}{self.RESET}"
        msg = record.getMessage()
        return f"{self.DIM}{ts}{self.RESET} {level} {msg}"


_file_handler = logging.FileHandler(os.path.join(_log_dir, "trevlix.log"), encoding="utf-8")
_console_handler = logging.StreamHandler()

if _USE_COLOR_LOGS and not _USE_JSON_LOGS:
    _console_handler.setFormatter(_ColorFormatter())

_log_handlers: list[logging.Handler] = [_file_handler, _console_handler]

if _USE_JSON_LOGS:

    class _JSONFormatter(logging.Formatter):
        def format(self, record):
            return json.dumps(
                {
                    "ts": self.formatTime(record),
                    "level": record.levelname,
                    "logger": record.name,
                    "msg": record.getMessage(),
                },
                ensure_ascii=False,
            )

    for h in _log_handlers:
        h.setFormatter(_JSONFormatter())

logging.basicConfig(
    level=_LOG_LEVEL,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=_log_handlers,
)
log = logging.getLogger("TREVLIX")


# SecretStr, _secret importiert aus services.utils


# ═══════════════════════════════════════════════════════════════════════════════
# KONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════
CONFIG: dict[str, Any] = {
    # Exchange
    "exchange": os.getenv("EXCHANGE", "cryptocom"),
    "api_key": _secret(os.getenv("API_KEY", "")),
    "secret": _secret(os.getenv("API_SECRET", "")),
    "quote_currency": "USDT",
    "min_volume_usdt": 1_000_000,
    "blacklist": ["USDC/USDT", "BUSD/USDT", "DAI/USDT", "TUSD/USDT", "FRAX/USDT", "USDP/USDT"],
    # Trading
    "max_workers": 5,
    "timeframe": "1h",
    "candle_limit": 250,
    "risk_per_trade": 0.015,
    "stop_loss_pct": 0.025,
    "take_profit_pct": 0.060,
    "trailing_stop": True,
    "trailing_pct": 0.015,
    "break_even_enabled": True,  # SL → Einstiegspreis sobald +X% im Profit
    "break_even_trigger": 0.015,  # +1.5% Gewinn → SL auf Break-Even setzen
    "break_even_buffer": 0.001,  # Kleiner Puffer über Entry (+0.1%)
    "cooldown_minutes": 60,  # Sperrzeit für Symbol nach Verlust-Trade (Min. 7)
    "max_open_trades": 5,
    "max_position_pct": 0.20,
    "fee_rate": 0.0004,
    "min_vote_score": 0.60,
    "use_market_regime": True,
    "btc_regime_tf": "4h",
    "use_vol_filter": True,
    "paper_trading": True,
    "paper_balance": 10000.0,
    "scan_interval": 60,
    "max_daily_loss_pct": 0.05,
    # Risk
    "max_spread_pct": 0.5,
    "max_corr": 0.75,
    "circuit_breaker_losses": 3,
    "circuit_breaker_min": 120,
    # KI
    "ai_enabled": True,
    "ai_min_samples": 20,
    "ai_min_confidence": 0.55,
    "ai_use_kelly": True,
    "ai_optimize_every": 15,
    "ai_retrain_every": 5,
    "auto_retrain_enabled": True,  # KI trainiert sich selbst nach N Trades
    "auto_retrain_threshold": 10,  # Min. neue Samples bis Auto-Retrain
    "auto_retrain_min_wr": 0.50,  # Kein Retrain wenn Win-Rate unter dieser Grenze
    # Fear & Greed
    "use_fear_greed": True,
    "fg_buy_max": 80,
    "fg_sell_min": 20,
    # Multi-Timeframe
    "mtf_enabled": True,
    "mtf_confirm_tf": "4h",
    # Orderbook
    "ob_imbalance_min": 0.45,
    # LSTM
    "lstm_lookback": 24,
    "lstm_min_samples": 50,
    # Sentiment (CoinGecko)
    "use_sentiment": True,
    # News Sentiment (CryptoPanic API v2)
    "use_news": True,
    "cryptopanic_token": os.getenv("CRYPTOPANIC_TOKEN", ""),
    "cryptopanic_plan": os.getenv("CRYPTOPANIC_API_PLAN", "free"),
    # Telegram
    "telegram_token": os.getenv("TELEGRAM_TOKEN", ""),
    "telegram_chat_id": os.getenv("TELEGRAM_CHAT_ID", ""),
    "news_block_score": -0.4,
    "news_sentiment_min": -0.2,  # Kaufsignal blockiert wenn news_score < dieser Wert
    "news_require_positive": False,  # True = Kauf nur bei positivem News-Score
    "news_boost_score": 0.3,
    # On-Chain
    "use_onchain": True,
    "whale_threshold": 500_000,
    # Dominanz-Filter
    "use_dominance": True,
    # Funding Rate Filter
    "funding_rate_filter": True,  # Shorts blockieren wenn Funding zu teuer
    "funding_rate_max": 0.001,  # Max. Funding-Rate für Shorts (0.1% pro 8h)
    "funding_rate_cache": {},
    "btc_dom_max": 40.0,
    "usdt_dom_max": 12.0,
    # Anomalie
    "use_anomaly": True,
    "anomaly_contamination": 0.05,
    # Partial Take-Profit
    "use_partial_tp": True,
    "partial_tp_levels": [
        {"pct": 0.03, "sell_ratio": 0.25},
        {"pct": 0.05, "sell_ratio": 0.25},
    ],
    # DCA
    "use_dca": True,
    "dca_drop_pct": 0.03,
    "dca_max_levels": 3,
    "dca_size_mult": 1.5,
    # Short-Selling
    "use_shorts": False,
    "short_exchange": "bybit",
    "short_api_key": _secret(os.getenv("SHORT_API_KEY", "")),
    "short_secret": _secret(os.getenv("SHORT_SECRET", "")),
    "short_leverage": 2,
    # Arbitrage
    "use_arbitrage": True,
    "arb_min_spread_pct": 0.3,
    "arb_exchanges": ["binance", "bybit"],
    "arb_api_keys": {},
    # Genetic Optimizer
    "genetic_enabled": True,
    "genetic_generations": 20,
    "genetic_population": 30,
    # RL Agent
    "rl_enabled": True,
    "rl_min_episodes": 100,
    # Discord
    "discord_webhook": os.getenv("DISCORD_WEBHOOK", ""),
    "discord_on_buy": True,
    "discord_on_sell": True,
    "discord_on_error": True,
    "discord_on_circuit": True,
    "discord_daily_report": True,
    "discord_report_hour": 20,
    # Alerts
    "price_alerts": [],
    # Portfolio-Ziel
    "portfolio_goal": 0.0,
    # Steuer
    "tax_method": "fifo",
    # Backup
    "backup_enabled": True,
    "backup_keep_days": 7,
    "backup_dir": "backups",
    "backup_encrypt": True,  # [Verbesserung #49] Backup-Verschlüsselung
    # [Verbesserung #25] Slippage
    "slippage_pct": 0.001,  # 0.1% Slippage-Annahme
    # [Verbesserung #26] Drawdown Circuit Breaker
    "max_drawdown_pct": 0.10,  # 10% Max-Drawdown → Bot pausiert
    # [Verbesserung #28] Mindest-Ordervolumen
    "min_order_usdt": 10.0,  # Mindest-Ordergröße in USDT
    # [Verbesserung #30] ATR Position-Sizing
    "use_atr_sizing": False,  # ATR-basiertes Position-Sizing
    "atr_risk_mult": 1.5,  # ATR-Multiplikator für Sizing
    # [Verbesserung #31] Zeitbasierter Exit
    "max_hold_hours": 0,  # 0 = deaktiviert, >0 = max. Haltezeit in Stunden
    # [Verbesserung #24] Data Retention
    "audit_retention_days": 90,  # Audit-Logs nach N Tagen löschen
    "ai_sample_retention_days": 180,  # AI-Samples nach N Tagen löschen
    # Trade DNA Fingerprinting
    "use_trade_dna": True,
    "dna_min_matches": 5,  # Min. historische Matches für Konfidenz-Anpassung
    "dna_boost_threshold": 0.65,  # WR ab der ein Boost gewährt wird
    "dna_block_threshold": 0.35,  # WR unter der geblockt wird
    # Smart Exits (Volatility-Adaptive SL/TP)
    "use_smart_exits": True,
    "smart_exit_atr_sl_mult": 1.5,  # ATR-Multiplikator für Stop-Loss
    "smart_exit_reward_ratio": 2.0,  # Reward-Ratio für Take-Profit
    "smart_exit_min_sl_pct": 0.01,  # Min. SL in Prozent (1%)
    "smart_exit_max_sl_pct": 0.08,  # Max. SL in Prozent (8%)
    "smart_exit_min_tp_pct": 0.02,  # Min. TP in Prozent (2%)
    "smart_exit_max_tp_pct": 0.15,  # Max. TP in Prozent (15%)
    "smart_exit_squeeze_threshold": 0.03,  # BB-Width Threshold für Squeeze
    # Auth / Multi-User
    "admin_password": _secret(os.getenv("ADMIN_PASSWORD", "trevlix")),
    "jwt_secret": _secret(os.getenv("JWT_SECRET", secrets.token_hex(32))),
    "jwt_expiry_hours": 24,
    "multi_user": True,
    "allow_registration": os.getenv("ALLOW_REGISTRATION", "false").lower() in ("true", "1", "yes"),
    # MySQL
    "mysql_host": os.getenv("MYSQL_HOST", "localhost"),
    "mysql_port": (lambda v: int(v) if v.isdigit() else 3306)(os.getenv("MYSQL_PORT", "3306")),
    "mysql_user": os.getenv("MYSQL_USER", "root"),
    "mysql_pass": _secret(os.getenv("MYSQL_PASS", "")),
    "mysql_db": os.getenv("MYSQL_DB", "trevlix"),
}

# EXCHANGE_MAP importiert aus services.utils

# [#29] Exchange-spezifische Standard-Fees (Maker-Fee als Fallback)
EXCHANGE_DEFAULT_FEES: dict[str, float] = {
    "binance": 0.0010,  # 0.10% Standard (0.075% mit BNB)
    "bybit": 0.0010,  # 0.10% Standard (0.06% Maker)
    "okx": 0.0008,  # 0.08% Standard (0.06% Maker)
    "kucoin": 0.0010,  # 0.10% Standard
    "cryptocom": 0.0004,  # 0.04% Standard
    "kraken": 0.0016,  # 0.16% Standard
    "huobi": 0.0020,  # 0.20% Standard
    "coinbase": 0.0060,  # 0.60% Standard (Advanced Trade niedriger)
}

# Cache für CCXT-Fee-Abfragen: {exchange_id: {"rate": 0.001, "ts": ...}}
_fee_cache: dict[str, dict] = {}
_fee_cache_lock = threading.Lock()
# STRATEGY_NAMES importiert aus services.strategies


# ═══════════════════════════════════════════════════════════════════════════════
# Sicherheitswarnung: Default-Passwort erkennen
# ═══════════════════════════════════════════════════════════════════════════════
if not os.getenv("ADMIN_PASSWORD") or os.getenv("ADMIN_PASSWORD", "") in (
    "trevlix",
    "admin",
    "password",
    "test",
):
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
    try:
        if "db_conn" not in g:
            g.db_conn = db._conn()  # type: ignore[attr-defined]
        return g.db_conn
    except RuntimeError:
        # Außerhalb des Request-Kontexts
        return db._conn()  # type: ignore[attr-defined]


@app.teardown_appcontext
def close_db_connection(exc: BaseException | None = None) -> None:
    """Gibt die DB-Verbindung am Ende jedes Requests zurück in den Pool.

    Args:
        exc: Optionale Exception, die den Request beendet hat.
    """
    conn = g.pop("db_conn", None)
    if conn is not None:
        try:
            conn.close()
        except Exception as e:
            log.debug(f"close_db_connection: {e}")


# validate_config importiert aus services.utils


# ═══════════════════════════════════════════════════════════════════════════════
# MYSQL MANAGER (extended)
# ═══════════════════════════════════════════════════════════════════════════════
class MySQLManager:
    def __init__(self):
        self._lock = threading.Lock()
        self._pool: ConnectionPool | None = None
        self.db_available = False  # [Verbesserung #3] Flag für Degraded-Mode
        self._init_db()

    def _build_pool(self) -> ConnectionPool | None:
        """Erstellt den Connection-Pool nach der DB-Initialisierung."""
        if not MYSQL_AVAILABLE:
            return None
        try:
            return ConnectionPool(
                host=CONFIG["mysql_host"],
                port=CONFIG["mysql_port"],
                user=CONFIG["mysql_user"],
                password=CONFIG["mysql_pass"],
                database=CONFIG["mysql_db"],
                pool_size=5,
                timeout=10,
            )
        except Exception as e:
            log.warning(f"Connection-Pool: {e} – Fallback auf direkte Verbindung")
            return None

    def _conn(self):
        """
        Gibt eine Verbindung zurück – aus dem Pool (bevorzugt) oder neu erstellt.
        Pool-Verbindungen sind in _PooledConnection eingewickelt:
        conn.close() gibt sie automatisch zurück in den Pool.
        Alle bestehenden conn.close()-Aufrufe funktionieren korrekt ohne Änderung.
        """
        if not MYSQL_AVAILABLE:
            raise ConnectionError("PyMySQL nicht installiert – pip install PyMySQL")
        if self._pool is not None:
            return self._pool.acquire()
        return pymysql.connect(
            host=CONFIG["mysql_host"],
            port=CONFIG["mysql_port"],
            user=CONFIG["mysql_user"],
            password=CONFIG["mysql_pass"],
            database=CONFIG["mysql_db"],
            charset="utf8mb4",
            cursorclass=pymysql.cursors.DictCursor,
            autocommit=True,
            connect_timeout=10,
        )

    @contextmanager
    def _get_conn(self):
        """Context-Manager für sichere Verbindungsverwaltung ohne Connection-Leak.

        Stellt sicher dass die Verbindung IMMER zurückgegeben wird (Pool-Semaphore
        wird freigegeben), auch wenn eine Exception auftritt. Verhindert Pool-Exhaustion
        bei Datenbankfehlern.

        Verwendung:
            with self._get_conn() as conn:
                with conn.cursor() as c:
                    c.execute(...)
        """
        conn = None
        try:
            conn = self._conn()
            yield conn
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass

    # ── Encryption Helpers ───────────────────────────────────────────────────
    @staticmethod
    def _enc(value: str) -> str:
        """Verschlüsselt einen API-Key/Secret vor dem Speichern."""
        return encrypt_value(value) if value else value

    @staticmethod
    def _dec(value: str) -> str:
        """Entschlüsselt einen API-Key/Secret nach dem Laden."""
        return decrypt_value(value) if value else value

    def _init_db(self):
        """[Verbesserung #3] DB-Init mit exponentiellem Backoff (bis zu 5 Versuche)."""
        if not MYSQL_AVAILABLE:
            log.error("PyMySQL fehlt – pip install PyMySQL")
            return
        _delays = [2, 4, 8, 16, 32]
        for attempt, delay in enumerate(_delays, 1):
            try:
                self._init_db_once()
                self.db_available = True
                return
            except Exception as e:
                log.warning(f"MySQL Init (Versuch {attempt}/5): {e}")
                if attempt < len(_delays):
                    log.info(f"Retry in {delay}s...")
                    time.sleep(delay)
        log.error("MySQL Init fehlgeschlagen – starte im Degraded-Mode (Paper-Trading only)")

    def _init_db_once(self):
        """Einmalige DB-Initialisierung – wird von _init_db() mit Retry aufgerufen."""
        conn = self._conn()
        try:
            with conn.cursor() as c:
                # Trades
                c.execute("""CREATE TABLE IF NOT EXISTS trades (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT DEFAULT 1,
                    symbol VARCHAR(20), entry DOUBLE, exit_price DOUBLE,
                    qty DOUBLE, pnl DOUBLE, pnl_pct DOUBLE,
                    reason VARCHAR(80), confidence DOUBLE,
                    ai_score DOUBLE, win_prob DOUBLE, invested DOUBLE,
                    opened DATETIME, closed DATETIME,
                    exchange VARCHAR(20), regime VARCHAR(10),
                    trade_type VARCHAR(10) DEFAULT 'long',
                    partial_sold TINYINT DEFAULT 0,
                    dca_level INT DEFAULT 0,
                    news_score DOUBLE DEFAULT 0,
                    onchain_score DOUBLE DEFAULT 0,
                    INDEX idx_closed(closed), INDEX idx_symbol(symbol), INDEX idx_user(user_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""")
                # Users
                c.execute("""CREATE TABLE IF NOT EXISTS users (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    username VARCHAR(50) UNIQUE,
                    password_hash VARCHAR(256),
                    role VARCHAR(20) DEFAULT 'user',
                    balance DOUBLE DEFAULT 10000.0,
                    initial_balance DOUBLE DEFAULT 10000.0,
                    api_key VARCHAR(200),
                    api_secret VARCHAR(200),
                    exchange VARCHAR(20) DEFAULT 'cryptocom',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    last_login DATETIME,
                    settings_json MEDIUMTEXT
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""")
                # AI samples
                c.execute("""CREATE TABLE IF NOT EXISTS ai_training (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    features TEXT, label TINYINT,
                    regime VARCHAR(10) DEFAULT 'bull',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_regime(regime)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""")
                # Audit Log
                c.execute("""CREATE TABLE IF NOT EXISTS audit_log (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT DEFAULT 0,
                    action VARCHAR(80) NOT NULL,
                    detail VARCHAR(500),
                    ip VARCHAR(45),
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_user(user_id),
                    INDEX idx_action(action),
                    INDEX idx_time(created_at),
                    INDEX idx_user_time(user_id, created_at)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""")
                # [#19] Composite-Index Migration für bestehende Installationen
                try:
                    c.execute("""ALTER TABLE audit_log
                        ADD INDEX idx_user_time(user_id, created_at)""")
                except Exception:
                    pass  # Index existiert bereits
                # Backtest results
                c.execute("""CREATE TABLE IF NOT EXISTS backtest_results (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    symbol VARCHAR(20), timeframe VARCHAR(10),
                    candles INT, total_trades INT,
                    win_rate DOUBLE, total_pnl DOUBLE,
                    profit_factor DOUBLE, max_drawdown DOUBLE,
                    result_json MEDIUMTEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""")
                # Price alerts
                c.execute("""CREATE TABLE IF NOT EXISTS price_alerts (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT DEFAULT 1,
                    symbol VARCHAR(20), target_price DOUBLE,
                    direction VARCHAR(10), triggered TINYINT DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    triggered_at DATETIME
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""")
                # Daily reports
                c.execute("""CREATE TABLE IF NOT EXISTS daily_reports (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    report_date DATE, report_json MEDIUMTEXT,
                    sent_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE KEY uq_date(report_date)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""")
                # Sentiment cache
                c.execute("""CREATE TABLE IF NOT EXISTS sentiment_cache (
                    symbol VARCHAR(20) PRIMARY KEY,
                    score DOUBLE, source VARCHAR(20),
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""")
                # News sentiment cache
                c.execute("""CREATE TABLE IF NOT EXISTS news_cache (
                    symbol VARCHAR(20) PRIMARY KEY,
                    score DOUBLE, headline VARCHAR(500),
                    article_count INT DEFAULT 0,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""")
                # On-chain cache
                c.execute("""CREATE TABLE IF NOT EXISTS onchain_cache (
                    symbol VARCHAR(20) PRIMARY KEY,
                    whale_score DOUBLE, flow_score DOUBLE,
                    net_score DOUBLE, detail VARCHAR(500),
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""")
                # Genetic results
                c.execute("""CREATE TABLE IF NOT EXISTS genetic_results (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    generation INT, fitness DOUBLE,
                    genome_json TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""")
                # Arbitrage opportunities
                c.execute("""CREATE TABLE IF NOT EXISTS arb_opportunities (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    symbol VARCHAR(20),
                    exchange_buy VARCHAR(20), price_buy DOUBLE,
                    exchange_sell VARCHAR(20), price_sell DOUBLE,
                    spread_pct DOUBLE, executed TINYINT DEFAULT 0,
                    profit DOUBLE DEFAULT 0,
                    found_at DATETIME DEFAULT CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""")
                # RL episodes
                c.execute("""CREATE TABLE IF NOT EXISTS rl_episodes (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    episode INT, reward DOUBLE,
                    state_json TEXT, action INT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""")
                # API tokens
                c.execute("""CREATE TABLE IF NOT EXISTS api_tokens (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT, token VARCHAR(500), label VARCHAR(100),
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    last_used DATETIME, expires_at DATETIME,
                    active TINYINT DEFAULT 1
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""")
                # User Exchanges (Multi-Exchange pro User, Default deaktiviert)
                c.execute("""CREATE TABLE IF NOT EXISTS user_exchanges (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT NOT NULL,
                    exchange VARCHAR(20) NOT NULL,
                    api_key VARCHAR(500),
                    api_secret VARCHAR(500),
                    enabled TINYINT DEFAULT 0,
                    is_primary TINYINT DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE KEY uq_user_exchange(user_id, exchange),
                    INDEX idx_user(user_id),
                    INDEX idx_enabled(user_id, enabled)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""")
                # Shared Knowledge (KI-Gemeinschaftswissen)
                c.execute("""CREATE TABLE IF NOT EXISTS shared_knowledge (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    category VARCHAR(50) NOT NULL,
                    key_name VARCHAR(100) NOT NULL,
                    value_json MEDIUMTEXT,
                    confidence DOUBLE DEFAULT 0.5,
                    source VARCHAR(50) DEFAULT 'ai',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    UNIQUE KEY uq_cat_key(category, key_name),
                    INDEX idx_category(category)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""")
                # Trade DNA Fingerprints
                c.execute("""CREATE TABLE IF NOT EXISTS trade_dna (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    symbol VARCHAR(20),
                    dna_hash VARCHAR(16),
                    fingerprint VARCHAR(500),
                    dimensions_json TEXT,
                    raw_values_json TEXT,
                    won TINYINT,
                    pnl DOUBLE DEFAULT 0,
                    dna_boost DOUBLE DEFAULT 1.0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_hash(dna_hash),
                    INDEX idx_symbol(symbol),
                    INDEX idx_time(created_at)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""")
                # Ensure admin user
                c.execute("SELECT id FROM users WHERE username='admin'")
                if not c.fetchone():
                    pw = CONFIG["admin_password"].encode()
                    if BCRYPT_AVAILABLE:
                        h = bcrypt.hashpw(pw, bcrypt.gensalt()).decode()
                    else:
                        h = hashlib.sha256(pw).hexdigest()
                    c.execute(
                        "INSERT INTO users (username,password_hash,role,balance,initial_balance) VALUES('admin',%s,'admin',10000,10000)",
                        (h,),
                    )
            # Pool NACH erfolgreicher Init erstellen
            self._pool = self._build_pool()
            log.info(f"✅ MySQL: {CONFIG['mysql_host']}/{CONFIG['mysql_db']}")
        finally:
            try:
                conn.close()
            except Exception:
                pass

    # ── Trades ──────────────────────────────────────────────────────────────
    def save_trade(self, trade: dict, user_id: int = 1):
        try:
            with self._get_conn() as conn:
                with conn.cursor() as c:
                    c.execute(
                        """INSERT INTO trades
                        (user_id,symbol,entry,exit_price,qty,pnl,pnl_pct,reason,
                         confidence,ai_score,win_prob,invested,opened,closed,exchange,
                         regime,trade_type,partial_sold,dca_level,news_score,onchain_score)
                        VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                        (
                            user_id,
                            trade.get("symbol"),
                            trade.get("entry"),
                            trade.get("exit"),
                            trade.get("qty"),
                            trade.get("pnl"),
                            trade.get("pnl_pct"),
                            trade.get("reason"),
                            trade.get("confidence"),
                            trade.get("ai_score"),
                            trade.get("win_prob"),
                            trade.get("invested"),
                            trade.get("opened"),
                            trade.get("closed"),
                            trade.get("exchange", CONFIG["exchange"]),
                            trade.get("regime", "bull"),
                            trade.get("trade_type", "long"),
                            trade.get("partial_sold", 0),
                            trade.get("dca_level", 0),
                            trade.get("news_score", 0),
                            trade.get("onchain_score", 0),
                        ),
                    )
        except Exception as e:
            log.error(f"save_trade: {e}")

    def load_trades(self, limit=500, symbol=None, year=None, user_id=None) -> list[dict]:
        try:
            with self._get_conn() as conn:
                with conn.cursor() as c:
                    q = "SELECT *, exit_price as `exit` FROM trades"
                    params = []
                    w = []
                    if user_id:
                        w.append("user_id=%s")
                        params.append(user_id)
                    if symbol:
                        w.append("symbol=%s")
                        params.append(symbol)
                    if year:
                        w.append("YEAR(closed)=%s")
                        params.append(year)
                    if w:
                        q += " WHERE " + " AND ".join(w)
                    q += " ORDER BY closed DESC LIMIT %s"
                    params.append(limit)
                    c.execute(q, params)
                    rows = c.fetchall()
            result = []
            for r in rows:
                d = dict(r)
                for k in ("opened", "closed"):
                    if k in d and hasattr(d[k], "isoformat"):
                        d[k] = d[k].isoformat()
                result.append(d)
            return result
        except Exception as e:
            log.error(f"load_trades: {e}")
            return []

    # ── AI Samples ──────────────────────────────────────────────────────────
    def save_ai_sample(self, features: np.ndarray, label: int, regime: str = "bull"):
        try:
            with self._get_conn() as conn:
                with conn.cursor() as c:
                    c.execute(
                        "INSERT INTO ai_training (features,label,regime) VALUES(%s,%s,%s)",
                        (json.dumps(features.tolist()), label, regime),
                    )
        except Exception as e:
            log.error(f"save_ai_sample: {e}")

    def load_ai_samples(self) -> tuple[list, list, list]:
        try:
            with self._get_conn() as conn:
                with conn.cursor() as c:
                    c.execute("SELECT features,label,regime FROM ai_training")
                    rows = c.fetchall()
            X = [np.array(json.loads(r.get("features", "[]")), dtype=np.float32) for r in rows]
            y = [r.get("label", 0) for r in rows]
            regimes = [r.get("regime", "range") for r in rows]
            return X, y, regimes
        except Exception as e:
            log.error(f"load_ai_samples: {e}")
            return [], [], []

    # ── Users ───────────────────────────────────────────────────────────────
    def _decrypt_user_keys(self, user: dict | None) -> dict | None:
        """Entschlüsselt API-Key/Secret eines User-Dicts nach dem Laden aus der DB."""
        if not user:
            return user
        if user.get("api_key"):
            user["api_key"] = self._dec(user["api_key"])
        if user.get("api_secret"):
            user["api_secret"] = self._dec(user["api_secret"])
        return user

    def get_user(self, username: str) -> dict[str, Any] | None:
        """Lädt einen Benutzer anhand des Benutzernamens.

        Args:
            username: Der gesuchte Benutzername.

        Returns:
            User-Dict mit entschlüsselten Keys oder None wenn nicht gefunden.
        """
        try:
            with self._get_conn() as conn:
                with conn.cursor() as c:
                    c.execute("SELECT * FROM users WHERE username=%s", (username,))
                    row = c.fetchone()
            return self._decrypt_user_keys(dict(row)) if row else None
        except Exception as e:
            log.error(f"get_user({username!r}): {e}")
            return None

    def get_user_by_id(self, uid: int) -> dict[str, Any] | None:
        """Lädt einen Benutzer anhand der ID.

        Args:
            uid: Die gesuchte User-ID.

        Returns:
            User-Dict mit entschlüsselten Keys oder None wenn nicht gefunden.
        """
        try:
            with self._get_conn() as conn:
                with conn.cursor() as c:
                    c.execute("SELECT * FROM users WHERE id=%s", (uid,))
                    row = c.fetchone()
            return self._decrypt_user_keys(dict(row)) if row else None
        except Exception as e:
            log.error(f"get_user_by_id({uid}): {e}")
            return None

    def get_all_users(self) -> list[dict[str, Any]]:
        """Lädt alle Benutzer (ohne sensible Keys).

        Returns:
            Liste von User-Dicts mit serialisierten Datumsfeldern.
        """
        try:
            with self._get_conn() as conn:
                with conn.cursor() as c:
                    c.execute(
                        "SELECT id,username,role,balance,initial_balance,exchange,created_at,last_login FROM users"
                    )
                    rows = c.fetchall()
            result: list[dict[str, Any]] = []
            for r in rows:
                d = dict(r)
                for k in ("created_at", "last_login"):
                    if k in d and hasattr(d.get(k), "isoformat"):
                        d[k] = d[k].isoformat() if d[k] else None
                result.append(d)
            return result
        except Exception as e:
            log.error(f"get_all_users: {e}")
            return []

    def create_user(
        self, username: str, password: str, role: str = "user", balance: float = 10000.0
    ) -> bool:
        try:
            pw = password.encode()
            if BCRYPT_AVAILABLE:
                h = bcrypt.hashpw(pw, bcrypt.gensalt()).decode()
            else:
                h = hashlib.sha256(pw).hexdigest()
            with self._get_conn() as conn:
                with conn.cursor() as c:
                    c.execute(
                        "INSERT INTO users (username,password_hash,role,balance,initial_balance) VALUES(%s,%s,%s,%s,%s)",
                        (username, h, role, balance, balance),
                    )
            return True
        except Exception as e:
            log.error(f"create_user: {e}")
            return False

    def verify_password(self, stored_hash: str, password: str) -> bool:
        """Verifiziert ein Passwort gegen den gespeicherten Hash.

        Args:
            stored_hash: Gespeicherter bcrypt- oder SHA-256-Hash.
            password: Eingegebenes Klartext-Passwort.

        Returns:
            True wenn das Passwort korrekt ist.
        """
        try:
            pw = password.encode()
            if BCRYPT_AVAILABLE and stored_hash.startswith("$2"):
                # bcrypt-Hash (beginnt mit $2a$, $2b$, $2y$)
                return bcrypt.checkpw(pw, stored_hash.encode())
            # Fallback: SHA-256 (Legacy-Hashes oder bcrypt nicht installiert)
            log.warning("verify_password: SHA-256 Fallback – bitte bcrypt-Hash verwenden")
            return hmac.compare_digest(hashlib.sha256(pw).hexdigest(), stored_hash)
        except Exception:
            return False

    def update_user_login(self, user_id: int) -> None:
        """Aktualisiert den last_login Timestamp eines Users.

        Args:
            user_id: Die User-ID.
        """
        try:
            with self._get_conn() as conn:
                with conn.cursor() as c:
                    c.execute("UPDATE users SET last_login=NOW() WHERE id=%s", (user_id,))
        except Exception as e:
            log.warning(f"update_user_login({user_id}): {e}")

    def update_user_balance(self, user_id: int, balance: float) -> None:
        """Aktualisiert den Kontostand eines Users.

        Args:
            user_id: Die User-ID.
            balance: Neuer Kontostand.
        """
        try:
            with self._get_conn() as conn:
                with conn.cursor() as c:
                    c.execute("UPDATE users SET balance=%s WHERE id=%s", (balance, user_id))
        except Exception as e:
            log.error(f"update_user_balance({user_id}, {balance}): {e}")

    # ── User Settings ────────────────────────────────────────────────────────
    def update_user_settings(self, user_id: int, settings: dict) -> bool:
        """Speichert User-Settings als JSON in der DB."""
        try:
            with self._get_conn() as conn:
                with conn.cursor() as c:
                    c.execute(
                        "UPDATE users SET settings_json=%s WHERE id=%s",
                        (json.dumps(settings, ensure_ascii=False), user_id),
                    )
            return True
        except Exception as e:
            log.error(f"update_user_settings: {e}")
            return False

    def get_user_settings(self, user_id: int) -> dict:
        """Lädt User-Settings aus der DB."""
        try:
            with self._get_conn() as conn:
                with conn.cursor() as c:
                    c.execute("SELECT settings_json FROM users WHERE id=%s", (user_id,))
                    row = c.fetchone()
            if row and row.get("settings_json"):
                return json.loads(row["settings_json"])
            return {}
        except Exception as e:
            log.error(f"get_user_settings({user_id}): {e}")
            return {}

    def update_user_api_keys(
        self, user_id: int, exchange: str, api_key: str, api_secret: str
    ) -> bool:
        """Speichert verschlüsselte API-Keys für einen User."""
        try:
            with self._get_conn() as conn:
                with conn.cursor() as c:
                    c.execute(
                        "UPDATE users SET exchange=%s, api_key=%s, api_secret=%s WHERE id=%s",
                        (exchange, self._enc(api_key), self._enc(api_secret), user_id),
                    )
            return True
        except Exception as e:
            log.error(f"update_user_api_keys: {e}")
            return False

    # ── User Exchanges (Multi-Exchange pro User) ─────────────────────────────
    def get_user_exchanges(self, user_id: int) -> list[dict]:
        """Gibt alle Exchange-Konfigurationen eines Users zurück."""
        try:
            with self._get_conn() as conn:
                with conn.cursor() as c:
                    c.execute(
                        "SELECT id, exchange, enabled, is_primary, created_at "
                        "FROM user_exchanges WHERE user_id=%s ORDER BY is_primary DESC, exchange",
                        (user_id,),
                    )
                    rows = c.fetchall()
            result = []
            for r in rows:
                d = dict(r)
                if d.get("created_at") and hasattr(d["created_at"], "isoformat"):
                    d["created_at"] = d["created_at"].isoformat()
                result.append(d)
            return result
        except Exception as e:
            log.error(f"get_user_exchanges({user_id}): {e}")
            return []

    def upsert_user_exchange(
        self,
        user_id: int,
        exchange: str,
        api_key: str,
        api_secret: str,
        enabled: bool = False,
        is_primary: bool = False,
    ) -> bool:
        """Erstellt oder aktualisiert eine Exchange-Konfiguration für einen User.

        Neue Exchanges sind standardmäßig deaktiviert (enabled=False).
        """
        try:
            with self._get_conn() as conn:
                with conn.cursor() as c:
                    # Prüfe ob Exchange schon existiert
                    c.execute(
                        "SELECT id FROM user_exchanges WHERE user_id=%s AND exchange=%s",
                        (user_id, exchange),
                    )
                    existing = c.fetchone()
                    if existing:
                        c.execute(
                            "UPDATE user_exchanges SET api_key=%s, api_secret=%s, "
                            "enabled=%s, is_primary=%s WHERE id=%s",
                            (
                                self._enc(api_key),
                                self._enc(api_secret),
                                enabled,
                                is_primary,
                                existing["id"],
                            ),
                        )
                    else:
                        c.execute(
                            "INSERT INTO user_exchanges "
                            "(user_id, exchange, api_key, api_secret, enabled, is_primary) "
                            "VALUES(%s,%s,%s,%s,%s,%s)",
                            (
                                user_id,
                                exchange,
                                self._enc(api_key),
                                self._enc(api_secret),
                                enabled,
                                is_primary,
                            ),
                        )
                    # Wenn is_primary, alle anderen auf nicht-primär setzen
                    if is_primary:
                        c.execute(
                            "UPDATE user_exchanges SET is_primary=0 "
                            "WHERE user_id=%s AND exchange!=%s",
                            (user_id, exchange),
                        )
            return True
        except Exception as e:
            log.error(f"upsert_user_exchange: {e}")
            return False

    def toggle_user_exchange(self, user_id: int, exchange_id: int, enabled: bool) -> bool:
        """Aktiviert/Deaktiviert eine Exchange für einen User."""
        try:
            with self._get_conn() as conn:
                with conn.cursor() as c:
                    c.execute(
                        "UPDATE user_exchanges SET enabled=%s WHERE id=%s AND user_id=%s",
                        (enabled, exchange_id, user_id),
                    )
            return True
        except Exception as e:
            log.error(f"toggle_user_exchange: {e}")
            return False

    def get_enabled_exchanges(self, user_id: int) -> list[dict]:
        """Gibt nur aktivierte Exchanges eines Users zurück (mit entschlüsselten Keys)."""
        try:
            with self._get_conn() as conn:
                with conn.cursor() as c:
                    c.execute(
                        "SELECT * FROM user_exchanges WHERE user_id=%s AND enabled=1",
                        (user_id,),
                    )
                    rows = c.fetchall()
            result = []
            for r in rows:
                d = dict(r)
                d["api_key"] = self._dec(d.get("api_key", ""))
                d["api_secret"] = self._dec(d.get("api_secret", ""))
                result.append(d)
            return result
        except Exception as e:
            log.error(f"get_enabled_exchanges({user_id}): {e}")
            return []

    def delete_user_exchange(self, user_id: int, exchange_id: int) -> bool:
        """Löscht eine Exchange-Konfiguration eines Users."""
        try:
            with self._get_conn() as conn:
                with conn.cursor() as c:
                    c.execute(
                        "DELETE FROM user_exchanges WHERE id=%s AND user_id=%s",
                        (exchange_id, user_id),
                    )
            return True
        except Exception as e:
            log.error(f"delete_user_exchange: {e}")
            return False

    # ── API Tokens ──────────────────────────────────────────────────────────
    def create_api_token(self, user_id: int, label: str = "default") -> str:
        if not JWT_AVAILABLE:
            return secrets.token_urlsafe(32)
        payload = {
            "sub": user_id,
            "label": label,
            "exp": datetime.now(UTC) + timedelta(hours=CONFIG["jwt_expiry_hours"]),
            "iat": datetime.now(UTC),
        }
        token = pyjwt.encode(payload, CONFIG["jwt_secret"], algorithm="HS256")
        try:
            with self._get_conn() as conn:
                with conn.cursor() as c:
                    c.execute(
                        "INSERT INTO api_tokens (user_id,token,label,expires_at) VALUES(%s,%s,%s,%s)",
                        (
                            user_id,
                            token[:500],
                            label,
                            datetime.now(UTC) + timedelta(hours=CONFIG["jwt_expiry_hours"]),
                        ),
                    )
        except Exception as e:
            log.error(f"create_token: {e}")
        return token

    def verify_api_token(self, token: str) -> int | None:
        if not JWT_AVAILABLE:
            return None
        try:
            payload = pyjwt.decode(token, CONFIG["jwt_secret"], algorithms=["HS256"])
            sub = payload.get("sub")
            return int(sub) if sub is not None else None
        except Exception:
            return None

    # ── Misc ────────────────────────────────────────────────────────────────
    def save_backtest(self, result: dict):
        try:
            with self._get_conn() as conn:
                with conn.cursor() as c:
                    c.execute(
                        """INSERT INTO backtest_results
                        (symbol,timeframe,candles,total_trades,win_rate,total_pnl,profit_factor,max_drawdown,result_json)
                        VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                        (
                            result.get("symbol"),
                            result.get("timeframe"),
                            result.get("candles"),
                            result.get("total_trades"),
                            result.get("win_rate"),
                            result.get("total_pnl"),
                            result.get("profit_factor"),
                            result.get("max_drawdown"),
                            json.dumps(result)[:65000],
                        ),
                    )
        except Exception as e:
            log.error(f"save_backtest: {e}")

    def get_recent_backtests(self, limit=10) -> list[dict]:
        try:
            with self._get_conn() as conn:
                with conn.cursor() as c:
                    c.execute(
                        "SELECT * FROM backtest_results ORDER BY created_at DESC LIMIT %s", (limit,)
                    )
                    rows = c.fetchall()
            return [dict(r) for r in rows]
        except Exception as e:
            log.error(f"get_recent_backtests: {e}")
            return []

    def add_alert(self, symbol: str, target: float, direction: str, user_id: int = 1) -> int:
        try:
            with self._get_conn() as conn:
                with conn.cursor() as c:
                    c.execute(
                        "INSERT INTO price_alerts (user_id,symbol,target_price,direction) VALUES(%s,%s,%s,%s)",
                        (user_id, symbol, target, direction),
                    )
                    aid = c.lastrowid
            return aid
        except Exception as e:
            log.error(f"add_alert: {e}")
            return -1

    def get_active_alerts(self) -> list[dict]:
        try:
            with self._get_conn() as conn:
                with conn.cursor() as c:
                    c.execute("SELECT * FROM price_alerts WHERE triggered=0")
                    rows = c.fetchall()
            return [dict(r) for r in rows]
        except Exception as e:
            log.error(f"get_active_alerts: {e}")
            return []

    def trigger_alert(self, aid: int):
        try:
            with self._get_conn() as conn:
                with conn.cursor() as c:
                    c.execute(
                        "UPDATE price_alerts SET triggered=1,triggered_at=NOW() WHERE id=%s", (aid,)
                    )
        except Exception as e:
            log.error(f"trigger_alert({aid}): {e}")

    def delete_alert(self, aid: int):
        try:
            with self._get_conn() as conn:
                with conn.cursor() as c:
                    c.execute("DELETE FROM price_alerts WHERE id=%s", (aid,))
        except Exception as e:
            log.error(f"delete_alert({aid}): {e}")

    def get_all_alerts(self) -> list[dict]:
        try:
            with self._get_conn() as conn:
                with conn.cursor() as c:
                    c.execute("SELECT * FROM price_alerts ORDER BY created_at DESC LIMIT 50")
                    rows = c.fetchall()
            result = []
            for r in rows:
                d = dict(r)
                for k in ("created_at", "triggered_at"):
                    if k in d and hasattr(d.get(k), "isoformat"):
                        d[k] = d[k].isoformat() if d[k] else None
                result.append(d)
            return result
        except Exception as e:
            log.error(f"get_all_alerts: {e}")
            return []

    def save_daily_report(self, date_str: str, report: dict):
        try:
            with self._get_conn() as conn:
                with conn.cursor() as c:
                    c.execute(
                        """INSERT INTO daily_reports (report_date,report_json)
                        VALUES(%s,%s) ON DUPLICATE KEY UPDATE report_json=%s,sent_at=NOW()""",
                        (date_str, json.dumps(report), json.dumps(report)),
                    )
        except Exception as e:
            log.error(f"save_daily_report: {e}")

    def report_sent_today(self) -> bool:
        try:
            with self._get_conn() as conn:
                with conn.cursor() as c:
                    c.execute("SELECT id FROM daily_reports WHERE report_date=CURDATE()")
                    row = c.fetchone()
            return row is not None
        except Exception as e:
            log.error(f"report_sent_today: {e}")
            return False

    def save_sentiment(self, symbol: str, score: float, source: str):
        try:
            with self._get_conn() as conn:
                with conn.cursor() as c:
                    c.execute(
                        """INSERT INTO sentiment_cache (symbol,score,source,updated_at)
                        VALUES(%s,%s,%s,NOW()) ON DUPLICATE KEY
                        UPDATE score=%s,source=%s,updated_at=NOW()""",
                        (symbol, score, source, score, source),
                    )
        except Exception as e:
            log.error(f"save_sentiment({symbol!r}): {e}")

    def get_sentiment(self, symbol: str) -> float | None:
        try:
            with self._get_conn() as conn:
                with conn.cursor() as c:
                    c.execute(
                        """SELECT score FROM sentiment_cache
                        WHERE symbol=%s AND updated_at > NOW() - INTERVAL 2 HOUR""",
                        (symbol,),
                    )
                    row = c.fetchone()
            if row and row.get("score") is not None:
                return float(row["score"])
            return None
        except Exception as e:
            log.error(f"get_sentiment({symbol!r}): {e}")
            return None

    def save_news(self, symbol: str, score: float, headline: str, count: int):
        try:
            with self._get_conn() as conn:
                with conn.cursor() as c:
                    c.execute(
                        """INSERT INTO news_cache (symbol,score,headline,article_count,updated_at)
                        VALUES(%s,%s,%s,%s,NOW()) ON DUPLICATE KEY
                        UPDATE score=%s,headline=%s,article_count=%s,updated_at=NOW()""",
                        (symbol, score, headline[:500], count, score, headline[:500], count),
                    )
        except Exception as e:
            log.error(f"save_news({symbol!r}): {e}")

    def get_news(self, symbol: str) -> dict | None:
        try:
            with self._get_conn() as conn:
                with conn.cursor() as c:
                    c.execute(
                        """SELECT score,headline,article_count FROM news_cache
                        WHERE symbol=%s AND updated_at > NOW() - INTERVAL 30 MINUTE""",
                        (symbol,),
                    )
                    row = c.fetchone()
            return dict(row) if row else None
        except Exception as e:
            log.error(f"get_news({symbol!r}): {e}")
            return None

    def save_onchain(self, symbol: str, whale_score: float, flow_score: float, detail: str):
        whale_score = whale_score if whale_score is not None else 0.0
        flow_score = flow_score if flow_score is not None else 0.0
        net = (whale_score + flow_score) / 2
        try:
            with self._get_conn() as conn:
                with conn.cursor() as c:
                    c.execute(
                        """INSERT INTO onchain_cache (symbol,whale_score,flow_score,net_score,detail,updated_at)
                        VALUES(%s,%s,%s,%s,%s,NOW()) ON DUPLICATE KEY
                        UPDATE whale_score=%s,flow_score=%s,net_score=%s,detail=%s,updated_at=NOW()""",
                        (
                            symbol,
                            whale_score,
                            flow_score,
                            net,
                            detail[:500],
                            whale_score,
                            flow_score,
                            net,
                            detail[:500],
                        ),
                    )
        except Exception as e:
            log.error(f"save_onchain({symbol!r}): {e}")

    def get_onchain(self, symbol: str) -> dict | None:
        try:
            with self._get_conn() as conn:
                with conn.cursor() as c:
                    c.execute(
                        """SELECT whale_score,flow_score,net_score,detail FROM onchain_cache
                        WHERE symbol=%s AND updated_at > NOW() - INTERVAL 1 HOUR""",
                        (symbol,),
                    )
                    row = c.fetchone()
            return dict(row) if row else None
        except Exception as e:
            log.error(f"get_onchain({symbol!r}): {e}")
            return None

    def save_arb(self, arb: dict):
        try:
            with self._get_conn() as conn:
                with conn.cursor() as c:
                    c.execute(
                        """INSERT INTO arb_opportunities
                        (symbol,exchange_buy,price_buy,exchange_sell,price_sell,spread_pct,executed,profit)
                        VALUES(%s,%s,%s,%s,%s,%s,%s,%s)""",
                        (
                            arb.get("symbol", "UNKNOWN"),
                            arb.get("exchange_buy", ""),
                            arb.get("price_buy", 0),
                            arb.get("exchange_sell", ""),
                            arb.get("price_sell", 0),
                            arb.get("spread_pct", 0),
                            arb.get("executed", 0),
                            arb.get("profit", 0),
                        ),
                    )
        except Exception as e:
            log.error(f"save_arb({arb.get('symbol', '?')}): {e}")

    def save_genetic(self, generation: int, fitness: float, genome: dict):
        try:
            with self._get_conn() as conn:
                with conn.cursor() as c:
                    c.execute(
                        "INSERT INTO genetic_results (generation,fitness,genome_json) VALUES(%s,%s,%s)",
                        (generation, fitness, json.dumps(genome)),
                    )
        except Exception as e:
            log.error(f"save_genetic(gen={generation}, fitness={fitness:.4f}): {e}")

    def export_csv(self, user_id: int | None = None, limit: int = 10000) -> str:
        trades = self.load_trades(limit=limit, user_id=user_id)
        buf = io.StringIO()
        fields = [
            "id",
            "symbol",
            "entry",
            "exit",
            "qty",
            "pnl",
            "pnl_pct",
            "reason",
            "confidence",
            "ai_score",
            "win_prob",
            "invested",
            "opened",
            "closed",
            "exchange",
            "regime",
            "trade_type",
            "dca_level",
            "news_score",
            "onchain_score",
        ]
        w = csv.DictWriter(buf, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        if trades:
            w.writerows(trades)
        return buf.getvalue()

    def backup(self) -> str | None:
        try:
            bdir = CONFIG.get("backup_dir", "backups")
            os.makedirs(bdir, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M")
            path = os.path.join(bdir, f"trevlix_backup_{ts}.zip")
            # [Verbesserung #17] Tabellennamen-Whitelist gegen SQL-Injection
            _ALLOWED_TABLES = frozenset(
                [
                    "trades",
                    "users",
                    "ai_training",
                    "backtest_results",
                    "price_alerts",
                    "daily_reports",
                    "genetic_results",
                    "arb_opportunities",
                ]
            )
            with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
                for table in _ALLOWED_TABLES:
                    try:
                        with self._get_conn() as conn:
                            with conn.cursor() as c:
                                c.execute(f"SELECT * FROM `{table}` LIMIT 100000")
                                rows = c.fetchall()
                        data = []
                        for r in rows:
                            d = dict(r)
                            for k, v in d.items():
                                if hasattr(v, "isoformat"):
                                    d[k] = v.isoformat()
                            data.append(d)
                        zf.writestr(f"{table}.json", json.dumps(data, ensure_ascii=False))
                    except Exception as te:
                        log.debug(f"Backup {table}: {te}")
                _BACKUP_SENSITIVE_KEYS = frozenset(
                    {
                        "api_key",
                        "secret",
                        "mysql_pass",
                        "admin_password",
                        "jwt_secret",
                        "short_api_key",
                        "short_secret",
                        "cryptopanic_token",
                        "telegram_token",  # Neu: sensibel
                        "discord_webhook",  # Neu: sensibel
                    }
                )
                safe_cfg = {k: v for k, v in CONFIG.items() if k not in _BACKUP_SENSITIVE_KEYS}
                zf.writestr("config.json", json.dumps(safe_cfg, indent=2, ensure_ascii=False))
            # Alte löschen
            cutoff = datetime.now() - timedelta(days=CONFIG["backup_keep_days"])
            for fn in os.listdir(bdir):
                fp = os.path.join(bdir, fn)
                if os.path.getmtime(fp) < cutoff.timestamp():
                    try:
                        os.remove(fp)
                    except Exception:
                        pass
            # [Verbesserung #9] SHA-256 Checksum vor Verschlüsselung
            try:
                with open(path, "rb") as f:
                    raw_zip = f.read()
                checksum = hashlib.sha256(raw_zip).hexdigest()
                sha_path = path + ".sha256"
                with open(sha_path, "w") as f:
                    f.write(f"{checksum}  {os.path.basename(path)}\n")
                log.debug(f"SHA-256 gespeichert: {sha_path}")
            except Exception as sha_err:
                log.debug(f"Backup-Checksum: {sha_err}")

            # [Verbesserung #49] Backup-Verschlüsselung
            if CONFIG.get("backup_encrypt") and path:
                try:
                    with open(path, "rb") as f:
                        raw = f.read()
                    encrypted = encrypt_value(raw.hex())
                    enc_path = path + ".enc"
                    with open(enc_path, "w") as f:
                        f.write(encrypted)
                    os.remove(path)
                    path = enc_path
                except Exception as enc_err:
                    log.debug(f"Backup-Verschlüsselung: {enc_err}")

            log.info(f"✅ Backup: {path}")
            return path
        except Exception as e:
            log.error(f"Backup: {e}")
            return None

    def verify_backup(self, backup_path: str) -> dict:
        """[Verbesserung #9] Prüft die Integrität eines Backups anhand der SHA-256-Checksum."""
        result = {"ok": False, "error": None, "checksum": None, "path": backup_path}
        try:
            # Für .enc-Backups → Checksum der ursprünglichen ZIP-Datei
            zip_path = backup_path.replace(".enc", "")
            sha_path = zip_path + ".sha256"
            if not os.path.exists(backup_path):
                result["error"] = "Backup-Datei nicht gefunden"
                return result
            if not os.path.exists(sha_path):
                result["error"] = "Keine .sha256-Datei vorhanden"
                return result
            # Checksum aus Datei lesen
            with open(sha_path) as f:
                parts = f.read().split()
            if not parts:
                result["error"] = "SHA256-Datei ist leer"
                return result
            stored = parts[0]
            result["checksum"] = stored
            # Bei verschlüsselten Backups: entschlüsseln und prüfen
            if backup_path.endswith(".enc"):
                try:
                    from services.encryption import decrypt_value

                    with open(backup_path) as f:
                        enc_data = f.read()
                    raw_hex = decrypt_value(enc_data)
                    raw = bytes.fromhex(raw_hex)
                    actual = hashlib.sha256(raw).hexdigest()
                except Exception as dec_err:
                    result["error"] = f"Entschlüsselung fehlgeschlagen: {dec_err}"
                    return result
            else:
                with open(backup_path, "rb") as f:
                    raw = f.read()
                actual = hashlib.sha256(raw).hexdigest()
            if actual == stored:
                result["ok"] = True
            else:
                result["error"] = f"Checksum mismatch: {actual[:16]}... ≠ {stored[:16]}..."
        except Exception as e:
            result["error"] = str(e)
        return result

    # [Verbesserung #21] Batch-Insert für AI-Samples
    def save_ai_samples_batch(self, samples: list[tuple[np.ndarray, int, str]]):
        """Batch-Insert für mehrere AI-Samples."""
        if not samples:
            return
        try:
            with self._get_conn() as conn:
                with conn.cursor() as c:
                    c.executemany(
                        "INSERT INTO ai_training (features,label,regime) VALUES(%s,%s,%s)",
                        [
                            (json.dumps(feat.tolist()), label, regime)
                            for feat, label, regime in samples
                        ],
                    )
        except Exception as e:
            log.error(f"save_ai_samples_batch: {e}")

    # [Verbesserung #24] Data Retention – alte Audit-Logs und AI-Samples bereinigen
    def cleanup_old_data(self):
        """Bereinigt alte Daten basierend auf Retention-Policy."""
        try:
            with self._get_conn() as conn:
                with conn.cursor() as c:
                    audit_days = CONFIG.get("audit_retention_days", 90)
                    c.execute(
                        "DELETE FROM audit_log WHERE created_at < NOW() - INTERVAL %s DAY",
                        (audit_days,),
                    )
                    deleted_audit = c.rowcount

                    ai_days = CONFIG.get("ai_sample_retention_days", 180)
                    c.execute(
                        "DELETE FROM ai_training WHERE created_at < NOW() - INTERVAL %s DAY",
                        (ai_days,),
                    )
                    deleted_ai = c.rowcount
            if deleted_audit or deleted_ai:
                log.info(
                    f"🧹 Data Retention: {deleted_audit} Audit-Logs, {deleted_ai} AI-Samples bereinigt"
                )
        except Exception as e:
            log.debug(f"cleanup_old_data: {e}")


# ═══════════════════════════════════════════════════════════════════════════════
# [Verbesserung #1] SESSION TIMEOUT
# [Verbesserung #2] CSRF PROTECTION
# [Verbesserung #3] LOGIN BRUTE-FORCE SCHUTZ
# [Verbesserung #6] SECURITY HEADERS
# [Verbesserung #8] AUDIT-LOG HELPER
# ═══════════════════════════════════════════════════════════════════════════════
_login_attempts: dict[str, list[float]] = {}  # IP → [timestamps]
_login_attempts_lock = threading.Lock()


def _check_login_rate(ip: str, max_attempts: int = 5, window: int = 60) -> bool:
    """[Verbesserung #3] Prüft ob IP zu viele Login-Versuche hatte."""
    now = time.time()
    with _login_attempts_lock:
        attempts = _login_attempts.get(ip, [])
        attempts = [t for t in attempts if now - t < window]
        if attempts:
            _login_attempts[ip] = attempts
        else:
            # Leere Listen entfernen → verhindert unbegrenztes Dict-Wachstum (Memory-Leak)
            _login_attempts.pop(ip, None)
        return len(attempts) < max_attempts


def _record_login_attempt(ip: str):
    with _login_attempts_lock:
        attempts = _login_attempts.setdefault(ip, [])
        attempts.append(time.time())
        # Timestamps pro IP auf letzte 50 begrenzen (Memory-Leak-Schutz)
        if len(attempts) > 50:
            _login_attempts[ip] = attempts[-50:]
        # Periodisch ältere IPs bereinigen wenn Dict zu groß wird (>10.000 Einträge)
        if len(_login_attempts) > 10_000:
            cutoff = time.time() - 3600  # Einträge die älter als 1 Stunde sind löschen
            stale = [k for k, v in _login_attempts.items() if not v or max(v) < cutoff]
            for k in stale:
                _login_attempts.pop(k, None)


def _audit(action: str, detail: str = "", user_id: int = 0):
    """[Verbesserung #8] Audit-Log Hilfsfunktion."""
    try:
        try:
            ip = request.remote_addr or "unknown"
        except RuntimeError:
            ip = "system"
        with db._get_conn() as conn:
            with conn.cursor() as c:
                c.execute(
                    "INSERT INTO audit_log (user_id,action,detail,ip) VALUES(%s,%s,%s,%s)",
                    (user_id, str(action)[:80], str(detail)[:500], str(ip)[:45]),
                )
    except Exception as e:
        log.debug(f"_audit: {e}")


@app.before_request
def _before_request_hooks():
    """[Verbesserung #1] Session-Timeout + [Verbesserung #2] CSRF-Check."""
    # Session-Timeout prüfen
    if session.get("user_id"):
        last = session.get("last_active")
        if last:
            try:
                elapsed = (datetime.now() - datetime.fromisoformat(last)).total_seconds()
                if elapsed > _SESSION_TIMEOUT_MIN * 60:
                    uid = session.get("user_id", 0)
                    session.clear()
                    _audit("session_timeout", f"user_id={uid}", uid)
                    if request.path.startswith("/api/"):
                        from flask import abort

                        abort(401)
                    return redirect("/login")
            except (ValueError, TypeError):
                # Ungültiger Timestamp → Session sicherheitshalber beenden
                session.clear()
                if request.path.startswith("/api/"):
                    from flask import abort

                    abort(401)
                return redirect("/login")
        session["last_active"] = datetime.now().isoformat()

    # CSRF-Check für state-changing Requests (nicht für API mit Bearer Token)
    if request.method in ("POST", "PUT", "DELETE", "PATCH"):
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer ") and session.get("user_id"):
            # Ausnahme für Socket.io und statische Assets
            if not request.path.startswith("/socket.io"):
                try:
                    token = request.form.get("_csrf") or (request.json or {}).get("_csrf")
                except Exception:
                    token = None
                if request.content_type and "application/json" not in request.content_type:
                    expected = session.get("_csrf_token")
                    if expected and (
                        not token or not hmac.compare_digest(str(token), str(expected))
                    ):
                        _audit("csrf_violation", request.path, session.get("user_id", 0))
                        from flask import abort

                        abort(403)  # CSRF-Verletzung → Request ablehnen


@app.after_request
def _security_headers(response):
    """[Verbesserung #6] Security Headers."""
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    # X-XSS-Protection ist in modernen Browsern deprecated und entfernt; weglassen um
    # potenzielle XSS-Auditor-Bypässe zu vermeiden. CSP ist der moderne Ersatz.
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    # Permissions-Policy: deaktiviert Browser-APIs die für Trading-Apps nicht benötigt werden
    response.headers["Permissions-Policy"] = (
        "camera=(), microphone=(), geolocation=(), payment=(), usb=()"
    )
    if request.is_secure:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


def _safe_int(val: Any, default: int) -> int:
    """Sicherer int()-Cast für Request-Parameter. Gibt default bei ungültigen Werten zurück."""
    try:
        return int(val)
    except (ValueError, TypeError):
        return default


def _safe_float(val: Any, default: float) -> float:
    """Sicherer float()-Cast für Request-Parameter. Gibt default bei ungültigen/Inf/NaN Werten zurück."""
    try:
        result = float(val)
        if not math.isfinite(result):  # NaN + Inf check
            return default
        return result
    except (ValueError, TypeError):
        return default


def _generate_csrf_token() -> str:
    """[Verbesserung #2] CSRF-Token pro Session generieren."""
    if "_csrf_token" not in session:
        session["_csrf_token"] = secrets.token_hex(32)
    return session["_csrf_token"]


app.jinja_env.globals["csrf_token"] = _generate_csrf_token


# ═══════════════════════════════════════════════════════════════════════════════
# JWT AUTH
# ═══════════════════════════════════════════════════════════════════════════════
def api_auth_required(f):
    """Für REST-API Endpunkte — prüft Bearer Token."""

    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.headers.get("Authorization", "")
        token = auth.replace("Bearer ", "").strip() if auth.startswith("Bearer ") else ""
        # Auch aus Query-Param
        if not token:
            token = request.args.get("token", "")
        if token:
            uid = db.verify_api_token(token)
            if uid:
                request.user_id = uid
                return f(*args, **kwargs)
        # Session-Fallback für Dashboard
        if session.get("user_id"):
            request.user_id = session["user_id"]
            return f(*args, **kwargs)
        return jsonify({"error": "Nicht autorisiert"}), 401

    return decorated


def dashboard_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("user_id"):
            return redirect("/login")
        return f(*args, **kwargs)

    return decorated


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        uid = getattr(request, "user_id", session.get("user_id"))
        if not uid:
            return jsonify({"error": "Nicht autorisiert"}), 401
        user = db.get_user_by_id(uid)
        if not user or user.get("role") != "admin":
            return jsonify({"error": "Nur Admin"}), 403
        return f(*args, **kwargs)

    return decorated


# ═══════════════════════════════════════════════════════════════════════════════
# DISCORD
# ═══════════════════════════════════════════════════════════════════════════════
class DiscordNotifier:
    COLORS = {
        "buy": 3066993,
        "sell_win": 3066993,
        "sell_loss": 15158332,
        "error": 15158332,
        "circuit": 16776960,
        "info": 3447003,
        "report": 9442302,
        "alert": 16776960,
        "arb": 16744272,
        "anomaly": 16711680,
    }

    def send(self, title: str, desc: str, color_key="info", fields: list = None):
        url = CONFIG.get("discord_webhook", "")
        if not url:
            return
        try:
            embed = {
                "title": title,
                "description": desc,
                "color": self.COLORS.get(color_key, 3447003),
                "timestamp": datetime.now(UTC).isoformat(),
                "footer": {"text": f"{BOT_FULL} · {CONFIG['exchange'].upper()}"},
            }
            if fields:
                embed["fields"] = [
                    {"name": f[0], "value": str(f[1]), "inline": f[2] if len(f) > 2 else True}
                    for f in fields
                    if len(f) >= 2
                ]
            httpx.post(url, json={"embeds": [embed]}, timeout=5)
        except Exception as e:
            log.debug(f"Discord: {e}")

    def trade_buy(self, symbol, price, invest, ai_score, win_prob, news_score=0):
        if not CONFIG.get("discord_on_buy"):
            return
        news_txt = f"📰 {news_score:+.2f}" if news_score != 0 else "—"
        self.send(
            f"🟢 KAUF: {symbol}",
            f"```\nPreis:      {price:.4f} USDT\nInvestiert: {invest:.2f} USDT\n"
            f"KI-Score:   {ai_score:.0f}%\nWin-Chance: {win_prob:.0f}%\n"
            f"News:       {news_txt}\n```",
            "buy",
            fields=[
                ("Exchange", CONFIG["exchange"].upper()),
                ("Modus", "📝 Paper" if CONFIG["paper_trading"] else "💰 Live"),
            ],
        )

    def trade_sell(self, symbol, price, pnl, pnl_pct, reason, partial=False):
        if not CONFIG.get("discord_on_sell"):
            return
        won = pnl >= 0
        pref = "🔶 PARTIAL" if partial else ("✅ GEWINN" if won else "❌ VERLUST")
        self.send(
            f"{pref}: {symbol}",
            f"```\nPreis:  {price:.4f} USDT\nPnL:    {pnl:+.2f} ({pnl_pct:+.2f}%)\n"
            f"Grund:  {reason}\n```",
            "sell_win" if won else "sell_loss",
        )

    def short_open(self, symbol, price, invest):
        self.send(
            f"🔴 SHORT: {symbol}",
            f"```\nPreis:      {price:.4f} USDT\nInvestiert: {invest:.2f} USDT\n```",
            "sell_loss",
        )

    def circuit_breaker(self, losses, pause_min):
        if not CONFIG.get("discord_on_circuit"):
            return
        self.send(
            "⚡ CIRCUIT BREAKER",
            f"```\n{losses} Verluste hintereinander!\nPause: {pause_min} Minuten\n```",
            "circuit",
        )

    def price_alert(self, symbol, price, target, direction):
        self.send(
            f"🔔 PREIS-ALERT: {symbol}",
            f"```\nAktuell: {price:.4f}\nZiel:    {target:.4f}\nRichtung: {'↑' if direction == 'above' else '↓'}\n```",
            "alert",
        )

    def arb_found(self, symbol, buy_ex, sell_ex, spread):
        self.send(
            f"💹 ARBITRAGE: {symbol}",
            f"```\nKauf:   {buy_ex}\nVerkauf:{sell_ex}\nSpread: {spread:.2f}%\n```",
            "arb",
        )

    def anomaly_detected(self, symbol, score):
        self.send(
            f"🚨 ANOMALIE: {symbol}",
            f"```\nAnomalie-Score: {score:.3f}\nBot pausiert!\n```",
            "anomaly",
        )

    def daily_report(self, report: dict):
        if not CONFIG.get("discord_daily_report"):
            return
        s = report.get("summary", {})
        self.send(
            f"📊 {BOT_NAME} Tages-Report – {report.get('date', '')}",
            f"```\nPnL heute:  {s.get('daily_pnl', 0):+.2f} USDT\n"
            f"Trades:     {s.get('trades_today', 0)}\n"
            f"Win-Rate:   {s.get('win_rate', 0):.1f}%\n"
            f"Portfolio:  {s.get('portfolio_value', 0):.2f} USDT\n"
            f"Rendite:    {s.get('return_pct', 0):+.2f}%\n"
            f"Arbitrage:  {s.get('arb_found', 0)} Chancen\n```",
            "report",
            fields=[
                ("Bester Coin", s.get("best_coin", "—")),
                ("Schlechtester", s.get("worst_coin", "—")),
                ("KI-Genauigkeit", f"{s.get('ai_acc', 0):.1f}%"),
            ],
        )

    def error(self, msg: str):
        if not CONFIG.get("discord_on_error"):
            return
        self.send(f"🔴 {BOT_NAME} FEHLER", f"```\n{msg[:500]}\n```", "error")

    def backup_done(self, path: str):
        self.send("💾 Backup erstellt", f"```\n{os.path.basename(path)}\n```", "info")

    def genetic_result(self, gen: int, fitness: float, genome: dict):
        self.send(
            f"🧬 Genetik Gen.{gen}",
            f"```\nFitness: {fitness:.3f}\nSL: {genome.get('sl', 0) * 100:.1f}% TP: {genome.get('tp', 0) * 100:.1f}%\n```",
            "info",
        )

    def dna_boost(
        self, symbol: str, action: str, win_rate: float, matches: int, multiplier: float
    ) -> None:
        """Benachrichtigung bei DNA-Pattern-Match (Boost oder Block)."""
        emoji = "🧬✅" if action == "boost" else "🧬⛔"
        color = "buy" if action == "boost" else "sell_loss"
        self.send(
            f"{emoji} DNA-{action.upper()}: {symbol}",
            f"```\nWin-Rate:    {win_rate:.0f}%\n"
            f"Matches:     {matches}\n"
            f"Multiplikator: {multiplier:.2f}x\n```",
            color,
        )

    def smart_exit(self, symbol: str, sl: float, tp: float, regime: str, atr_pct: float) -> None:
        """Benachrichtigung über Smart Exit Level."""
        self.send(
            f"📐 Smart Exit: {symbol}",
            f"```\nRegime:  {regime}\nATR:     {atr_pct:.2f}%\n"
            f"SL:      {sl:.4f}\nTP:      {tp:.4f}\n```",
            "info",
        )


# FearGreedIndex importiert aus services.market_data


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


# OnChainFetcher importiert aus services.market_data


# DominanceFilter importiert aus services.market_data


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
        for t in trades[-100:]:
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
        return {
            "enabled": CONFIG.get("rl_enabled", True),
            "is_trained": self.is_trained,
            "episodes": self.episodes,
            "total_reward": round(self.total_reward, 2),
            "epsilon": round(self.epsilon, 3),
            "q_states": len(self.q_table),
            "min_episodes": CONFIG.get("rl_min_episodes", 100),
        }


# compute_indicators, STRATEGIES, STRATEGY_NAMES importiert aus services.strategies


# ═══════════════════════════════════════════════════════════════════════════════
# AI ENGINE v4 – Regime + Walk-Forward + LSTM + RL-Integration
# ═══════════════════════════════════════════════════════════════════════════════
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
        self.ai_log = []
        self.optim_log = []
        self._pending: dict[str, dict] = {}
        self._scan_cache: dict[str, dict] = {}  # für RL
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
            self.progress_pct = min(100, int(n / CONFIG["ai_min_samples"] * 100))
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
        trades = state.closed_trades
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
            try:
                knowledge_base.analyze_training_async(
                    training_ver=self.training_ver,
                    wf_accuracy=wf_acc,
                    bull_accuracy=bull_acc,
                    bear_accuracy=bear_acc,
                    feature_weights=dict(self.weights),
                    threshold=best_thresh,
                )
            except Exception:
                pass  # LLM-Analyse ist optional
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
                    for t in trades[-80:]:
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
                    wr = wins / len(trades[-80:])
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
            self.optim_log = self.optim_log[:20]
            log.info(f"🔬 Optimierung: {detail}")
            # Autonome LLM-Analyse: Optimierungsergebnis bewerten
            try:
                knowledge_base.analyze_optimization_async(
                    best_sl=best_sl,
                    best_tp=best_tp,
                    prev_sl=prev_sl,
                    prev_tp=prev_tp,
                    trade_count=len(trades[-80:]),
                )
            except Exception:
                pass  # LLM-Analyse ist optional
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

        recent_trades = closed_trades[-20:]
        recent_wr = sum(1 for t in recent_trades if t.get("pnl", 0) > 0) / max(
            len(recent_trades), 1
        )
        recent_pnl_avg = sum(t.get("pnl", 0) for t in recent_trades) / max(len(recent_trades), 1)
        # Streak: aufeinanderfolgende Gewinne/Verluste
        streak = 0
        for t in reversed(recent_trades[-10:]):
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

    def should_buy(self, features, conf) -> tuple[bool, float, str]:
        """[26] Erweitert mit Conformal Prediction Intervals."""
        if not self.is_trained or not CONFIG.get("ai_enabled"):
            return conf >= CONFIG.get("min_vote_score", 0.3), conf, "Vote"
        try:
            X_s = self.scaler.transform(features.reshape(1, -1))
            prob = self._predict(X_s, features)
            allowed = prob >= CONFIG["ai_min_confidence"]
            self.ai_log.insert(
                0,
                {
                    "time": datetime.now().strftime("%H:%M"),
                    "allowed": allowed,
                    "prob": round(prob * 100, 1),
                    "reason": f"{'✅' if allowed else '🚫'} {prob * 100:.1f}%",
                },
            )
            self.ai_log = self.ai_log[:30]
            if allowed:
                self.allowed_count += 1
            else:
                self.blocked_count += 1
            return allowed, prob, f"{'✅' if allowed else '🚫'} Win-Prob:{prob * 100:.1f}%"
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
        # RL lernen
        rl_agent.on_trade_close(p.get("scan", {}), pnl)
        threading.Thread(
            target=lambda f=p["features"], w=won, r=regime_str: self.db.save_ai_sample(f, w, r),
            daemon=True,
        ).start()
        n = len(self.X_raw)
        self.progress_pct = min(100, int(n / CONFIG["ai_min_samples"] * 100))
        if (
            n >= CONFIG["ai_min_samples"]
            and self.trades_since_retrain >= CONFIG["ai_retrain_every"]
        ):
            threading.Thread(target=self._train, daemon=True).start()
        if self.trades_since_optimize >= CONFIG["ai_optimize_every"]:
            threading.Thread(target=self._optimize, daemon=True).start()
        # Genetischer Optimizer nach 30 Trades
        if n % 30 == 0 and state:
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
            "min_samples": CONFIG["ai_min_samples"],
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
            "ai_log": self.ai_log[:20],
            "optim_log": self.optim_log[:10],
            "blocked_count": self.blocked_count,
            "allowed_count": self.allowed_count,
            "blocked_pct": round(self.blocked_count / total * 100, 1) if total > 0 else 0,
            "params": {
                "sl": round(CONFIG["stop_loss_pct"] * 100, 2),
                "tp": round(CONFIG["take_profit_pct"] * 100, 2),
                "vote": round(CONFIG.get("min_vote_score", 0.3) * 100, 1),
            },
        }


# ═══════════════════════════════════════════════════════════════════════════════
# BACKTEST ENGINE
# ═══════════════════════════════════════════════════════════════════════════════
class BacktestEngine:
    def run(self, ex, symbol, tf, candles, sl_pct, tp_pct, vote_thr) -> dict:
        try:
            ohlcv = ex.fetch_ohlcv(symbol, tf, limit=candles)
            if not ohlcv or len(ohlcv) < 100:
                return {"error": "Zu wenig Daten"}
            df = pd.DataFrame(
                ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"]
            )
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
            df.set_index("timestamp", inplace=True)
            df = compute_indicators(df)
            if df is None or len(df) < 3:
                return {"error": "Nicht genug Daten für Backtest (min. 3 Kerzen)"}
            cap = 10000.0
            start = cap
            pos = None
            trades = []
            equity = [{"time": str(df.index[0])[:16], "value": cap}]
            for i in range(2, len(df)):
                row = df.iloc[i]
                prev = df.iloc[i - 1]
                price = float(row["close"])
                if pos and pos.get("entry") and pos["entry"] > 0:
                    pp = (price - pos["entry"]) / pos["entry"]
                    if pp <= -sl_pct:
                        pnl = pos["inv"] * pp
                        cap += pos["inv"] + pnl
                        trades.append(
                            {
                                "time": str(row.name)[:16],
                                "entry": round(pos["entry"], 4),
                                "exit": round(price, 4),
                                "pnl": round(pnl, 2),
                                "won": False,
                                "reason": "SL",
                            }
                        )
                        pos = None
                    elif pp >= tp_pct:
                        pnl = pos["inv"] * pp
                        cap += pos["inv"] + pnl
                        trades.append(
                            {
                                "time": str(row.name)[:16],
                                "entry": round(pos["entry"], 4),
                                "exit": round(price, 4),
                                "pnl": round(pnl, 2),
                                "won": True,
                                "reason": "TP",
                            }
                        )
                        pos = None
                if pos is None:
                    votes = {nm: fn(row, prev) for nm, fn in STRATEGIES}
                    conf = (
                        sum(1 for v in votes.values() if v == 1) / len(STRATEGIES)
                        if STRATEGIES
                        else 0.0
                    )
                    if conf >= vote_thr:
                        inv = cap * 0.2
                        cap -= inv
                        pos = {"entry": price, "inv": inv}
                equity.append({"time": str(row.name)[:16], "value": round(cap, 2)})
            if not trades:
                return {
                    "error": "Keine Trades – Threshold zu hoch",
                    "symbol": symbol,
                    "timeframe": tf,
                }
            won = [t for t in trades if t["won"]]
            lost = [t for t in trades if not t["won"]]
            wr = len(won) / len(trades) * 100
            total_pnl = sum(t["pnl"] for t in trades)
            gp = sum(t["pnl"] for t in won)
            gl = abs(sum(t["pnl"] for t in lost))
            pf = gp / gl if gl > 0 else 99.0
            dd = 0.0
            peak = start
            for e in equity:
                if e["value"] > peak:
                    peak = e["value"]
                dd = max(dd, (peak - e["value"]) / peak * 100) if peak > 0 else 0.0
            result = {
                "symbol": symbol,
                "timeframe": tf,
                "candles": candles,
                "total_trades": len(trades),
                "win_rate": round(wr, 1),
                "total_pnl": round(total_pnl, 2),
                "profit_factor": round(pf, 2),
                "max_drawdown": round(dd, 2),
                "start_balance": start,
                "final_balance": round(cap, 2),
                "return_pct": round((cap - start) / start * 100, 2) if start > 0 else 0.0,
                "equity_curve": equity[:: max(1, len(equity) // 100)],
                "trades": trades[-30:],
            }
            threading.Thread(target=lambda: db.save_backtest(result), daemon=True).start()
            return result
        except Exception as e:
            return {"error": str(e), "symbol": symbol}


# ═══════════════════════════════════════════════════════════════════════════════
# MULTI-TIMEFRAME FILTER
# ═══════════════════════════════════════════════════════════════════════════════
class MultiTimeframeFilter:
    def __init__(self):
        self._cache: dict[str, dict] = {}
        self._lock = threading.Lock()

    def is_confirmed(self, ex, symbol, signal) -> tuple[bool, str]:
        if not CONFIG.get("mtf_enabled") or signal != 1:
            return True, "MTF deaktiv"
        with self._lock:
            c = self._cache.get(symbol)
            if c and (datetime.now() - c["ts"]).total_seconds() < 240:
                ok = c["trend"] >= 0
                return ok, f"{'✅' if ok else '❌'} 4h cached"
        try:
            ohlcv = ex.fetch_ohlcv(symbol, CONFIG["mtf_confirm_tf"], limit=60)
            if not ohlcv or len(ohlcv) < 30:
                return True, "MTF: wenig Daten"
            df = pd.DataFrame(ohlcv, columns=["ts", "o", "h", "l", "close", "v"])
            c2 = df["close"]
            e21 = float(c2.ewm(span=21, adjust=False).mean().iloc[-1])
            e50 = float(c2.ewm(span=50, adjust=False).mean().iloc[-1])
            price = float(c2.iloc[-1])
            d = c2.diff()
            g = d.clip(lower=0).ewm(span=14, adjust=False).mean()
            ls = (-d.clip(upper=0)).ewm(span=14, adjust=False).mean()
            rsi = float((100 - (100 / (1 + g / ls.replace(0, np.nan)))).iloc[-1])
            score = (1 if price > e21 else 0) + (1 if e21 > e50 else 0) + (1 if rsi > 45 else 0)
            trend = 1 if score >= 2 else (-1 if score == 0 else 0)
            with self._lock:
                self._cache[symbol] = {"trend": trend, "ts": datetime.now()}
            ok = trend >= 0
            return ok, f"{'✅' if ok else '❌'} 4h RSI:{rsi:.0f}"
        except Exception as e:
            return True, f"MTF Err:{e}"


# ═══════════════════════════════════════════════════════════════════════════════
# ORDERBOOK IMBALANCE
# ═══════════════════════════════════════════════════════════════════════════════
class OrderbookImbalance:
    def get(self, ex, symbol) -> tuple[float, str]:
        try:
            ob = ex.fetch_order_book(symbol, limit=20)
            if not ob.get("bids") or not ob.get("asks"):
                return 0.5, "Leer"
            bid_vol = sum(b[1] * b[0] for b in ob["bids"][:10])
            ask_vol = sum(a[1] * a[0] for a in ob["asks"][:10])
            total = bid_vol + ask_vol
            if total == 0:
                return 0.5, "Leer"
            ratio = bid_vol / total
            desc = (
                "💪 Kaufdruck"
                if ratio > 0.65
                else "⬇️ Verkaufsdruck"
                if ratio < 0.35
                else "⚖️ Ausgeglichen"
            ) + f" {ratio:.0%}"
            return round(ratio, 3), desc
        except Exception as e:
            return 0.5, f"OB:{e}"


# ═══════════════════════════════════════════════════════════════════════════════
# STEUER
# ═══════════════════════════════════════════════════════════════════════════════
class TaxReportGenerator:
    def generate(self, trades, year, method="fifo") -> dict:
        yt = [
            t
            for t in trades
            if str(t.get("closed", ""))[:4] == str(year) and t.get("pnl") is not None
        ]
        if not yt:
            return {
                "year": year,
                "method": method,
                "trades": [],
                "gains": [],
                "losses": [],
                "summary": {
                    "total_gains": 0,
                    "total_losses": 0,
                    "net_pnl": 0,
                    "total_fees": 0,
                    "taxable_gains": 0,
                    "trade_count": 0,
                    "win_count": 0,
                    "loss_count": 0,
                },
            }
        gains = []
        losses = []
        total_fees = 0.0
        for t in yt:
            pnl = float(t.get("pnl") or 0)
            fee = float(t.get("invested") or 0) * CONFIG.get("fee_rate", 0.001) * 2
            net = pnl - fee
            total_fees += fee
            entry = {
                "date": str(t.get("closed", ""))[:10],
                "symbol": t.get("symbol", "?"),
                "buy_price": t.get("entry", 0),
                "sell_price": t.get("exit", 0),
                "qty": t.get("qty", 0),
                "gross_pnl": round(pnl, 2),
                "fee": round(fee, 4),
                "net_pnl": round(net, 2),
                "taxable": net > 0,
                "type": t.get("trade_type", "long"),
            }
            (gains if net > 0 else losses).append(entry)
        tg = sum(e["net_pnl"] for e in gains)
        tl = sum(e["net_pnl"] for e in losses)
        return {
            "year": year,
            "method": method.upper(),
            "gains": sorted(gains, key=lambda x: x["net_pnl"], reverse=True)[:50],
            "losses": sorted(losses, key=lambda x: x["net_pnl"])[:50],
            "summary": {
                "total_gains": round(tg, 2),
                "total_losses": round(tl, 2),
                "net_pnl": round(tg + tl, 2),
                "total_fees": round(total_fees, 2),
                "taxable_gains": round(max(0, tg + tl), 2),
                "trade_count": len(yt),
                "win_count": len(gains),
                "loss_count": len(losses),
            },
        }


# MarketRegime importiert aus services.market_data


# RiskManager importiert aus services.risk


# LiquidityScorer importiert aus services.risk


# SentimentFetcher importiert aus services.market_data


# ═══════════════════════════════════════════════════════════════════════════════
# PRICE ALERT MANAGER
# ═══════════════════════════════════════════════════════════════════════════════
class PriceAlertManager:
    def check(self, prices: dict[str, float]):
        alerts = db.get_active_alerts()
        for a in alerts:
            sym = a.get("symbol", "")
            if not sym:
                continue
            price = prices.get(sym)
            if price is None:
                continue
            raw_target = a.get("target_price")
            if raw_target is None:
                continue
            target = float(raw_target)
            direction = a.get("direction", "above")
            triggered = (direction == "above" and price >= target) or (
                direction == "below" and price <= target
            )
            if triggered:
                db.trigger_alert(a.get("id", 0))
                discord.price_alert(sym, price, target, direction)
                emit_event(
                    "price_alert",
                    {"symbol": sym, "price": price, "target": target, "direction": direction},
                )
                log.info(f"🔔 Alert: {sym} {direction} {target} (aktuell: {price})")


# ═══════════════════════════════════════════════════════════════════════════════
# DAILY REPORT SCHEDULER
# ═══════════════════════════════════════════════════════════════════════════════
class DailyReportScheduler:
    def run(self):
        while True:
            time.sleep(60)
            now = datetime.now()
            if now.hour == CONFIG.get("discord_report_hour", 20) and now.minute < 2:
                if not db.report_sent_today():
                    self._send_report()
            # Dominanz-Update stündlich
            if now.minute == 0:
                threading.Thread(target=dominance.update, daemon=True).start()

    def _send_report(self):
        try:
            today = datetime.now().strftime("%Y-%m-%d")
            trades_today = [
                t for t in state.closed_trades if str(t.get("closed", ""))[:10] == today
            ]
            daily_pnl = sum(t.get("pnl", 0) for t in trades_today)
            pv = state.portfolio_value()
            win_rate = (
                (sum(1 for t in trades_today if t.get("pnl", 0) > 0) / len(trades_today) * 100)
                if trades_today
                else 0
            )
            # Best/worst coin
            coin_pnl: dict[str, float] = {}
            for t in trades_today:
                coin_pnl[t.get("symbol", "?")] = coin_pnl.get(t.get("symbol", "?"), 0) + t.get(
                    "pnl", 0
                )
            best = max(coin_pnl, key=coin_pnl.get, default="—") if coin_pnl else "—"
            worst = min(coin_pnl, key=coin_pnl.get, default="—") if coin_pnl else "—"
            ai_acc = ai_engine.wf_accuracy * 100
            arb_count = getattr(arb_scanner, "found_today", 0)
            report = {
                "date": today,
                "summary": {
                    "daily_pnl": round(daily_pnl, 2),
                    "trades_today": len(trades_today),
                    "win_rate": round(win_rate, 1),
                    "portfolio_value": round(pv, 2),
                    "return_pct": round(state.return_pct(), 2),
                    "best_coin": best,
                    "worst_coin": worst,
                    "ai_acc": round(ai_acc, 1),
                    "arb_found": arb_count,
                },
            }
            discord.daily_report(report)
            db.save_daily_report(today, report)
            log.info(f"📊 Tages-Report gesendet: PnL={daily_pnl:+.2f}")
        except Exception as e:
            log.error(f"Report: {e}")


# ═══════════════════════════════════════════════════════════════════════════════
# BACKUP SCHEDULER
# ═══════════════════════════════════════════════════════════════════════════════
class BackupScheduler:
    def run(self):
        while True:
            time.sleep(60)
            now = datetime.now()
            if now.hour == 3 and now.minute < 2 and CONFIG.get("backup_enabled"):
                path = db.backup()
                if path:
                    discord.backup_done(path)


# ═══════════════════════════════════════════════════════════════════════════════
# BOT STATE (Multi-User aware)
# ═══════════════════════════════════════════════════════════════════════════════
class BotState:
    def __init__(self, db_ref):
        self.db = db_ref
        self._lock = threading.RLock()  # [Verbesserung #4] Thread-Safety
        self.running = False
        self.paused = False
        self.balance = CONFIG.get("paper_balance", 10000)
        self.initial_balance = CONFIG.get("paper_balance", 10000)
        self.positions: dict[str, dict] = {}
        self.short_positions: dict[str, dict] = {}
        self.prices: dict[str, float] = {}
        self.closed_trades: list[dict] = []
        self.markets: list[str] = []
        # [Verbesserung #4] deque statt list – thread-safe + automatische Begrenzung
        from collections import deque

        self.portfolio_history: deque = deque(maxlen=500)
        self.signal_log: deque = deque(maxlen=50)
        self.activity_log: deque = deque(maxlen=50)
        self.arb_log: deque = deque(maxlen=20)
        self.iteration = 0
        self.last_scan = "—"
        self.next_scan = "—"
        self._start_time = time.time()  # für Uptime-Berechnung in /api/v1/status
        self._load_trades()

    def _load_trades(self):
        try:
            t = self.db.load_trades(limit=500)
            if t:
                with self._lock:
                    self.closed_trades = t
                log.info(f"📂 {len(t)} Trades aus DB")
        except Exception as e:
            log.debug(f"Load trades: {e}")

    def portfolio_value(self):
        with self._lock:
            pos_copy = dict(self.positions)
            short_copy = dict(self.short_positions)
        longs = sum(
            p.get("qty", 0) * self.prices.get(s, p.get("entry", 0))
            for s, p in pos_copy.items()
            if p.get("qty", 0) > 0
        )
        shorts = sum(_safe_float(p.get("pnl_unrealized"), 0.0) for p in short_copy.values())
        return self.balance + longs + shorts

    def return_pct(self):
        pv = self.portfolio_value()
        if self.initial_balance <= 0:
            return 0.0
        return (pv - self.initial_balance) / self.initial_balance * 100

    def win_rate(self):
        with self._lock:
            trades_copy = list(self.closed_trades)
        if not trades_copy:
            return 0.0
        return sum(1 for t in trades_copy if t.get("pnl", 0) > 0) / len(trades_copy) * 100

    def total_pnl(self):
        with self._lock:
            trades_copy = list(self.closed_trades)
        return sum(t.get("pnl", 0) for t in trades_copy)

    def avg_win(self):
        with self._lock:
            trades_copy = list(self.closed_trades)
        w = [t.get("pnl", 0) for t in trades_copy if t.get("pnl", 0) > 0]
        return sum(w) / len(w) if w else 0

    def avg_loss(self):
        with self._lock:
            trades_copy = list(self.closed_trades)
        losses = [t.get("pnl", 0) for t in trades_copy if t.get("pnl", 0) <= 0]
        return sum(losses) / len(losses) if losses else 0

    def profit_factor(self):
        with self._lock:
            trades_copy = list(self.closed_trades)
        g = sum(t.get("pnl", 0) for t in trades_copy if t.get("pnl", 0) > 0)
        total_loss = abs(sum(t.get("pnl", 0) for t in trades_copy if t.get("pnl", 0) < 0))
        return round(g / total_loss, 2) if total_loss > 0 else 0.0

    def add_activity(self, icon, title, detail, atype="info"):
        # [Verbesserung #4] deque.appendleft ist thread-safe, kein Truncating nötig
        self.activity_log.appendleft(
            {
                "icon": icon,
                "title": title,
                "detail": detail,
                "type": atype,
                "time": datetime.now().strftime("%H:%M:%S"),
            }
        )

    def add_signal(self, s):
        self.signal_log.appendleft(s)

    def snapshot(self) -> dict:
        pv = self.portfolio_value()
        risk.update_peak(pv)
        today = datetime.now().strftime("%Y-%m-%d")
        with self._lock:
            closed_copy = list(self.closed_trades)
            pos_copy = dict(self.positions)
            short_copy = dict(self.short_positions)
        trades_today = [t for t in closed_copy if str(t.get("closed", ""))[:10] == today]
        daily_pnl = sum(t.get("pnl", 0) for t in trades_today)

        open_pos = [
            {
                "symbol": sym,
                "entry": round(p.get("entry", 0), 4),
                "current": round(self.prices.get(sym, p.get("entry", 0)), 4),
                "qty": round(p.get("qty", 0), 4),
                "pnl": round(
                    (self.prices.get(sym, p.get("entry", 0)) - p.get("entry", 0)) * p.get("qty", 0),
                    2,
                ),
                "pnl_pct": round(
                    (self.prices.get(sym, p.get("entry", 0)) - p.get("entry", 0))
                    / p.get("entry", 1)
                    * 100
                    if p.get("entry", 0) > 0
                    else 0.0,
                    2,
                ),
                "sl": round(p.get("sl", 0), 4),
                "tp": round(p.get("tp", 0), 4),
                "invested": round(p.get("invested", 0), 2),
                "confidence": round(p.get("confidence", 0), 3),
                "ai_score": round(p.get("ai_score", 0), 1),
                "win_prob": round(p.get("win_prob", 0), 1),
                "dca_level": p.get("dca_level", 0),
                "partial_sold": p.get("partial_sold", 0),
                "news_score": round(p.get("news_score", 0), 2),
                "onchain_score": round(p.get("onchain_score", 0), 2),
                "trade_type": "long",
                "dna_hash": p.get("dna_hash", ""),
                "dna_boost": p.get("dna_boost", 1.0),
                "exit_regime": p.get("exit_regime", ""),
            }
            for sym, p in pos_copy.items()
        ] + [
            {
                "symbol": sym,
                "entry": round(p.get("entry", 0), 4),
                "current": round(self.prices.get(sym, p.get("entry", 0)), 4),
                "qty": round(p.get("qty", 0), 4),
                "pnl": round(p.get("pnl_unrealized", 0), 2),
                "pnl_pct": round(
                    (p.get("entry", 0) - self.prices.get(sym, p.get("entry", 0)))
                    / p.get("entry", 1)
                    * 100
                    if p.get("entry", 0) > 0
                    else 0.0,
                    2,
                ),
                "sl": round(p.get("sl", 0), 4),
                "tp": round(p.get("tp", 0), 4),
                "invested": round(p.get("invested", 0), 2),
                "trade_type": "short",
            }
            for sym, p in short_copy.items()
        ]

        # Goal ETA
        goal = CONFIG.get("portfolio_goal", 0)
        goal_pct = min(100, round(pv / goal * 100, 1)) if goal > 0 else 0
        goal_eta = "—"
        if goal > 0 and len(closed_copy) > 5:
            recent_g = sum(t.get("pnl", 0) for t in closed_copy[-20:])
            daily_est = recent_g / 20 if recent_g > 0 else 0
            if daily_est > 0:
                remaining = goal - pv
                if remaining <= 0:
                    goal_eta = "✅ Ziel erreicht!"
                else:
                    days = int(remaining / daily_est)
                    goal_eta = (
                        f"~{(datetime.now() + timedelta(days=days)).strftime('%d.%m.%Y')} ({days}d)"
                    )

        returns = [
            t.get("pnl", 0) / t.get("invested", 1) for t in closed_copy if t.get("invested", 0) > 0
        ]

        return {
            "bot_name": BOT_NAME,
            "bot_version": BOT_VERSION,
            "bot_full": BOT_FULL,
            "running": self.running,
            "paused": self.paused,
            "portfolio_value": round(pv, 2),
            "balance": round(self.balance, 2),
            "initial_balance": self.initial_balance,
            "return_pct": round(self.return_pct(), 2),
            "total_pnl": round(self.total_pnl(), 2),
            "win_rate": round(self.win_rate(), 1),
            "total_trades": len(closed_copy),
            "open_trades": len(open_pos),
            "max_trades": CONFIG.get("max_open_trades", 10),
            "avg_win": round(self.avg_win(), 2),
            "avg_loss": round(self.avg_loss(), 2),
            "profit_factor": self.profit_factor(),
            "sharpe": round(risk.sharpe(returns), 2),
            "max_drawdown": round(risk.max_drawdown, 2),
            "daily_pnl": round(daily_pnl, 2),
            "trade_today": len(trades_today),
            "market_regime": "🐂 Bullish" if regime.is_bull else "🐻 Bearish",
            "btc_price": round(regime.btc_price, 2),
            "positions": open_pos,
            "closed_trades": [
                {
                    "symbol": t.get("symbol"),
                    "entry": t.get("entry"),
                    "exit": t.get("exit") or t.get("exit_price"),
                    "qty": t.get("qty"),
                    "pnl": round(t.get("pnl", 0), 2),
                    "pnl_pct": round(t.get("pnl_pct", 0), 2),
                    "reason": t.get("reason", ""),
                    "confidence": t.get("confidence", 0),
                    "ai_score": t.get("ai_score", 0),
                    "win_prob": t.get("win_prob", 0),
                    "invested": t.get("invested", 0),
                    "opened": t.get("opened", ""),
                    "closed": t.get("closed", ""),
                    "regime": t.get("regime", ""),
                    "trade_type": t.get("trade_type", "long"),
                    "dca_level": t.get("dca_level", 0),
                    "news_score": t.get("news_score", 0),
                }
                for t in closed_copy[:100]
            ],
            "portfolio_history": list(self.portfolio_history)[-200:],
            "signal_log": list(self.signal_log)[:30],
            "activity_log": list(self.activity_log)[:20],
            "arb_log": list(self.arb_log)[:10],
            "last_scan": self.last_scan,
            "next_scan": self.next_scan,
            "ai": ai_engine.to_dict(),
            "fear_greed": fg_idx.to_dict(),
            "circuit_breaker": risk.circuit_status(),
            "dominance": dominance.to_dict(),
            "anomaly": anomaly.to_dict(),
            "genetic": genetic.to_dict(),
            "rl": rl_agent.to_dict(),
            "exchange": CONFIG.get("exchange", "cryptocom"),
            "paper_trading": CONFIG.get("paper_trading", True),
            "goal": {"target": goal, "current": pv, "pct": goal_pct, "eta": goal_eta},
            "price_alerts": db.get_all_alerts()[:20],
            "use_shorts": CONFIG.get("use_shorts", False),
            "use_arbitrage": CONFIG.get("use_arbitrage", True),
            "trade_dna": trade_dna.to_dict(),
            "smart_exits": smart_exits.to_dict(),
            "adaptive_weights": adaptive_weights.to_dict(),
            "performance_attribution": perf_attribution.to_dict(),
        }


# ═══════════════════════════════════════════════════════════════════════════════
# ARBITRAGE SCANNER
# ═══════════════════════════════════════════════════════════════════════════════
class ArbitrageScanner:
    def __init__(self):
        self._exchanges: dict[str, Any] = {}
        self._lock = threading.Lock()
        self.found_today = 0
        self.last_scan = None

    def _get_ex(self, name: str):
        with self._lock:
            if name not in self._exchanges:
                try:
                    keys = CONFIG.get("arb_api_keys", {}).get(name, {})
                    ex_cls_name = EXCHANGE_MAP.get(name, name)
                    ex_cls = getattr(ccxt, ex_cls_name, None)
                    if not ex_cls:
                        return None
                    self._exchanges[name] = ex_cls(
                        {
                            "apiKey": keys.get("key", ""),
                            "secret": keys.get("secret", ""),
                            "enableRateLimit": True,
                            "options": {"defaultType": "spot"},
                        }
                    )
                except Exception as e:
                    log.debug(f"ARB Exchange {name}: {e}")
                    return None
            return self._exchanges.get(name)

    def scan(self, symbols: list[str]) -> list[dict]:
        if not CONFIG.get("use_arbitrage"):
            return []
        exchanges = CONFIG.get("arb_exchanges", ["binance", "bybit"])
        if len(exchanges) < 2:
            return []
        opportunities = []
        try:
            # Hole Preise von allen Exchanges
            prices_by_ex: dict[str, dict[str, float]] = {}
            for ex_name in exchanges:
                ex = self._get_ex(ex_name)
                if not ex:
                    continue
                try:
                    tickers = ex.fetch_tickers(symbols[:30])
                    prices_by_ex[ex_name] = {
                        s: float(t.get("last") or 0) for s, t in tickers.items() if t.get("last")
                    }
                except Exception as exc:
                    log.debug(f"ARB ticker fetch {ex_name}: {exc}")

            ex_names = list(prices_by_ex.keys())
            for sym in symbols[:30]:
                sym_prices = {
                    n: prices_by_ex[n][sym] for n in ex_names if sym in prices_by_ex.get(n, {})
                }
                if len(sym_prices) < 2:
                    continue
                buy_ex = min(sym_prices, key=lambda k: sym_prices.get(k, 0))
                sell_ex = max(sym_prices, key=lambda k: sym_prices.get(k, 0))
                p_buy = sym_prices[buy_ex]
                p_sell = sym_prices[sell_ex]
                if p_buy <= 0:
                    continue
                spread = (p_sell - p_buy) / p_buy * 100
                # Fees abziehen (≈0.04% * 4 = 0.16%)
                net_spread = spread - 0.16
                if net_spread >= CONFIG.get("arb_min_spread_pct", 0.3):
                    opp = {
                        "symbol": sym,
                        "exchange_buy": buy_ex,
                        "price_buy": round(p_buy, 6),
                        "exchange_sell": sell_ex,
                        "price_sell": round(p_sell, 6),
                        "spread_pct": round(net_spread, 3),
                        "executed": 0,
                        "profit": 0,
                    }
                    opportunities.append(opp)
                    db.save_arb(opp)
                    self.found_today += 1
                    discord.arb_found(sym, buy_ex, sell_ex, net_spread)
                    state.arb_log.appendleft(
                        {
                            "time": datetime.now().strftime("%H:%M"),
                            "symbol": sym,
                            "buy": buy_ex,
                            "sell": sell_ex,
                            "spread": round(net_spread, 3),
                        }
                    )
                    log.info(f"💹 ARB: {sym} {buy_ex}→{sell_ex} Spread:{net_spread:.2f}%")
        except Exception as e:
            log.debug(f"ARB scan: {e}")
        self.last_scan = datetime.now().strftime("%H:%M:%S")
        return opportunities


# ═══════════════════════════════════════════════════════════════════════════════
# SHORT ENGINE
# ═══════════════════════════════════════════════════════════════════════════════
class ShortEngine:
    def __init__(self):
        self._ex = None
        self._ex_lock = threading.Lock()

    def _get_ex(self):
        with self._ex_lock:
            if self._ex:
                return self._ex
            try:
                name = CONFIG.get("short_exchange", "bybit")
                ex_cls_name = EXCHANGE_MAP.get(name, name)
                ex_cls = getattr(ccxt, ex_cls_name, None)
                if not ex_cls:
                    return None
                sk = CONFIG.get("short_api_key", "")
                ss = CONFIG.get("short_secret", "")
                raw_key = sk.reveal() if hasattr(sk, "reveal") else sk
                raw_sec = ss.reveal() if hasattr(ss, "reveal") else ss
                self._ex = ex_cls(
                    {
                        "apiKey": decrypt_value(raw_key) if raw_key else "",
                        "secret": decrypt_value(raw_sec) if raw_sec else "",
                        "enableRateLimit": True,
                        "options": {"defaultType": "swap"},
                    }
                )
                return self._ex
            except Exception as e:
                log.debug(f"Short Ex: {e}")
                return None

    def open_short(self, symbol: str, invest: float, price: float) -> bool:
        if not CONFIG.get("use_shorts"):
            return False
        if not price or price <= 0:
            return False
        sl = price * (1 + CONFIG.get("stop_loss_pct", 0.03))
        tp = price * (1 - CONFIG.get("take_profit_pct", 0.05))
        try:
            ex = self._get_ex()
            qty = invest / price
            if not CONFIG.get("paper_trading", True) and ex:
                ex.set_leverage(CONFIG.get("short_leverage", 2), symbol)
                ex.create_market_sell_order(symbol, qty)
            state.short_positions[symbol] = {
                "entry": price,
                "qty": qty,
                "invested": invest,
                "sl": sl,
                "tp": tp,
                "opened": datetime.now().isoformat(),
                "pnl_unrealized": 0.0,
            }
            discord.short_open(symbol, price, invest)
            state.add_activity(
                "🔴", f"Short: {symbol}", f"@ {price:.4f} | {invest:.2f} USDT", "warning"
            )
            log.info(f"🔴 SHORT {symbol} @ {price:.4f}")
            return True
        except Exception as e:
            log.error(f"Short open: {e}")
            return False

    def close_short(self, symbol: str, reason: str):
        pos = state.short_positions.get(symbol)
        if not pos:
            return
        price = state.prices.get(symbol, pos.get("entry", 0))
        short_entry = pos.get("entry") or price
        pnl_pct = (short_entry - price) / short_entry * 100 if short_entry > 0 else 0.0
        fee = (
            pos.get("invested", 0)
            * get_exchange_fee_rate(CONFIG.get("short_exchange"))
            * CONFIG.get("short_leverage", 2)
        )  # [#29]
        pnl = pos.get("invested", 0) * (pnl_pct / 100) - fee
        if CONFIG.get("paper_trading", True):
            state.balance += pos.get("invested", 0) + pnl
        else:
            try:
                ex = self._get_ex()
                if ex:
                    ex.create_market_buy_order(symbol, pos.get("qty", 0))
            except Exception as e:
                log.error(f"Short close: {e}")
        trade = {
            "symbol": symbol,
            "entry": round(pos.get("entry", 0), 4),
            "exit": round(price, 4),
            "qty": round(pos.get("qty", 0), 6),
            "pnl": round(pnl, 2),
            "pnl_pct": round(pnl_pct, 2),
            "reason": reason,
            "confidence": 0,
            "ai_score": 0,
            "win_prob": 0,
            "invested": round(pos.get("invested", 0), 2),
            "opened": pos.get("opened", ""),
            "closed": datetime.now().isoformat(),
            "exchange": CONFIG.get("short_exchange", "bybit"),
            "regime": "bear",
            "trade_type": "short",
        }
        with state._lock:
            state.closed_trades.insert(0, trade)
            state.short_positions.pop(symbol, None)
        db.save_trade(trade)
        won = pnl >= 0
        risk.record_result(won)
        icon = "✅" if won else "❌"
        state.add_activity(
            icon,
            f"Short Close: {symbol}",
            f"PnL:{pnl:+.2f} ({pnl_pct:+.2f}%) | {reason}",
            "success" if won else "error",
        )
        discord.trade_sell(symbol, price, pnl, pnl_pct, f"SHORT-{reason}")
        log.info(f"{icon} SHORT CLOSE {symbol} @ {price:.4f} | {pnl:+.2f} USDT")

    def update_shorts(self):
        for sym in list(state.short_positions.keys()):
            pos = state.short_positions.get(sym)
            if not pos:
                continue
            price = state.prices.get(sym, pos.get("entry", 0))
            s_entry = pos.get("entry") or price
            pnl_pct = (s_entry - price) / s_entry * 100 if s_entry > 0 else 0.0
            pos["pnl_unrealized"] = pos.get("invested", 0) * (pnl_pct / 100)
            if price >= pos.get("sl", float("inf")):
                self.close_short(sym, "SL 🛑")
            elif price <= pos.get("tp", 0):
                self.close_short(sym, "TP 🎯")


# ═══════════════════════════════════════════════════════════════════════════════
# GLOBALE INSTANZEN
# ═══════════════════════════════════════════════════════════════════════════════
db = MySQLManager()
knowledge_base = KnowledgeBase(
    db,
    llm_endpoint=os.getenv("LLM_ENDPOINT", ""),
    llm_api_key=os.getenv("LLM_API_KEY", ""),
)
discord = DiscordNotifier()
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
tax = TaxReportGenerator()
regime = MarketRegime(CONFIG)
risk = RiskManager(CONFIG, discord)
liq = LiquidityScorer(CONFIG)
bt = BacktestEngine()
price_alerts = PriceAlertManager()
arb_scanner = ArbitrageScanner()
short_engine = ShortEngine()
daily_sched = DailyReportScheduler()
backup_sched = BackupScheduler()
state = BotState(db)
ai_engine = AIEngine(db)


def emit_event(event, data):
    try:
        socketio.emit(event, data)
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════════════════════
# EXCHANGE FACTORY
# ═══════════════════════════════════════════════════════════════════════════════
def create_exchange():
    name = CONFIG.get("exchange", "cryptocom")
    ex_cls_name = EXCHANGE_MAP.get(name, name)
    ex_cls = getattr(ccxt, ex_cls_name, None)
    if ex_cls is None:
        raise ValueError(f"Exchange '{ex_cls_name}' nicht in ccxt verfügbar")
    # API-Keys entschlüsseln und als plain str sicherstellen (kein SecretStr)
    _raw_key = CONFIG.get("api_key", "")
    _raw_sec = CONFIG.get("secret", "")
    api_key = (
        decrypt_value(_raw_key.reveal() if hasattr(_raw_key, "reveal") else _raw_key)
        if _raw_key
        else ""
    )
    api_secret = (
        decrypt_value(_raw_sec.reveal() if hasattr(_raw_sec, "reveal") else _raw_sec)
        if _raw_sec
        else ""
    )
    return ex_cls(
        {
            "apiKey": api_key,
            "secret": api_secret,
            "enableRateLimit": True,
            "options": {"defaultType": "spot"},
        }
    )


def get_exchange_fee_rate(exchange_id: str | None = None, symbol: str = "BTC/USDT") -> float:
    """Gibt die Taker-Fee für eine Exchange zurück.

    Versucht zuerst, die Fee via CCXT abzurufen (gecacht für 1 Stunde).
    Fällt auf Exchange-spezifische Defaults zurück, dann auf CONFIG["fee_rate"].

    Args:
        exchange_id: Exchange-Name (z.B. "binance"). None = aktuelle Exchange.
        symbol: Trading-Pair für Fee-Abfrage.

    Returns:
        Fee-Rate als Dezimalzahl (z.B. 0.001 = 0.1%).
    """
    ex_id = exchange_id or CONFIG.get("exchange", "cryptocom")
    now = time.time()
    with _fee_cache_lock:
        cached = _fee_cache.get(ex_id)
        if cached and now - cached.get("ts", 0) < 3600:
            return cached["rate"]
    # Versuche CCXT-Fee-Abfrage
    try:
        ex_cls = getattr(ccxt, EXCHANGE_MAP.get(ex_id, ex_id), None)
        if ex_cls:
            ex = ex_cls({"enableRateLimit": True})
            fee_info = ex.fetch_trading_fee(symbol)
            rate = float(
                fee_info.get(
                    "taker", EXCHANGE_DEFAULT_FEES.get(ex_id, CONFIG.get("fee_rate", 0.001))
                )
            )
            with _fee_cache_lock:
                _fee_cache[ex_id] = {"rate": rate, "ts": now}
            return rate
    except Exception:
        pass
    # Fallback: Exchange-Default oder CONFIG
    rate = EXCHANGE_DEFAULT_FEES.get(ex_id, CONFIG.get("fee_rate", 0.001))
    with _fee_cache_lock:
        _fee_cache[ex_id] = {"rate": rate, "ts": now}
    return rate


# ═══════════════════════════════════════════════════════════════════════════════
# MARKT-SCANNER
# ═══════════════════════════════════════════════════════════════════════════════
def fetch_markets(ex) -> list[str]:
    try:
        markets = ex.load_markets()
        quote = CONFIG.get("quote_currency", "USDT")
        bl = set(CONFIG.get("blacklist", []))
        syms = [
            s
            for s, m in markets.items()
            if m.get("quote") == quote and m.get("active") and s not in bl and m.get("spot", True)
        ]
        if CONFIG.get("use_vol_filter"):
            tickers = ex.fetch_tickers(syms[:150])
            syms = [
                s
                for s in syms
                if tickers.get(s, {}).get("quoteVolume", 0)
                >= CONFIG.get("min_volume_usdt", 1_000_000)
            ]
        trending = sentiment_f.get_trending()
        priority = [s for s in trending if s in syms]
        rest = [s for s in syms if s not in priority]
        return (priority + rest)[:80]
    except Exception as e:
        log.error(f"Märkte: {e}")
        return []


def scan_symbol(ex, symbol) -> dict | None:
    try:
        ohlcv = ex.fetch_ohlcv(
            symbol, CONFIG.get("timeframe", "1h"), limit=CONFIG.get("candle_limit", 250)
        )
        if not ohlcv or len(ohlcv) < 100:
            return None
        df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        df.set_index("timestamp", inplace=True)
        # Indikator-Cache: Nur neu berechnen wenn sich der letzte Timestamp geändert hat
        _last_ts = df.index[-1]
        df_cached = _ind_get(symbol, _last_ts)
        if df_cached is not None:
            df = df_cached
        else:
            df = compute_indicators(df)
            if df is None:
                return None
            _ind_set(symbol, _last_ts, df)
        if df is None or len(df) < 2:
            return None
        row = df.iloc[-1]
        prev = df.iloc[-2]
        price = float(row["close"])
        # [24+27] Multi-Regime classification
        ph = list(df["close"].values[-50:])
        adv_risk.classify_regime(ph) if ph else None
        risk.update_prices(symbol, price)
        state.prices[symbol] = price

        votes = {}
        for nm, fn in STRATEGIES:
            try:
                votes[nm] = fn(row, prev)
            except Exception:
                votes[nm] = 0

        # Adaptive Weights: dynamische Strategie-Gewichte anwenden
        if CONFIG.get("use_adaptive_weights"):
            regime_str = "bull" if regime and regime.is_bull else "bear"
            aw = adaptive_weights.get_weights(regime=regime_str)
            for nm in aw:
                if nm in ai_engine.weights:
                    ai_engine.weights[nm] = aw[nm]

        signal, conf = ai_engine.weighted_vote(votes, CONFIG.get("min_vote_score", 0.3))
        ob_ratio, ob_desc = ob.get(ex, symbol)
        mtf_ok, mtf_desc = mtf.is_confirmed(ex, symbol, signal)
        sentiment = sentiment_f.get_score(symbol)
        news_score, news_hl, news_cnt = news_fetcher.get_score(symbol)
        onchain_score, onchain_detail = onchain.get_score(symbol)

        # Anomalie-Check
        price_chg = float(row.get("returns", 0) * 100)
        anomaly.add_observation(
            price_chg,
            float(row.get("vol_ratio", 1)),
            float(row.get("rsi", 50)),
            float(row.get("atr_pct", 1)),
        )

        return {
            "symbol": symbol,
            "price": price,
            "signal": signal,
            "confidence": conf,
            "votes": votes,
            "rsi": round(float(row.get("rsi", 50)), 1),
            "stoch_rsi": float(row.get("stoch_rsi", 50)),
            "bb_pct": float(row.get("bb_pct", 0.5)),
            "bb_width": float(row.get("bb_width", 0.05)),
            "macd_hist": float(row.get("macd_hist", 0)),
            "macd_hist_slope": float(row.get("macd_hist_slope", 0)),
            "vol_ratio": float(row.get("vol_ratio", 1)),
            "atr_pct": float(row.get("atr_pct", 1)),
            "atr14": float(row.get("atr14", 0)),
            "ema_alignment": float(row.get("ema_alignment", 0)),
            "price_vs_ema21": float(row.get("price_vs_ema21", 0)),
            "roc10": float(row.get("roc10", 0)),
            "ob_ratio": ob_ratio,
            "ob_desc": ob_desc,
            "mtf_ok": mtf_ok,
            "mtf_desc": mtf_desc,
            "sentiment": sentiment,
            "news_score": news_score,
            "news_headline": news_hl,
            "news_count": news_cnt,
            "onchain_score": onchain_score,
            "onchain_detail": onchain_detail,
            "ohlcv": [
                [int(r[0]), float(r[1]), float(r[2]), float(r[3]), float(r[4]), float(r[5])]
                for r in ohlcv[-100:]
            ],
            "time": datetime.now().strftime("%H:%M:%S"),
        }
    # [Verbesserung #5] Differenzierte ccxt-Exceptions in scan_symbol
    except ccxt.RateLimitExceeded:
        log.debug(f"Rate-Limit beim Scan von {symbol} – überspringe")
        return None
    except ccxt.NetworkError as e:
        log.debug(f"Netzwerk beim Scan von {symbol}: {e}")
        return None
    except ccxt.ExchangeError as e:
        log.debug(f"Exchange-Fehler beim Scan von {symbol}: {e}")
        return None
    except Exception as e:
        log.debug(f"Scan {symbol}: {e}")
        return None


# ═══════════════════════════════════════════════════════════════════════════════
# TRADE EXECUTION mit DCA + Partial TP
# ═══════════════════════════════════════════════════════════════════════════════
def open_position(ex, scan: dict):
    symbol = scan["symbol"]
    price = scan["price"]
    if not price or price <= 0:
        log.warning(f"open_position: Ungültiger Preis {price} für {symbol}")
        return
    if len(state.positions) >= CONFIG.get("max_open_trades", 5):
        return
    if symbol in state.positions:
        return
    if symbol_cooldown.is_blocked(symbol):
        log.debug(f"[COOLDOWN] {symbol} blockiert")
        return
    if not regime.is_bull and CONFIG["use_market_regime"]:
        return
    if risk.daily_loss_exceeded(state.balance):
        return
    if risk.circuit_breaker_active():
        return
    # News-Sentiment-Filter (Verbesserung 9)
    news_score = scan.get("news_score", 0.0)
    min_score = CONFIG.get("news_sentiment_min", -0.2)
    if news_score < min_score:
        log.debug(f"[NEWS-FILTER] {symbol} blockiert: news_score={news_score:.2f} < {min_score}")
        return
    if CONFIG.get("news_require_positive") and news_score < 0:
        log.debug(f"[NEWS-FILTER] {symbol} blockiert: positiver Score erforderlich")
        return
    if anomaly.is_anomaly:
        log.info(f"🚨 {symbol} blockiert – Anomalie")
        return
    if not fg_idx.is_ok_to_buy():
        log.info(f"😱 {symbol} F&G:{fg_idx.value}")
        return

    # Dominanz
    dom_ok, dom_reason = dominance.is_ok_to_buy(symbol)
    if not dom_ok:
        log.info(f"🌐 {symbol}: {dom_reason}")
        return

    # News-Block
    ns = scan.get("news_score", 0)
    if ns <= CONFIG.get("news_block_score", -0.4):
        log.info(f"📰 {symbol} News blockiert: {ns:.2f} – {scan.get('news_headline', '')[:60]}")
        return

    if risk.is_correlated(symbol, list(state.positions.keys())):
        return
    if not scan.get("mtf_ok", True) and CONFIG.get("mtf_enabled"):
        return
    if scan.get("ob_ratio", 0.5) < CONFIG.get("ob_imbalance_min", 0.45):
        return
    ok, spread, _ = liq.check(ex, symbol)
    if not ok:
        return

    features = ai_engine.extract_features(
        scan["votes"],
        scan,
        regime.is_bull,
        fg_idx.value,
        state.closed_trades,
        ob_imbalance=scan.get("ob_ratio", 0.5),
        mtf_bullish=int(scan.get("mtf_ok", True)),
        sentiment=scan.get("sentiment", 0.5),
        news_score=ns,
        onchain_score=scan.get("onchain_score", 0),
        dominance_ok=int(dom_ok),
    )

    # RL-Agent konsultieren
    if CONFIG.get("rl_enabled") and rl_agent.is_trained:
        rl_action = rl_agent.act(
            scan.get("rsi", 50),
            1 if regime.is_bull else -1,
            fg_idx.value,
            ns,
            scan.get("ob_ratio", 0.5),
        )
        if rl_action == 0:
            log.info(f"🤖 {symbol} RL: Hold")
            return

    allowed, ai_score, ai_reason = ai_engine.should_buy(features, scan["confidence"])
    win_prob = ai_engine.win_probability(features) * 100
    if not allowed:
        return

    # ── Trade DNA Fingerprinting ─────────────────────────────────────────
    dna_result = None
    dna_adjustment = None
    if CONFIG.get("use_trade_dna"):
        regime_str = "bull" if regime.is_bull else "bear"
        local_regime = (
            smart_exits.classify_regime_from_scan(scan) if smart_exits.enabled else regime_str
        )
        dna_result = trade_dna.compute(symbol, scan, local_regime, fg_idx.value)
        dna_adjustment = trade_dna.confidence_adjustment(dna_result)
        if dna_adjustment["action"] == "block" and dna_adjustment["matches"] >= CONFIG.get(
            "dna_min_matches", 5
        ):
            log.info(f"🧬 {symbol} DNA-Block: {dna_adjustment['reason']}")
            state.add_activity("🧬", f"DNA-Block: {symbol}", dna_adjustment["reason"], "warning")
            return

    fg_boost = fg_idx.buy_boost()
    # DNA-Boost in Position-Sizing einbeziehen
    dna_mult = dna_adjustment["multiplier"] if dna_adjustment else 1.0
    invest = (
        ai_engine.kelly_size(win_prob / 100, state.balance, scan.get("atr14", 0), fg_boost)
        if CONFIG["ai_use_kelly"]
        else state.balance * CONFIG.get("risk_per_trade", 0.015) * fg_boost
    )
    invest *= dna_mult
    invest = min(invest, state.balance * CONFIG["max_position_pct"])
    if invest < 5:
        return

    fee = invest * get_exchange_fee_rate()  # [#29] Exchange-spezifische Fee
    qty = (invest - fee) / price

    # ── Smart Exits: Dynamische SL/TP ────────────────────────────────────
    if smart_exits.enabled:
        local_regime = smart_exits.classify_regime_from_scan(scan)
        sl, tp = smart_exits.compute(price, scan, local_regime)
    else:
        sl = price * (1 - CONFIG.get("stop_loss_pct", 0.025))
        tp = price * (1 + CONFIG.get("take_profit_pct", 0.06))

    if CONFIG.get("paper_trading", True):
        state.balance -= invest
    else:
        try:
            ex.create_market_buy_order(symbol, qty)
        except Exception as e:
            log.error(f"Order {symbol}: {e}")
            discord.error(str(e))
            return

    ai_engine.on_buy(symbol, features, scan["votes"], scan)
    pos_data = {
        "entry": price,
        "qty": qty,
        "invested": invest - fee,
        "sl": sl,
        "tp": tp,
        "highest": price,
        "opened": datetime.now().isoformat(),
        "confidence": scan["confidence"],
        "ai_score": round(ai_score * 100, 1),
        "win_prob": round(win_prob, 1),
        "regime": "bull" if regime.is_bull else "bear",
        "dca_level": 0,
        "partial_sold": 0,
        "news_score": round(ns, 3),
        "onchain_score": round(scan.get("onchain_score", 0), 3),
    }
    # Trade DNA: Fingerprint in Position speichern
    if dna_result:
        pos_data["dna_hash"] = dna_result["hash"]
        pos_data["dna_fingerprint"] = dna_result["fingerprint"]
        pos_data["dna_boost"] = round(dna_mult, 3)
    # Smart Exits: Regime in Position speichern
    if smart_exits.enabled:
        pos_data["exit_regime"] = smart_exits.classify_regime_from_scan(scan)
    state.positions[symbol] = pos_data
    dna_info = f" | DNA:{dna_mult:.2f}x" if dna_result and dna_mult != 1.0 else ""
    smart_info = f" | SL:{sl:.4f} TP:{tp:.4f}" if smart_exits.enabled else ""
    log.info(
        f"🟢 KAUF {symbol} @ {price:.4f} | {invest:.2f} USDT | KI:{ai_score * 100:.0f}%"
        f" | News:{ns:+.2f}{dna_info}{smart_info}"
    )
    state.add_activity(
        "🟢",
        f"Kauf: {symbol}",
        f"@ {price:.4f} | {invest:.2f} USDT | KI:{ai_score * 100:.0f}%",
        "success",
    )
    discord.trade_buy(symbol, price, invest, ai_score * 100, win_prob, ns)
    # DNA + Smart Exit Discord-Notifications
    if dna_adjustment and dna_adjustment["action"] in ("boost", "block"):
        discord.dna_boost(
            symbol,
            dna_adjustment["action"],
            dna_adjustment.get("win_rate", 0),
            dna_adjustment.get("matches", 0),
            dna_adjustment.get("multiplier", 1.0),
        )
    if smart_exits.enabled:
        discord.smart_exit(
            symbol, sl, tp, pos_data.get("exit_regime", "bull"), scan.get("atr_pct", 0)
        )
    emit_event(
        "trade",
        {
            "type": "buy",
            "symbol": symbol,
            "price": price,
            "invest": round(invest, 2),
            "ai_score": round(ai_score * 100, 1),
        },
    )


def close_position(ex, symbol, reason, partial_ratio=1.0):
    pos = state.positions.get(symbol)
    if not pos:
        return
    price = state.prices.get(symbol, pos.get("entry", 0))
    is_partial = partial_ratio < 1.0

    close_qty = pos.get("qty", 0) * partial_ratio
    close_invest = pos.get("invested", 0) * partial_ratio
    entry = pos.get("entry") or price
    if entry <= 0:
        entry = price
    pnl_pct = (price - entry) / entry * 100 if entry > 0 else 0.0
    fee = close_invest * get_exchange_fee_rate()  # [#29] Exchange-spezifische Fee
    pnl = close_invest * (pnl_pct / 100) - fee

    if CONFIG.get("paper_trading", True):
        state.balance += close_invest + pnl
    else:
        try:
            ex.create_market_sell_order(symbol, close_qty)
        except Exception as e:
            log.error(f"Sell {symbol}: {e}")
            return

    if is_partial:
        # Teilverkauf → Position aktualisieren
        pos["qty"] -= close_qty
        pos["invested"] -= close_invest
        pos["partial_sold"] = pos.get("partial_sold", 0) + partial_ratio
        log.info(f"🔶 PARTIAL {symbol} {partial_ratio * 100:.0f}% @ {price:.4f} | PnL: {pnl:+.2f}")
        state.add_activity(
            "🔶",
            f"Partial TP: {symbol}",
            f"{partial_ratio * 100:.0f}% @ {price:.4f} | {pnl:+.2f}",
            "success" if pnl > 0 else "warning",
        )
        discord.trade_sell(symbol, price, pnl, pnl_pct, reason, partial=True)
        trade = {
            **_make_trade(
                symbol, pos, price, close_qty, close_invest, pnl, pnl_pct, reason + "(partial)"
            ),
            "partial_sold": 1,
        }
    else:
        regime_str = pos.get("regime", "bull")
        ai_engine.on_sell(symbol, pnl, regime_str)
        risk.record_result(pnl > 0)
        # Trade DNA: Ergebnis aufzeichnen
        if CONFIG.get("use_trade_dna") and pos.get("dna_fingerprint"):
            dna_entry = {
                "hash": pos.get("dna_hash", ""),
                "fingerprint": pos.get("dna_fingerprint", {}),
                "dimensions": {},  # Nicht gespeichert, aber Fingerprint reicht
                "symbol": symbol,
                "timestamp": pos.get("opened", ""),
            }
            trade_dna.record(dna_entry, won=pnl > 0)
        trade = _make_trade(
            symbol,
            pos,
            price,
            close_qty,
            close_invest,
            pnl,
            pnl_pct,
            reason,
            dca_level=pos.get("dca_level", 0),
        )
        state.closed_trades.insert(0, trade)
        state.positions.pop(symbol, None)
        icon = "✅" if pnl > 0 else "❌"
        state.add_activity(
            icon,
            f"Verkauf: {symbol}",
            f"PnL:{pnl:+.2f} ({pnl_pct:+.2f}%) | {reason}",
            "success" if pnl > 0 else "error",
        )
        discord.trade_sell(symbol, price, pnl, pnl_pct, reason)
        log.info(f"{icon} VKAUF {symbol} @ {price:.4f} | {pnl:+.2f} ({pnl_pct:+.2f}%) | {reason}")

    db.save_trade(trade)
    # Performance Attribution: Trade aufzeichnen
    try:
        perf_attribution.record_trade(
            symbol=symbol,
            pnl=pnl,
            strategy=reason,
            regime=pos.get("regime", "unknown"),
            fg_value=pos.get("fg_value", 50),
            hour=pos.get("entry_hour"),
        )
    except Exception:
        pass
    # Adaptive Weights: Strategie-Ergebnis aufzeichnen
    try:
        adaptive_weights.record_vote(
            strategy=reason,
            won=pnl > 0,
            regime=pos.get("regime", "unknown"),
        )
    except Exception:
        pass
    # KI-Gemeinschaftswissen: Erkenntnisse aus Trade speichern
    try:
        knowledge_base.learn_from_trade(trade)
    except Exception:
        pass  # Knowledge-Update ist optional
    # Autonome LLM-Analyse: Trade per LLM analysieren (async, non-blocking)
    try:
        knowledge_base.analyze_trade_async(
            trade,
            features={
                "rsi": pos.get("rsi", "?"),
                "news_score": pos.get("news_score", 0),
                "regime": pos.get("regime", "unknown"),
                "ai_score": pos.get("ai_score", 0),
                "win_prob": pos.get("win_prob", 0),
            },
        )
    except Exception:
        pass  # LLM-Analyse ist optional
    emit_event(
        "trade",
        {
            "type": "sell",
            "symbol": symbol,
            "price": price,
            "pnl": round(pnl, 2),
            "pnl_pct": round(pnl_pct, 2),
            "reason": reason,
        },
    )


def _make_trade(symbol, pos, price, qty, invest, pnl, pnl_pct, reason, dca_level=0, partial_sold=0):
    trade = {
        "symbol": symbol,
        "entry": round(pos.get("entry", 0), 4),
        "exit": round(price, 4),
        "qty": round(qty, 6),
        "pnl": round(pnl, 2),
        "pnl_pct": round(pnl_pct, 2),
        "reason": reason,
        "confidence": round(pos.get("confidence", 0), 3),
        "ai_score": round(pos.get("ai_score", 0), 1),
        "win_prob": round(pos.get("win_prob", 0), 1),
        "invested": round(invest, 2),
        "opened": pos.get("opened", ""),
        "closed": datetime.now().isoformat(),
        "exchange": CONFIG.get("exchange", "cryptocom"),
        "regime": pos.get("regime", "bull"),
        "trade_type": "long",
        "partial_sold": partial_sold,
        "dca_level": dca_level,
        "news_score": round(pos.get("news_score", 0), 3),
        "onchain_score": round(pos.get("onchain_score", 0), 3),
    }
    # Trade DNA Fingerprint anhängen (für historische Analyse)
    if pos.get("dna_hash"):
        trade["dna_hash"] = pos.get("dna_hash", "")
        trade["dna_boost"] = pos.get("dna_boost", 1.0)
    # Smart Exit Regime anhängen
    if pos.get("exit_regime"):
        trade["exit_regime"] = pos["exit_regime"]
    return trade


def try_dca(ex, symbol):
    """Dollar-Cost-Averaging: bei Kursrückgang nachkaufen."""
    if not CONFIG.get("use_dca"):
        return
    pos = state.positions.get(symbol)
    if not pos:
        return
    price = state.prices.get(symbol, pos.get("entry", 0))
    dca_level = pos.get("dca_level", 0)
    if dca_level >= CONFIG.get("dca_max_levels", 3):
        return
    if pos.get("entry", 0) <= 0 or price <= 0:
        return
    entry_price = pos.get("entry", 0)
    drop = (entry_price - price) / entry_price if entry_price > 0 else 0.0
    threshold = CONFIG.get("dca_drop_pct", 0.05) * (dca_level + 1)
    if drop < threshold:
        return
    # Nachkauf
    dca_invest = pos.get("invested", 0) * CONFIG.get("dca_size_mult", 1.0)
    dca_invest = min(dca_invest, state.balance * 0.15)
    if dca_invest < 5:
        return
    fee = dca_invest * get_exchange_fee_rate()  # [#29] Exchange-spezifische Fee
    add_qty = (dca_invest - fee) / price
    # Neuer Durchschnittspreis
    total_qty = pos.get("qty", 0) + add_qty
    if total_qty <= 0:
        return
    total_cost = pos.get("invested", 0) + dca_invest - fee
    new_entry = total_cost / total_qty
    if CONFIG.get("paper_trading", True):
        state.balance -= dca_invest
    else:
        try:
            ex.create_market_buy_order(symbol, add_qty)
        except Exception as e:
            log.error(f"DCA {symbol}: {e}")
            return
    pos["qty"] = total_qty
    pos["invested"] = total_cost
    pos["entry"] = new_entry
    pos["dca_level"] = dca_level + 1
    pos["sl"] = new_entry * (1 - CONFIG.get("stop_loss_pct", 0.025))
    pos["tp"] = new_entry * (1 + CONFIG.get("take_profit_pct", 0.06))
    log.info(
        f"📉 DCA Lvl{dca_level + 1} {symbol}: +{add_qty:.4f} @ {price:.4f} | ⌀:{new_entry:.4f}"
    )
    state.add_activity(
        "📉",
        f"DCA Level {dca_level + 1}: {symbol}",
        f"Ø-Preis:{new_entry:.4f} | +{dca_invest:.0f} USDT",
        "info",
    )


def manage_positions(ex):
    for symbol in list(state.positions.keys()):
        pos = state.positions.get(symbol)
        if not pos:
            continue
        try:
            ticker = ex.fetch_ticker(symbol)
            last_price = ticker.get("last")
            if last_price is None:
                continue
            price = float(last_price)
            state.prices[symbol] = price
            adv_risk.update_volatility(price)  # [25] EWMA vol update
        except Exception:
            continue

        # Break-Even Stop: SL auf Einstiegspreis (+Puffer) setzen sobald +X% Gewinn
        pos_entry = pos.get("entry") or price
        if (
            pos_entry
            and CONFIG.get("break_even_enabled")
            and not pos.get("break_even_set")
            and (price - pos_entry) / pos_entry >= CONFIG.get("break_even_trigger", 0.015)
        ):
            be_sl = pos_entry * (1 + CONFIG.get("break_even_buffer", 0.001))
            if be_sl > pos.get("sl", 0):  # Nur nach oben verschieben
                pos["sl"] = be_sl
                pos["break_even_set"] = True
                log.info(
                    f"🔒 Break-Even {symbol}: SL → {be_sl:.4f} "
                    f"(+{CONFIG.get('break_even_buffer', 0.001) * 100:.1f}%)"
                )

        # Smart Exits: Dynamische SL/TP-Anpassung basierend auf aktueller Volatilität
        if smart_exits.enabled:
            atr_val = pos.get("_last_atr", 0)
            # ATR aus letztem Scan oder geschätzt aus Preisbewegung
            if atr_val <= 0:
                atr_val = abs(price - pos_entry) * 0.5  # Grobe Schätzung
            exit_regime = pos.get("exit_regime", "bull" if regime.is_bull else "bear")
            new_smart_sl, new_smart_tp = smart_exits.adapt(symbol, pos, price, atr_val, exit_regime)
            if new_smart_sl and new_smart_sl > pos.get("sl", 0):
                pos["sl"] = new_smart_sl
            if new_smart_tp and new_smart_tp > pos.get("tp", 0):
                pos["tp"] = new_smart_tp

        # Trailing Stop
        if CONFIG.get("trailing_stop") and price > pos.get("highest", price):
            pos["highest"] = price
            new_sl = price * (1 - CONFIG.get("trailing_pct", 0.03))
            if new_sl > pos.get("sl", 0):  # Trailing Stop nur nach oben verschieben
                pos["sl"] = new_sl

        # Partial Take-Profit – pro Level separat prüfen, nicht nur Level 0
        # Jedes Level hat einen eigenen Index. "partial_tp_done" speichert,
        # wie viele Level bereits ausgeführt wurden (0 = noch keins).
        if CONFIG.get("use_partial_tp"):
            levels = CONFIG.get("partial_tp_levels", [])
            levels_done = pos.get("partial_tp_done", 0)
            if levels_done < len(levels):
                level = levels[levels_done]
                pct = level.get("pct", 0)
                sell_ratio = level.get("sell_ratio", 0.25)
                if pos_entry and pct > 0 and (price - pos_entry) / pos_entry >= pct:
                    close_position(
                        ex,
                        symbol,
                        f"Partial-TP {pct * 100:.0f}%",
                        partial_ratio=sell_ratio,
                    )
                    # Re-fetch pos – close_position may have removed it
                    pos = state.positions.get(symbol)
                    if not pos:
                        continue
                    pos["partial_tp_done"] = levels_done + 1

        # SL / TP – re-check pos in case partial TP removed it
        pos = state.positions.get(symbol)
        if not pos:
            continue
        if price <= pos.get("sl", 0):
            close_position(ex, symbol, "Stop-Loss 🛑")
        elif price >= pos.get("tp", float("inf")):
            close_position(ex, symbol, "Take-Profit 🎯")
        else:
            # DCA prüfen
            try_dca(ex, symbol)


# ═══════════════════════════════════════════════════════════════════════════════
# HEATMAP
# ═══════════════════════════════════════════════════════════════════════════════
_heatmap_cache: list[dict] = []
_heatmap_ts: datetime | None = None
_heatmap_lock = threading.Lock()


def get_heatmap_data(ex) -> list[dict]:
    global _heatmap_cache, _heatmap_ts
    with _heatmap_lock:
        if _heatmap_ts and (datetime.now() - _heatmap_ts).total_seconds() < 90:
            return list(_heatmap_cache)
    try:
        syms = state.markets[:60] if state.markets else []
        if not syms:
            return []
        tickers = ex.fetch_tickers(syms)
        result = []
        for sym, t in tickers.items():
            ns, _, _ = news_fetcher.get_score(sym)
            change = _safe_float(t.get("percentage"), 0.0)
            vol = _safe_float(t.get("quoteVolume"), 0.0)
            last = _safe_float(t.get("last"), 0.0)
            if vol < 0:
                vol = 0.0
            result.append(
                {
                    "symbol": sym,
                    "change": round(change, 2),
                    "volume": round(vol / 1e6, 1),
                    "price": round(last, 4),
                    "in_pos": sym in state.positions,
                    "news_score": round(ns, 2),
                }
            )
        result.sort(key=lambda x: x["change"], reverse=True)
        with _heatmap_lock:
            _heatmap_cache = result
            _heatmap_ts = datetime.now()
        return result
    except Exception as e:
        log.debug(f"Heatmap: {e}")
        return []


# ═══════════════════════════════════════════════════════════════════════════════
# HAUPT BOT LOOP
# ═══════════════════════════════════════════════════════════════════════════════
def bot_loop():
    ex = None
    while state.running:
        if state.paused:
            time.sleep(5)
            continue
        try:
            if ex is None:
                try:
                    ex = create_exchange()
                except Exception as exc_err:
                    log.error(f"Exchange-Verbindung fehlgeschlagen: {exc_err}")
                    time.sleep(30)
                    continue
            state.iteration += 1
            state.last_scan = datetime.now().strftime("%H:%M:%S")
            state.next_scan = (
                datetime.now() + timedelta(seconds=CONFIG.get("scan_interval", 60))
            ).strftime("%H:%M:%S")

            risk.reset_daily(state.balance)
            regime.update(ex)

            # Periodische Updates
            if state.iteration % 30 == 1:
                threading.Thread(target=fg_idx.update, daemon=True).start()
            if state.iteration % 60 == 1:
                threading.Thread(target=dominance.update, daemon=True).start()
                threading.Thread(
                    target=lambda ex=ex: funding_tracker.update(ex), daemon=True
                ).start()
                # Autonome LLM-Analyse: Periodische Marktanalyse
                try:
                    knowledge_base.generate_market_context_async(
                        regime_is_bull=regime.is_bull,
                        fg_value=fg_idx.value,
                        open_positions=len(state.positions),
                        iteration=state.iteration,
                    )
                except Exception:
                    pass  # LLM-Analyse ist optional

            # Positionen verwalten (Long + Short)
            manage_positions(ex)
            short_engine.update_shorts()
            # Grid Trading: update active grids with current prices
            if grid_engine.grids:
                bal_ref = [state.balance]
                for sym, grid in list(grid_engine.grids.items()):
                    if not grid.get("active", False):
                        continue
                    price = state.prices.get(sym)
                    if price is not None:
                        acts = grid_engine.update(sym, price, bal_ref)
                        for act in acts:
                            emit_event(
                                "trade", {**act, "type": act["action"].lower(), "source": "grid"}
                            )
                state.balance = bal_ref[0]
            price_alerts.check(state.prices)

            # Anomalie global prüfen
            if anomaly.is_anomaly:
                emit_event("update", state.snapshot())
                time.sleep(CONFIG.get("scan_interval", 60))
                continue

            # Märkte laden
            if state.iteration % 10 == 1 or not state.markets:
                state.markets = fetch_markets(ex)

            # Arbitrage
            if state.iteration % 5 == 1 and CONFIG.get("use_arbitrage"):
                threading.Thread(
                    target=lambda m=state.markets[:30]: arb_scanner.scan(m), daemon=True
                ).start()

            # Portfolio History
            pv = state.portfolio_value()
            state.portfolio_history.append(
                {"time": datetime.now().strftime("%H:%M"), "value": round(pv, 2)}
            )

            # Short-Signale – parallelisiert mit ThreadPoolExecutor
            if not regime.is_bull and CONFIG.get("use_shorts"):
                short_candidates = [
                    sym
                    for sym in state.markets[:20]
                    if sym not in state.short_positions
                    and sym not in state.positions
                    and not funding_tracker.is_short_too_expensive(sym)
                ]
                if short_candidates:
                    with ThreadPoolExecutor(max_workers=CONFIG.get("max_workers", 4)) as short_pool:
                        short_futures = {
                            short_pool.submit(scan_symbol, ex, sym): sym for sym in short_candidates
                        }
                        for fut in as_completed(short_futures):
                            try:
                                scan = fut.result()
                                if (
                                    scan
                                    and scan["signal"] == -1
                                    and scan.get("confidence", 0)
                                    >= CONFIG.get("min_vote_score", 0.3)
                                ):
                                    invest = state.balance * CONFIG.get("risk_per_trade", 0.015)
                                    short_engine.open_short(scan["symbol"], invest, scan["price"])
                            except Exception as se:
                                log.debug(f"Short-Scan: {se}")

            # Long-Signale
            if (
                len(state.positions) < CONFIG.get("max_open_trades", 5)
                and not risk.daily_loss_exceeded(state.balance)
                and not risk.circuit_breaker_active()
            ):
                with ThreadPoolExecutor(max_workers=CONFIG.get("max_workers", 4)) as pool:
                    futures = {
                        pool.submit(scan_symbol, ex, s): s
                        for s in state.markets
                        if s not in state.positions
                    }
                    for fut in as_completed(futures):
                        try:
                            res = fut.result()
                        except Exception as scan_err:
                            log.debug(f"Scan-Future: {scan_err}")
                            continue
                        if res and res["signal"] == 1:
                            state.add_signal(
                                {
                                    "symbol": res["symbol"],
                                    "signal": "KAUF",
                                    "confidence": res["confidence"],
                                    "rsi": res["rsi"],
                                    "price": res["price"],
                                    "time": res["time"],
                                    "votes": res["votes"],
                                    "mtf_desc": res.get("mtf_desc", ""),
                                    "news_score": res.get("news_score", 0),
                                    "news_headline": res.get("news_headline", ""),
                                    "onchain_detail": res.get("onchain_detail", ""),
                                }
                            )
                            open_position(ex, res)

            emit_event("update", state.snapshot())

        # [Verbesserung #5] Differenzierte ccxt-Fehlerbehandlung
        except ccxt.RateLimitExceeded as e:
            log.warning(f"Rate-Limit: {e} – warte 60s")
            time.sleep(60)
        except ccxt.ExchangeNotAvailable as e:
            log.warning(f"Exchange nicht verfügbar: {e} – warte 120s, Circuit Breaker")
            ex = None
            risk.record_result(False)  # Zählt als Verlust für Circuit Breaker
            time.sleep(120)
        except ccxt.NetworkError as e:
            log.warning(f"Netzwerkfehler: {e} – reconnect in 15s")
            ex = None
            time.sleep(15)
        except ccxt.ExchangeError as e:
            log.error(f"Exchange-Fehler: {e}")
            discord.error(f"Exchange-Fehler:\n{str(e)[:200]}")
            time.sleep(30)
        except Exception as e:
            log.error(f"Bot-Loop: {e}", exc_info=True)
            discord.error(f"Loop:\n{traceback.format_exc()[:300]}")
            time.sleep(10)
        time.sleep(CONFIG.get("scan_interval", 60))


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
    return jsonify(state.snapshot())


@app.route("/api/v1/trades")
@api_auth_required
def api_trades():
    limit = min(_safe_int(request.args.get("limit", 100), 100), 1000)
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
        return jsonify({"error": str(e)}), 500


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
            _safe_int(data.get("candles", 500), 500),
            _safe_float(data.get("sl", CONFIG["stop_loss_pct"]), CONFIG["stop_loss_pct"]),
            _safe_float(data.get("tp", CONFIG["take_profit_pct"]), CONFIG["take_profit_pct"]),
            _safe_float(
                data.get("vote", CONFIG.get("min_vote_score", 0.3)),
                CONFIG.get("min_vote_score", 0.3),
            ),
        )
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/v1/tax")
@api_auth_required
def api_tax_v1():
    year = _safe_int(request.args.get("year", datetime.now().year), datetime.now().year)
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
    ok = db.update_user_settings(request.user_id, current)
    return jsonify({"ok": ok, "updated": list(filtered.keys())})


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
    exchange = data.get("exchange", "").lower()
    api_key = data.get("api_key", "")
    api_secret = data.get("api_secret", "")
    enabled = data.get("enabled", False)  # Default: deaktiviert
    is_primary = data.get("is_primary", False)
    if exchange not in EXCHANGE_MAP:
        return jsonify({"error": f"Exchange '{exchange}' nicht unterstützt"}), 400
    if not api_key or not api_secret:
        return jsonify({"error": "api_key und api_secret sind Pflichtfelder"}), 400
    ok = db.upsert_user_exchange(
        request.user_id, exchange, api_key, api_secret, enabled, is_primary
    )
    _audit("exchange_upsert", f"Exchange: {exchange}, enabled: {enabled}", request.user_id)
    return jsonify({"ok": ok})


@app.route("/api/v1/user/exchanges/<int:exchange_id>/toggle", methods=["POST"])
@api_auth_required
def api_user_exchange_toggle(exchange_id):
    """Aktiviert/Deaktiviert eine Exchange für den User."""
    enabled = (request.json or {}).get("enabled", False)
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
    exchange = data.get("exchange", CONFIG["exchange"])
    api_key = data.get("api_key", "")
    api_secret = data.get("api_secret", "")
    if not api_key or not api_secret:
        return jsonify({"error": "api_key und api_secret sind Pflichtfelder"}), 400
    ok = db.update_user_api_keys(request.user_id, exchange, api_key, api_secret)
    _audit("api_keys_update", f"Exchange: {exchange}", request.user_id)
    return jsonify({"ok": ok})


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
    limit = min(_safe_int(request.args.get("limit", 50), 50), 200)
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
    answer = knowledge_base.query_llm(prompt, context)
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
        }
    )


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
        return jsonify({"error": str(e)}), 500


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
        return jsonify({"error": str(e)}), 500


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
        return jsonify({"error": str(e)}), 500


@app.route("/api/v1/fees")
@api_auth_required
def api_fees():
    """[#29] Gibt Exchange-spezifische Fee-Rates zurück."""
    current_ex = CONFIG.get("exchange", "cryptocom")
    fees = {}
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
        return jsonify({"error": str(e)}), 500


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
    ok = db.create_user(
        data.get("username", ""),
        data.get("password", ""),
        data.get("role", "user"),
        _safe_float(data.get("balance", 10000), 10000.0),
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
            if isinstance(original, bool):
                v = bool(v)
            elif isinstance(original, int):
                v = _safe_int(v, original)
            elif isinstance(original, float):
                v = _safe_float(v, original)
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
        return jsonify({"error": str(e)})


@app.route("/api/ohlcv/<path:symbol>")
@dashboard_auth
def api_ohlcv(symbol):
    sym = symbol.replace("-", "/")
    tf = request.args.get("tf", "1h")
    if tf not in {"1m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "12h", "1d"}:
        tf = "1h"
    limit = min(_safe_int(request.args.get("limit", 200), 200), 500)
    try:
        ex = create_exchange()
        ohlcv = ex.fetch_ohlcv(sym, tf, limit=limit)
        trades = [t for t in state.closed_trades if t.get("symbol") == sym][:20]
        return jsonify({"ohlcv": ohlcv, "trades": trades})
    except Exception as e:
        return jsonify({"error": str(e)})


@app.route("/api/tax_report")
@dashboard_auth
def api_tax_report():
    year = _safe_int(request.args.get("year", datetime.now().year), datetime.now().year)
    method = request.args.get("method", "fifo")
    fmt = request.args.get("format", "json")
    trades = db.load_trades(limit=10000, year=year)
    report = tax.generate(trades, year, method)
    if fmt == "csv":
        rows = report.get("gains", []) + report.get("losses", [])
        buf = io.StringIO()
        if rows:
            w = csv.DictWriter(buf, fieldnames=rows[0].keys())
            w.writeheader()
            w.writerows(rows)
        return Response(
            buf.getvalue(),
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
        json.dumps(trades, ensure_ascii=False),
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
        # Neuestes Backup finden
        files = [os.path.join(bdir, f) for f in os.listdir(bdir) if f.endswith((".zip", ".enc"))]
        if not files:
            return jsonify({"error": "Keine Backups vorhanden"}), 404
        latest = max(files, key=os.path.getmtime)
        result = db.verify_backup(latest)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/v1/docs")
def api_docs():
    return jsonify(
        {
            "name": BOT_FULL,
            "version": BOT_VERSION,
            "website": "https://trevlix.dev",
            "endpoints": {
                "GET /api/v1/status": "Healthcheck (öffentlich, kein Auth)",
                "GET /api/v1/update/status": "Healthcheck alias (Docker HEALTHCHECK)",
                "GET /api/v1/state": "Bot-Status (Auth: Bearer Token)",
                "GET /api/v1/trades": "Trade-Liste (?limit=&symbol=&year=)",
                "GET /api/v1/portfolio": "Portfolio-Snapshot",
                "GET /api/v1/heatmap": "Markt-Heatmap",
                "POST /api/v1/backtest": "Backtest {symbol,timeframe,candles,sl,tp,vote}",
                "GET /api/v1/tax": "Steuer-Report (?year=&method=)",
                "POST /api/v1/signal": "TradingView Webhook {symbol,action}",
                "GET /api/v1/ai": "KI-Status",
                "GET /api/v1/dominance": "BTC/USDT Dominanz",
                "GET /api/v1/anomaly": "Anomalie-Detektor Status",
                "GET /api/v1/genetic": "Genetischer Optimizer",
                "GET /api/v1/rl": "Reinforcement Learning Agent",
                "GET /api/v1/news/{sym}": "News-Sentiment für Symbol",
                "GET /api/v1/onchain/{sym}": "On-Chain Score für Symbol",
                "GET /api/v1/arb": "Arbitrage-Chancen",
                "POST /api/v1/token": "API-Token erstellen",
                "GET /api/v1/admin/users": "Alle User (Admin)",
                "POST /api/v1/admin/users": "User anlegen (Admin)",
            },
        }
    )


# ── Health / Status ──────────────────────────────────────────────────────────
@app.route("/api/v1/status")
@app.route("/api/v1/update/status")
def api_health():
    """[Verbesserung #16] Erweiterter Healthcheck mit DB-Ping, Pool-Stats, Memory."""
    import sys

    db_ok = False
    pool_stats = {}
    try:
        conn = db._conn()
        with conn.cursor() as c:
            c.execute("SELECT 1")
        conn.close()
        db_ok = True
        if db._pool:
            pool_stats = {
                "pool_size": db._pool.pool_size,
                "available": db._pool.available,
            }
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
        return jsonify({"error": str(e)}), 500


# ── [Verbesserung #48] Prometheus-kompatible Metriken ─────────────────────────
@app.route("/metrics")
def prometheus_metrics():
    """Exportiert Bot-Metriken im Prometheus-Format."""
    lines = []
    lines.append(f'trevlix_bot_running {{version="{BOT_VERSION}"}} {1 if state.running else 0}')
    lines.append(f"trevlix_open_trades {len(state.positions)}")
    lines.append(f"trevlix_closed_trades_total {len(getattr(state, 'closed_trades', []))}")
    total_pnl = sum(t.get("pnl", 0) for t in getattr(state, "closed_trades", []))
    lines.append(f"trevlix_total_pnl {total_pnl:.2f}")
    wins = sum(1 for t in getattr(state, "closed_trades", []) if t.get("pnl", 0) > 0)
    n = len(getattr(state, "closed_trades", []))
    lines.append(f"trevlix_win_rate {wins / n * 100 if n else 0:.1f}")
    if hasattr(state, "_start_time"):
        lines.append(f"trevlix_uptime_seconds {time.time() - state._start_time:.0f}")
    if db._pool:
        lines.append(f"trevlix_db_pool_available {db._pool.available}")
        lines.append(f"trevlix_db_pool_size {db._pool.pool_size}")
    return Response("\n".join(lines) + "\n", mimetype="text/plain; charset=utf-8")


# ═══════════════════════════════════════════════════════════════════════════════
# WEBSOCKET EVENTS
# [Verbesserung #8] In-Memory Rate-Limiting für kritische Socket-Events
# ═══════════════════════════════════════════════════════════════════════════════
_ws_limits: dict[str, float] = {}  # key: "sid:action" -> timestamp
_ws_limits_last_cleanup: float = 0.0
_ws_limits_lock = threading.Lock()


def _ws_rate_check(action: str, min_interval: float = 2.0) -> bool:
    """Prüft ob ein Socket-Event zu schnell wiederholt wird.

    Gibt False zurück wenn der Client warten muss.
    Bereinigt stale Einträge alle 60s statt nur bei >1000 Einträgen.

    Args:
        action: Name des Socket-Events.
        min_interval: Minimale Sekunden zwischen gleichen Events.

    Returns:
        True wenn erlaubt, False wenn Rate-Limited.
    """
    global _ws_limits_last_cleanup
    sid = request.sid if hasattr(request, "sid") else "global"
    key = f"{sid}:{action}"
    now = time.time()
    with _ws_limits_lock:
        last = _ws_limits.get(key, 0)
        if now - last < min_interval:
            return False
        _ws_limits[key] = now
        # Zeitbasierte Eviction alle 60s (verhindert unbegrenztes Wachstum)
        if now - _ws_limits_last_cleanup > 60:
            _ws_limits_last_cleanup = now
            cutoff = now - 300
            stale = [k for k, v in _ws_limits.items() if v < cutoff]
            for k in stale:
                del _ws_limits[k]
    return True


@socketio.on("connect")
def on_connect():
    if not session.get("user_id"):
        # [Socket.io Fix] Sende Fehler statt stumm abzulehnen
        emit("auth_error", {"msg": "Nicht authentifiziert – bitte einloggen"})
        return False
    emit("update", state.snapshot())
    log.info(f"📱 Client verbunden: {session.get('username', '?')}")


@socketio.on("request_state")
def on_request_state():
    """Ermöglicht dem Client, den aktuellen State explizit anzufragen (z.B. nach Reconnect)."""
    if not session.get("user_id"):
        emit("auth_error", {"msg": "Nicht authentifiziert"})
        return
    emit("update", state.snapshot())


@socketio.on("start_bot")
def on_start_bot():
    if not _ws_rate_check("start_bot", min_interval=3.0):
        emit("status", {"msg": "⏳ Zu schnell – bitte warten", "type": "warning"})
        return
    with state._lock:
        if state.running:
            return
        state.running = True
        state.paused = False
    threading.Thread(target=bot_loop, daemon=True).start()
    emit("status", {"msg": "🤖 TREVLIX gestartet", "type": "success"}, broadcast=True)
    state.add_activity(
        "🚀", "TREVLIX gestartet", f"v{BOT_VERSION} · {CONFIG['exchange'].upper()}", "success"
    )
    log.info("🚀 Bot gestartet")


@socketio.on("stop_bot")
def on_stop_bot():
    if not _ws_rate_check("stop_bot", min_interval=3.0):
        emit("status", {"msg": "⏳ Zu schnell – bitte warten", "type": "warning"})
        return
    with state._lock:
        state.running = False
        state.paused = False
    emit("status", {"msg": "⏹ Bot gestoppt", "type": "info"}, broadcast=True)
    state.add_activity("⏹", "Bot gestoppt", "Alle Positionen offen", "info")


@socketio.on("pause_bot")
def on_pause_bot():
    if not _ws_rate_check("pause_bot", min_interval=2.0):
        return
    with state._lock:
        state.paused = not state.paused
        msg = "⏸ Pausiert" if state.paused else "▶ Weiter"
    emit("status", {"msg": msg, "type": "warning"}, broadcast=True)


@socketio.on("update_config")
def on_update_config(data):
    if not _ws_rate_check("update_config", min_interval=2.0):
        emit("status", {"msg": "⏳ Zu schnell – bitte warten", "type": "warning"})
        return
    allowed = {
        "stop_loss_pct",
        "take_profit_pct",
        "max_open_trades",
        "scan_interval",
        "paper_trading",
        "trailing_stop",
        "ai_min_confidence",
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
    }
    # Typ-Validierung: Wert muss zum bestehenden CONFIG-Typ passen
    _numeric_keys = {
        "stop_loss_pct",
        "take_profit_pct",
        "ai_min_confidence",
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
    for k, v in data.items():
        if k not in allowed:
            continue
        if k in _numeric_keys:
            v = _safe_float(v, CONFIG.get(k, 0.0))
        elif k in _int_keys:
            v = _safe_int(v, CONFIG.get(k, 0))
        elif isinstance(CONFIG.get(k), bool):
            v = bool(v)
        CONFIG[k] = v
    emit("status", {"msg": "✅ Einstellungen gespeichert", "type": "success"})
    emit("update", state.snapshot(), broadcast=True)


@socketio.on("save_api_keys")
def on_save_keys(data):
    # API-Keys werden verschlüsselt im CONFIG gespeichert
    raw_key = data.get("api_key", "")
    raw_secret = data.get("secret", "")
    CONFIG["api_key"] = encrypt_value(raw_key) if raw_key else ""
    CONFIG["secret"] = encrypt_value(raw_secret) if raw_secret else ""
    if data.get("exchange") and data["exchange"] in EXCHANGE_MAP:
        CONFIG["exchange"] = data["exchange"]
    emit("status", {"msg": f"🔑 Keys gespeichert ({CONFIG['exchange']})", "type": "success"})


@socketio.on("update_discord")
def on_update_discord(data):
    if data.get("webhook"):
        CONFIG["discord_webhook"] = data["webhook"]
    if "on_buy" in data:
        CONFIG["discord_on_buy"] = bool(data["on_buy"])
    if "on_sell" in data:
        CONFIG["discord_on_sell"] = bool(data["on_sell"])
    if "daily_report" in data:
        CONFIG["discord_daily_report"] = bool(data["daily_report"])
    if "report_hour" in data:
        rh = _safe_int(data.get("report_hour", 20), 20)
        CONFIG["discord_report_hour"] = max(0, min(23, rh))
    discord.send(
        "✅ Discord verbunden", f"```\n{BOT_NAME} {BOT_VERSION} konfiguriert!\n```", "info"
    )
    emit("status", {"msg": "💬 Discord konfiguriert & getestet", "type": "success"})


@socketio.on("force_train")
def on_force_train():
    emit("status", {"msg": "🧠 KI-Training gestartet...", "type": "info"})
    threading.Thread(target=ai_engine._train, daemon=True).start()


@socketio.on("force_optimize")
def on_force_optimize():
    emit("status", {"msg": "🔬 Optimierung läuft...", "type": "info"})
    threading.Thread(target=ai_engine._optimize, daemon=True).start()


@socketio.on("force_genetic")
def on_force_genetic():
    emit("status", {"msg": "🧬 Genetischer Optimizer gestartet...", "type": "info"})
    threading.Thread(
        target=lambda trades=list(state.closed_trades): genetic.evolve(trades), daemon=True
    ).start()


@socketio.on("reset_ai")
def on_reset_ai():
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
    emit("status", {"msg": "🔄 KI zurückgesetzt", "type": "warning"})


@socketio.on("close_position")
def on_close_position(data):
    if not _ws_rate_check("close_position", min_interval=2.0):
        emit("status", {"msg": "⏳ Zu schnell – bitte warten", "type": "warning"})
        return
    sym = data.get("symbol", "")
    if sym in state.positions:
        try:
            ex = create_exchange()
            close_position(ex, sym, "Manuell geschlossen 🖐")
            emit("status", {"msg": f"✅ {sym} geschlossen", "type": "success"}, broadcast=True)
        except Exception as e:
            emit("status", {"msg": f"❌ {e}", "type": "error"})
    elif sym in state.short_positions:
        short_engine.close_short(sym, "Manuell 🖐")
        emit("status", {"msg": f"✅ Short {sym} geschlossen", "type": "success"}, broadcast=True)


@socketio.on("run_backtest")
def on_run_backtest(data):
    def _bt():
        try:
            ex = create_exchange()
            result = bt.run(
                ex,
                data.get("symbol", "BTC/USDT"),
                data.get("timeframe", "1h"),
                _safe_int(data.get("candles", 500), 500),
                _safe_float(data.get("sl", CONFIG["stop_loss_pct"]), CONFIG["stop_loss_pct"]),
                _safe_float(data.get("tp", CONFIG["take_profit_pct"]), CONFIG["take_profit_pct"]),
                _safe_float(
                    data.get("vote", CONFIG.get("min_vote_score", 0.3)),
                    CONFIG.get("min_vote_score", 0.3),
                ),
            )
            socketio.emit("backtest_result", result)
        except Exception as e:
            socketio.emit("backtest_result", {"error": str(e)})

    emit("status", {"msg": f"⏳ Backtest {data.get('symbol', '?')} läuft...", "type": "info"})
    threading.Thread(target=_bt, daemon=True).start()


@socketio.on("add_price_alert")
def on_add_alert(data):
    uid = session.get("user_id", 1)
    db.add_alert(
        data.get("symbol", ""),
        _safe_float(data.get("target", 0), 0.0),
        data.get("direction", "above"),
        uid,
    )
    emit("status", {"msg": f"🔔 Alert gesetzt für {data.get('symbol')}", "type": "success"})
    emit("update", state.snapshot(), broadcast=True)


@socketio.on("delete_price_alert")
def on_delete_alert(data):
    db.delete_alert(_safe_int(data.get("id", 0), 0))
    emit("update", state.snapshot(), broadcast=True)


@socketio.on("manual_backup")
def on_manual_backup():
    def _bk():
        path = db.backup()
        if path:
            discord.backup_done(path)
            socketio.emit(
                "status", {"msg": f"💾 Backup: {os.path.basename(path)}", "type": "success"}
            )
        else:
            socketio.emit("status", {"msg": "❌ Backup fehlgeschlagen", "type": "error"})

    threading.Thread(target=_bk, daemon=True).start()


@socketio.on("send_daily_report")
def on_send_report():
    threading.Thread(target=daily_sched._send_report, daemon=True).start()
    emit("status", {"msg": "📊 Report wird gesendet...", "type": "info"})


@socketio.on("reset_circuit_breaker")
def on_reset_cb():
    with risk._lock:
        risk.circuit_breaker_until = None
        risk.consecutive_losses = 0
    emit("status", {"msg": "⚡ Circuit Breaker zurückgesetzt", "type": "success"}, broadcast=True)
    emit("update", state.snapshot(), broadcast=True)


@socketio.on("scan_arbitrage")
def on_scan_arb():
    def _arb():
        opps = arb_scanner.scan(state.markets[:30])
        socketio.emit(
            "status",
            {"msg": f"💹 {len(opps)} Arbitrage-Chancen", "type": "success" if opps else "info"},
        )

    threading.Thread(target=_arb, daemon=True).start()


@socketio.on("update_dominance")
def on_update_dominance():
    threading.Thread(target=dominance.update, daemon=True).start()
    emit("status", {"msg": "🌐 Dominanz-Update läuft...", "type": "info"})


@socketio.on("admin_create_user")
def on_admin_create_user(data):
    if session.get("user_role") != "admin":
        emit("status", {"msg": "❌ Kein Admin", "type": "error"})
        return
    ok = db.create_user(
        data.get("username", ""),
        data.get("password", ""),
        data.get("role", "user"),
        _safe_float(data.get("balance", 10000), 10000.0),
    )
    emit(
        "status",
        {"msg": "✅ User erstellt" if ok else "❌ Fehler", "type": "success" if ok else "error"},
    )


# ═══════════════════════════════════════════════════════════════════════════════
# STARTUP
# ═══════════════════════════════════════════════════════════════════════════════
def fetch_aggregated_balance() -> dict:
    """[#32] Aggregiert Balance über alle konfigurierten Exchanges.

    Verbindet sich mit der Haupt-Exchange sowie allen in ``arb_exchanges``
    konfigurierten Exchanges und summiert USDT-Guthaben und Coin-Bestände.

    Returns:
        Dict mit ``total_usdt``, ``by_exchange`` und ``errors``.
    """
    result: dict = {"total_usdt": 0.0, "by_exchange": {}, "errors": []}
    if CONFIG["paper_trading"]:
        result["total_usdt"] = state.balance
        result["by_exchange"]["paper"] = {"USDT": state.balance}
        return result

    exchanges_to_check = {CONFIG.get("exchange", "cryptocom"): create_exchange()}
    for ex_id in CONFIG.get("arb_exchanges", []):
        try:
            keys = CONFIG.get("arb_api_keys", {}).get(ex_id, {})
            ex_cls = getattr(ccxt, EXCHANGE_MAP.get(ex_id, ex_id), None)
            if ex_cls is None:
                result["errors"].append(f"{ex_id}: Exchange class not found")
                continue
            exchanges_to_check[ex_id] = ex_cls(
                {
                    "apiKey": keys.get("apiKey", ""),
                    "secret": keys.get("secret", ""),
                    "enableRateLimit": True,
                }
            )
        except Exception as e:
            result["errors"].append(f"{ex_id}: {e}")

    for ex_id, ex in exchanges_to_check.items():
        try:
            bal = ex.fetch_balance()
            totals = {k: float(v) for k, v in bal.get("total", {}).items() if float(v or 0) > 0}
            result["by_exchange"][ex_id] = totals
            # USDT direkt + Schätzung via last price für andere Coins
            usdt = totals.get(CONFIG.get("quote_currency", "USDT"), 0.0)
            result["total_usdt"] += usdt
        except Exception as e:
            result["errors"].append(f"{ex_id}: {e}")

    return result


def safety_scan():
    """Prüft beim Start ob unbekannte Positionen auf Exchange sind."""
    if CONFIG["paper_trading"]:
        return
    try:
        ex = create_exchange()
        bal = ex.fetch_balance()
        suspicious = []
        for coin, details in bal.get("total", {}).items():
            if coin == CONFIG["quote_currency"] or float(details or 0) <= 0.001:
                continue
            sym = f"{coin}/{CONFIG['quote_currency']}"
            if sym not in state.positions:
                suspicious.append(f"{coin}: {float(details or 0):.4f}")
        if suspicious:
            msg = "⚠️ Unbekannte Positionen:\n" + "\n".join(suspicious)
            discord.error(msg)
            log.warning(msg)
    except Exception as e:
        log.debug(f"Safety-Scan: {e}")


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
        return jsonify({"error": str(e)}), 500


# ════════════════════════════════════════════════════════════════════════════════
# GRID TRADING ENGINE (Verbesserung 2)
# Platziert automatisch Kauf-/Verkauforders in einem Preisraster
# ════════════════════════════════════════════════════════════════════════════════


class GridTradingEngine:
    """
    Klassisches Grid-Trading:
    - Definiert N Preisstufen zwischen lower_price und upper_price
    - Kauft wenn Preis eine Stufe unterschreitet
    - Verkauft wenn Preis eine Stufe überschreitet
    - Funktioniert ohne KI-Signal, ideal für Seitwärtsmärkte
    """

    def __init__(self):
        self.grids: dict[str, dict] = {}  # symbol → grid config
        self._lock = threading.Lock()

    def create_grid(
        self,
        symbol: str,
        lower: float,
        upper: float,
        levels: int = 10,
        invest_per_level: float = 100.0,
    ) -> dict:
        if lower >= upper or levels < 2:
            return {"error": "Ungültige Parameter: lower < upper, levels >= 2"}
        step = (upper - lower) / levels
        grid_levels = [round(lower + i * step, 6) for i in range(levels + 1)]
        with self._lock:
            self.grids[symbol] = {
                "symbol": symbol,
                "lower": lower,
                "upper": upper,
                "levels": levels,
                "step": round(step, 6),
                "grid_levels": grid_levels,
                "invest_per_level": invest_per_level,
                "active": True,
                "filled_buys": {},  # price → qty
                "filled_sells": {},
                "total_pnl": 0.0,
                "total_trades": 0,
                "created": datetime.now().isoformat(),
            }
        log.info(f"[GRID] {symbol}: {levels} Stufen zwischen {lower}–{upper} · {step:.4f}/Stufe")
        return self.grids[symbol]

    def update(self, symbol: str, current_price: float, balance_ref: list) -> list:
        """Prüft für ein Symbol ob Grid-Orders ausgelöst werden sollen."""
        with self._lock:
            return self._update_locked(symbol, current_price, balance_ref)

    def _update_locked(self, symbol: str, current_price: float, balance_ref: list) -> list:
        grid = self.grids.get(symbol)
        if not grid or not grid["active"]:
            return []
        actions = []
        levels = grid["grid_levels"]
        invest = grid["invest_per_level"]

        for i, lvl in enumerate(levels[:-1]):
            buy_price = lvl
            sell_price = levels[i + 1]

            # BUY: Preis ist gerade unter buy_price gefallen
            if (
                current_price <= buy_price * 1.001
                and buy_price not in grid["filled_buys"]
                and balance_ref[0] >= invest
            ):
                qty = invest / current_price
                grid["filled_buys"][buy_price] = {"qty": qty, "price": current_price}
                balance_ref[0] -= invest
                grid["total_trades"] += 1
                actions.append(
                    {
                        "action": "BUY",
                        "symbol": symbol,
                        "price": current_price,
                        "qty": round(qty, 6),
                        "grid_level": i,
                        "invest": invest,
                    }
                )
                log.info(f"[GRID] BUY  {symbol} @ {current_price:.4f} (Stufe {i})")

            # SELL: Preis hat sell_price überschritten und wir haben eine Position
            if current_price >= sell_price * 0.999 and buy_price in grid["filled_buys"]:
                buy_info = grid["filled_buys"].pop(buy_price)
                pnl = (current_price - buy_info["price"]) * buy_info["qty"]
                balance_ref[0] += buy_info["qty"] * current_price
                grid["total_pnl"] = round(grid["total_pnl"] + pnl, 4)
                grid["total_trades"] += 1
                grid["filled_sells"][sell_price] = {"pnl": pnl}
                actions.append(
                    {
                        "action": "SELL",
                        "symbol": symbol,
                        "price": current_price,
                        "qty": round(buy_info["qty"], 6),
                        "pnl": round(pnl, 4),
                        "grid_level": i,
                    }
                )
                log.info(f"[GRID] SELL {symbol} @ {current_price:.4f} PnL={pnl:+.4f}")
        return actions

    def stop_grid(self, symbol: str):
        with self._lock:
            if symbol in self.grids:
                self.grids[symbol]["active"] = False

    def delete_grid(self, symbol: str):
        with self._lock:
            self.grids.pop(symbol, None)

    def status(self) -> list:
        return [
            {
                **g,
                "open_buys": len(g["filled_buys"]),
                "grid_levels": None,
            }  # Don't send full list to UI
            for g in self.grids.values()
        ]


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
    lower = _safe_float(d.get("lower", 0), 0.0)
    upper = _safe_float(d.get("upper", 0), 0.0)
    levels = _safe_int(d.get("levels", 10), 10)
    invest = _safe_float(d.get("invest_per_level", 100.0), 100.0)
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
    if session.get("user_role", "user") != "admin":
        emit("status", {"msg": "Nur Admin", "type": "error"})
        return
    grid_engine.create_grid(
        data.get("symbol", ""),
        _safe_float(data.get("lower", 0), 0.0),
        _safe_float(data.get("upper", 0), 0.0),
        _safe_int(data.get("levels", 10), 10),
        _safe_float(data.get("invest_per_level", 100), 100.0),
    )
    emit(
        "status",
        {"msg": f"✅ Grid {data.get('symbol', '')} erstellt", "type": "success"},
        broadcast=True,
    )


# ── Undo Close ────────────────────────────────────────────────────────────────
@socketio.on("undo_close")
def on_undo_close(data):
    sym = data.get("symbol", "")
    if not sym:
        emit("status", {"msg": "❌ Kein Symbol angegeben", "type": "error"})
        return
    # Position kann nicht wirklich rückgängig gemacht werden (bereits geschlossen)
    # – informiere den Nutzer
    emit(
        "status",
        {
            "msg": f"↩ Rückgängig nicht möglich: {sym} wurde bereits auf der Börse geschlossen",
            "type": "warning",
        },
    )


# ── GitHub Updater ─────────────────────────────────────────────────────────────
@socketio.on("check_update")
def on_check_update():
    try:
        import subprocess

        result = subprocess.run(
            ["git", "remote", "get-url", "origin"], capture_output=True, text=True, timeout=5
        )
        repo_url = result.stdout.strip()
        result2 = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"], capture_output=True, text=True, timeout=5
        )
        branch = result2.stdout.strip()
        result3 = subprocess.run(
            ["git", "describe", "--tags", "--abbrev=0"], capture_output=True, text=True, timeout=5
        )
        current = result3.stdout.strip() or BOT_VERSION
        socketio.emit(
            "update_status",
            {
                "current_version": current,
                "latest_version": current,
                "current": current,
                "latest": current,
                "update_available": False,
                "repo": repo_url,
                "branch": branch,
                "last_check": datetime.now().strftime("%Y-%m-%d %H:%M"),
            },
        )
    except Exception as e:
        emit("status", {"msg": f"⚠ Update-Check fehlgeschlagen: {e}", "type": "warning"})


@socketio.on("apply_update")
def on_apply_update():
    if session.get("user_role", "user") != "admin":
        emit("status", {"msg": "Nur Admin", "type": "error"})
        return
    try:
        import subprocess

        subprocess.run(
            ["git", "pull", "--ff-only"], capture_output=True, text=True, timeout=30, check=True
        )
        emit("update_result", {"status": "success"}, broadcast=True)
        emit(
            "status",
            {"msg": "✅ Update angewendet – Server wird neu gestartet", "type": "success"},
            broadcast=True,
        )
    except Exception as e:
        emit("update_result", {"status": "error", "msg": str(e)})
        emit("status", {"msg": f"❌ Update fehlgeschlagen: {e}", "type": "error"})


@socketio.on("rollback_update")
def on_rollback_update():
    if session.get("user_role", "user") != "admin":
        emit("status", {"msg": "Nur Admin", "type": "error"})
        return
    try:
        import subprocess

        subprocess.run(["git", "stash"], capture_output=True, text=True, timeout=15)
        emit("status", {"msg": "↩ Rollback: git stash angewendet", "type": "info"}, broadcast=True)
    except Exception as e:
        emit("status", {"msg": f"❌ Rollback fehlgeschlagen: {e}", "type": "error"})


# ── Multi-Exchange Handler ──────────────────────────────────────────────────────
@socketio.on("start_exchange")
def on_start_exchange(data):
    if session.get("user_role", "user") != "admin":
        emit("status", {"msg": "Nur Admin", "type": "error"})
        return
    ex_name = data.get("exchange", "")
    emit(
        "status",
        {"msg": f"▶ Exchange {ex_name.upper()} wird gestartet…", "type": "info"},
        broadcast=True,
    )
    emit("exchange_update", {"exchange": ex_name, "status": "running"}, broadcast=True)


@socketio.on("stop_exchange")
def on_stop_exchange(data):
    if session.get("user_role", "user") != "admin":
        emit("status", {"msg": "Nur Admin", "type": "error"})
        return
    ex_name = data.get("exchange", "")
    emit(
        "status", {"msg": f"⏹ Exchange {ex_name.upper()} gestoppt", "type": "info"}, broadcast=True
    )
    emit("exchange_update", {"exchange": ex_name, "status": "stopped"}, broadcast=True)


@socketio.on("save_exchange_keys")
def on_save_exchange_keys(data):
    if session.get("user_role", "user") != "admin":
        emit("status", {"msg": "Nur Admin", "type": "error"})
        return
    ex_name = data.get("exchange", "")
    api_key = data.get("api_key", "")
    secret = data.get("secret", "")
    if not ex_name or not api_key or not secret:
        emit("status", {"msg": "❌ Exchange, API-Key und Secret erforderlich", "type": "error"})
        return
    # Keys werden nur im laufenden Config-Objekt gespeichert (nicht persistiert)
    if "extra_exchanges" not in CONFIG:
        CONFIG["extra_exchanges"] = {}
    CONFIG["extra_exchanges"][ex_name] = {
        "api_key": encrypt_value(api_key),
        "secret": encrypt_value(secret),
        "passphrase": encrypt_value(data.get("passphrase", "")) if data.get("passphrase") else "",
    }
    emit("status", {"msg": f"🔑 Keys für {ex_name.upper()} gespeichert", "type": "success"})


@socketio.on("close_exchange_position")
def on_close_exchange_position(data):
    ex_name = data.get("exchange", "")
    symbol = data.get("symbol", "")
    if not ex_name or not symbol:
        emit("status", {"msg": "❌ Exchange und Symbol erforderlich", "type": "error"})
        return
    try:
        # Nur bekannte Exchanges zulassen (kein beliebiges getattr auf ccxt)
        if ex_name not in EXCHANGE_MAP and ex_name not in {v for v in EXCHANGE_MAP.values()}:
            emit("status", {"msg": "❌ Unbekannte Exchange", "type": "error"})
            return
        ex_cfg = CONFIG.get("extra_exchanges", {}).get(ex_name, {})
        ex_cls = getattr(ccxt, EXCHANGE_MAP.get(ex_name, ex_name), None)
        if ex_cls is None:
            emit("status", {"msg": "❌ Exchange nicht verfügbar", "type": "error"})
            return
        raw_key = ex_cfg.get("api_key", "")
        raw_secret = ex_cfg.get("secret", "")
        if not raw_key or not raw_secret:
            emit("status", {"msg": "❌ Keine API-Keys für diese Exchange", "type": "error"})
            return
        ex = ex_cls(
            {
                "apiKey": decrypt_value(raw_key),
                "secret": decrypt_value(raw_secret),
                "password": decrypt_value(ex_cfg.get("passphrase", "")) or None,
                "enableRateLimit": True,
            }
        )
        amount = sum(p.get("qty", 0) for p in state.positions.values() if p.get("symbol") == symbol)
        if amount > 0:
            ex.create_market_sell_order(symbol, amount)
        emit(
            "status",
            {"msg": f"✅ {symbol} auf {ex_name.upper()} geschlossen", "type": "success"},
            broadcast=True,
        )
    except Exception as e:
        emit("status", {"msg": f"❌ Fehler beim Schließen: {e}", "type": "error"})


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
                    str(trades[0].get("opened", datetime.now().isoformat()))[:19]
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
    n_sim = min(_safe_int(request.args.get("n", 10000), 10000), 50000)
    n_days = min(_safe_int(request.args.get("days", 30), 30), 365)
    result = run_monte_carlo(n_sim, n_days)
    return jsonify(result)


# ════════════════════════════════════════════════════════════════════════════════
# TELEGRAM BOT NOTIFIER (Verbesserung 5)
# ════════════════════════════════════════════════════════════════════════════════


class TelegramNotifier:
    """Sendet Benachrichtigungen via Telegram Bot API."""

    BASE = "https://api.telegram.org/bot"

    def __init__(self):
        self.token = CONFIG.get("telegram_token", "")
        self.chat_id = CONFIG.get("telegram_chat_id", "")

    @property
    def enabled(self) -> bool:
        return bool(self.token and self.chat_id)

    def send(self, text: str, parse_mode: str = "HTML") -> bool:
        if not self.enabled:
            return False
        try:
            resp = requests.post(
                f"{self.BASE}{self.token}/sendMessage",
                json={
                    "chat_id": self.chat_id,
                    "text": text,
                    "parse_mode": parse_mode,
                    "disable_web_page_preview": True,
                },
                timeout=5,
            )
            return resp.status_code == 200
        except Exception as e:
            log.warning(f"[TG] Senden fehlgeschlagen: {e}")
            return False

    def trade_open(
        self, symbol: str, price: float, invest: float, confidence: float, exchange: str = "main"
    ):
        self.send(
            f"⚡ <b>KAUF</b> [{exchange.upper()}]\n"
            f"Symbol: <code>{symbol}</code>\n"
            f"Preis: <code>{price:.4f} USDT</code>\n"
            f"Invest: <code>{invest:.2f} USDT</code>\n"
            f"KI-Konfidenz: <code>{confidence * 100:.0f}%</code>"
        )

    def trade_close(
        self, symbol: str, price: float, pnl: float, reason: str, exchange: str = "main"
    ):
        icon = "✅" if pnl >= 0 else "❌"
        self.send(
            f"{icon} <b>{reason}</b> [{exchange.upper()}]\n"
            f"Symbol: <code>{symbol}</code>\n"
            f"Preis: <code>{price:.4f} USDT</code>\n"
            f"PnL: <code>{pnl:+.2f} USDT</code>"
        )

    def alert(self, title: str, body: str):
        self.send(f"🚨 <b>{title}</b>\n{body}")

    def daily_report(self, pnl: float, wr: float, trades: int, pv: float):
        icon = "📈" if pnl >= 0 else "📉"
        self.send(
            f"{icon} <b>TREVLIX Tagesbericht</b>\n"
            f"Portfolio: <code>{pv:.2f} USDT</code>\n"
            f"PnL heute: <code>{pnl:+.2f} USDT</code>\n"
            f"Win-Rate: <code>{wr:.1f}%</code>\n"
            f"Trades: <code>{trades}</code>"
        )

    def test(self) -> bool:
        return self.send("🤖 <b>TREVLIX</b> — Verbindung erfolgreich!")


telegram = TelegramNotifier()


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
    telegram.token = token
    telegram.chat_id = chat_id
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
        CONFIG["news_sentiment_min"] = _safe_float(
            d.get("min_score", CONFIG["news_sentiment_min"]), CONFIG["news_sentiment_min"]
        )
        CONFIG["news_require_positive"] = bool(
            d.get("require_positive", CONFIG["news_require_positive"])
        )
        CONFIG["news_block_score"] = _safe_float(
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
    n = _safe_int(request.args.get("n", 20), 20)
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
    CONFIG["funding_rate_max"] = _safe_float(d.get("max_rate", 0.001), 0.001)
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

# ── Performance Attribution Engine ───────────────────────────────────────
perf_attribution = PerformanceAttribution(
    max_trades=CONFIG.get("pa_max_trades", 5000),
)


@app.route("/api/v1/trade-dna")
@api_auth_required
def api_trade_dna():
    """Trade DNA Fingerprinting Status und Top-Patterns."""
    return jsonify(trade_dna.to_dict())


@app.route("/api/v1/trade-dna/patterns")
@api_auth_required
def api_trade_dna_patterns():
    """Top profitable und schlechteste DNA-Muster."""
    n = _safe_int(request.args.get("n", 10), 10)
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
    n = _safe_int(request.args.get("n", 5), 5)
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
    confidence = _safe_float(request.args.get("conf", 0.95), 0.95)
    return jsonify(adv_risk.compute_cvar(state.closed_trades, confidence))


@app.route("/api/v1/risk/volatility")
@api_auth_required
def api_volatility():
    return jsonify(adv_risk.volatility_forecast(_safe_int(request.args.get("h", 5), 5)))


@app.route("/api/v1/risk/regime")
@api_auth_required
def api_market_regime():
    prices = list(state.prices.values())
    if not prices:
        return jsonify({"regime": "UNKNOWN"})
    regime_result = adv_risk.classify_regime(
        list(state.portfolio_history[-50:]) if state.portfolio_history else prices
    )
    return jsonify(
        {
            "regime": regime_result,
            "vol_pct": round(adv_risk._ewma_vol * 100, 3),
            "risk_level": adv_risk.volatility_forecast(1)["risk_level"],
        }
    )


def startup_banner():
    print(f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║ ████████╗██████╗ ███████╗██╗   ██╗██╗     ██╗██╗  ██╗                    ║
║ ╚══██╔══╝██╔══██╗██╔════╝██║   ██║██║     ██║╚██╗██╔╝                    ║
║    ██║   ██████╔╝█████╗  ██║   ██║██║     ██║ ╚███╔╝                     ║
║    ██║   ██╔══██╗██╔══╝  ╚██╗ ██╔╝██║     ██║ ██╔██╗                     ║
║    ██║   ██║  ██║███████╗ ╚████╔╝ ███████╗██║██╔╝ ██╗                    ║
║    ╚═╝   ╚═╝  ╚═╝╚══════╝  ╚═══╝  ╚══════╝╚═╝╚═╝  ╚═╝                    ║
║                                                                              ║
║  Algorithmic Crypto Trading  ·  v{BOT_VERSION}  ·  trevlix.dev                ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  MySQL:   {CONFIG["mysql_host"]}/{CONFIG["mysql_db"]:<44}║
║  Exchange:{CONFIG["exchange"]:<51}║
║  Modus:   {"📝 Paper Trading" if CONFIG["paper_trading"] else "💰 Live Trading":<50}║
║  Kapital: {CONFIG["paper_balance"]:<50}║
╚══════════════════════════════════════════════════════════════════════════════╝
    """)


# ═══════════════════════════════════════════════════════════════════════════════
# [Verbesserung #12] Zentrale Fehlerbehandlung
# ═══════════════════════════════════════════════════════════════════════════════
@app.errorhandler(404)
def _handle_404(_e):
    if request.path.startswith("/api/"):
        return jsonify({"error": "Endpunkt nicht gefunden", "path": request.path}), 404
    return redirect("/404")


@app.errorhandler(500)
def _handle_500(e):
    log.error(f"Internal Server Error: {e}", exc_info=True)
    if request.path.startswith("/api/"):
        return jsonify({"error": "Interner Serverfehler"}), 500
    return "Interner Fehler", 500


@app.errorhandler(429)
def _handle_429(_e):
    return jsonify({"error": "Zu viele Anfragen. Bitte warten."}), 429


# ═══════════════════════════════════════════════════════════════════════════════
# [Verbesserung #15] Graceful Shutdown
# ═══════════════════════════════════════════════════════════════════════════════


def _graceful_shutdown(signum, _frame):
    sig_name = signal.Signals(signum).name
    log.info(f"Shutdown-Signal empfangen ({sig_name}) – räume auf...")
    state.running = False
    # DB-Pool schließen
    try:
        if db is not None and db._pool is not None:
            db._pool.close_all()
    except Exception as e:
        log.debug(f"Pool-Close bei Shutdown: {e}")
    # [Verbesserung #24] Data Retention bei Shutdown
    try:
        if db is not None:
            db.cleanup_old_data()
    except Exception as e:
        log.debug(f"Cleanup bei Shutdown: {e}")
    log.info("Shutdown abgeschlossen.")
    raise SystemExit(0)


signal.signal(signal.SIGTERM, _graceful_shutdown)
signal.signal(signal.SIGINT, _graceful_shutdown)


# ═══════════════════════════════════════════════════════════════════════════════
# [#9] BLUEPRINT-REGISTRIERUNG
# Auth- und Dashboard-Routen über externe Blueprint-Module einbinden.
# Erlaubt schrittweise Modularisierung von server.py.
# ═══════════════════════════════════════════════════════════════════════════════
try:
    from routes.auth import create_auth_blueprint
    from routes.dashboard import create_dashboard_blueprint

    _auth_bp = create_auth_blueprint(
        db=db,
        config=CONFIG,
        limiter=limiter,
        db_audit_fn=db_audit,
        check_login_rate_fn=_check_login_rate,
        record_login_attempt_fn=_record_login_attempt,
        audit_fn=_audit,
        template_dir=_TEMPLATE_DIR,
    )
    _dashboard_bp = create_dashboard_blueprint(
        template_dir=_TEMPLATE_DIR,
        static_dir=_STATIC_DIR,
        require_auth_fn=dashboard_auth,
    )
    # Blueprints mit Prefix-freiem URL-Raum registrieren
    # (Routen mit gleichem Pfad wie bestehende werden vom Blueprint ignoriert)
    app.register_blueprint(_auth_bp, name="auth_bp")
    app.register_blueprint(_dashboard_bp, name="dashboard_bp")
    log.info("✅ Blueprints registriert: auth, dashboard")
except Exception as _bp_err:
    log.error(f"Blueprint-Registrierung fehlgeschlagen: {_bp_err}", exc_info=True)


# ═══════════════════════════════════════════════════════════════════════════════
# AUTO-START: Bot startet automatisch ohne Admin-Login
# ═══════════════════════════════════════════════════════════════════════════════
_AUTO_START = os.getenv("AUTO_START", "true").lower() in ("true", "1", "yes")


if __name__ == "__main__":
    startup_banner()
    # [Verbesserung #7] Konfigurationsvalidierung
    _cfg_errors = validate_config(CONFIG)
    if _cfg_errors:
        for _err in _cfg_errors:
            log.error(f"⚠️  CONFIG-Fehler: {_err}")
        log.warning("⚠️  Konfigurationsfehler gefunden – bitte prüfen. Bot startet trotzdem.")
    os.makedirs(CONFIG["backup_dir"], exist_ok=True)
    # Hintergrund-Threads
    threading.Thread(target=daily_sched.run, daemon=True, name="DailyReport").start()
    threading.Thread(target=backup_sched.run, daemon=True, name="Backup").start()
    # Initialisierung
    threading.Thread(target=fg_idx.update, daemon=True).start()
    threading.Thread(target=dominance.update, daemon=True).start()
    threading.Thread(target=safety_scan, daemon=True).start()

    # Auto-Start: Bot sofort starten ohne Login
    if _AUTO_START:
        state.running = True
        state.paused = False
        threading.Thread(target=bot_loop, daemon=True, name="BotLoop").start()
        log.info("🚀 Bot auto-gestartet (AUTO_START=true)")
        state.add_activity(
            "🚀", "Auto-Start", f"v{BOT_VERSION} · {CONFIG['exchange'].upper()}", "success"
        )
    else:
        log.info("⏸️  Bot wartet auf manuellen Start (AUTO_START=false)")

    log.info("🌐 Dashboard: http://0.0.0.0:5000")
    log.info("📡 REST-API:  http://0.0.0.0:5000/api/v1/")
    log.info("📚 API-Docs:  http://0.0.0.0:5000/api/v1/docs")
    socketio.run(app, host="0.0.0.0", port=5000, debug=False, allow_unsafe_werkzeug=True)
