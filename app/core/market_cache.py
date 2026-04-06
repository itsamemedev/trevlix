"""Persistent market-cache helpers."""

from __future__ import annotations

import json
import os
import time


def build_cache_paths(base_dir: str) -> tuple[str, str]:
    cache_dir = os.path.join(base_dir, "data")
    cache_file = os.path.join(cache_dir, "market_cache.json")
    return cache_dir, cache_file


def save_market_cache(*, markets: list[str], cache_dir: str, cache_file: str, log) -> None:
    """Persist market list to disk for restart resilience."""
    try:
        os.makedirs(cache_dir, exist_ok=True)
        payload = {"ts": time.time(), "markets": markets}
        tmp = cache_file + ".tmp"
        with open(tmp, "w") as f:
            json.dump(payload, f)
        os.replace(tmp, cache_file)
    except Exception as exc:
        log.debug("Markt-Cache schreiben fehlgeschlagen: %s", exc)


def load_market_cache(*, cache_file: str, max_age: int, log) -> list[str]:
    """Load market list from disk; return empty list if unavailable."""
    try:
        with open(cache_file) as f:
            data = json.load(f)
        age = time.time() - data.get("ts", 0)
        markets = data.get("markets", [])
        if not markets:
            return []
        if age > max_age:
            log.warning(
                "Markt-Cache veraltet (%.0f h) – wird trotzdem als Fallback genutzt.",
                age / 3600,
            )
        return markets
    except (FileNotFoundError, json.JSONDecodeError, KeyError):
        return []
    except Exception as exc:
        log.debug("Markt-Cache lesen fehlgeschlagen: %s", exc)
        return []
