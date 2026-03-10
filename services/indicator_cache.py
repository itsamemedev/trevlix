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
    """Gibt gecachte Indikatoren zurück, falls vorhanden und noch aktuell.

    Cache-Treffer nur wenn Timestamp identisch UND Eintrag innerhalb TTL.
    Verhindert redundante Neuberechnung technischer Indikatoren bei
    mehreren Aufrufen für dieselbe Kerze.

    Args:
        symbol: Handelspaar, z.B. 'BTC/USDT'.
        last_timestamp: Zeitstempel der letzten Kerze im OHLCV-DataFrame.
            Wird als String verglichen für stabilen Vergleich.

    Returns:
        pd.DataFrame mit berechneten Indikatoren bei Cache-Hit, None sonst.
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
            return entry["df"].copy()

    return None


def set_cached(symbol: str, last_timestamp: Any, df: pd.DataFrame) -> None:
    """Speichert berechnete Indikatoren im Cache.

    Überschreibt bestehende Einträge für dasselbe Symbol. Wenn der Cache
    ``MAX_CACHE_SIZE`` überschreitet, wird der älteste Eintrag entfernt
    (LRU-Eviction, Verbesserung #20).

    Args:
        symbol: Handelspaar, z.B. 'BTC/USDT'.
        last_timestamp: Zeitstempel der letzten Kerze im OHLCV-DataFrame.
        df: DataFrame mit allen berechneten technischen Indikatoren.
    """
    key = symbol
    ts_str = str(last_timestamp)

    with _lock:
        _cache[key] = {
            "df": df.copy(),
            "last_ts": ts_str,
            "created": time.monotonic(),
        }
        # [Verbesserung #20] LRU-Eviction: älteste Einträge entfernen
        if len(_cache) > MAX_CACHE_SIZE:
            oldest_key = min(_cache, key=lambda k: _cache[k]["created"])
            _cache.pop(oldest_key, None)


def invalidate(symbol: str | None = None) -> None:
    """Leert den Cache für ein Symbol oder den gesamten Cache.

    Args:
        symbol: Symbol zum Leeren (z.B. 'ETH/USDT'), oder None für alle Einträge.
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
        ``stale_entries`` und ``ttl_seconds``. Nützlich für
        Dashboard-Anzeige und Debugging.
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
        }
