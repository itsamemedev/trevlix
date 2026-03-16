# Tasks

## Session: follow-instructions-VGCsp

### Aufgaben

- [x] Repository erkunden und verstehen
- [x] Tests ausführen und Fehler identifizieren (41 failing)
- [x] Fehlende Dependencies installieren (ccxt, flask-cors, flask-socketio, httpx)
- [x] Alle 131 Tests zum Bestehen bringen
- [x] Ruff Lint-Fehler beheben (7 Fehler, davon 1 echter Bug B023)
- [x] Code formatieren (5 Dateien)
- [x] CI/CD Pipeline komplett grün

### Behobene Probleme

| # | Datei | Problem | Fix |
|---|-------|---------|-----|
| 1 | `server.py:5363` | B023: Lambda bindet Loop-Variable `ex` nicht | `lambda ex=ex:` – bindet Wert zum Aufrufzeitpunkt |
| 2 | `server.py` (4x) | UP017: `timezone.utc` statt `datetime.UTC` | Auto-fix via ruff |
| 3 | `server.py:1753` | UP017: `timezone.utc` statt `datetime.UTC` | Auto-fix via ruff |
| 4 | `services/config.py:217` | UP037: Quoted type annotation | Auto-fix via ruff |
| 5 | `services/notifications.py:75` | UP017: `timezone.utc` statt `datetime.UTC` | Auto-fix via ruff |
| 6 | `ai_engine.py`, `routes/auth.py`, `server.py`, `tests/test_auth.py`, `validate_env.py` | Formatierung | `ruff format` |

### Ergebnis

- **Vorher:** 41 Tests failing, 7 Lint-Fehler, 5 Formatierungsprobleme
- **Nachher:** 131/131 Tests ✓ | Lint ✓ | Format ✓

## Session: process-list-systematically-VYM2A

### Aufgaben

- [x] Aktuellen Stand verifizieren (Tests, Lint, Format)
- [x] 3 Formatierungsprobleme in services/ beheben (market_data.py, risk.py, strategies.py)
- [x] Erneut verifizieren: 131/131 Tests ✓ | Lint ✓ | Format ✓
- [x] Commit und Push

### Ergebnis

- **Vorher:** 3 services-Dateien nicht korrekt formatiert
- **Nachher:** 131/131 Tests ✓ | Lint ✓ | Format ✓ (29/29 Dateien)

## Session: admin-settings-trading-bot-qur3J

### Aufgaben

- [x] Admin-only Zugriff auf .env Einstellungen absichern (sensible Felder blockiert)
- [x] Farbige Konsolenausgabe (ANSI-Farben, COLOR_LOGS env var)
- [x] User-Settings in DB/Profil speichern (settings_json, API-Endpunkte)
- [x] Exchange-Integration: Default-Deaktiviert, user_exchanges Tabelle
- [x] Admin Multi-Exchange Management (alle Exchanges gleichzeitig)
- [x] KI-Gemeinschaftswissen Service (services/knowledge.py, shared_knowledge Tabelle)
- [x] LLM-Anbindung (Ollama/LM Studio/OpenAI-kompatibel via LLM_ENDPOINT)
- [x] Bot Auto-Start ohne Admin-Login (AUTO_START env var)
- [x] Projekt weiter modularisiert (exchange_manager.py, knowledge.py)
- [x] Repo aufgeräumt: Lint, Format, Tests
- [x] 10 neue Tests für KnowledgeBase, alle 141 Tests bestehen

### Neue Dateien

| Datei | Beschreibung |
|-------|-------------|
| `services/knowledge.py` | KI-Gemeinschaftswissen Service (Markt-Insights, LLM-Anbindung) |
| `services/exchange_manager.py` | Multi-Exchange Manager (cached Instanzen, Admin/User) |
| `tests/test_knowledge.py` | 10 Unit-Tests für KnowledgeBase |

### Geänderte Dateien

| Datei | Änderung |
|-------|----------|
| `server.py` | Farbige Logs, Admin-Config-Schutz, User-Settings-API, Exchange-API, Knowledge-API, Auto-Start |
| `.env.example` | AUTO_START, COLOR_LOGS, LLM_ENDPOINT, LLM_API_KEY |
| `docker/mysql-init.sql` | user_exchanges + shared_knowledge Tabellen |

### Neue API-Endpunkte

