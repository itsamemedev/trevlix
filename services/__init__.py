"""
TREVLIX Services Package
========================
Wiederverwendbare Dienste für Datenbankzugriff, Verschlüsselung, Caching
und externe API-Integrationen.

Verwendung:
    from services.db_pool import ConnectionPool
    from services.encryption import encrypt_value, decrypt_value
    from services.indicator_cache import get_cached, set_cached, invalidate
    from services.cryptopanic import CryptoPanicClient
"""

from .db_pool import ConnectionPool
from .encryption import encrypt_value, decrypt_value, is_encrypted
from .indicator_cache import get_cached, set_cached, invalidate, cache_stats
from .cryptopanic import CryptoPanicClient

__all__ = [
    "ConnectionPool",
    "encrypt_value",
    "decrypt_value",
    "is_encrypted",
    "get_cached",
    "set_cached",
    "invalidate",
    "cache_stats",
    "CryptoPanicClient",
]
