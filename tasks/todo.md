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
