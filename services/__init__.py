"""
TREVLIX Services Package
========================
Wiederverwendbare Dienste für Datenbankzugriff, Verschlüsselung und Caching.

Verwendung:
    from services.db_pool import ConnectionPool
    from services.encryption import encrypt_value, decrypt_value
    from services.indicator_cache import get_cached, set_cached, invalidate
"""

from .db_pool import ConnectionPool
from .encryption import encrypt_value, decrypt_value, is_encrypted
from .indicator_cache import get_cached, set_cached, invalidate, cache_stats

__all__ = [
    "ConnectionPool",
    "encrypt_value",
    "decrypt_value",
    "is_encrypted",
    "get_cached",
    "set_cached",
    "invalidate",
    "cache_stats",
]
