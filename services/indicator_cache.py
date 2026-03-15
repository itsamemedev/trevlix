"""
TREVLIX – Indicator Cache Service
===================================
Verhindert redundante Neuberechnung technischer Indikatoren.

Cacht berechnete Indikatoren pro Symbol + letztem Timestamp.
Wird die letzte Kerze nicht aktualisiert, wird das Cache-Ergebnis
zurückgegeben statt neu zu berechnen.

LRU eviction via collections.OrderedDict: O(1) move-to-end on hit,
O(1) popitem(last=False) on size overflow — previously O(n) min() scan.
"""

import logging
import threading
import time
from collections import OrderedDict
from typing import Any

import pandas as pd

log = logging.getLogger("trevlix.indicator_cache")

# Cache-Lebensdauer in Sekunden — etwas unter dem Standard-Scan-Interval
CACHE_TTL_SECONDS = 55

# Maximum number of symbols kept in cache at once
MAX_CACHE_SIZE = 200

# Cache entry type:  {"df": pd.DataFrame, "last_ts": str, "created": float}
_cache: OrderedDict[str, dict[str, Any]] = OrderedDict()
_lock = threading.Lock()


def get_cached(symbol: str, last_timestamp: Any) -> pd.DataFrame | None:
    """Gibt gecachte Indikatoren zurück, falls vorhanden und noch aktuell.

    Cache-Treffer nur wenn Timestamp identisch UND Eintrag innerhalb TTL.
    Moves the entry to the end of the OrderedDict (LRU access tracking).

    Args:
        symbol: Handelspaar, z.B. 'BTC/USDT'.
        last_timestamp: Zeitstempel der letzten Kerze im OHLCV-DataFrame.

    Returns:
        pd.DataFrame mit berechneten Indikatoren bei Cache-Hit, None sonst.
    """
    ts_str = str(last_timestamp)

    with _lock:
        entry = _cache.get(symbol)
        if entry is None:
            return None

        age = time.monotonic() - entry["created"]
        if entry["last_ts"] == ts_str and age < CACHE_TTL_SECONDS:
            # Move to end to mark as recently used
            _cache.move_to_end(symbol)
            return entry["df"].copy()

    return None


def set_cached(symbol: str, last_timestamp: Any, df: pd.DataFrame) -> None:
    """Speichert berechnete Indikatoren im Cache.

    Überschreibt bestehende Einträge für dasselbe Symbol.
    LRU eviction via OrderedDict.popitem(last=False) — O(1), no scan.

    Args:
        symbol: Handelspaar, z.B. 'BTC/USDT'.
        last_timestamp: Zeitstempel der letzten Kerze im OHLCV-DataFrame.
        df: DataFrame mit allen berechneten technischen Indikatoren.
    """
    ts_str = str(last_timestamp)

    with _lock:
        _cache[symbol] = {
            "df": df.copy(),
            "last_ts": ts_str,
            "created": time.monotonic(),
        }
        # Move to end (most recently used)
        _cache.move_to_end(symbol)

        # Evict oldest entry (front of OrderedDict) if over limit — O(1)
        while len(_cache) > MAX_CACHE_SIZE:
            _cache.popitem(last=False)


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
        now = time.monotonic()
        entries = len(_cache)
        fresh = sum(1 for e in _cache.values() if (now - e["created"]) < CACHE_TTL_SECONDS)
        return {
            "total_entries": entries,
            "fresh_entries": fresh,
            "stale_entries": entries - fresh,
            "ttl_seconds": CACHE_TTL_SECONDS,
            "max_size": MAX_CACHE_SIZE,
        }
