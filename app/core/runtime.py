"""Runtime helper for TREVLIX server startup."""

from __future__ import annotations

import os
import threading
from collections.abc import Callable
from typing import Any

from app.core.startup_view import render_ready_summary


def _db_ping(db) -> bool:
    """Prüft per SELECT 1, ob die DB antwortet."""
    try:
        with db._get_conn() as conn:
            with conn.cursor() as c:
                c.execute("SELECT 1")
                c.fetchone()
        return True
    except Exception:  # noqa: BLE001
        return False


def _run_env_validation(log) -> None:
    """Runs ``validate_env.validate`` at startup and logs any findings.

    In production (``TREVLIX_ENV=production`` or ``FLASK_ENV=production``)
    critical issues abort startup. In dev, they are logged as errors but
    do not block the server.
    """
    try:
        import validate_env  # type: ignore
    except Exception as exc:  # noqa: BLE001
        log.debug(f"validate_env nicht importierbar: {exc}")
        return

    try:
        issues = validate_env.validate()
    except Exception as exc:  # noqa: BLE001
        log.warning(f"Env-Validierung übersprungen: {exc}")
        return

    criticals = [i for i in issues if i.severity == "critical"]
    warnings = [i for i in issues if i.severity == "warning"]
    for i in warnings:
        log.warning(f"⚠️  ENV {i.var}: {i.msg}")
    for i in criticals:
        log.error(f"✖ ENV {i.var}: {i.msg}")

    env = (os.getenv("TREVLIX_ENV") or os.getenv("FLASK_ENV") or "").strip().lower()
    if criticals and env == "production":
        raise RuntimeError(
            f"{len(criticals)} kritische ENV-Fehler in Produktion – Start abgebrochen."
        )


def _ollama_ping() -> bool | None:
    """Liefert True/False bei konfiguriertem Ollama, sonst None (nicht angezeigt)."""
    host = os.getenv("OLLAMA_HOST", "").strip()
    model = os.getenv("OLLAMA_MODEL", "").strip()
    endpoint = os.getenv("LLM_ENDPOINT", "").strip()
    if not (host or model or "11434" in endpoint):
        return None
    try:
        from services.ollama_client import is_ollama_available

        return is_ollama_available()
    except Exception:  # noqa: BLE001
        return False


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
    db=None,
) -> None:
    """Startet Hintergrunddienste und den SocketIO-Server."""
    startup_banner()

    _run_env_validation(log)

    cfg_errors = validate_config(config)
    if cfg_errors:
        for err in cfg_errors:
            log.error(f"⚠️  CONFIG-Fehler: {err}")
        log.warning("⚠️  Konfigurationsfehler gefunden – bitte prüfen. Bot startet trotzdem.")
    else:
        log.info("✅ Config validiert (keine Fehler)")

    os.makedirs(config["backup_dir"], exist_ok=True)
    log.info(f"📁 Backup-Verzeichnis: {config['backup_dir']}")

    bg_threads = [
        ("DailyReport", daily_sched.run),
        ("Backup", backup_sched.run),
        ("FearGreedIndex", fg_idx.update),
        ("BTCDominance", dominance.update),
        ("SafetyScan", safety_scan),
    ]
    for name, target in bg_threads:
        threading.Thread(target=target, daemon=True, name=name).start()
        log.info(f"🧵 Thread gestartet: {name}")

    healer_ok = False
    try:
        healer.start()
        healer_ok = True
        log.info("🩺 Auto-Healing Agent gestartet")
    except Exception as exc:  # noqa: BLE001
        log.warning(f"Auto-Healing Agent Start fehlgeschlagen: {exc}")

    auto_started = False
    exchanges_ready = has_configured_exchanges() if has_configured_exchanges else True
    if auto_start:
        if exchanges_ready:
            state.running = True
            state.paused = False
            threading.Thread(target=bot_loop, daemon=True, name="BotLoop").start()
            auto_started = True
            log.info(f"🚀 Bot auto-gestartet (AUTO_START=true · {config['exchange'].upper()})")
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

    # ── Ready-Summary ───────────────────────────────────────────────────
    active_threads = sum(
        1 for t in threading.enumerate() if t.is_alive() and t is not threading.main_thread()
    )
    db_ok = _db_ping(db) if db is not None else False
    ollama_ok = _ollama_ping()
    try:
        print(
            render_ready_summary(
                bot_version=bot_version,
                config=config,
                thread_count=active_threads + (1 if healer_ok else 0),
                db_ok=db_ok,
                ollama_ok=ollama_ok,
                auto_started=auto_started,
                exchange_ready=exchanges_ready,
            )
        )
    except Exception as exc:  # noqa: BLE001
        log.debug(f"Ready-Summary Rendering fehlgeschlagen: {exc}")

    port = int(os.getenv("PORT", "5000"))
    log.info(f"🌐 Dashboard: http://0.0.0.0:{port}")
    log.info(f"📡 REST-API:  http://0.0.0.0:{port}/api/v1/")
    log.info(f"📚 API-Docs:  http://0.0.0.0:{port}/api/v1/docs")
    socketio.run(app, host="0.0.0.0", port=port, debug=False, allow_unsafe_werkzeug=True)
