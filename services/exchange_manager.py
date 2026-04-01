"""TREVLIX – Exchange Manager Service.

Verwaltet Multi-Exchange-Konfigurationen für Admin und User.
Ermöglicht das gleichzeitige Betreiben mehrerer Exchanges.

Verwendung:
    from services.exchange_manager import ExchangeManager
    mgr = ExchangeManager(db, config)
    exchanges = mgr.get_active_exchanges(user_id=1)
    for name, ex_inst in exchanges:
        balance = ex_inst.fetch_balance()
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any

try:
    import ccxt

    CCXT_AVAILABLE = True
except ImportError:
    CCXT_AVAILABLE = False

from services.encryption import decrypt_value
from services.utils import EXCHANGE_MAP

log = logging.getLogger("trevlix.exchange_manager")


class ExchangeManager:
    """Verwaltet Exchange-Instanzen für Multi-Exchange-Betrieb.

    Cached Exchange-Instanzen pro User/Exchange-Kombination.
    Exchanges ohne expliziten Toggle gelten als deaktiviert.

    Thread-safety note: all cache reads and writes are performed under
    ``self._lock`` to eliminate the TOCTOU (check-then-act) race that
    existed when the lock was only acquired for writes.
    """

    def __init__(self, db_manager, config: dict):
        self._db = db_manager
        self._config = config
        self._instances: dict[str, Any] = {}  # "user_id:exchange" → ccxt instance
        self._lock = threading.Lock()
        self._request_timeout_ms = int(config.get("exchange_timeout_ms", 10000))
        self._max_retries = int(config.get("exchange_retries", 3))
        self._base_backoff = float(config.get("exchange_backoff_base", 0.5))

    def _create_instance(self, exchange_name: str, api_key: str, api_secret: str) -> Any | None:
        """Erstellt eine CCXT Exchange-Instanz.

        Args:
            exchange_name: Name der Exchange (binance, bybit, etc.)
            api_key: Entschlüsselter API-Key.
            api_secret: Entschlüsseltes API-Secret.

        Returns:
            CCXT Exchange-Instanz oder None bei Fehler.
        """
        if not CCXT_AVAILABLE:
            log.error("CCXT nicht installiert")
            return None
        try:
            cls_name = EXCHANGE_MAP.get(exchange_name, exchange_name)
            ex_cls = getattr(ccxt, cls_name, None)
            if ex_cls is None:
                raise ValueError(f"Exchange class '{cls_name}' not found in ccxt")
            return ex_cls(
                {
                    "apiKey": api_key,
                    "secret": api_secret,
                    "enableRateLimit": True,
                    "timeout": self._request_timeout_ms,
                    "options": {"defaultType": "spot"},
                }
            )
        except Exception as e:
            log.error(f"Exchange erstellen fehlgeschlagen ({exchange_name}): {e}")
            return None

    def get_user_exchange(self, user_id: int, exchange_name: str) -> Any | None:
        """Gibt eine cached Exchange-Instanz für einen User zurück.

        The cache check and update are both performed under the same lock
        to prevent the TOCTOU race where two threads could simultaneously
        miss the cache and each create a new instance.

        Args:
            user_id: User-ID.
            exchange_name: Name der Exchange.

        Returns:
            CCXT Exchange-Instanz oder None.
        """
        cache_key = f"{user_id}:{exchange_name}"

        with self._lock:
            if cache_key in self._instances:
                return self._instances[cache_key]

            # Not in cache — load credentials from DB and create instance.
            # Lock is held during DB access to prevent duplicate creation;
            # DB reads are fast (indexed lookup) so this is acceptable.
            exchanges = self._db.get_enabled_exchanges(user_id)
            for ex_data in exchanges:
                if ex_data.get("exchange") == exchange_name:
                    api_key = decrypt_value(ex_data.get("api_key", ""))
                    api_secret = decrypt_value(ex_data.get("api_secret", ""))
                    if not api_key or not api_secret:
                        log.warning(
                            "Exchange %s: API-Schlüssel konnten nicht entschlüsselt werden",
                            exchange_name,
                        )
                        return None
                    inst = self._create_instance(
                        exchange_name,
                        api_key,
                        api_secret,
                    )
                    if inst:
                        self._instances[cache_key] = inst
                    return inst
        return None

    def _call_with_retry(self, exchange_name: str, fn: Any, operation: str) -> Any:
        """Führt einen Exchange-Call mit Retry + exponentiellem Backoff aus."""
        last_exc: Exception | None = None
        for attempt in range(1, self._max_retries + 1):
            try:
                return fn()
            except Exception as exc:
                last_exc = exc
                # Handle klassische Timeout-Signaturen (requests/ccxt/socket)
                timeout_like = isinstance(exc, TimeoutError) or "timeout" in str(exc).lower()
                if CCXT_AVAILABLE and isinstance(exc, ccxt.NetworkError):
                    timeout_like = timeout_like or True
                if CCXT_AVAILABLE and isinstance(exc, ccxt.RequestTimeout):
                    timeout_like = True

                if timeout_like:
                    log.warning(
                        "Exchange timeout (%s/%s) on %s.%s: %s",
                        attempt,
                        self._max_retries,
                        exchange_name,
                        operation,
                        exc,
                    )
                else:
                    log.warning(
                        "Exchange error (%s/%s) on %s.%s: %s",
                        attempt,
                        self._max_retries,
                        exchange_name,
                        operation,
                        exc,
                    )

                if attempt >= self._max_retries:
                    break

                sleep_seconds = self._base_backoff * (2 ** (attempt - 1))
                time.sleep(sleep_seconds)

        assert last_exc is not None
        raise last_exc

    def get_active_exchanges(self, user_id: int) -> list[tuple[str, Any]]:
        """Gibt alle aktivierten Exchange-Instanzen eines Users zurück.

        Args:
            user_id: User-ID.

        Returns:
            Liste von (exchange_name, ccxt_instance) Tupeln.
        """
        exchanges = self._db.get_enabled_exchanges(user_id)
        result: list[tuple[str, Any]] = []

        for ex_data in exchanges:
            name = ex_data.get("exchange", "unknown")
            cache_key = f"{user_id}:{name}"

            with self._lock:
                if cache_key in self._instances:
                    result.append((name, self._instances[cache_key]))
                    continue

                # Not cached — create under lock to avoid duplicate instances
                inst = self._create_instance(
                    name,
                    decrypt_value(ex_data.get("api_key", "")),
                    decrypt_value(ex_data.get("api_secret", "")),
                )
                if inst:
                    self._instances[cache_key] = inst
                    result.append((name, inst))

        return result

    def get_admin_exchange(self) -> Any | None:
        """Erstellt eine Exchange-Instanz aus der globalen CONFIG (.env).

        Returns:
            CCXT Exchange-Instanz für den Admin.
        """
        raw_key = self._config.get("api_key", "")
        raw_sec = self._config.get("secret", "")
        api_key = (
            decrypt_value(raw_key.reveal() if hasattr(raw_key, "reveal") else raw_key)
            if raw_key
            else ""
        )
        api_secret = (
            decrypt_value(raw_sec.reveal() if hasattr(raw_sec, "reveal") else raw_sec)
            if raw_sec
            else ""
        )
        return self._create_instance(
            self._config.get("exchange", "cryptocom"),
            api_key,
            api_secret,
        )

    def invalidate_cache(self, user_id: int, exchange_name: str | None = None) -> None:
        """Invalidiert den Cache für einen User (z.B. nach API-Key-Update).

        Args:
            user_id: User-ID.
            exchange_name: Optional spezifische Exchange. None = alle.
        """
        with self._lock:
            if exchange_name:
                self._instances.pop(f"{user_id}:{exchange_name}", None)
            else:
                keys_to_remove = [k for k in self._instances if k.startswith(f"{user_id}:")]
                for k in keys_to_remove:
                    del self._instances[k]

    def get_all_balances(self, user_id: int) -> dict[str, dict]:
        """Aggregiert Balances über alle aktivierten Exchanges eines Users.

        Args:
            user_id: User-ID.

        Returns:
            Dict: {exchange_name: {"total": {...}, "free": {...}}} oder Fehler.
        """
        result: dict[str, dict] = {}
        for name, inst in self.get_active_exchanges(user_id):
            try:
                bal = self._call_with_retry(name, inst.fetch_balance, "fetch_balance") or {}
                result[name] = {
                    "total": {
                        k: float(v)
                        for k, v in (bal.get("total") or {}).items()
                        if isinstance(v, (int, float)) and v > 0
                    },
                    "free": {
                        k: float(v)
                        for k, v in (bal.get("free") or {}).items()
                        if isinstance(v, (int, float)) and v > 0
                    },
                }
            except Exception as e:
                log.exception("Balance-Abruf fehlgeschlagen für %s", name)
                err_msg = str(e).strip() or "Unbekannter Fehler"
                if "timeout" in err_msg.lower():
                    err_msg = (
                        "Exchange-Antwort dauerte zu lange. Bitte später erneut versuchen."
                    )
                result[name] = {"error": err_msg}
        return result
