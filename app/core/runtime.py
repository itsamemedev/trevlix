"""Runtime helper for TREVLIX server startup."""

from __future__ import annotations

import os
import threading
from collections.abc import Callable
from typing import Any


def run_server(
    *,
    startup_banner: Callable[[], None],
    validate_config: Callable[[dict[str, Any]], list[str]],
    config: dict[str, Any],
    log,
    daily_sched,
    backup_sched,
    fg_idx,
    dominance,
    safety_scan: Callable[[], None],
    healer,
    state,
    bot_loop: Callable[[], None],
    bot_version: str,
    socketio,
    app,
    auto_start: bool,
    has_configured_exchanges: Callable[[], bool] | None = None,
) -> None:
    """Startet Hintergrunddienste und den SocketIO-Server."""
    startup_banner()

    cfg_errors = validate_config(config)
    if cfg_errors:
        for err in cfg_errors:
            log.error(f"⚠️  CONFIG-Fehler: {err}")
        log.warning("⚠️  Konfigurationsfehler gefunden – bitte prüfen. Bot startet trotzdem.")

    os.makedirs(config["backup_dir"], exist_ok=True)

    threading.Thread(target=daily_sched.run, daemon=True, name="DailyReport").start()
    threading.Thread(target=backup_sched.run, daemon=True, name="Backup").start()
    threading.Thread(target=fg_idx.update, daemon=True).start()
    threading.Thread(target=dominance.update, daemon=True).start()
    threading.Thread(target=safety_scan, daemon=True).start()

    try:
        healer.start()
        log.info("🩺 Auto-Healing Agent gestartet")
    except Exception as exc:  # noqa: BLE001
        log.warning(f"Auto-Healing Agent Start fehlgeschlagen: {exc}")

    if auto_start:
        exchanges_ready = has_configured_exchanges() if has_configured_exchanges else True
        if exchanges_ready:
            state.running = True
            state.paused = False
            threading.Thread(target=bot_loop, daemon=True, name="BotLoop").start()
            log.info("🚀 Bot auto-gestartet (AUTO_START=true)")
            state.add_activity(
                "🚀", "Auto-Start", f"v{bot_version} · {config['exchange'].upper()}", "success"
            )
        else:
            log.info(
                "⏸️  AUTO_START aktiv, aber keine Exchange konfiguriert – "
                "Bot startet automatisch, sobald ein Exchange hinzugefügt wird."
            )
    else:
        log.info("⏸️  Bot wartet auf manuellen Start (AUTO_START=false)")

    log.info("🌐 Dashboard: http://0.0.0.0:5000")
    log.info("📡 REST-API:  http://0.0.0.0:5000/api/v1/")
    log.info("📚 API-Docs:  http://0.0.0.0:5000/api/v1/docs")
    socketio.run(app, host="0.0.0.0", port=5000, debug=False, allow_unsafe_werkzeug=True)
