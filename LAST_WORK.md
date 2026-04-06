# LAST_WORK

## Zuletzt erledigt (2026-04-06)

1. WebSocket-Rate-Limiting modularisiert: neues Core-Modul `app/core/websocket_guard.py` mit zentraler Klasse `WsRateLimiter`.
2. `server.py` entschlackt: lokale Rate-Limit-Globalzustände und Cleanup-Details entfernt; `_ws_rate_check(...)` delegiert nun auf das Core-Modul.
3. `routes/websocket.py` vereinheitlicht: verwendet jetzt ebenfalls `WsRateLimiter` statt eigener paralleler Implementierung.
4. Neue Tests ergänzt (`tests/test_websocket_guard.py`) für Intervall-Blockierung, Freigabe und Stale-Cleanup.
5. Iterativer Validierungslauf erfolgreich:
   - `python -m compileall -q server.py app routes tests`
   - `pytest -q tests/test_default_config.py tests/test_websocket_guard.py tests/test_bootstrap.py tests/test_auth.py tests/test_api.py` (`38 passed, 1 skipped`)
   - `python scripts/check_i18n_keys.py`
6. Version und Doku auf `1.6.8` synchronisiert (`VERSION.md`, `CHANGELOG.md`, README, `pyproject.toml`, `services/utils.py`, technische Docs).

## Nächste sinnvolle Schritte

1. DB-Manager-/Persistence-Hilfsblöcke aus `server.py` in dedizierte Module überführen (z. B. `app/core/db_runtime.py`).
2. WebSocket-Handler schrittweise aus `server.py` in `routes/websocket.py` migrieren und dort gezielt Integrationstests ergänzen.
3. Große API-Abschnitte (Knowledge/Admin/Risk) in route-spezifische Module aufteilen, um den Entry-Point weiter zu verkleinern.
