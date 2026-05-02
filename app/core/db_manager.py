"""MySQLManager extracted from server.py.

Module-level globals are injected at startup via init_db_manager().
"""

from __future__ import annotations

import json
import logging as _stdlib_logging
import os
import threading
from contextlib import contextmanager
from typing import Any

try:
    import orjson as _orjson

    def _jdumps(obj: Any) -> str:
        """Fast JSON serialiser using orjson (falls back to stdlib json)."""
        return _orjson.dumps(obj).decode()

    def _jloads(s: str | bytes) -> Any:
        """Fast JSON deserialiser using orjson (falls back to stdlib json)."""
        return _orjson.loads(s)

except ImportError:

    def _jdumps(obj: Any) -> str:  # type: ignore[misc]
        return json.dumps(obj, ensure_ascii=False)

    def _jloads(s: str | bytes) -> Any:  # type: ignore[misc]
        return json.loads(s)


from tenacity import RetryError, before_sleep_log, retry, stop_after_attempt, wait_exponential

from services.encryption import decrypt_value, encrypt_value

# ---------------------------------------------------------------------------
# Module-level references – populated by init_db_manager()
# ---------------------------------------------------------------------------
CONFIG: dict = {}
log = None
MYSQL_AVAILABLE: bool = False
BCRYPT_AVAILABLE: bool = False
JWT_AVAILABLE: bool = False
pymysql = None
bcrypt = None
pyjwt = None
ConnectionPool = None


def init_db_manager(
    *,
    config: dict,
    logger,
    mysql_available: bool = False,
    bcrypt_available: bool = False,
    jwt_available: bool = False,
    pymysql_module=None,
    bcrypt_module=None,
    pyjwt_module=None,
    connection_pool_cls=None,
) -> None:
    """Inject runtime dependencies into this module's globals."""
    global CONFIG, log, MYSQL_AVAILABLE, BCRYPT_AVAILABLE, JWT_AVAILABLE
    global pymysql, bcrypt, pyjwt, ConnectionPool
    CONFIG = config
    log = logger
    MYSQL_AVAILABLE = mysql_available
    BCRYPT_AVAILABLE = bcrypt_available
    JWT_AVAILABLE = jwt_available
    pymysql = pymysql_module
    bcrypt = bcrypt_module
    pyjwt = pyjwt_module
    ConnectionPool = connection_pool_cls


