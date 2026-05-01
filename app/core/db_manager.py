"""MySQLManager extracted from server.py.

Module-level globals are injected at startup via init_db_manager().
"""

from __future__ import annotations

import csv
import hashlib
import hmac
import io
import json
import logging as _stdlib_logging
import os
import secrets
import threading
from contextlib import contextmanager
from datetime import datetime, timedelta
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

from app.core.time_compat import UTC
from services.encryption import decrypt_value, encrypt_value
from services.passwords import pbkdf2_hash, pbkdf2_verify

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
        try:
            with self._get_conn() as conn:
                with conn.cursor() as c:
                    c.execute(
                        """INSERT INTO trades
                        (user_id,symbol,entry,exit_price,qty,pnl,pnl_pct,reason,
                         confidence,ai_score,win_prob,invested,opened,closed,exchange,
                         regime,trade_type,partial_sold,dca_level,news_score,onchain_score,trade_mode,fees,order_ref)
                        VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
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
                            trade.get("exchange", CONFIG.get("exchange", "cryptocom")),
                            trade.get("regime", "bull"),
                            trade.get("trade_type", "long"),
                            trade.get("partial_sold", 0),
                            trade.get("dca_level", 0),
                            trade.get("news_score", 0),
                            trade.get("onchain_score", 0),
                            trade.get("trade_mode", "paper"),
                            trade.get("fees", 0),
                            trade.get("order_ref", ""),
                        ),
                    )
        except Exception as e:
            log.error(f"save_trade: {e}")

    def save_order(self, order: dict, user_id: int = 1) -> None:
        try:
            with self._get_conn() as conn:
                with conn.cursor() as c:
                    c.execute(
                        """INSERT INTO trade_orders
                        (user_id,symbol,side,order_type,status,price,qty,cost,fees,trade_mode,exchange,exchange_order_id,reason,meta_json)
                        VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                        (
                            user_id,
                            order.get("symbol"),
                            order.get("side", "buy"),
                            order.get("order_type", "market"),
                            order.get("status", "filled"),
                            order.get("price", 0),
                            order.get("qty", 0),
                            order.get("cost", 0),
                            order.get("fees", 0),
                            order.get("trade_mode", "paper"),
                            order.get("exchange", CONFIG.get("exchange", "cryptocom")),
                            str(order.get("exchange_order_id", "")),
                            order.get("reason", ""),
                            json.dumps(order.get("meta", {})),
                        ),
                    )
        except Exception as e:
            log.error(f"save_order: {e}")

    def save_trade_decision(self, decision: dict, user_id: int = 1) -> None:
        try:
            with self._get_conn() as conn:
                with conn.cursor() as c:
                    c.execute(
                        """INSERT INTO trade_decisions
                        (user_id,symbol,decision,reason,confidence,ai_score,win_prob,trade_mode,exchange,payload_json)
                        VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                        (
                            user_id,
                            decision.get("symbol", ""),
                            decision.get("decision", "hold"),
                            decision.get("reason", ""),
                            decision.get("confidence", 0),
                            decision.get("ai_score", 0),
                            decision.get("win_prob", 0),
                            decision.get("trade_mode", "paper"),
                            decision.get("exchange", CONFIG.get("exchange", "cryptocom")),
                            json.dumps(decision.get("payload", {})),
                        ),
                    )
        except Exception as e:
            log.error(f"save_trade_decision: {e}")

    def upsert_trade_position(self, position: dict, user_id: int = 1) -> None:
        try:
            with self._get_conn() as conn:
                with conn.cursor() as c:
                    c.execute(
                        """INSERT INTO trade_positions
                        (user_id,symbol,side,qty,entry_price,invested,stop_loss,take_profit,trade_mode,exchange,status,opened_at,meta_json)
                        VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'open',%s,%s)
                        ON DUPLICATE KEY UPDATE
                        qty=VALUES(qty), entry_price=VALUES(entry_price), invested=VALUES(invested),
                        stop_loss=VALUES(stop_loss), take_profit=VALUES(take_profit),
                        exchange=VALUES(exchange), meta_json=VALUES(meta_json)""",
                        (
                            user_id,
                            position.get("symbol"),
                            position.get("side", "long"),
                            position.get("qty", 0),
                            position.get("entry_price", 0),
                            position.get("invested", 0),
                            position.get("stop_loss", 0),
                            position.get("take_profit", 0),
                            position.get("trade_mode", "paper"),
                            position.get("exchange", CONFIG.get("exchange", "cryptocom")),
                            position.get("opened_at"),
                            json.dumps(position.get("meta", {})),
                        ),
                    )
        except Exception as e:
            log.error(f"upsert_trade_position: {e}")

    def close_trade_position(
        self, symbol: str, trade_mode: str = "paper", user_id: int = 1
    ) -> None:
        try:
            with self._get_conn() as conn:
                with conn.cursor() as c:
                    c.execute(
                        """UPDATE trade_positions
                        SET status='closed', closed_at=NOW()
                        WHERE user_id=%s AND symbol=%s AND trade_mode=%s AND status='open'""",
                        (user_id, symbol, trade_mode),
                    )
        except Exception as e:
            log.error(f"close_trade_position: {e}")

    def load_open_positions(
        self, user_id: int | None = None, trade_mode: str | None = None
    ) -> list[dict]:
        try:
            with self._get_conn() as conn:
                with conn.cursor() as c:
                    q = "SELECT * FROM trade_positions WHERE status='open'"
                    p = []
                    if user_id:
                        q += " AND user_id=%s"
                        p.append(user_id)
                    if trade_mode:
                        q += " AND trade_mode=%s"
                        p.append(trade_mode)
                    q += " ORDER BY opened_at DESC"
                    c.execute(q, p)
                    rows = c.fetchall()
            return [
                self._serialize_dates(dict(r), ("opened_at", "closed_at", "updated_at"))
                for r in rows
            ]
        except Exception as e:
            log.error(f"load_open_positions: {e}")
            return []

    def load_orders(
        self, limit: int = 200, user_id: int | None = None, trade_mode: str | None = None
    ) -> list[dict]:
        try:
            with self._get_conn() as conn:
                with conn.cursor() as c:
                    q = "SELECT * FROM trade_orders"
                    w = []
                    p = []
                    if user_id:
                        w.append("user_id=%s")
                        p.append(user_id)
                    if trade_mode:
                        w.append("trade_mode=%s")
                        p.append(trade_mode)
                    if w:
                        q += " WHERE " + " AND ".join(w)
                    q += " ORDER BY created_at DESC LIMIT %s"
                    p.append(limit)
                    c.execute(q, p)
                    rows = c.fetchall()
            return [self._serialize_dates(dict(r), ("created_at",)) for r in rows]
        except Exception as e:
            log.error(f"load_orders: {e}")
            return []

    def load_trade_decisions(
        self, limit: int = 200, user_id: int | None = None, trade_mode: str | None = None
    ) -> list[dict]:
        try:
            with self._get_conn() as conn:
                with conn.cursor() as c:
                    q = "SELECT * FROM trade_decisions"
                    w = []
                    p = []
                    if user_id:
                        w.append("user_id=%s")
                        p.append(user_id)
                    if trade_mode:
                        w.append("trade_mode=%s")
                        p.append(trade_mode)
                    if w:
                        q += " WHERE " + " AND ".join(w)
                    q += " ORDER BY created_at DESC LIMIT %s"
                    p.append(limit)
                    c.execute(q, p)
                    rows = c.fetchall()
            return [self._serialize_dates(dict(r), ("created_at",)) for r in rows]
        except Exception as e:
            log.error(f"load_trade_decisions: {e}")
            return []

    @staticmethod
    def _serialize_dates(row: dict, fields: tuple[str, ...]) -> dict:
        for f in fields:
            if f in row and hasattr(row[f], "isoformat"):
                row[f] = row[f].isoformat()
        return row

    def performance_breakdown(self, user_id: int | None = None) -> dict:
        try:
            with self._get_conn() as conn:
                with conn.cursor() as c:
                    p = []
                    wu = ""
                    if user_id:
                        wu = "WHERE user_id=%s"
                        p.append(user_id)
                    c.execute(
                        f"""SELECT trade_mode, COUNT(*) AS n, SUM(pnl) AS pnl, SUM(fees) AS fees
                            FROM trades {wu}
                            GROUP BY trade_mode""",
                        p,
                    )
                    by_mode = c.fetchall()
                    c.execute(
                        f"""SELECT exchange, COUNT(*) AS n, SUM(pnl) AS pnl
                            FROM trades {wu}
                            GROUP BY exchange ORDER BY pnl DESC""",
                        p,
                    )
                    by_exchange = c.fetchall()
                    c.execute(
                        f"""SELECT reason, COUNT(*) AS n, SUM(pnl) AS pnl
                            FROM trades {wu}
                            GROUP BY reason ORDER BY pnl DESC LIMIT 50""",
                        p,
                    )
                    by_strategy = c.fetchall()
                    c.execute(
                        f"""SELECT
                                COALESCE(SUM(CASE WHEN trade_mode='paper' THEN pnl END),0) AS paper_pnl,
                                COALESCE(SUM(CASE WHEN trade_mode='live' THEN pnl END),0) AS live_pnl,
                                COALESCE(SUM(CASE WHEN trade_mode='paper' THEN fees END),0) AS paper_fees,
                                COALESCE(SUM(CASE WHEN trade_mode='live' THEN fees END),0) AS live_fees,
                                COALESCE(COUNT(CASE WHEN trade_mode='paper' THEN 1 END),0) AS paper_trades,
                                COALESCE(COUNT(CASE WHEN trade_mode='live' THEN 1 END),0) AS live_trades
                            FROM trades {wu}""",
                        p,
                    )
                    compare = dict(c.fetchone() or {})
            return {
                "by_mode": [dict(r) for r in by_mode],
                "by_exchange": [dict(r) for r in by_exchange],
                "by_strategy": [dict(r) for r in by_strategy],
                "paper_vs_live": compare,
            }
        except Exception as e:
            log.error(f"performance_breakdown: {e}")
            return {"by_mode": [], "by_exchange": [], "by_strategy": [], "paper_vs_live": {}}

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
                h = pbkdf2_hash(pw)
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
            if stored_hash.startswith("pbkdf2$"):
                return pbkdf2_verify(pw, stored_hash)
            # Legacy SHA-256 hashes (migrate users to bcrypt/pbkdf2)
            log.warning("verify_password: SHA-256 Legacy-Hash – Migration empfohlen")
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

    def update_password(self, user_id: int, new_password: str) -> bool:
        """Setzt das Passwort eines Users neu (bcrypt oder SHA-256 Fallback).

        Args:
            user_id: Die User-ID.
            new_password: Das neue Klartext-Passwort.

        Returns:
            True bei Erfolg, False bei Fehler.
        """
        try:
            pw = new_password.encode()
            if BCRYPT_AVAILABLE:
                h = bcrypt.hashpw(pw, bcrypt.gensalt()).decode()
            else:
                h = hashlib.sha256(pw).hexdigest()
            with self._get_conn() as conn:
                with conn.cursor() as c:
                    c.execute("UPDATE users SET password_hash=%s WHERE id=%s", (h, user_id))
            return True
        except Exception as e:
            log.error("update_password(%s): %s", user_id, e)
            return False

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
                        (_jdumps(settings), user_id),
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
                try:
                    settings = _jloads(row["settings_json"])
                    return settings if isinstance(settings, dict) else {}
                except (json.JSONDecodeError, TypeError):
                    log.warning(f"get_user_settings({user_id}): invalid JSON in settings_json")
                    return {}
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
        if not JWT_AVAILABLE:
            return secrets.token_urlsafe(32)
        payload = {
            "sub": user_id,
            "label": label,
            "exp": datetime.now(UTC) + timedelta(hours=CONFIG.get("jwt_expiry_hours", 24)),
            "iat": datetime.now(UTC),
        }
        token = pyjwt.encode(payload, CONFIG.get("jwt_secret", ""), algorithm="HS256")
        try:
            with self._get_conn() as conn:
                with conn.cursor() as c:
                    c.execute(
                        "INSERT INTO api_tokens (user_id,token,label,expires_at) VALUES(%s,%s,%s,%s)",
                        (
                            user_id,
                            token[:500],
                            label,
                            datetime.now(UTC) + timedelta(hours=CONFIG.get("jwt_expiry_hours", 24)),
                        ),
                    )
        except Exception as e:
            log.error(f"create_token: {e}")
        return token

    def verify_api_token(self, token: str) -> int | None:
        if not JWT_AVAILABLE or not token:
            return None
        try:
            payload = pyjwt.decode(
                token,
                CONFIG.get("jwt_secret", ""),
                algorithms=["HS256"],
                options={"require": ["exp"]},
            )
            sub = payload.get("sub")
            return int(sub) if sub is not None else None
        except pyjwt.ExpiredSignatureError:
            log.info("verify_api_token: Token abgelaufen")
            return None
        except pyjwt.InvalidTokenError as exc:
            log.debug("verify_api_token: ungültig (%s)", exc)
            return None
        except Exception as exc:
            log.warning("verify_api_token: %s", exc)
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
