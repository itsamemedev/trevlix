"""
╔══════════════════════════════════════════════════════════════╗
║  TREVLIX – Indicator Cache Service                           ║
║  Verhindert redundante Neuberechnung technischer Indikatoren ║
╚══════════════════════════════════════════════════════════════╝

Cacht berechnete Indikatoren pro Symbol + letztem Timestamp.
Wird die letzte Kerze nicht aktualisiert, wird das Cache-Ergebnis
zurückgegeben statt neu zu berechnen.
"""

import logging
import threading
import time
from typing import Any

import pandas as pd

log = logging.getLogger("IndicatorCache")

# Cache-Eintrag: {"df": pd.DataFrame, "last_ts": str, "created": float}
_cache: dict[str, dict[str, Any]] = {}
_lock = threading.Lock()

# Cache-Lebensdauer in Sekunden – nach dieser Zeit wird immer neu berechnet
CACHE_TTL_SECONDS = 55  # Etwas unter dem Standard-Scan-Interval von 60s

# [Verbesserung #20] LRU-Eviction: Maximale Anzahl Cache-Einträge
MAX_CACHE_SIZE = 200


def get_cached(symbol: str, last_timestamp: Any) -> pd.DataFrame | None:
    """
    Gibt gecachte Indikatoren zurück, falls vorhanden und noch aktuell.

    Args:
        symbol:         Handelspaar, z.B. "BTC/USDT"
        last_timestamp: Zeitstempel der letzten Kerze im OHLCV-DataFrame

    Returns:
        pd.DataFrame wenn Cache-Hit, sonst None
    """
    key = symbol
    ts_str = str(last_timestamp)

    with _lock:
        entry = _cache.get(key)
        if entry is None:
            return None

        # Cache-Treffer nur bei gleichem Timestamp UND innerhalb TTL
        age = time.monotonic() - entry["created"]
        if entry["last_ts"] == ts_str and age < CACHE_TTL_SECONDS:
            return entry["df"]

    return None


def set_cached(symbol: str, last_timestamp: Any, df: pd.DataFrame) -> None:
    """
    Speichert berechnete Indikatoren im Cache.

    Args:
        symbol:         Handelspaar, z.B. "BTC/USDT"
        last_timestamp: Zeitstempel der letzten Kerze
        df:             DataFrame mit berechneten Indikatoren
    """
    key = symbol
    ts_str = str(last_timestamp)

    with _lock:
        _cache[key] = {
            "df": df,
            "last_ts": ts_str,
            "created": time.monotonic(),
        }
        # [Verbesserung #20] LRU-Eviction: älteste Einträge entfernen
        if len(_cache) > MAX_CACHE_SIZE:
            oldest_key = min(_cache, key=lambda k: _cache[k]["created"])
            _cache.pop(oldest_key, None)


def invalidate(symbol: str | None = None) -> None:
    """
    Leert den Cache für ein Symbol oder den gesamten Cache.

    Args:
        symbol: Symbol zum Leeren, oder None für alle
    """
    with _lock:
        if symbol:
            _cache.pop(symbol, None)
        else:
            _cache.clear()


def cache_stats() -> dict[str, Any]:
    """Gibt Cache-Statistiken zurück (für Dashboard/Debugging)."""
    with _lock:
        now = time.monotonic()
        entries = len(_cache)
        fresh = sum(1 for e in _cache.values() if (now - e["created"]) < CACHE_TTL_SECONDS)
        return {
            "total_entries": entries,
            "fresh_entries": fresh,
            "stale_entries": entries - fresh,
            "ttl_seconds": CACHE_TTL_SECONDS,
        }