| Route | Methode | Auth | Beschreibung |
|-------|---------|------|-------------|
| `/api/v1/user/settings` | GET/POST | User | User-Settings lesen/speichern |
| `/api/v1/user/exchanges` | GET/POST | User | Exchange-Konfigurationen |
| `/api/v1/user/exchanges/<id>/toggle` | POST | User | Exchange an/aus |
| `/api/v1/user/exchanges/<id>` | DELETE | User | Exchange löschen |
| `/api/v1/user/api-keys` | POST | User | API-Keys aktualisieren |
| `/api/v1/admin/exchanges` | GET | Admin | Alle User-Exchanges |
| `/api/v1/admin/exchanges/<id>/toggle` | POST | Admin | Admin Exchange-Toggle |
| `/api/v1/knowledge/summary` | GET | User | Markt-Zusammenfassung |
| `/api/v1/knowledge/<category>` | GET | User | Wissens-Kategorie |
| `/api/v1/knowledge/query` | POST | User | LLM-Anfrage |

### Ergebnis

- **Vorher:** 131 Tests, Admin-Config unsicher, kein Auto-Start, keine User-Settings
- **Nachher:** 141/141 Tests ✓ | Lint ✓ | Format ✓ | 10 neue API-Endpunkte

## Review

CI-Pipeline würde jetzt alle Stufen bestehen: Lint → Test → Coverage → Docker Build.

## Session: improve-and-optimize-MPdc7 (2026-03-16)

### Aufgaben

- [x] Market Data Caching: TTL-Cache für FearGreed + Dominance API-Aufrufe
- [x] WebSocket Rate-Limit Memory Leak Fix (zeitbasierte Eviction alle 60s)
- [x] Password Strength: Weak-Pattern + Sonderzeichen-Pflicht bei Registrierung
- [x] Type Hints auf MySQLManager DB-Methoden und RiskManager
- [x] Connection Pool Health Monitoring (pool_stats(), Erschöpfungs-Warnung)
- [x] 21 neue Tests für alle Verbesserungen
- [x] Lint ✓ | Format ✓ | Tests ✓

### Geänderte Dateien

| Datei | Änderung |
|-------|----------|
| `services/market_data.py` | `_TTLCache` Klasse + 5-Min-Cache für FearGreed & Dominance |
| `routes/auth.py` | Sonderzeichen-Pflicht + 15 Weak-Pattern-Checks bei Registrierung |
| `routes/websocket.py` | Zeitbasierte Rate-Limit-Eviction (60s Intervall statt >1000) |
| `server.py` | WS-Rate-Limit Fix + Type Hints auf DB-Methoden |
| `services/risk.py` | Type Hints auf `reset_daily`, `update_peak`, `update_prices` |
| `services/db_pool.py` | `pool_stats()` Monitoring + Pool-Erschöpfungs-Warnung |
| `tests/test_improvements.py` | 21 neue Tests (TTL-Cache, Password, Pool-Stats) |

### Ergebnis

- **Vorher:** 122 Tests, kein API-Caching, Memory-Leak-Risiko, schwache Passwort-Policy
- **Nachher:** 143/143 Tests ✓ | Lint ✓ | Format ✓ | 6 Verbesserungen

### Phase 2: Unique Features (2026-03-16)

- [x] Trade DNA Fingerprinting & Pattern Mining (services/trade_dna.py)
- [x] Smart Exit Engine – Volatility-Adaptive SL/TP (services/smart_exits.py)
- [x] Discord-Notifications für DNA-Boost und Smart Exit
- [x] Integration in server.py (open_position, close_position, manage_positions, snapshot)
- [x] 3 neue API-Endpunkte (/api/v1/trade-dna, /api/v1/trade-dna/patterns, /api/v1/smart-exits)
- [x] trade_dna DB-Tabelle (server.py + docker/mysql-init.sql)
- [x] 39 neue Tests (test_trade_dna.py + test_smart_exits.py)
- [x] Lint ✓ | Format ✓ | 182/182 Tests ✓

### Neue Dateien (Phase 2)

| Datei | Beschreibung |
|-------|-------------|
| `services/trade_dna.py` | Trade DNA Fingerprinting – 7-dimensionaler Fingerprint + Pattern Mining |
| `services/smart_exits.py` | Volatility-Adaptive SL/TP – ATR-basierte dynamische Exit-Level |
| `tests/test_trade_dna.py` | 19 Tests für DNA-Engine |
| `tests/test_smart_exits.py` | 20 Tests für Smart Exit Engine |

### Geänderte Dateien (Phase 2)

| Datei | Änderung |
|-------|----------|
| `server.py` | DNA + Smart Exits Integration (open/close/manage/snapshot + 3 API-Endpunkte) |
| `docker/mysql-init.sql` | `trade_dna` Tabelle mit Indizes |
| `services/notifications.py` | `dna_boost()` + `smart_exit()` Discord-Methoden |

### Ergebnis (Phase 2)

- **Vorher:** 143 Tests, fixe SL/TP, kein Trade-Pattern-Learning
- **Nachher:** 182/182 Tests ✓ | Lint ✓ | Format ✓ | 2 einzigartige Features

