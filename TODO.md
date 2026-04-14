# TODO

## Priorität Hoch
- [ ] `server.py`: REST-Endpunkte in thematische Blueprint-Module aufteilen (z. B. `routes/api_trading.py`, `routes/api_admin.py`).
      *Status:* Zurückgestellt – ~129 `@app.route`-Decorators mit tiefer Runtime-Kopplung (state, db, notifier, risk, …).
      Sichere Extraktion erfordert dedizierte Refactor-Session mit Factory-Pattern pro Blueprint.
- [ ] WebSocket-Events aus `server.py` schrittweise nach `routes/websocket.py` migrieren.
      *Status:* Modul-Skelett mit `register_handlers()` + `WsRateLimiter` existiert in `routes/websocket.py`.
      36 `@socketio.on(...)`-Handler bleiben bis zur vollständigen Migration in `server.py` aktiv.

## Priorität Mittel
- [ ] Gemeinsame Request-/Response-Schemas strukturieren (z. B. `models/schemas.py`).
      *Vorarbeit:* `app/core/request_helpers.py` liefert bereits `get_json_body`, `safe_int`,
      `safe_float`, `safe_bool`, `normalize_exchange_name`. Pydantic-basierte Endpoint-Schemas
      werden im Zuge der Blueprint-Aufteilung schrittweise nachgezogen.
- [x] Wiederholte Validierungs- und Parsing-Helfer aus `server.py` in Utility-Module auslagern.
      *Erledigt:* `app/core/request_helpers.py` (Session picfn); 26× `request.json or {}` ersetzt.
- [x] Logging-Konfiguration vollständig in eigenes Modul (`app/core/logging.py`) ausgliedern.
      *Erledigt:* `app/core/logging_setup.py` (via `configure_logging()` in `app_setup.py`
      verdrahtet). Unterstützt `LOG_LEVEL`, `JSON_LOGS`, `COLOR_LOGS`.

## Priorität Niedrig
- [x] Dokumentation in `docs/` mit Modul-Mapping ergänzen.
      *Erledigt:* `docs/MODULE_MAPPING.md` listet alle `services/`, `routes/`, `app/core/`-
      Module mit einzeiliger Beschreibung.
- [x] Optionale Entwicklerdoku (`DEVELOPMENT.md`) für lokale Workflows ausbauen.
      *Erledigt:* `DEVELOPMENT.md` dokumentiert Local-Setup, Tests, Ruff, Branch-Konventionen,
      pre-commit Checkliste.