class MySQLManager:
    """Per-domain DB facade.

    Repositories are exposed as lazy-init properties so test code that
    constructs the manager via ``MySQLManager.__new__`` (bypassing
    ``__init__``) and then patches ``_get_conn`` still picks up the
    repositories without any extra setup.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._pool: ConnectionPool | None = None
        self.db_available = False  # [Verbesserung #3] Flag für Degraded-Mode
        self._init_db()

    # ── Repository accessors (composition over inheritance) ───────────────
    # The manager keeps thin delegation wrappers on its public API so
    # existing callers (db.get_user(), db.create_user(), ...) keep working
    # unchanged. Each repository is built on first access so test code
    # using ``MySQLManager.__new__`` (without __init__) still gets them.
    @property
    def users(self):
        if not hasattr(self, "_users_repo"):
            from app.core.repositories.user_repo import UserRepository

            self._users_repo = UserRepository(self)
        return self._users_repo

    @property
    def trades(self):
        if not hasattr(self, "_trades_repo"):
            from app.core.repositories.trade_repo import TradeRepository

            self._trades_repo = TradeRepository(self)
        return self._trades_repo

    @property
    def exchanges(self):
        if not hasattr(self, "_exchanges_repo"):
            from app.core.repositories.exchange_repo import ExchangeRepository

            self._exchanges_repo = ExchangeRepository(self)
        return self._exchanges_repo

    @property
    def alerts(self):
        if not hasattr(self, "_alerts_repo"):
            from app.core.repositories.alert_repo import AlertRepository

            self._alerts_repo = AlertRepository(self)
        return self._alerts_repo

    @property
    def ai(self):
        if not hasattr(self, "_ai_repo"):
            from app.core.repositories.ai_repo import AIRepository

            self._ai_repo = AIRepository(self)
        return self._ai_repo

    @property
    def intel(self):
        if not hasattr(self, "_intel_repo"):
            from app.core.repositories.intel_repo import IntelRepository

            self._intel_repo = IntelRepository(self)
        return self._intel_repo

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
                pool_size=int(os.getenv("DB_POOL_SIZE", "15")),
                timeout=int(os.getenv("DB_POOL_TIMEOUT", "30")),
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

    def pool_stats(self) -> dict[str, int | float]:
        """Gibt Pool-Statistiken zurück (oder leeres Dict ohne Pool)."""
        if self._pool is not None:
            return self._pool.pool_stats()
        return {}

    @contextmanager
    def get_connection(self):
        """Alias für _get_conn() – öffentlicher Context-Manager."""
        with self._get_conn() as conn:
            yield conn

    def _check_pool_health(self) -> None:
        """Prüft Pool-Auslastung und loggt Warnungen bei hoher Nutzung."""
        if self._pool is None:
            return
        stats = self._pool.pool_stats()
        util = stats.get("utilization_pct", 0)
        if util >= 90:
            log.warning(
                "DB-Pool kritisch: %s%% Auslastung (%s/%s belegt)",
                util,
                stats.get("in_use", "?"),
                stats.get("pool_size", "?"),
            )
        elif util >= 70:
            log.info(
                "DB-Pool hoch: %s%% Auslastung (%s/%s belegt)",
                util,
                stats.get("in_use", "?"),
                stats.get("pool_size", "?"),
            )

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
        """DB-Init mit exponentiellem Backoff via tenacity (bis zu 5 Versuche)."""
        if not MYSQL_AVAILABLE:
            log.error("PyMySQL fehlt – pip install PyMySQL")
            return

        @retry(
            stop=stop_after_attempt(5),
            wait=wait_exponential(multiplier=2, min=2, max=32),
            before_sleep=before_sleep_log(log, _stdlib_logging.WARNING),
            reraise=True,
        )
        def _try() -> None:
            self._init_db_once()
            self.db_available = True

        try:
            _try()
        except (RetryError, Exception):
            log.error("MySQL Init fehlgeschlagen – starte im Degraded-Mode (Paper-Trading only)")

    def _init_db_once(self):
        """Einmalige DB-Initialisierung – wird von _init_db() mit Retry aufgerufen.

        DDL + Admin-Seed + .env-Key-Migration sind nach
        ``app/core/db_schema.apply_schema`` ausgelagert. Dieser Wrapper hält
        nur die Connection-Lifecycle und das Pool-Setup.
        """
        from app.core.db_schema import apply_schema

        conn = self._conn()
        try:
            with conn.cursor() as c:
                apply_schema(
                    c,
                    config=CONFIG,
                    log=log,
                    bcrypt_module=bcrypt,
                    bcrypt_available=BCRYPT_AVAILABLE,
                )
            # Pool NACH erfolgreicher Init erstellen
            self._pool = self._build_pool()
            log.info(f"✅ MySQL: {CONFIG['mysql_host']}/{CONFIG['mysql_db']}")
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def save_trade(self, trade: dict, user_id: int = 1):
        """Forwards to TradeRepository.save_trade."""
        return self.trades.save_trade(trade, user_id)
    def save_order(self, order: dict, user_id: int = 1) -> None:
        """Forwards to TradeRepository.save_order."""
        return self.trades.save_order(order, user_id)
    def save_trade_decision(self, decision: dict, user_id: int = 1) -> None:
        """Forwards to TradeRepository.save_trade_decision."""
        return self.trades.save_trade_decision(decision, user_id)
    def upsert_trade_position(self, position: dict, user_id: int = 1) -> None:
        """Forwards to TradeRepository.upsert_trade_position."""
        return self.trades.upsert_trade_position(position, user_id)
    def close_trade_position(
        self, symbol: str, trade_mode: str = "paper", user_id: int = 1
    ) -> None:
        """Forwards to TradeRepository.close_trade_position."""
        return self.trades.close_trade_position(symbol, trade_mode, user_id)
    def load_open_positions(
        self, user_id: int | None = None, trade_mode: str | None = None
    ) -> list[dict]:
        """Forwards to TradeRepository.load_open_positions."""
        return self.trades.load_open_positions(user_id, trade_mode)
    def load_orders(
        self, limit: int = 200, user_id: int | None = None, trade_mode: str | None = None
    ) -> list[dict]:
        """Forwards to TradeRepository.load_orders."""
        return self.trades.load_orders(limit, user_id, trade_mode)
    def load_trade_decisions(
        self, limit: int = 200, user_id: int | None = None, trade_mode: str | None = None
    ) -> list[dict]:
        """Forwards to TradeRepository.load_trade_decisions."""
        return self.trades.load_trade_decisions(limit, user_id, trade_mode)
    @staticmethod
    def _serialize_dates(row: dict, fields: tuple[str, ...]) -> dict:
        """Forwards to trade_repo._serialize_dates."""
        from app.core.repositories.trade_repo import _serialize_dates as _sd

        return _sd(row, fields)
    def _serialize_dates(row: dict, fields: tuple[str, ...]) -> dict:
        for f in fields:
            if f in row and hasattr(row[f], "isoformat"):
                row[f] = row[f].isoformat()
        return row

    def performance_breakdown(self, user_id: int | None = None) -> dict:
        """Forwards to TradeRepository.performance_breakdown."""
        return self.trades.performance_breakdown(user_id)
    def load_trades(self, limit=500, symbol=None, year=None, user_id=None) -> list[dict]:
        """Forwards to TradeRepository.load_trades."""
        return self.trades.load_trades(limit=limit, symbol=symbol, year=year, user_id=user_id)
    def save_ai_sample(self, features, label: int, regime: str = "bull"):
        """Forwards to AIRepository.save_ai_sample."""
        return self.ai.save_ai_sample(features, label, regime)
    def load_ai_samples(self) -> tuple[list, list, list]:
        """Forwards to AIRepository.load_ai_samples."""
        return self.ai.load_ai_samples()
    def _decrypt_user_keys(self, user: dict | None) -> dict | None:
        """Forwards to UserRepository._decrypt_user_keys."""
        return self.users._decrypt_user_keys(user)
    def get_user(self, username: str) -> dict[str, Any] | None:
        """Forwards to UserRepository.get_user."""
        return self.users.get_user(username)
    def get_user_by_id(self, uid: int) -> dict[str, Any] | None:
        """Forwards to UserRepository.get_user_by_id."""
        return self.users.get_user_by_id(uid)
    def get_all_users(self) -> list[dict[str, Any]]:
        """Forwards to UserRepository.get_all_users."""
        return self.users.get_all_users()
    def create_user(
        self, username: str, password: str, role: str = "user", balance: float = 10000.0
    ) -> bool:
        """Forwards to UserRepository.create_user."""
        return self.users.create_user(username, password, role, balance)
    def verify_password(self, stored_hash: str, password: str) -> bool:
        """Forwards to UserRepository.verify_password."""
        return self.users.verify_password(stored_hash, password)
    def update_user_login(self, user_id: int) -> None:
        """Forwards to UserRepository.update_user_login."""
        return self.users.update_user_login(user_id)
    def update_password(self, user_id: int, new_password: str) -> bool:
        """Forwards to UserRepository.update_password."""
        return self.users.update_password(user_id, new_password)
    def update_user_balance(self, user_id: int, balance: float) -> None:
        """Forwards to UserRepository.update_user_balance."""
        return self.users.update_user_balance(user_id, balance)
    def update_user_settings(self, user_id: int, settings: dict) -> bool:
        """Forwards to UserRepository.update_user_settings."""
        return self.users.update_user_settings(user_id, settings)
    def get_user_settings(self, user_id: int) -> dict:
        """Forwards to UserRepository.get_user_settings."""
        return self.users.get_user_settings(user_id)
    def update_user_api_keys(
        self, user_id: int, exchange: str, api_key: str, api_secret: str
    ) -> bool:
        """Forwards to UserRepository.update_user_api_keys."""
        return self.users.update_user_api_keys(user_id, exchange, api_key, api_secret)
    def get_user_exchanges(self, user_id: int) -> list[dict]:
        """Forwards to ExchangeRepository.get_user_exchanges."""
        return self.exchanges.get_user_exchanges(user_id)
    def upsert_user_exchange(
        self,
        user_id: int,
        exchange: str,
        api_key: str,
        api_secret: str,
        enabled: bool = False,
        is_primary: bool = False,
        passphrase: str = "",
    ) -> bool:
        """Forwards to ExchangeRepository.upsert_user_exchange."""
        return self.exchanges.upsert_user_exchange(
            user_id, exchange, api_key, api_secret, enabled, is_primary, passphrase
        )
    def toggle_user_exchange(self, user_id: int, exchange_id: int, enabled: bool) -> bool:
        """Forwards to ExchangeRepository.toggle_user_exchange."""
        return self.exchanges.toggle_user_exchange(user_id, exchange_id, enabled)
    def get_enabled_exchanges(self, user_id: int) -> list[dict]:
        """Forwards to ExchangeRepository.get_enabled_exchanges."""
        return self.exchanges.get_enabled_exchanges(user_id)
    def set_primary_exchange(self, user_id: int, exchange: str, enable: bool = True) -> bool:
        """Forwards to ExchangeRepository.set_primary_exchange."""
        return self.exchanges.set_primary_exchange(user_id, exchange, enable)
    def delete_user_exchange(self, user_id: int, exchange_id: int) -> bool:
        """Forwards to ExchangeRepository.delete_user_exchange."""
        return self.exchanges.delete_user_exchange(user_id, exchange_id)
    def create_api_token(self, user_id: int, label: str = "default") -> str:
        """Forwards to UserRepository.create_api_token."""
        return self.users.create_api_token(user_id, label)
    def verify_api_token(self, token: str) -> int | None:
        """Forwards to UserRepository.verify_api_token."""
        return self.users.verify_api_token(token)
    def save_backtest(self, result: dict):
        """Forwards to AIRepository.save_backtest."""
        return self.ai.save_backtest(result)
    def get_recent_backtests(self, limit=10) -> list[dict]:
        """Forwards to AIRepository.get_recent_backtests."""
        return self.ai.get_recent_backtests(limit)
    def add_alert(self, symbol: str, target: float, direction: str, user_id: int = 1) -> int:
        """Forwards to AlertRepository.add_alert."""
        return self.alerts.add_alert(symbol, target, direction, user_id)
    def get_active_alerts(self) -> list[dict]:
        """Forwards to AlertRepository.get_active_alerts."""
        return self.alerts.get_active_alerts()
    def trigger_alert(self, aid: int):
        """Forwards to AlertRepository.trigger_alert."""
        return self.alerts.trigger_alert(aid)
    def delete_alert(self, aid: int, user_id: int | None = None) -> bool:
        """Forwards to AlertRepository.delete_alert."""
        return self.alerts.delete_alert(aid, user_id)
    def get_all_alerts(self, user_id: int | None = None) -> list[dict]:
        """Forwards to AlertRepository.get_all_alerts."""
        return self.alerts.get_all_alerts(user_id)
    def save_daily_report(self, date_str: str, report: dict):
        """Forwards to IntelRepository.save_daily_report."""
        return self.intel.save_daily_report(date_str, report)
    def report_sent_today(self) -> bool:
        """Forwards to IntelRepository.report_sent_today."""
        return self.intel.report_sent_today()
    def save_sentiment(self, symbol: str, score: float, source: str):
        """Forwards to IntelRepository.save_sentiment."""
        return self.intel.save_sentiment(symbol, score, source)
    def get_sentiment(self, symbol: str) -> float | None:
        """Forwards to IntelRepository.get_sentiment."""
        return self.intel.get_sentiment(symbol)
    def save_news(self, symbol: str, score: float, headline: str, count: int):
        """Forwards to IntelRepository.save_news."""
        return self.intel.save_news(symbol, score, headline, count)
    def get_news(self, symbol: str) -> dict | None:
        """Forwards to IntelRepository.get_news."""
        return self.intel.get_news(symbol)
    def save_onchain(self, symbol: str, whale_score: float, flow_score: float, detail: str):
        """Forwards to IntelRepository.save_onchain."""
        return self.intel.save_onchain(symbol, whale_score, flow_score, detail)
    def get_onchain(self, symbol: str) -> dict | None:
        """Forwards to IntelRepository.get_onchain."""
        return self.intel.get_onchain(symbol)
    def save_arb(self, arb: dict):
        """Forwards to IntelRepository.save_arb."""
        return self.intel.save_arb(arb)
    def save_genetic(self, generation: int, fitness: float, genome: dict):
        """Forwards to AIRepository.save_genetic."""
        return self.ai.save_genetic(generation, fitness, genome)
    def export_csv(self, user_id: int | None = None, limit: int = 10000) -> str:
        """Forwards to TradeRepository.export_csv."""
        return self.trades.export_csv(user_id, limit)
    def backup(self) -> str | None:
        """Erzeugt ein Backup. Forwards to db_backup.create_backup."""
        from app.core.db_backup import create_backup

        return create_backup(get_conn=self._get_conn, config=CONFIG, log=log)

    def verify_backup(self, backup_path: str) -> dict:
        """Forwards to db_backup.verify_backup (sha256 sidecar check)."""
        from app.core.db_backup import verify_backup as _verify

        return _verify(backup_path)

    def save_ai_samples_batch(self, samples):
        """Forwards to AIRepository.save_ai_samples_batch."""
        return self.ai.save_ai_samples_batch(samples)
    def cleanup_old_data(self):
        """Forwards to db_backup.cleanup_old_data (retention sweep)."""
        from app.core.db_backup import cleanup_old_data as _cleanup

        _cleanup(get_conn=self._get_conn, config=CONFIG, log=log)
