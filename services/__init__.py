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
from .encryption import decrypt_value, encrypt_value, is_encrypted
from .indicator_cache import cache_stats, get_cached, invalidate, set_cached
from .virginie import (
    ActionResult,
    LLMPerformanceTracker,
    LLMResult,
    Opportunity,
    ProfitDecisionEngine,
    VirginieCore,
    VirginieGuardrails,
    VirginieIdentity,
)

# CryptoPanicClient erfordert httpx – optionaler Import damit Tests ohne
# httpx weiterhin funktionieren, wenn sie nur andere Services benötigen.
try:
    from .cryptopanic import CryptoPanicClient
except ImportError:
    CryptoPanicClient = None  # type: ignore[assignment,misc]

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
    "VirginieIdentity",
    "VirginieGuardrails",
    "Opportunity",
    "ActionResult",
    "ProfitDecisionEngine",
    "LLMResult",
    "LLMPerformanceTracker",
    "VirginieCore",
]
