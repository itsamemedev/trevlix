"""
╔══════════════════════════════════════════════════════════════╗
║  TREVLIX – Database Connection Pool                          ║
║  Thread-sicheres Connection-Pooling für MySQL                ║
╚══════════════════════════════════════════════════════════════╝

Ersetzt das bisherige "neue Verbindung pro Aufruf"-Muster durch
einen wiederverwendbaren Pool mit konfigurierbarer Größe.

Verwendung:
    from services.db_pool import ConnectionPool

    pool = ConnectionPool(host=..., port=..., ...)
    conn = pool.acquire()
    try:
        with conn.cursor() as c:
            c.execute(...)
    finally:
        pool.release(conn)

    # Oder als Context-Manager:
    with pool.connection() as conn:
        with conn.cursor() as c:
            c.execute(...)
"""

import logging
import threading
from contextlib import contextmanager

log = logging.getLogger("DBPool")

try:
    import pymysql
    import pymysql.cursors

    _PYMYSQL_AVAILABLE = True
except ImportError:
    _PYMYSQL_AVAILABLE = False


class _PooledConnection:
    """
    Proxy-Wrapper um eine pymysql-Verbindung.
    Leitet close() an den Pool weiter statt die Verbindung zu schließen.
    Alle anderen Attribute/Methoden werden transparent delegiert.
    Dadurch können alle bestehenden conn.close()-Aufrufe unverändert bleiben.
    """

    __slots__ = ("_conn", "_pool")

    def __init__(self, conn, pool: "ConnectionPool"):
        object.__setattr__(self, "_conn", conn)
        object.__setattr__(self, "_pool", pool)

    def __getattr__(self, name: str):
        return getattr(object.__getattribute__(self, "_conn"), name)

    def __setattr__(self, name: str, value):
        setattr(object.__getattribute__(self, "_conn"), name, value)

    def close(self) -> None:
        """Gibt die Verbindung zurück in den Pool statt sie zu schließen."""
        pool = object.__getattribute__(self, "_pool")
        conn = object.__getattribute__(self, "_conn")
        pool.release(conn)

    def cursor(self, *args, **kwargs):
        return object.__getattribute__(self, "_conn").cursor(*args, **kwargs)

    def ping(self, *args, **kwargs):
        return object.__getattribute__(self, "_conn").ping(*args, **kwargs)

    def commit(self):
        return object.__getattribute__(self, "_conn").commit()

    def rollback(self):
        return object.__getattribute__(self, "_conn").rollback()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class ConnectionPool:
    """Einfacher thread-sicherer MySQL-Connection-Pool.

    Verwaltet einen Pool aus wiederverwendbaren Datenbankverbindungen und
    verhindert so den Overhead beim Aufbau neuer Verbindungen pro Request.

    Args:
        host: MySQL-Server-Hostname oder IP-Adresse.
        port: MySQL-Server-Port (Standard: 3306).
        user: MySQL-Benutzername.
        password: MySQL-Passwort.
        database: Name der MySQL-Datenbank.
        pool_size: Maximale Anzahl Verbindungen im Pool. Defaults to 5.
        timeout: Sekunden bis Timeout beim Warten auf freie Verbindung. Defaults to 10.

    Example:
        pool = ConnectionPool(host='localhost', port=3306, user='root',
                              password='secret', database='mydb')
        with pool.connection() as conn:
            with conn.cursor() as c:
                c.execute('SELECT 1')
    """

    def __init__(
        self,
        host: str,
        port: int,
        user: str,
        password: str,
        database: str,
        pool_size: int = 5,
        timeout: int = 10,
    ):
        self._config = {
            "host": host,
            "port": port,
            "user": user,
            "password": password,
            "database": database,
            "charset": "utf8mb4",
            "cursorclass": pymysql.cursors.DictCursor if _PYMYSQL_AVAILABLE else None,
            "autocommit": True,
            "connect_timeout": 10,
            "read_timeout": 30,  # [Verbesserung #23] Query-Timeout
            "write_timeout": 30,  # [Verbesserung #23] Query-Timeout
        }
        self._pool_size = pool_size
        self._timeout = timeout
        self._pool: list = []
        self._lock = threading.Lock()
        self._semaphore = threading.Semaphore(pool_size)
        # Pre-fill pool
        for _ in range(pool_size):
            try:
                conn = self._create_connection()
                if conn:
                    self._pool.append(conn)
            except Exception as e:
                log.debug(f"Pool init connection: {e}")

        log.info(f"✅ DB-Pool: {len(self._pool)}/{pool_size} Verbindungen")

    def _create_connection(self):
        if not _PYMYSQL_AVAILABLE:
            return None
        return pymysql.connect(**self._config)

    def _is_alive(self, conn) -> bool:
        """Prüft ob eine Verbindung noch aktiv ist."""
        try:
            conn.ping(reconnect=True)
            return True
        except Exception:
            return False

    def acquire(self, retries: int = 2) -> "_PooledConnection":
        """Gibt eine Verbindung aus dem Pool zurück.

        Wartet bis zu ``self._timeout`` Sekunden auf eine freie Verbindung.
        Durch ``_PooledConnection`` wird ``conn.close()`` transparent an
        ``release()`` weitergeleitet, so dass bestehende close()-Aufrufe
        unverändert bleiben können.

        Args:
            retries: Anzahl der Wiederholungsversuche bei Fehlern. Defaults to 2.
                     Backoff: 0.5s, 1.0s zwischen den Versuchen.

        Returns:
            Eine in ``_PooledConnection`` gewrappte Datenbankverbindung.

        Raises:
            TimeoutError: Wenn kein freier Verbindungsslot im Timeout verfügbar.
            Exception: Wenn die Verbindungserstellung nach allen Retries fehlschlägt.
        """
        last_err = None
        for attempt in range(retries + 1):
            try:
                if not self._semaphore.acquire(timeout=self._timeout):
                    raise TimeoutError("Kein freier DB-Connection-Slot im Timeout")

                with self._lock:
                    while self._pool:
                        conn = self._pool.pop()
                        if self._is_alive(conn):
                            return _PooledConnection(conn, self)

                # Pool leer → neue Verbindung erstellen
                try:
                    conn = self._create_connection()
                    return _PooledConnection(conn, self)
                except Exception as e:
                    self._semaphore.release()
                    raise e
            except Exception as e:
                last_err = e
                if attempt < retries:
                    import time as _time

                    _time.sleep(0.5 * (attempt + 1))  # Backoff: 0.5s, 1.0s
                    log.debug(f"Pool acquire retry {attempt + 1}/{retries}: {e}")
        raise last_err  # type: ignore[misc]

    def release(self, conn) -> None:
        """Gibt eine Verbindung zurück in den Pool."""
        if conn is None:
            self._semaphore.release()
            return
        with self._lock:
            if len(self._pool) < self._pool_size and self._is_alive(conn):
                self._pool.append(conn)
            else:
                try:
                    conn.close()
                except Exception:
                    pass
        self._semaphore.release()

    @contextmanager
    def connection(self):
        """
        Context-Manager für sichere Verbindungsverwaltung.

        Beispiel:
            with pool.connection() as conn:
                with conn.cursor() as c:
                    c.execute(...)
        """
        conn = self.acquire()
        try:
            yield conn
        finally:
            self.release(conn)

    def close_all(self) -> None:
        """Schließt alle Verbindungen im Pool."""
        with self._lock:
            for conn in self._pool:
                try:
                    conn.close()
                except Exception:
                    pass
            self._pool.clear()
        log.info("DB-Pool geschlossen")

    @property
    def pool_size(self) -> int:
        return self._pool_size

    @property
    def available(self) -> int:
        with self._lock:
            return len(self._pool)
