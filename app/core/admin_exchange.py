"""Admin exchange-selection helpers extracted from server.py."""

from __future__ import annotations


def _get_admin_id(db) -> int | None:
    if db is None or not getattr(db, "db_available", False):
        return None
    with db._get_conn() as conn:
        with conn.cursor() as c:
            c.execute("SELECT id FROM users WHERE role='admin' ORDER BY id ASC LIMIT 1")
            row = c.fetchone()
            return row["id"] if row else None


def get_exchange_key_states(db) -> dict[str, bool]:
    """Return which exchanges have API keys configured for admin user."""
    exchanges = (
        "cryptocom",
        "binance",
        "bybit",
        "okx",
        "kucoin",
        "kraken",
        "huobi",
        "coinbase",
        "bitget",
        "mexc",
        "gateio",
        "nonkyc",
    )
    result = {ex: False for ex in exchanges}
    try:
        admin_id = _get_admin_id(db)
        if not admin_id:
            return result
        for ex_info in db.get_enabled_exchanges(admin_id):
            ex_name = ex_info.get("exchange", "")
            if ex_name in result:
                result[ex_name] = bool(ex_info.get("api_key") and ex_info.get("api_key") != "")
    except Exception:
        pass
    return result


def get_admin_primary_exchange(db, log) -> dict | None:
    """Get admin primary exchange config as dict or None."""
    try:
        admin_id = _get_admin_id(db)
        if not admin_id:
            return None
        enabled = db.get_enabled_exchanges(admin_id)
        if not enabled:
            return None
        item = enabled[0]
        return {
            "exchange": item.get("exchange", ""),
            "api_key": item.get("api_key", "") or "",
            "api_secret": item.get("api_secret", "") or "",
            "passphrase": item.get("passphrase", "") or "",
        }
    except Exception as exc:
        log.debug("_get_admin_primary_exchange: %s", exc)
        return None


def get_admin_exchange_by_name(db, exchange_name: str, log) -> dict | None:
    """Get enabled admin exchange config for a specific exchange name."""
    if not exchange_name:
        return None
    try:
        admin_id = _get_admin_id(db)
        if not admin_id:
            return None
        for ex in db.get_enabled_exchanges(admin_id):
            if ex.get("exchange") == exchange_name:
                return {
                    "exchange": ex.get("exchange", ""),
                    "api_key": ex.get("api_key", "") or "",
                    "api_secret": ex.get("api_secret", "") or "",
                    "passphrase": ex.get("passphrase", "") or "",
                }
    except Exception as exc:
        log.debug("_get_admin_exchange_by_name(%s): %s", exchange_name, exc)
    return None


def pin_user_exchange(db, user_id: int | None, exchange_name: str, log) -> bool:
    """Set a user's preferred exchange as primary if possible."""
    if not user_id or not exchange_name or db is None:
        return False
    try:
        return bool(db.set_primary_exchange(user_id, exchange_name, enable=True))
    except Exception as exc:
        log.debug("_pin_user_exchange(%s, %s): %s", user_id, exchange_name, exc)
        return False
