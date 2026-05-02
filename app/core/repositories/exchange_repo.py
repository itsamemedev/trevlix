"""User-exchange repository extracted from MySQLManager.

Holds the per-row CRUD for the ``user_exchanges`` table: list/upsert/
toggle/get-enabled/set-primary/delete. Encryption + decryption of
api_key/api_secret/passphrase is delegated to the manager's ``_enc``/
``_dec`` helpers via the back-reference.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.core.db_manager import MySQLManager


def _module():
    from app.core import db_manager as _m

    return _m


class ExchangeRepository:
    """Per-row CRUD for user_exchanges (multi-exchange per user)."""

    def __init__(self, manager: MySQLManager) -> None:
        self._m = manager

    def get_user_exchanges(self, user_id: int) -> list[dict]:
        """Gibt alle Exchange-Konfigurationen eines Users zurück (ohne Keys, nur Flags)."""
        log = _module().log
        try:
            with self._m._get_conn() as conn:
                with conn.cursor() as c:
                    c.execute(
                        "SELECT id, exchange, enabled, is_primary, created_at, "
                        "(api_key IS NOT NULL AND api_key!='') AS has_key, "
                        "(passphrase IS NOT NULL AND passphrase!='') AS has_passphrase "
                        "FROM user_exchanges WHERE user_id=%s "
                        "ORDER BY is_primary DESC, exchange",
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
        """Erstellt oder aktualisiert eine Exchange-Konfiguration für einen User."""
        log = _module().log
        try:
            with self._m._get_conn() as conn:
                with conn.cursor() as c:
                    c.execute(
                        "SELECT id, api_key, api_secret, passphrase "
                        "FROM user_exchanges WHERE user_id=%s AND exchange=%s",
                        (user_id, exchange),
                    )
                    existing = c.fetchone()
                    if existing:
                        enc_key = (
                            self._m._enc(api_key) if api_key else (existing.get("api_key") or "")
                        )
                        enc_secret = (
                            self._m._enc(api_secret)
                            if api_secret
                            else (existing.get("api_secret") or "")
                        )
                        enc_passphrase = (
                            self._m._enc(passphrase)
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
                            "(user_id, exchange, api_key, api_secret, passphrase, "
                            " enabled, is_primary) "
                            "VALUES(%s,%s,%s,%s,%s,%s,%s)",
                            (
                                user_id,
                                exchange,
                                self._m._enc(api_key),
                                self._m._enc(api_secret),
                                self._m._enc(passphrase) if passphrase else "",
                                enabled,
                                is_primary,
                            ),
                        )
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
        log = _module().log
        try:
            with self._m._get_conn() as conn:
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
        log = _module().log
        try:
            with self._m._get_conn() as conn:
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
                d["api_key"] = self._m._dec(d.get("api_key", ""))
                d["api_secret"] = self._m._dec(d.get("api_secret", ""))
                d["passphrase"] = (
                    self._m._dec(d.get("passphrase", "")) if d.get("passphrase") else ""
                )
                result.append(d)
            return result
        except Exception as e:
            log.error(f"get_enabled_exchanges({user_id}): {e}")
            return []

    def set_primary_exchange(self, user_id: int, exchange: str, enable: bool = True) -> bool:
        """Setzt eine vorhandene User-Exchange als primär.

        Transaktion mit ``FOR UPDATE`` verhindert konkurrierende
        Toggle/Primary-Wechsel-Races.
        """
        log = _module().log
        try:
            with self._m._get_conn() as conn:
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
        log = _module().log
        try:
            with self._m._get_conn() as conn:
                with conn.cursor() as c:
                    c.execute(
                        "DELETE FROM user_exchanges WHERE id=%s AND user_id=%s",
                        (exchange_id, user_id),
                    )
            return True
        except Exception as e:
            log.error(f"delete_user_exchange: {e}")
            return False
