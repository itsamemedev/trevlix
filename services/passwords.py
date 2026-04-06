"""Password-Hashing Utilities (PBKDF2)."""

from __future__ import annotations

import hashlib
import hmac
import secrets


def pbkdf2_hash(password: bytes, salt: bytes | None = None) -> str:
    """Erstellt einen PBKDF2-Hash im Format ``pbkdf2$<salt_hex>$<digest_hex>``."""
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password, salt, 600_000)
    return f"pbkdf2${salt.hex()}${digest.hex()}"


def pbkdf2_verify(password: bytes, stored: str) -> bool:
    """Verifiziert einen PBKDF2-Hash aus ``pbkdf2_hash``."""
    try:
        algo, salt_hex, hash_hex = stored.split("$", 2)
        if algo != "pbkdf2":
            return False
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(hash_hex)
        cand = hashlib.pbkdf2_hmac("sha256", password, salt, 600_000)
        return hmac.compare_digest(cand, expected)
    except Exception:
        return False
