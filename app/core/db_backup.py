"""Backup, verification and retention helpers extracted from db_manager.

Three operations that are mostly disk I/O and table dumps – no
``MySQLManager``-specific state besides "give me a pooled connection".
Pulling them out keeps ``MySQLManager`` focused on transactional
single-row CRUD and avoids growing the class beyond manageability.

Each function takes its dependencies as keyword arguments so unit
tests can pass a mock connection-context-manager.
"""

from __future__ import annotations

import hashlib
import json
import os
import zipfile
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any

from services.encryption import decrypt_value, encrypt_value

# Whitelist of tables included in the JSON dump. Anything else (auth
# tokens, encrypted user_exchanges, healing incidents, ...) is excluded
# so an exfiltrated backup is less catastrophic.
_ALLOWED_TABLES: frozenset[str] = frozenset(
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

# Config keys that must never reach ``config.json`` inside the archive.
_BACKUP_SENSITIVE_KEYS: frozenset[str] = frozenset(
    {
        "api_key",
        "secret",
        "mysql_pass",
        "admin_password",
        "jwt_secret",
        "short_api_key",
        "short_secret",
        "cryptopanic_token",
        "telegram_token",
        "discord_webhook",
    }
)


def create_backup(
    *,
    get_conn: Callable[[], Any],
    config: dict[str, Any],
    log,
) -> str | None:
    """Dump whitelisted tables + scrubbed CONFIG into a ZIP, prune old.

    Args:
        get_conn: Zero-arg callable that returns a context-manager
            yielding a pooled connection. Typically ``self._get_conn``
            from ``MySQLManager``.
        config: Runtime config dict. Keys ``backup_dir``,
            ``backup_keep_days``, and ``backup_encrypt`` are honoured.
        log: Standard logger.

    Returns:
        The path to the produced backup file (``.zip`` or
        ``.zip.enc`` if encryption was enabled), or ``None`` on
        catastrophic failure.
    """
    try:
        bdir = config.get("backup_dir", "backups")
        os.makedirs(bdir, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M")
        path = os.path.join(bdir, f"trevlix_backup_{ts}.zip")

        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
            for table in _ALLOWED_TABLES:
                try:
                    with get_conn() as conn:
                        with conn.cursor() as c:
                            # Table name comes from the allowlist, not user input.
                            c.execute(f"SELECT * FROM `{table}` LIMIT 100000")  # noqa: S608
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
                    log.debug("Backup %s: %s", table, te)
            safe_cfg = {k: v for k, v in config.items() if k not in _BACKUP_SENSITIVE_KEYS}
            zf.writestr("config.json", json.dumps(safe_cfg, indent=2, ensure_ascii=False))

        # Retention sweep
        cutoff = datetime.now() - timedelta(days=config.get("backup_keep_days", 30))
        for fn in os.listdir(bdir):
            fp = os.path.join(bdir, fn)
            if os.path.getmtime(fp) < cutoff.timestamp():
                try:
                    os.remove(fp)
                except Exception:
                    pass

        # SHA-256 sidecar before optional encryption
        try:
            with open(path, "rb") as f:
                raw_zip = f.read()
            checksum = hashlib.sha256(raw_zip).hexdigest()
            sha_path = path + ".sha256"
            with open(sha_path, "w") as f:
                f.write(f"{checksum}  {os.path.basename(path)}\n")
            log.debug("SHA-256 gespeichert: %s", sha_path)
        except Exception as sha_err:
            log.debug("Backup-Checksum: %s", sha_err)

        if config.get("backup_encrypt") and path:
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
                log.debug("Backup-Verschlüsselung: %s", enc_err)

        log.info("✅ Backup: %s", path)
        return path
    except Exception as e:
        log.error("Backup: %s", e)
        return None


def verify_backup(backup_path: str) -> dict[str, Any]:
    """Verify a backup against its sidecar SHA-256 (handles .enc files).

    For ``.enc`` backups, the original ``.zip`` checksum is the source
    of truth; the function decrypts in-memory and re-hashes to
    compare. No ``log`` argument is needed because every result path
    fills ``result["error"]``.
    """
    result: dict[str, Any] = {
        "ok": False,
        "error": None,
        "checksum": None,
        "path": backup_path,
    }
    try:
        zip_path = backup_path.replace(".enc", "")
        sha_path = zip_path + ".sha256"
        if not os.path.exists(backup_path):
            result["error"] = "Backup-Datei nicht gefunden"
            return result
        try:
            with open(sha_path) as f:
                parts = f.read().split()
        except FileNotFoundError:
            result["error"] = "Keine .sha256-Datei vorhanden"
            return result
        if not parts:
            result["error"] = "SHA256-Datei ist leer"
            return result
        stored = parts[0]
        result["checksum"] = stored

        if backup_path.endswith(".enc"):
            try:
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
            result["error"] = (
                f"Checksum mismatch: {actual[:16]}... ≠ {stored[:16]}..."
            )
    except Exception as e:
        result["error"] = str(e)
    return result


def cleanup_old_data(
    *,
    get_conn: Callable[[], Any],
    config: dict[str, Any],
    log,
) -> None:
    """Apply retention policies to ``audit_log`` and ``ai_training``."""
    try:
        with get_conn() as conn:
            with conn.cursor() as c:
                audit_days = config.get("audit_retention_days", 90)
                c.execute(
                    "DELETE FROM audit_log WHERE created_at < NOW() - INTERVAL %s DAY",
                    (audit_days,),
                )
                deleted_audit = c.rowcount

                ai_days = config.get("ai_sample_retention_days", 180)
                c.execute(
                    "DELETE FROM ai_training WHERE created_at < NOW() - INTERVAL %s DAY",
                    (ai_days,),
                )
                deleted_ai = c.rowcount
        if deleted_audit or deleted_ai:
            log.info(
                "🧹 Data Retention: %s Audit-Logs, %s AI-Samples bereinigt",
                deleted_audit,
                deleted_ai,
            )
    except Exception as e:
        log.debug("cleanup_old_data: %s", e)
