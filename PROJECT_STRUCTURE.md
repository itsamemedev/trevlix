# PROJECT_STRUCTURE

## Zielbild (Stand 2026-04-06)

```text
trevlix/
├── app/
│   └── core/
│       ├── bootstrap.py       # Flask/CORS/Socket.IO/Limiter Setup
│       ├── logging_setup.py   # Logging-Konfiguration & Formatter
│       ├── runtime.py         # Startsequenz/Hintergrund-Thread-Wiring
│       ├── http_routes.py     # Systemrouten + Error-Handler + Blueprint-Wiring
│       └── lifecycle.py       # Graceful Shutdown + Signal-Handling
├── routes/                    # Flask Blueprints & Websocket-Migrationsmodule
├── services/                  # Business-Logik
├── static/                    # Frontend Assets
├── templates/                 # HTML Templates
├── tests/                     # Test-Suite
├── docs/                      # Technische Dokumentation
├── server.py                  # Entry Point + Orchestrierung
└── *.md                       # Betriebs- und Projekt-Dokumentation
```

## Trennung der Verantwortlichkeiten

- **API/Serverlogik**: `server.py`, `routes/`
- **Services/Business-Logik**: `services/`
- **Core/Setup**: `app/core/`
- **Datenmodelle/Schemas**: aktuell verteilt, perspektivisch in eigenes Modul (`models/`) überführen
- **Utils/Helper**: `services/utils.py` (perspektivisch zusätzlich `app/utils/`)
- **Dokumentation**: `README.md`, `CHANGELOG.md`, `docs/`, `LAST_WORK.md`, `WORKFLOW_RULES.md`
