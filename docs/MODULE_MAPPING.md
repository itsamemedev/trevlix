# TREVLIX – Modul-Mapping

Vollständige Übersicht aller produktiven Python-Module im Repository mit je
einer kurzen Zweckbeschreibung. Dient als schnelles Nachschlagewerk für neue
Mitentwickler und als Referenz bei Refactorings.

Für High-Level-Architektur siehe `docs/ARCHITECTURE.md`.
Für die Service-Schicht siehe `docs/SERVICES.md`.

---

## Root

| Datei | Zweck |
|-------|-------|
| `server.py` | Haupteinstiegspunkt. Flask- und SocketIO-App, Bot-Lifecycle, REST- und WebSocket-Handler, DB-Init. |
| `trevlix_i18n.py` | Backend-Übersetzungen für DE/EN/ES/RU/PT. |
| `validate_env.py` | Environment-Variablen-Validierung vor Serverstart. |
| `legacy/ai_engine.py` | Archivierte Referenzimplementierung. Nicht aktiv, nicht importiert, kein Lint-Zwang. Wird in einem zukünftigen Release entfernt. |

## `routes/` – Flask-Blueprints

| Modul | Zweck |
|-------|-------|
| `auth.py` | Login, Registrierung, Passwort-Reset, 2FA, Admin-Auth. Nutzt `templates/auth.html` / `templates/auth_admin.html`. |
| `dashboard.py` | Statische Seiten (`/about`, `/faq`, `/strategies`, `/INSTALLATION`, `/dashboard`, …). Rendert Jinja-Partials (`_partials/site_nav.html` u. a.). |
| `websocket.py` | Skelett für ausgelagerte SocketIO-Handler + `WsRateLimiter`. Vollständige Migration ist offen (siehe TODO). |

## `services/` – Geschäftslogik (stateless Kern)

| Modul | Zweck |
|-------|-------|
| `adaptive_weights.py` | Adaptive Gewichtung der Voting-Strategien basierend auf historischer Performance. |
| `alert_escalation.py` | Eskalationslogik für Preisalarme und Risikowarnungen. |
| `auto_healing.py` | Auto-Healing-Agent: überwacht Subsysteme und startet bei Fehlern neu. |
| `backtest.py` | Historisches Backtesting der Trading-Strategien. |
| `cluster_control.py` | Multi-Node-/Cluster-Koordination zwischen Bot-Instanzen. |
| `config.py` | Pydantic-basierte Konfigurationsverwaltung (`.env` → `CONFIG`-Dict). |
| `cryptopanic.py` | CryptoPanic-News-Client mit Rate-Limiter (2 s Free-Plan). |
| `db_pool.py` | Thread-sicherer MySQL-/MariaDB-Connection-Pool. |
| `encryption.py` | Fernet-Verschlüsselung für API-Keys (in DB gespeicherte Exchange-Credentials). |
| `exchange_factory.py` | Registry aller 11 unterstützten Exchanges (binance, bybit, coinbase, cryptocom, gateio, huobi, kraken, kucoin, mexc, okx, bitget). |
| `exchange_manager.py` | Per-User-Multi-Exchange-Manager via CCXT; thread-safe. |
| `git_ops.py` | Git-Operationen für In-App-Updates. |
| `grid_trading.py` | Grid-Trading-Strategie. |
| `indicator_cache.py` | Caching für technische Indikatoren (RSI, MACD, BB, …). |
| `knowledge.py` | KI-Wissensbasis + LLM-Integration (OpenAI-kompatibel, Ollama-aware). |
| `llm_providers.py` | Multi-LLM-Provider mit Failover (Groq, Cerebras, OpenRouter, HuggingFace). |
| `market_data.py` | Fear/Greed-Index, BTC-Dominance, On-Chain-Daten, Sentiment. |
| `mcp_tools.py` | Model-Context-Protocol-Tool-Layer für externe KI-Clients. |
| `notifications.py` | Discord-Webhook + Telegram-Bot-Notifications. |
| `ollama_client.py` | Lightweight-Wrapper um lokale Ollama-Instanz (Health, Chat, Model-Pull). |
| `passwords.py` | Passwort-Policies + sichere Hashing-Helfer. |
| `performance_attribution.py` | PnL-Attribution pro Strategie/Exchange/Symbol. |
| `redis_market_cache.py` | Optionaler Redis-Cache für Market-Data mit In-Memory-Fallback. |
| `revenue_tracking.py` | Revenue-Tracking inkl. Fees/Taxes. |
| `risk.py` | Risk-Manager, Circuit-Breaker, Drawdown-Schutz. |
| `smart_exits.py` | Trailing-Stops, Break-Even, dynamische Exit-Logik. |
| `strategies.py` | Die 9 Voting-Strategien (Konsens-basiert). |
| `tax_report.py` | Steuerreports (FIFO, Haltefristen). |
| `trade_dna.py` | Fingerprinting von Trades zur Mustererkennung. |
| `trade_execution.py` | Order-Placement-Layer über CCXT. |
| `trading_algorithms.py` | Algorithmische Orderausführung (TWAP/VWAP/Iceberg). |
| `trading_mode.py` | Paper- vs. Live-Trading-Switch. |
| `utils.py` | Gemeinsame Hilfsfunktionen. |
| `virginie.py` | Virginie-KI: kontrolliert Bots über Autonomie-Gewichtung und Gating. |

