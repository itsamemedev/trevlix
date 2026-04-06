# TODO

## Priorität Hoch
- [ ] `server.py`: REST-Endpunkte in thematische Blueprint-Module aufteilen (z. B. `routes/api_trading.py`, `routes/api_admin.py`).
- [ ] WebSocket-Events aus `server.py` schrittweise nach `routes/websocket.py` migrieren.

## Priorität Mittel
- [ ] Gemeinsame Request-/Response-Schemas strukturieren (z. B. `models/schemas.py`).
- [ ] Wiederholte Validierungs- und Parsing-Helfer aus `server.py` in Utility-Module auslagern.
- [ ] Logging-Konfiguration vollständig in eigenes Modul (`app/core/logging.py`) ausgliedern.

## Priorität Niedrig
- [ ] Dokumentation in `docs/` mit Modul-Mapping ergänzen.
- [ ] Optionale Entwicklerdoku (`DEVELOPMENT.md`) für lokale Workflows ausbauen.