## Session: fix-bugs-create-docs-gC9Lq (2026-03-15)

### Aufgaben

- [x] Vollständiges Codebase-Audit durchgeführt
- [x] CLAUDE.md erstellt (Workflow Orchestration, Task Management, Core Principles, Architecture)
- [x] Bug #1: Thread-Safety in `services/encryption.py` behoben – `Fernet()` Instanziierung nun innerhalb des Locks
- [x] Bug #2: Schwache Passwort-Erkennung in `validate_env.py` – jetzt auch Substring-Matches gefunden (z.B. "password123")
- [x] `tasks/lessons.md` aktualisiert
- [x] Lint ✓ | Format ✓ | Tests ✓

### Behobene Bugs

| # | Datei | Problem | Fix |
|---|-------|---------|-----|
| 1 | `services/encryption.py:57` | Thread-Safety: `Fernet(_get_fernet._temp_key)` außerhalb des Locks – Race Condition möglich | `return Fernet(...)` in den `with _fernet_lock:` Block verschoben |
| 2 | `validate_env.py:177` | Schwache Werte nur per Exact-Match erkannt – "password123" wurde nicht erkannt | `any(w in val for w in weak_values)` – auch Substring-Matches werden jetzt erkannt |

### Neue Dateien

| Datei | Beschreibung |
|-------|-------------|
| `CLAUDE.md` | Workflow-Richtlinien für Claude Code (aus Bild-Vorgabe) – Orchestration, Task Management, Core Principles, Projekt-Regeln |

### Ergebnis

- **Vorher:** 2 Bugs offen, kein CLAUDE.md
- **Nachher:** 141/141 Tests ✓ | Lint ✓ | Format ✓ | CLAUDE.md ✓ | Bugs behoben ✓

## Session: improve-install-script-NpvV7 (2026-03-15)

### Aufgaben

- [x] Bugs im install.sh behoben (--dir Flag, VENV_DIR vor Definition verwendet)
- [x] MySQL durch MariaDB ersetzt (direkte Installation)
- [x] Domain-Abfrage hinzugefügt (z.B. example.com, app.example.com)
- [x] Certbot SSL-Zertifikat Integration (Let's Encrypt)
- [x] Nginx Reverse Proxy Konfiguration (bei Domain-Setup)
- [x] Fail2ban Installation & Konfiguration (SSH, Nginx, Trevlix Login)
- [x] UFW Firewall Regeln verbessert (SSH, HTTP/HTTPS oder Port 5000)
- [x] Zusammenfassung mit allen Zugangsdaten (Admin, MariaDB, Domain)
- [x] .env vollständiger mit allen Variablen aus .env.example
- [x] Passwort-Generierung nach venv (Fernet-Key korrekt)

### Behobene Bugs

| # | Zeile | Problem | Fix |
|---|-------|---------|-----|
| 1 | Z.37-44 | `--dir` Flag: `shift` in `for`-Loop funktioniert nicht | `while [[ $# -gt 0 ]]` mit korrektem `shift 2` |
| 2 | Z.52 | `INSTALL_DIR` wird nach Flag-Parsing erneut hart gesetzt | `CUSTOM_INSTALL_DIR` Variable, Default via `${CUSTOM_INSTALL_DIR:-/opt/trevlix}` |
| 3 | Z.281 | `$VENV_DIR` vor Definition verwendet (Fernet-Key) | Secret-Generierung nach venv-Erstellung verschoben |
| 4 | Z.202 | `python3.8` in detect_python obwohl min. 3.9 | Entfernt |
| 5 | Z.135 | UUOC: `cat /etc/debian_version \| cut` | `cut -d. -f1 < /etc/debian_version` |

### Neue Features

| Feature | Beschreibung |
|---------|-------------|
| Domain-Setup | Interaktive Domain-Abfrage mit Validierung |
| Certbot SSL | Automatisches Let's Encrypt Zertifikat + Auto-Renewal |
| Nginx Proxy | Vollständiger Reverse Proxy mit Rate-Limiting, WebSocket, Security Headers |
| Fail2ban | SSH (3 Versuche/2h Ban), Nginx, Trevlix-Login (5 Versuche/1h Ban) |
| UFW Hardening | Default deny incoming, SSH immer erlaubt, Domain: 80/443, sonst: 5000 |
| Credential-Anzeige | Admin-PW, DB-User/PW, Root-PW am Ende sichtbar |

### Ergebnis

- **Vorher:** install.sh v1.0.4 mit Bugs, MySQL, keine Domain/SSL/Fail2ban
- **Nachher:** install.sh v2.0.0 – MariaDB, Domain+SSL, Fail2ban, UFW, Bugfixes