## `app/core/` – Wiring-Schicht und Framework-Integration

| Modul | Zweck |
|-------|-------|
| `admin_exchange.py` | Admin-Endpunkte zur Verwaltung von User-Exchanges. |
| `admin_password_policy.py` | Policy-Checks für Admin-Passwörter. |
| `admin_user_validation.py` | Validatoren für Admin-User-CRUD. |
| `ai_engine.py` | **Aktive** AI-Engine (RandomForest, XGBoost, LSTM, Kelly-Sizing, Virginie-Orchestrator). |
| `api_docs_schema.py` | OpenAPI/Swagger-Schemas für `/api/v1/docs`. |
| `app_setup.py` | Flask-App-Konstruktion, CORS, Limiter, Session-Config. Verdrahtet `configure_logging()`. |
| `audit_writer.py` | Asynchroner Audit-Log-Writer. |
| `auth_guards.py` | Decorators: `require_auth`, `api_auth_required`, Admin-Gates. |
| `backup_verify.py` | Integritätsprüfung für Backup-Archive. |
| `bootstrap.py` | Frühinitialisierung (vor Flask). |
| `bot_heartbeat.py` | Heartbeat-Emitter an WebSocket-Clients. |
| `db_manager.py` | `MySQLManager` – Schema-Init, High-Level-DB-API. |
| `db_request_context.py` | Per-Request-DB-Transaktionskontext. |
| `default_config.py` | Default-Werte für `CONFIG`-Dict. |
| `exchange_runtime.py` | Runtime-Wiring für aktive Exchanges. |
| `exchange_secret.py` | Key-Load/Save via `services/encryption`. |
| `http_routes.py` | Kleinere HTTP-Utility-Routen (Healthcheck, etc.). |
| `lifecycle.py` | Graceful-Shutdown-Handler; Signal-Registrierung. |
| `logging_setup.py` | Zentrales Logging: `configure_logging()` mit JSON/Color-Unterstützung. |
| `market_cache.py` | App-Level-Cache für Market-Snapshots. |
| `ml_models.py` | Initialisierung der ML-Modelle (Random Forest, XGBoost, LSTM). |
| `paper_mode.py` | Paper-Trading-Simulation. |
| `prometheus_metrics.py` | `/metrics`-Endpoint für Prometheus. |
| `request_helpers.py` | `get_json_body`, `safe_int`, `safe_float`, `safe_bool`, `normalize_exchange_name`. |
| `runtime.py` | `run_server()` – startet Background-Threads, Ready-Summary, SocketIO-Server. |
| `security.py` | CSP-/CSRF-/Rate-Limit-Header, Security-Middleware. |
| `session_guard.py` | Session-Timeout, Manipulationsschutz. |
| `socket_emit.py` | Thread-safe Emit-Wrapper für SocketIO. |
| `socket_error_logger.py` | Fehler-Logger für fehlgeschlagene Socket-Emits. |
| `startup_view.py` | Startup-Banner + Ready-Summary (farbige Multi-Section-Box). |
| `tax_export.py` | CSV/JSON-Export der Steuerreports. |
| `time_compat.py` | Kompatibilitätswrapper für `datetime.utcnow` → `now(timezone.utc)`. |
| `trade_export.py` | Export von Trades (CSV). |
| `trading_classes.py` | Domain-Objekte: `Position`, `Trade`, `BotState`. |
| `trading_ops.py` | Trade-Open/Close-Operationen auf Domain-Ebene. |
| `websocket_authz.py` | Socket-Authorisierung (Admin/User-Rolle). |
| `websocket_guard.py` | `WsRateLimiter` – LRU-basiertes Rate-Limiting pro Socket-Sid. |
| `websocket_state.py` | Per-Socket-State mit Bereinigung bei Disconnect. |
| `ws_rate_gate.py` | Event-Gate für WebSocket-Rate-Limits. |

## Weitere Verzeichnisse

| Pfad | Inhalt |
|------|--------|
| `templates/` | Jinja2-Templates (`auth.html`, `auth_admin.html`, `dashboard.html`, statische Seiten, `_partials/`). |
| `static/js/` | Frontend: `dashboard.js`, `socket_manager.js`, `state_store.js`, `page_i18n.js`, `trevlix_translations.js`. |
| `static/css/` | `dashboard.css`, `auth.css`, Landing-Page-CSS. |
| `docker/` | `mysql-init.sql` (Schema), Nginx-Configs, SSL-Helfer. |
| `tests/` | Pytest-Suite (500+ Tests) – Namen spiegeln das Ziel-Modul (`test_risk.py`, `test_virginie.py`, …). |
| `tasks/` | Session-Tracking: `todo.md`, `lessons.md`, `memory.md`, `plan.md`. |
| `scripts/` | Operational Scripts: `backup_db.sh`, `health_check.sh` (vom Installer erzeugt). |

---

## Hinweise zur Pflege

Neue Module bitte hier mit einer Zeile Zweckbeschreibung ergänzen. Bei
Umstrukturierungen sollte zuerst dieses Mapping aktualisiert werden, bevor
der Code umgezogen wird – das verhindert Drift zwischen Doku und Realität.
