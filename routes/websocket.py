"""
TREVLIX – WebSocket Handlers
=============================
[Verbesserung #6] Ausgelagertes WebSocket-Modul.

Registriert alle Flask-SocketIO Event-Handler.
Wird von server.py über register_handlers() eingebunden.

Migration-Status: Vorbereitet – Handler bleiben bis zur vollständigen
Modularisierung noch in server.py aktiv.

Verwendung (nach vollständiger Migration):
    from routes.websocket import register_handlers
    register_handlers(socketio, state, CONFIG, db, ...)
"""

import logging

log = logging.getLogger("NEXUS.websocket")


def register_handlers(
    socketio,
    state,
    config: dict,
    db,
    discord,
    ai_engine,
    risk,
    regime,
    arb_scanner,
    short_engine,
    fg_idx,
    dominance,
    bot_loop_fn,
    backup_fn,
    daily_report_fn,
    _ws_limits: dict,
):
    """
    Registriert alle SocketIO-Event-Handler.

    Args:
        socketio:       Flask-SocketIO Instanz
        state:          BotState Instanz
        config:         CONFIG-Dict (Referenz)
        db:             MySQLManager Instanz
        discord:        DiscordNotifier Instanz
        ai_engine:      AIEngine Instanz
        risk:           RiskManager Instanz
        regime:         MarketRegime Instanz
        arb_scanner:    ArbitrageScanner Instanz
        short_engine:   ShortEngine Instanz
        fg_idx:         FearGreedIndex Instanz
        dominance:      DominanceFilter Instanz
        bot_loop_fn:    bot_loop-Funktion
        backup_fn:      backup-Funktion
        daily_report_fn: daily_report-Funktion
        _ws_limits:     Dict für Rate-Limiting (sid -> timestamp)
    """

    # ── Rate-Limit-Hilfsfunktion ────────────────────────────────────────────
    _last_cleanup = [0.0]  # Mutable Container für nonlocal-freien Zugriff

    import threading

    _ws_limits_lock = threading.Lock()

    def _ws_rate_check(sid: str, action: str, min_interval: float = 2.0) -> bool:
        """Gibt True zurück wenn der Request erlaubt ist.

        Blockiert wenn min_interval seit letztem gleichen Event nicht vergangen.
        Bereinigt stale Einträge alle 60 Sekunden um Memory-Leaks zu verhindern.

        Args:
            sid: Socket-ID des Clients.
            action: Name des Events (z.B. 'start_bot').
            min_interval: Minimale Sekunden zwischen gleichen Events.

        Returns:
            True wenn der Request erlaubt ist, False wenn Rate-Limited.
        """
        import time

        key = f"{sid}:{action}"
        now = time.time()
        with _ws_limits_lock:
            last = _ws_limits.get(key, 0)
            if now - last < min_interval:
                return False
            _ws_limits[key] = now

            # Zeitbasierte Eviction alle 60s (statt nur bei >1000 Einträgen)
            if now - _last_cleanup[0] > 60:
                _last_cleanup[0] = now
                cutoff = now - 300  # Einträge älter als 5 Minuten entfernen
                stale = [k for k, v in _ws_limits.items() if v < cutoff]
                for k in stale:
                    _ws_limits.pop(k, None)
                if stale:
                    log.debug(f"WS Rate-Limit: {len(stale)} stale Einträge entfernt")

        return True

    # Die eigentliche Handler-Registrierung erfolgt noch in server.py.
    # Dieses Modul enthält die Hilfsfunktionen und dient als Migrations-Target.
    log.info("WebSocket-Handler-Modul geladen (Migration vorbereitet)")
    return _ws_rate_check
