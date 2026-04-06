# PROJECT_STRUCTURE

## Zielbild (Stand 2026-04-06)

```text
trevlix/
├── app/
│   └── core/
│       ├── bootstrap.py       # Flask/CORS/Socket.IO/Limiter Setup
│       ├── logging_setup.py   # Logging-Konfiguration & Formatter
│       ├── default_config.py  # Zentrale Erzeugung der Runtime-Default-Config
│       ├── runtime.py         # Startsequenz/Hintergrund-Thread-Wiring
│       ├── http_routes.py     # Systemrouten + Error-Handler + Blueprint-Wiring
│       ├── lifecycle.py       # Graceful Shutdown + Signal-Handling
│       ├── request_helpers.py # Sichere Request-Parser + Exchange-Normalisierung
│       ├── websocket_guard.py # Gemeinsame Socket.IO-Rate-Limit-Helfer
│       ├── auth_guards.py     # Login-Rate-Limiting + Auth-Decorator-Fabriken
│       ├── session_guard.py   # Session-Timeout + CSRF-Guard für before_request
│       ├── socket_emit.py     # Sichere Socket.IO-Emission aus Background-Threads
│       ├── exchange_secret.py # Secret-Entschlüsselung + Single-Mode-Helfer
│       ├── admin_exchange.py  # Admin-Exchange-Auswahl inkl. DB-Fallback-Helfer
│       ├── market_cache.py    # Persistenter Markt-Cache (Disk I/O)
│       ├── exchange_runtime.py# Exchange-Erzeugung + Preflight/Recovery
│       ├── paper_mode.py      # Erzwingt sicheren Paper-Modus beim Start
│       ├── admin_password_policy.py # Schwache Admin-Passwort-Erkennung
│       ├── db_request_context.py # Request-skopierte DB-Connection-Helfer
│       ├── audit_writer.py    # Audit-Log-Persistenz Helper
│       ├── bot_heartbeat.py   # Heartbeat-basiertes Sleep im Bot-Loop
│       ├── api_docs_schema.py # API-Dokumentationspayload-Builder
│       ├── websocket_state.py # Socket-State Snapshot inkl. user_role
│       ├── socket_error_logger.py # Einheitliches Socket-Error-Logging
│       ├── websocket_authz.py # WS Auth/Admin-Prüfungen
│       ├── ws_rate_gate.py    # WS Rate-Gate Delegation
│       ├── backup_verify.py   # Backup-Verifikation (latest file)
│       ├── tax_export.py      # Steuerreport-CSV-Konvertierung
│       ├── trade_export.py    # Trade-JSON-Export-Konvertierung
│       ├── startup_view.py    # Startup-Banner Renderer
│       ├── prometheus_metrics.py # Prometheus-Metrikzeilen-Builder
│       └── security.py        # Security-Header + CSRF-Token-Handling
├── routes/                    # Flask Blueprints & Websocket-Migrationsmodule
├── services/                  # Business-Logik
│   └── passwords.py           # PBKDF2 Passwort-Hashing-Fallback
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
- **Utils/Helper**: `services/utils.py` + `app/core/request_helpers.py` (perspektivisch zusätzlich `app/utils/`)
- **Dokumentation**: `README.md`, `CHANGELOG.md`, `docs/`, `LAST_WORK.md`, `WORKFLOW_RULES.md`
