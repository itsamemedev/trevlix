"""User repository extracted from MySQLManager.

Holds the per-row CRUD for the ``users`` table plus the JWT-backed
``api_tokens`` table. All methods are dependency-injected through the
``MySQLManager`` reference passed at construction so encryption,
connection-pool, and module-global feature flags (BCRYPT_AVAILABLE,
JWT_AVAILABLE) stay in one place.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

from app.core.time_compat import UTC
from services.passwords import pbkdf2_hash, pbkdf2_verify

if TYPE_CHECKING:
    from app.core.db_manager import MySQLManager


def _module():
    """Return ``app.core.db_manager`` for late binding to its globals."""
    from app.core import db_manager as _m

    return _m


class UserRepository:
    """Per-row CRUD for users, settings, API keys, and JWT tokens."""

    def __init__(self, manager: MySQLManager) -> None:
        self._m = manager

    # ── Read ────────────────────────────────────────────────────────────────
    def _decrypt_user_keys(self, user: dict | None) -> dict | None:
        """Entschlüsselt API-Key/Secret eines User-Dicts nach dem Laden aus der DB."""
        if not user:
            return user
        if user.get("api_key"):
            user["api_key"] = self._m._dec(user["api_key"])
        if user.get("api_secret"):
            user["api_secret"] = self._m._dec(user["api_secret"])
        return user

    def get_user(self, username: str) -> dict[str, Any] | None:
        """Lädt einen Benutzer anhand des Benutzernamens."""
        log = _module().log
        try:
            with self._m._get_conn() as conn:
                with conn.cursor() as c:
                    c.execute("SELECT * FROM users WHERE username=%s", (username,))
                    row = c.fetchone()
            return self._decrypt_user_keys(dict(row)) if row else None
        except Exception as e:
            log.error(f"get_user({username!r}): {e}")
            return None

    def get_user_by_id(self, uid: int) -> dict[str, Any] | None:
        """Lädt einen Benutzer anhand der ID."""
        log = _module().log
        try:
            with self._m._get_conn() as conn:
                with conn.cursor() as c:
                    c.execute("SELECT * FROM users WHERE id=%s", (uid,))
                    row = c.fetchone()
            return self._decrypt_user_keys(dict(row)) if row else None
        except Exception as e:
            log.error(f"get_user_by_id({uid}): {e}")
            return None

    def get_all_users(self) -> list[dict[str, Any]]:
        """Lädt alle Benutzer (ohne sensible Keys)."""
        log = _module().log
        try:
            with self._m._get_conn() as conn:
                with conn.cursor() as c:
                    c.execute(
                        "SELECT id,username,role,balance,initial_balance,exchange,"
                        "created_at,last_login FROM users"
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

    # ── Create / Update ─────────────────────────────────────────────────────
    def create_user(
        self, username: str, password: str, role: str = "user", balance: float = 10000.0
    ) -> bool:
        m = _module()
        log = m.log
        try:
            pw = password.encode()
            if m.BCRYPT_AVAILABLE:
                h = m.bcrypt.hashpw(pw, m.bcrypt.gensalt()).decode()
            else:
                h = pbkdf2_hash(pw)
            with self._m._get_conn() as conn:
                with conn.cursor() as c:
                    c.execute(
                        "INSERT INTO users (username,password_hash,role,balance,initial_balance) "
                        "VALUES(%s,%s,%s,%s,%s)",
                        (username, h, role, balance, balance),
                    )
            return True
        except Exception as e:
            log.error(f"create_user: {e}")
            return False

    def verify_password(self, stored_hash: str, password: str) -> bool:
        """Verifiziert ein Passwort gegen den gespeicherten Hash."""
        m = _module()
        log = m.log
        try:
            pw = password.encode()
            if m.BCRYPT_AVAILABLE and stored_hash.startswith("$2"):
                # bcrypt hashes start with $2a$, $2b$, $2y$
                return m.bcrypt.checkpw(pw, stored_hash.encode())
            if stored_hash.startswith("pbkdf2$"):
                return pbkdf2_verify(pw, stored_hash)
            log.warning("verify_password: SHA-256 Legacy-Hash – Migration empfohlen")
            return hmac.compare_digest(hashlib.sha256(pw).hexdigest(), stored_hash)
        except Exception:
            return False

    def update_user_login(self, user_id: int) -> None:
        """Aktualisiert den last_login Timestamp eines Users."""
        log = _module().log
        try:
            with self._m._get_conn() as conn:
                with conn.cursor() as c:
                    c.execute("UPDATE users SET last_login=NOW() WHERE id=%s", (user_id,))
        except Exception as e:
            log.warning(f"update_user_login({user_id}): {e}")

    def update_password(self, user_id: int, new_password: str) -> bool:
        """Setzt das Passwort eines Users neu."""
        m = _module()
        log = m.log
        try:
            pw = new_password.encode()
            if m.BCRYPT_AVAILABLE:
                h = m.bcrypt.hashpw(pw, m.bcrypt.gensalt()).decode()
            else:
                h = hashlib.sha256(pw).hexdigest()
            with self._m._get_conn() as conn:
                with conn.cursor() as c:
                    c.execute("UPDATE users SET password_hash=%s WHERE id=%s", (h, user_id))
            return True
        except Exception as e:
            log.error("update_password(%s): %s", user_id, e)
            return False

    def update_user_balance(self, user_id: int, balance: float) -> None:
        """Aktualisiert den Kontostand eines Users."""
        log = _module().log
        try:
            with self._m._get_conn() as conn:
                with conn.cursor() as c:
                    c.execute("UPDATE users SET balance=%s WHERE id=%s", (balance, user_id))
        except Exception as e:
            log.error(f"update_user_balance({user_id}, {balance}): {e}")

    # ── Settings ────────────────────────────────────────────────────────────
    def update_user_settings(self, user_id: int, settings: dict) -> bool:
        """Speichert User-Settings als JSON in der DB."""
        m = _module()
        log = m.log
        try:
            with self._m._get_conn() as conn:
                with conn.cursor() as c:
                    c.execute(
                        "UPDATE users SET settings_json=%s WHERE id=%s",
                        (m._jdumps(settings), user_id),
                    )
            return True
        except Exception as e:
            log.error(f"update_user_settings: {e}")
            return False

    def get_user_settings(self, user_id: int) -> dict:
        """Lädt User-Settings aus der DB."""
        m = _module()
        log = m.log
        try:
            with self._m._get_conn() as conn:
                with conn.cursor() as c:
                    c.execute("SELECT settings_json FROM users WHERE id=%s", (user_id,))
                    row = c.fetchone()
            if row and row.get("settings_json"):
                try:
                    settings = m._jloads(row["settings_json"])
                    return settings if isinstance(settings, dict) else {}
                except (json.JSONDecodeError, TypeError):
                    log.warning(
                        f"get_user_settings({user_id}): invalid JSON in settings_json"
                    )
                    return {}
            return {}
        except Exception as e:
            log.error(f"get_user_settings({user_id}): {e}")
            return {}

    # ── API keys ────────────────────────────────────────────────────────────
    def update_user_api_keys(
        self, user_id: int, exchange: str, api_key: str, api_secret: str
    ) -> bool:
        """Speichert verschlüsselte API-Keys für einen User."""
        log = _module().log
        try:
            with self._m._get_conn() as conn:
                with conn.cursor() as c:
                    c.execute(
                        "UPDATE users SET exchange=%s, api_key=%s, api_secret=%s WHERE id=%s",
                        (
                            exchange,
                            self._m._enc(api_key),
                            self._m._enc(api_secret),
                            user_id,
                        ),
                    )
            return True
        except Exception as e:
            log.error(f"update_user_api_keys: {e}")
            return False

    # ── JWT API tokens ──────────────────────────────────────────────────────
    def create_api_token(self, user_id: int, label: str = "default") -> str:
        m = _module()
        log = m.log
        if not m.JWT_AVAILABLE:
            return secrets.token_urlsafe(32)
        cfg = m.CONFIG
        payload = {
            "sub": user_id,
            "label": label,
            "exp": datetime.now(UTC) + timedelta(hours=cfg.get("jwt_expiry_hours", 24)),
            "iat": datetime.now(UTC),
        }
        token = m.pyjwt.encode(payload, cfg.get("jwt_secret", ""), algorithm="HS256")
        try:
            with self._m._get_conn() as conn:
                with conn.cursor() as c:
                    c.execute(
                        "INSERT INTO api_tokens (user_id,token,label,expires_at) "
                        "VALUES(%s,%s,%s,%s)",
                        (
                            user_id,
                            token[:500],
                            label,
                            datetime.now(UTC)
                            + timedelta(hours=cfg.get("jwt_expiry_hours", 24)),
                        ),
                    )
        except Exception as e:
            log.error(f"create_token: {e}")
        return token

    def verify_api_token(self, token: str) -> int | None:
        m = _module()
        log = m.log
        if not m.JWT_AVAILABLE or not token:
            return None
        try:
            payload = m.pyjwt.decode(
                token,
                m.CONFIG.get("jwt_secret", ""),
                algorithms=["HS256"],
                options={"require": ["exp"]},
            )
            sub = payload.get("sub")
            return int(sub) if sub is not None else None
        except m.pyjwt.ExpiredSignatureError:
            log.info("verify_api_token: Token abgelaufen")
            return None
        except m.pyjwt.InvalidTokenError as exc:
            log.debug("verify_api_token: ungültig (%s)", exc)
            return None
        except Exception as exc:
            log.warning("verify_api_token: %s", exc)
            return None
