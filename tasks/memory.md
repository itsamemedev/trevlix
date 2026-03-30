# TREVLIX – Session Memory

Dieses Dokument speichert den aktuellen Projektstand und wichtige Kontextinformationen
zwischen Sessions.

---

## Projekt-Status

**Version:** 1.5.0
**Status:** Aktiv in Entwicklung
**Tests:** 284+ passing (pytest)
**Lint:** Clean (ruff)

---

## Architektur-Entscheidungen

### DB Connection Pool
- **Pool-Size:** 15 (konfigurierbar via `DB_POOL_SIZE` env var, vorher: 5)
- **Timeout:** 30s (konfigurierbar via `DB_POOL_TIMEOUT` env var, vorher: 10s)
- **Grund:** Pool-Size 5 war zu klein, verursachte Login-Ausfälle nach langem Betrieb
- **Health-Monitoring:** `_check_pool_health()` wird alle 10 Bot-Iterationen aufgerufen
- **Stale-Cleanup:** `cleanup_stale()` Methode entfernt tote Verbindungen und erstellt neue
- **Fix:** Healthcheck-Endpoint nutzt jetzt `_get_conn()` Context-Manager statt direktem `_conn()`

### Login / Auth Flow
- Login redirected zu `/` welches `dashboard.html` liefert
- Session enthält: `user_id`, `username`, `user_role`, `last_active`, `session_created`
- JWT-Cookie wird gesetzt für Socket.io-Auth
- `/api/v1/state` liefert jetzt `user_role` aus der Session
- Initial State Fetch im Dashboard appliziert jetzt die Rolle sofort

### Dashboard Role-System
- CSS-Klasse `admin-only` versteckt Elemente standardmäßig
- `body.is-admin` macht admin-only Elemente sichtbar
- `applyRoleUI()` setzt CSS-Klassen UND inline display-Styles
- **Analytics** Section und Nav-Button sind jetzt `admin-only`
- Role wird aus HTTP-State UND WebSocket-Update angewendet

### MCP-Tool-Integration
- `services/mcp_tools.py`: MCPToolRegistry mit 8 eingebauten Tools
- Tools: market_price, market_news, technical_summary, portfolio_status,
  risk_assessment, knowledge_query, trade_history, strategy_performance
- Integration in `services/knowledge.py` via `query_llm_with_tools()`
- Unterstützt sowohl OpenAI tool_use als auch Ollama Text-Parsing
- API-Endpunkte: `/api/v1/mcp/tools` (GET), `/api/v1/mcp/execute` (POST)
- Tool-Ergebnis-Cache: 60s TTL, max 200 Einträge

---

## Wichtige Dateien

| Datei | Zweck |
|-------|-------|
| `server.py` | Haupt-Applikation (Flask + Socket.io) |
| `services/db_pool.py` | Thread-sicherer MySQL Connection Pool |
| `services/knowledge.py` | KI-Gemeinschaftswissen + LLM-Integration |
| `services/mcp_tools.py` | MCP-Tool-Registry für KI-Tools |
| `routes/auth.py` | Login, Register, Logout, Admin-Auth |
| `routes/dashboard.py` | Statische Seiten-Routes |
| `templates/dashboard.html` | Haupt-Dashboard SPA |
| `static/js/dashboard.js` | Dashboard JavaScript (121 KB) |
| `static/css/dashboard.css` | Dashboard Styles |

---

## Bekannte Probleme / Offene Punkte

1. ~~DB-Pool exhaustion nach langem Betrieb~~ -> Fixed (Pool 5->15, Health-Monitoring)
2. ~~Login redirect funktioniert nicht~~ -> Fixed (user_role in /api/v1/state, initiale Role-Anwendung)
3. ~~Analytics für nicht-Admin sichtbar~~ -> Fixed (admin-only Klasse)
4. `db.pool_stats()` und `db.get_connection()` fehlten -> Hinzugefügt
5. Dashboard-Template braucht noch Anpassungen ans Admin-Design (User: "wie auf dem Bild")

---

## Environment Variablen (neu)

| Variable | Default | Beschreibung |
|----------|---------|-------------|
| `DB_POOL_SIZE` | 15 | Maximale DB-Verbindungen im Pool |
| `DB_POOL_TIMEOUT` | 30 | Timeout in Sekunden für Pool-Acquire |

---

## Zuletzt geändert

- **2026-03-30:** DB-Pool Fix, Login-Redirect Fix, Analytics Admin-Only, MCP-Integration, Memory.md erstellt
