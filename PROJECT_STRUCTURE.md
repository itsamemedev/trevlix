# PROJECT_STRUCTURE

## Zielbild (Stand 2026-04-07, v1.7.0)

```text
trevlix/
├── app/
│   └── core/
│       ├── bootstrap.py       # Flask/CORS/Socket.IO/Limiter Setup
│       ├── app_setup.py       # Entrypoint-Orchestrierung (App/Logger/Limiter/Session-Timeout)
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
│       ├── admin_user_validation.py # Gemeinsame Admin-User-Payload-Validierung (HTTP + WS)
│       ├── backup_verify.py   # Backup-Verifikation (latest file)
│       ├── tax_export.py      # Steuerreport-CSV-Konvertierung
│       ├── trade_export.py    # Trade-JSON-Export-Konvertierung
│       ├── startup_view.py    # Startup-Banner Renderer
│       ├── prometheus_metrics.py # Prometheus-Metrikzeilen-Builder
│       ├── security.py        # Security-Header + CSRF-Token-Handling
│       │
│       │   ── NEU in v1.7.0 (aus server.py extrahiert) ──
│       ├── db_manager.py      # MySQLManager – DB-Initialisierung, CRUD, Backups (~1500 Zeilen)
│       ├── ai_engine.py       # AIEngine v4 – ML-Modelle, Walk-Forward, LSTM (~1280 Zeilen)
│       ├── ml_models.py       # AnomalyDetector, GeneticOptimizer, RLAgent, NewsSentimentAnalyzer (~470 Zeilen)
│       ├── trading_classes.py # BotState, MultiTimeframeFilter, OrderbookImbalance, PriceAlertManager,
│       │                      # DailyReportScheduler, BackupScheduler, ArbitrageScanner, ShortEngine (~870 Zeilen)
│       └── trading_ops.py     # create_exchange, fetch_markets, scan_symbol, open_position,
│                              # close_position, manage_positions, bot_loop, etc. (~1560 Zeilen)
├── routes/                    # Flask Blueprints & Websocket-Migrationsmodule
│   ├── auth.py                # Login, Register, 2FA, Admin-Routen
│   ├── dashboard.py           # Statische Seitenrouten
│   └── websocket.py           # WebSocket-Event-Handler (teilweise)
├── services/                  # Business-Logik (modulare Services)
│   ├── config.py              # Pydantic-Konfigurationsmanagement
│   ├── db_pool.py             # Thread-safe MySQL Connection-Pooling
│   ├── encryption.py          # Fernet API-Key-Verschlüsselung
│   ├── exchange_manager.py    # Multi-Exchange-Manager (CCXT)
│   ├── exchange_factory.py    # Exchange-Instanz-Erzeugung
│   ├── strategies.py          # 9 Voting-Trading-Strategien
│   ├── risk.py                # Risk Management + Circuit Breaker
│   ├── knowledge.py           # AI Knowledge Base + LLM-Integration
│   ├── notifications.py       # Discord & Telegram Alerts
│   ├── trading_algorithms.py  # Selbstlernende Kauf-/Verkaufsalgorithmen
│   ├── trade_dna.py           # Trade DNA Fingerprinting
│   ├── smart_exits.py         # ATR-basierte Smart Exits
│   ├── market_data.py         # Fear/Greed, On-Chain Daten
│   ├── indicator_cache.py     # Technischer Indikator-Cache
│   ├── adaptive_weights.py    # Adaptive Strategie-Gewichtung
│   ├── performance_attribution.py # Performance-Analyse
│   ├── revenue_tracking.py    # Revenue Tracking
│   ├── auto_healing.py        # Autonomous Auto-Healing Agent
│   ├── alert_escalation.py    # Alert-Eskalations-Manager
│   ├── cluster_control.py     # Cluster-Controller
│   ├── backtest.py            # Backtesting-Engine
│   ├── grid_trading.py        # Grid-Trading-Strategie
│   ├── cryptopanic.py         # CryptoPanic API Client
│   ├── llm_providers.py       # LLM-Provider-Abstraktion
│   ├── mcp_tools.py           # MCP-Tool-Registry
│   ├── tax_report.py          # Steuerreport-Generierung
│   ├── passwords.py           # PBKDF2 Passwort-Hashing
│   ├── git_ops.py             # Git-basierte Updates
│   └── utils.py               # Shared Utilities + Versionskonstanten
├── static/                    # Frontend Assets (CSS, JS)
├── templates/                 # Jinja2 HTML Templates
├── tests/                     # Pytest Test-Suite (393 Tests)
├── docker/                    # Nginx Config, MySQL Init, SSL
├── docs/                      # Technische Dokumentation
├── tasks/                     # Session Tracking (todo.md, lessons.md)
├── server.py                  # Entry Point (~4000 Zeilen): App-Setup, Routen, WebSocket, Startup
└── *.md                       # Betriebs- und Projekt-Dokumentation
```

## Trennung der Verantwortlichkeiten

- **Entry Point / App-Orchestrierung**: `server.py` (App-Setup, Instanz-Erstellung, Routen, WebSocket-Handler, Startup)
- **Core-Logik**: `app/core/` (DB-Manager, AI-Engine, Trading-Operations, ML-Models, Trading-Klassen)
- **Core-Infrastruktur**: `app/core/` (Bootstrap, Logging, Lifecycle, Security, Auth, Caching)
- **Services/Business-Logik**: `services/` (Strategien, Risk, Notifications, Exchange, Knowledge)
- **API-Routen**: `routes/` (Auth Blueprint, Dashboard Blueprint) + `server.py` (REST-API, WebSocket)
- **Datenmodelle/Schemas**: aktuell verteilt, perspektivisch in `models/` überführen
- **Utils/Helper**: `services/utils.py` + `app/core/request_helpers.py`
- **Dokumentation**: `README.md`, `CHANGELOG.md`, `docs/`, `LAST_WORK.md`, `WORKFLOW_RULES.md`
