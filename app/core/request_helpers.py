"""Helper für robustes Parsing und Normalisierung von Request-Werten."""

from __future__ import annotations

import math
from typing import Any


def get_json_body() -> dict:
    """Gibt den JSON-Body des aktuellen Flask-Requests als Dict zurück.

    Ersatz für das wiederkehrende ``request.json or {}``-Muster. Liefert
    immer ein Dict – leer, wenn der Body fehlt oder kein JSON-Dict enthält.
    """
    from flask import request

    data = request.json or {}
    return data if isinstance(data, dict) else {}


def safe_int(val: Any, default: int) -> int:
    """Sicherer int()-Cast für Request-Parameter."""
    try:
        return int(val)
    except (ValueError, TypeError):
        return default


def safe_float(val: Any, default: float | None) -> float | None:
    """Sicherer float()-Cast inkl. NaN/Inf-Filter."""
    try:
        result = float(val)
        if not math.isfinite(result):
            return default
        return result
    except (ValueError, TypeError):
        return default


def safe_bool(val: Any, default: bool = False) -> bool:
    """Sicherer Bool-Cast für JSON-/Form-Werte mit String-Support."""
    if isinstance(val, bool):
        return val
    if isinstance(val, (int, float)):
        return bool(val)
    if isinstance(val, str):
        normalized = val.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off", ""}:
            return False
    return default


def normalize_exchange_name(raw: Any, exchange_map: dict[str, str]) -> str:
    """Normalisiert und validiert einen Exchange-Namen."""
    if raw is None:
        return ""
    name = str(raw).strip().lower()
    if not name:
        return ""
    if name in exchange_map:
        return name
    for canonical, ccxt_name in exchange_map.items():
        if name == ccxt_name:
            return canonical
    return ""
