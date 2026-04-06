"""Runtime helpers for creating exchanges and preflighting market availability."""

from __future__ import annotations

import time
from typing import Any


def create_exchange_instance(
    *,
    config: dict,
    normalize_exchange_name,
    get_admin_exchange_by_name,
    get_admin_primary_exchange,
    is_single_exchange_mode,
    reveal_and_decrypt,
    safe_int,
    create_ccxt_exchange,
    log,
):
    """Create primary exchange instance using DB/admin/env fallback rules."""
    desired_name = normalize_exchange_name(config.get("exchange", ""))
    db_cfg = get_admin_exchange_by_name(desired_name) if desired_name else None
    if db_cfg is None:
        db_cfg = get_admin_primary_exchange()
    single_mode = is_single_exchange_mode()

    if db_cfg and db_cfg.get("exchange"):
        name = db_cfg["exchange"]
        db_key = db_cfg["api_key"]
        db_secret = db_cfg["api_secret"]
        db_pass = db_cfg["passphrase"]
        if config.get("exchange") != name:
            config["exchange"] = name
    elif single_mode:
        name = desired_name or config.get("exchange", "cryptocom")
        db_key = db_secret = db_pass = ""
    else:
        name = desired_name or config.get("exchange", "cryptocom")
        db_key = db_secret = db_pass = ""
        log.info(
            "ℹ️  Multi-Exchange-Mode aktiv (EXCHANGE env leer) – "
            "richte Exchange-Keys im Dashboard unter 'Exchanges' ein."
        )

    if config.get("paper_trading", True):
        api_key = ""
        api_secret = ""
        passphrase = ""
    elif db_key or db_secret:
        api_key = db_key
        api_secret = db_secret
        passphrase = db_pass
    else:
        api_key = reveal_and_decrypt(config.get("api_key", ""))
        api_secret = reveal_and_decrypt(config.get("secret", ""))
        passphrase = reveal_and_decrypt(config.get("api_passphrase", ""))

    timeout_ms = safe_int(config.get("exchange_timeout_ms", 0), 0)
    extra: dict[str, Any] = {}
    if timeout_ms > 0:
        extra["timeout"] = max(3000, timeout_ms)

    inst = create_ccxt_exchange(
        name,
        api_key=api_key,
        api_secret=api_secret,
        passphrase=passphrase,
        default_type="spot",
        extra_options=extra or None,
    )
    if inst is None:
        raise ValueError(f"Exchange '{name}' konnte nicht erstellt werden")
    return inst


def preflight_exchange_markets(
    *,
    max_attempts: int,
    create_exchange,
    fetch_markets,
    normalize_exchange_name,
    config: dict,
    db,
    pin_user_exchange,
    log,
    load_market_cache,
):
    """Preflight exchange + markets with retry and cache fallback."""
    last_err = ""
    for attempt in range(1, max_attempts + 1):
        try:
            preflight_ex = create_exchange()
            markets = fetch_markets(preflight_ex)
            if markets:
                return markets, None
            last_err = "keine Märkte geladen"
        except Exception as exc:
            last_err = str(exc)
        if attempt < max_attempts:
            time.sleep(min(2**attempt, 10))

    try:
        current_ex = normalize_exchange_name(config.get("exchange", ""))
        if db is not None and getattr(db, "db_available", False):
            with db._get_conn() as conn:
                with conn.cursor() as c:
                    c.execute("SELECT id FROM users WHERE role='admin' ORDER BY id ASC LIMIT 1")
                    row = c.fetchone()
                    admin_id = row["id"] if row else None
            if admin_id:
                enabled = db.get_enabled_exchanges(admin_id)
                for ex_cfg in enabled:
                    ex_name = normalize_exchange_name(ex_cfg.get("exchange", ""))
                    if not ex_name or ex_name == current_ex:
                        continue
                    try:
                        config["exchange"] = ex_name
                        candidate = create_exchange()
                        markets = fetch_markets(candidate)
                        if markets:
                            log.warning(
                                "Auto-Recovery: Exchange-Fallback aktiv %s -> %s",
                                (current_ex or "unknown").upper(),
                                ex_name.upper(),
                            )
                            pin_user_exchange(admin_id, ex_name)
                            return markets, None
                    except Exception as ex_err:
                        log.debug("Auto-Recovery Exchange %s fehlgeschlagen: %s", ex_name, ex_err)
                if current_ex:
                    config["exchange"] = current_ex
    except Exception as fallback_err:
        log.debug("Auto-Recovery übersprungen: %s", fallback_err)

    disk_cached = load_market_cache()
    if disk_cached:
        log.warning(
            "Preflight: Exchange nicht erreichbar – nutze persistenten Cache (%d Märkte).",
            len(disk_cached),
        )
        return disk_cached, None
    return [], last_err or "Exchange/Marktdaten nicht erreichbar"
