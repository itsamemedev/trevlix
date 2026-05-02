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


import numpy as np
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
    def __init__(self):
        from app.core.repositories.user_repo import UserRepository

        self._lock = threading.Lock()
        self._pool: ConnectionPool | None = None
        self.db_available = False  # [Verbesserung #3] Flag für Degraded-Mode
        # Per-domain repositories (composition over inheritance).
        # The manager keeps thin delegation wrappers on its public API
        # so existing callers (db.get_user(), db.create_user(), …) keep
        # working unchanged.
        self.users = UserRepository(self)
        from app.core.repositories.trade_repo import TradeRepository

        self.trades = TradeRepository(self)
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
            X: list = []
            y: list = []
            regimes: list = []
            for r in rows:
                try:
                    feats = json.loads(r.get("features", "[]"))
                    if not isinstance(feats, list):
                        continue
                    X.append(np.array(feats, dtype=np.float32))
                    y.append(r.get("label", 0))
                    regimes.append(r.get("regime", "range"))
                except (json.JSONDecodeError, ValueError, TypeError):
                    log.warning("load_ai_samples: skipping row with invalid features")
                    continue
            return X, y, regimes
        except Exception as e:
            log.error(f"load_ai_samples: {e}")
            return [], [], []

    # ── Users ───────────────────────────────────────────────────────────────
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
        """Gibt alle Exchange-Konfigurationen eines Users zurück (ohne Keys, nur Flags)."""
        try:
            with self._get_conn() as conn:
                with conn.cursor() as c:
                    c.execute(
                        "SELECT id, exchange, enabled, is_primary, created_at, "
                        "(api_key IS NOT NULL AND api_key!='') AS has_key, "
                        "(passphrase IS NOT NULL AND passphrase!='') AS has_passphrase "
                        "FROM user_exchanges WHERE user_id=%s ORDER BY is_primary DESC, exchange",
                        (user_id,),
                    )
                    rows = c.fetchall()
            result = []
            for r in rows:
                d = dict(r)
                if d.get("created_at") and hasattr(d["created_at"], "isoformat"):
                    d["created_at"] = d["created_at"].isoformat()
                d["has_key"] = bool(d.get("has_key"))
                d["has_passphrase"] = bool(d.get("has_passphrase"))
                # Für Dashboard-Chip-Zählung: api_key-Feld weiterhin als Indikator
                d["api_key"] = "***" if d["has_key"] else ""
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
        passphrase: str = "",
    ) -> bool:
        """Erstellt oder aktualisiert eine Exchange-Konfiguration für einen User.

        Neue Exchanges sind standardmäßig deaktiviert (enabled=False).
        """
        try:
            with self._get_conn() as conn:
                with conn.cursor() as c:
                    # Prüfe ob Exchange schon existiert
                    c.execute(
                        "SELECT id, api_key, api_secret, passphrase "
                        "FROM user_exchanges WHERE user_id=%s AND exchange=%s",
                        (user_id, exchange),
                    )
                    existing = c.fetchone()
                    if existing:
                        enc_key = self._enc(api_key) if api_key else (existing.get("api_key") or "")
                        enc_secret = (
                            self._enc(api_secret)
                            if api_secret
                            else (existing.get("api_secret") or "")
                        )
                        enc_passphrase = (
                            self._enc(passphrase)
                            if passphrase
                            else (existing.get("passphrase") or "")
                        )
                        c.execute(
                            "UPDATE user_exchanges SET api_key=%s, api_secret=%s, "
                            "passphrase=%s, enabled=%s, is_primary=%s WHERE id=%s",
                            (
                                enc_key,
                                enc_secret,
                                enc_passphrase,
                                enabled,
                                is_primary,
                                existing["id"],
                            ),
                        )
                    else:
                        c.execute(
                            "INSERT INTO user_exchanges "
                            "(user_id, exchange, api_key, api_secret, passphrase, enabled, is_primary) "
                            "VALUES(%s,%s,%s,%s,%s,%s,%s)",
                            (
                                user_id,
                                exchange,
                                self._enc(api_key),
                                self._enc(api_secret),
                                self._enc(passphrase) if passphrase else "",
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
                        "SELECT * FROM user_exchanges WHERE user_id=%s AND enabled=1 "
                        "ORDER BY is_primary DESC, id ASC",
                        (user_id,),
                    )
                    rows = c.fetchall()
            result = []
            for r in rows:
                d = dict(r)
                d["api_key"] = self._dec(d.get("api_key", ""))
                d["api_secret"] = self._dec(d.get("api_secret", ""))
                d["passphrase"] = self._dec(d.get("passphrase", "")) if d.get("passphrase") else ""
                result.append(d)
            return result
        except Exception as e:
            log.error(f"get_enabled_exchanges({user_id}): {e}")
            return []

    def set_primary_exchange(self, user_id: int, exchange: str, enable: bool = True) -> bool:
        """Setzt eine vorhandene User-Exchange als primär (optional inkl. Aktivierung).

        Alle Statements laufen in einer Transaktion mit ``FOR UPDATE``-Lock
        auf der Ziel-Zeile, damit konkurrierende Calls (z.B. paralleler
        Toggle + Primary-Wechsel) nicht zu zwei `is_primary=1`-Zeilen oder
        verwaisten Flags führen können.
        """
        conn = None
        try:
            with self._get_conn() as conn:
                # Innerhalb der Transaktion autocommit aus, damit ROLLBACK
                # bei Fehlern alle Updates rückgängig macht.
                conn.autocommit(False)
                try:
                    with conn.cursor() as c:
                        c.execute(
                            "SELECT id FROM user_exchanges "
                            "WHERE user_id=%s AND exchange=%s LIMIT 1 FOR UPDATE",
                            (user_id, exchange),
                        )
                        row = c.fetchone()
                        if not row:
                            conn.rollback()
                            return False
                        if enable:
                            c.execute(
                                "UPDATE user_exchanges SET enabled=1 "
                                "WHERE user_id=%s AND exchange=%s",
                                (user_id, exchange),
                            )
                        c.execute(
                            "UPDATE user_exchanges SET is_primary=0 WHERE user_id=%s",
                            (user_id,),
                        )
                        c.execute(
                            "UPDATE user_exchanges SET is_primary=1 "
                            "WHERE user_id=%s AND exchange=%s",
                            (user_id, exchange),
                        )
                    conn.commit()
                    return True
                except Exception:
                    conn.rollback()
                    raise
                finally:
                    conn.autocommit(True)
        except Exception as e:
            log.error(f"set_primary_exchange({user_id}, {exchange}): {e}")
            return False

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
        """Forwards to UserRepository.create_api_token."""
        return self.users.create_api_token(user_id, label)
    def verify_api_token(self, token: str) -> int | None:
        """Forwards to UserRepository.verify_api_token."""
        return self.users.verify_api_token(token)
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
                    c.execute("SELECT * FROM price_alerts WHERE triggered=0 LIMIT 500")
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

    def delete_alert(self, aid: int, user_id: int | None = None) -> bool:
        """Delete a price alert.

        If ``user_id`` is given, the delete is scoped to that user so a
        caller cannot delete another user's alert (IDOR protection).
        Returns True if a row was deleted.
        """
        try:
            with self._get_conn() as conn:
                with conn.cursor() as c:
                    if user_id is not None:
                        c.execute(
                            "DELETE FROM price_alerts WHERE id=%s AND user_id=%s",
                            (aid, user_id),
                        )
                    else:
                        c.execute("DELETE FROM price_alerts WHERE id=%s", (aid,))
                    return bool(c.rowcount)
        except Exception as e:
            log.error(f"delete_alert({aid}): {e}")
            return False

    def get_all_alerts(self, user_id: int | None = None) -> list[dict]:
        """Return recent price alerts.

        If ``user_id`` is provided the result is scoped to that user so
        shared snapshots do not leak other users' watchlists.
        """
        try:
            with self._get_conn() as conn:
                with conn.cursor() as c:
                    if user_id is not None:
                        c.execute(
                            "SELECT * FROM price_alerts WHERE user_id=%s "
                            "ORDER BY created_at DESC LIMIT 50",
                            (user_id,),
                        )
                    else:
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
        """Forwards to db_backup.cleanup_old_data (retention sweep)."""
        from app.core.db_backup import cleanup_old_data as _cleanup

        _cleanup(get_conn=self._get_conn, config=CONFIG, log=log)
