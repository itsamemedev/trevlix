"""Auto-start logic for the bot loop.

Two helpers extracted from ``server.py``:
- ``has_any_configured_exchange`` – feasibility check (paper mode,
  legacy env keys, or DB-backed user-exchanges).
- ``maybe_auto_start_bot`` – boots the trading loop in a daemon thread
  if auto-start is enabled and the feasibility check passes.

Both take their dependencies as keyword arguments so they remain
testable and free of module-level state.
"""

from __future__ import annotations

import os
import threading
from typing import Any


def has_any_configured_exchange(*, config: dict[str, Any], db: Any, log: Any) -> bool:
    """Return True if at least one usable exchange configuration exists.

    Paper-trading mode never requires real keys, so this short-circuits
    to True. Live mode accepts either the legacy single-exchange ENV
    pair (``API_KEY``/``API_SECRET``) or any enabled row in
    ``user_exchanges`` with a non-empty ``api_key``.
    """
    if config.get("paper_trading", True):
        return True
    legacy_key = (os.getenv("API_KEY") or "").strip()
    legacy_secret = (os.getenv("API_SECRET") or "").strip()
    if legacy_key and legacy_secret:
        return True
    try:
        with db._get_conn() as conn:
            with conn.cursor() as c:
                c.execute(
                    "SELECT COUNT(*) AS n FROM user_exchanges "
                    "WHERE enabled=1 AND api_key IS NOT NULL AND api_key!=''"
                )
                row = c.fetchone() or {}
                return int(row.get("n", 0) or 0) > 0
    except Exception as e:  # noqa: BLE001 – feasibility checks must not raise
        log.debug("has_any_configured_exchange: %s", e)
        return False


def maybe_auto_start_bot(
    *,
    auto_start_enabled: bool,
    config: dict[str, Any],
    state: Any,
    db: Any,
    log: Any,
    bot_loop,
    bot_version: str,
) -> bool:
    """Start the bot loop in a daemon thread if conditions are met.

    Returns True iff this call actually launched the loop. The atomic
    check-and-set under ``state._lock`` prevents two parallel HTTP/WS
    triggers from racing into a double launch.
    """
    if not auto_start_enabled:
        return False
    if not has_any_configured_exchange(config=config, db=db, log=log):
        return False
    with state._lock:
        if getattr(state, "running", False):
            return False
        state.running = True
        state.paused = False
    threading.Thread(target=bot_loop, daemon=True, name="BotLoop").start()
    log.info("🚀 Bot auto-gestartet (Exchange konfiguriert)")
    state.add_activity(
        "🚀",
        "Auto-Start",
        f"v{bot_version} · {config.get('exchange', '—').upper()}",
        "success",
    )
    return True
