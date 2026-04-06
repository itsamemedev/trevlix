"""Signal handling and graceful shutdown helpers."""

from __future__ import annotations

import os
import signal


def build_graceful_shutdown_handler(*, state, shutdown_event, healer, cluster_ctrl, db, socketio, log):
    """Erzeugt den Graceful-Shutdown-Handler mit gebundenen Abhängigkeiten."""

    def _graceful_shutdown(signum, _frame):
        sig_name = signal.Signals(signum).name
        log.info(f"Shutdown-Signal empfangen ({sig_name}) – räume auf...")
        state.running = False
        shutdown_event.set()

        try:
            healer.stop()
        except Exception as exc:  # noqa: BLE001
            log.debug(f"Healer stop: {exc}")
        try:
            cluster_ctrl.shutdown()
        except Exception as exc:  # noqa: BLE001
            log.debug(f"Cluster shutdown: {exc}")

        try:
            if db is not None and db._pool is not None:
                db._pool.close_all()
        except Exception as exc:  # noqa: BLE001
            log.debug(f"Pool-Close bei Shutdown: {exc}")

        try:
            if db is not None:
                db.cleanup_old_data()
        except Exception as exc:  # noqa: BLE001
            log.debug(f"Cleanup bei Shutdown: {exc}")

        try:
            socketio.stop()
        except Exception as exc:  # noqa: BLE001
            log.debug(f"socketio.stop: {exc}")

        log.info("Shutdown abgeschlossen.")
        os._exit(0)

    return _graceful_shutdown


def register_signal_handlers(handler) -> None:
    """Registriert SIGTERM und SIGINT auf den übergebenen Handler."""
    signal.signal(signal.SIGTERM, handler)
    signal.signal(signal.SIGINT, handler)
