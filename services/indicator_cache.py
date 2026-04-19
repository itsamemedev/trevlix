"""
TREVLIX – Indicator Cache Service
===================================
Verhindert redundante Neuberechnung technischer Indikatoren.

Cacht berechnete Indikatoren pro Symbol + letztem Timestamp.
Wird die letzte Kerze nicht aktualisiert, wird das Cache-Ergebnis
zurückgegeben statt neu zu berechnen.

TTL + LRU-Eviction via cachetools.TTLCache — O(1) inserts and lookups,
automatic expiry after CACHE_TTL_SECONDS without manual timestamp checks.
"""

from __future__ import annotations

import logging
import threading
from typing import Any

import pandas as pd
from cachetools import TTLCache

log = logging.getLogger("trevlix.indicator_cache")

# Cache-Lebensdauer in Sekunden — etwas unter dem Standard-Scan-Interval
CACHE_TTL_SECONDS = 55

# Maximum number of symbols kept in cache at once
MAX_CACHE_SIZE = 200

# TTLCache handles both LRU eviction (maxsize) and TTL expiry automatically
_cache: TTLCache[str, dict[str, Any]] = TTLCache(maxsize=MAX_CACHE_SIZE, ttl=CACHE_TTL_SECONDS)
_lock = threading.Lock()


def get_cached(symbol: str, last_timestamp: Any) -> pd.DataFrame | None:
    """Gibt gecachte Indikatoren zurück, falls vorhanden und noch aktuell.

    Cache-Treffer nur wenn Timestamp identisch. TTLCache übernimmt die
    zeitbasierte Expiry automatisch — kein manuelles time.monotonic() nötig.

    Args:
        symbol: Handelspaar, z.B. 'BTC/USDT'.
        last_timestamp: Zeitstempel der letzten Kerze im OHLCV-DataFrame.

    Returns:
        pd.DataFrame mit berechneten Indikatoren bei Cache-Hit, None sonst.
    """
    ts_str = str(last_timestamp)
    with _lock:
        entry = _cache.get(symbol)
        if entry is not None and entry["last_ts"] == ts_str:
            return entry["df"].copy()
    return None


def set_cached(symbol: str, last_timestamp: Any, df: pd.DataFrame) -> None:
    """Speichert berechnete Indikatoren im Cache.

    TTLCache übernimmt LRU-Eviction bei maxsize und automatische Expiry
    nach CACHE_TTL_SECONDS — kein manuelles OrderedDict-Management nötig.

    Args:
        symbol: Handelspaar, z.B. 'BTC/USDT'.
        last_timestamp: Zeitstempel der letzten Kerze im OHLCV-DataFrame.
        df: DataFrame mit allen berechneten technischen Indikatoren.
    """
    ts_str = str(last_timestamp)
    with _lock:
        _cache[symbol] = {"df": df.copy(), "last_ts": ts_str}


def invalidate(symbol: str | None = None) -> None:
    """Leert den Cache für ein Symbol oder den gesamten Cache.

    Args:
        symbol: Symbol zum Leeren (z.B. 'ETH/USDT'), oder None für alle.
    """
    with _lock:
        if symbol:
            _cache.pop(symbol, None)
        else:
            _cache.clear()


def cache_stats() -> dict[str, Any]:
    """Gibt Cache-Statistiken zurück.

    Returns:
        Dict mit Feldern ``total_entries``, ``fresh_entries``,
        ``stale_entries``, ``ttl_seconds`` und ``max_size``.
    """
    with _lock:
        total = len(_cache)
        return {
            "total_entries": total,
            "fresh_entries": total,  # TTLCache auto-expires stale entries on access
            "stale_entries": 0,
            "ttl_seconds": CACHE_TTL_SECONDS,
            "max_size": MAX_CACHE_SIZE,
        }
