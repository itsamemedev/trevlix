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
import threading

log = logging.getLogger("NEXUS.websocket")


def register_handlers(socketio, state, config: dict, db, discord, ai_engine,
                      risk, regime, arb_scanner, short_engine, fg_idx,
                      dominance, bot_loop_fn, backup_fn, daily_report_fn,
                      _ws_limits: dict):
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
    from flask import session
    from flask_socketio import emit

    # ── Rate-Limit-Hilfsfunktion ────────────────────────────────────────────
    def _ws_rate_check(sid: str, action: str, min_interval: float = 2.0) -> bool:
        """
        Gibt True zurück wenn der Request erlaubt ist.
        Blockiert wenn min_interval seit letztem gleichen Event nicht vergangen.
        """
        import time
        key = f"{sid}:{action}"
        now = time.time()
        last = _ws_limits.get(key, 0)
        if now - last < min_interval:
            return False
        _ws_limits[key] = now
        return True

    # Die eigentliche Handler-Registrierung erfolgt noch in server.py.
    # Dieses Modul enthält die Hilfsfunktionen und dient als Migrations-Target.
    log.info("WebSocket-Handler-Modul geladen (Migration vorbereitet)")
    return _ws_rate_check
