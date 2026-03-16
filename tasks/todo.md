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

### Ergebnis

- **Vorher:** 131 Tests, Admin-Config unsicher, kein Auto-Start, keine User-Settings
- **Nachher:** 141/141 Tests ✓ | Lint ✓ | Format ✓ | 10 neue API-Endpunkte

## Session: improve-and-optimize-MPdc7 (2026-03-16)

### Aufgaben

- [x] Market Data Caching: TTL-Cache für FearGreed + Dominance API-Aufrufe
- [x] WebSocket Rate-Limit Memory Leak Fix (zeitbasierte Eviction alle 60s)
- [x] Password Strength: Weak-Pattern + Sonderzeichen-Pflicht bei Registrierung
- [x] Type Hints auf MySQLManager DB-Methoden und RiskManager
- [x] Connection Pool Health Monitoring (pool_stats(), Erschöpfungs-Warnung)
- [x] 21 neue Tests für alle Verbesserungen

### Phase 2: Unique Features

- [x] Trade DNA Fingerprinting & Pattern Mining (services/trade_dna.py)
- [x] Smart Exit Engine – Volatility-Adaptive SL/TP (services/smart_exits.py)
- [x] Discord-Notifications für DNA-Boost und Smart Exit
- [x] Integration in server.py
- [x] 39 neue Tests

### Ergebnis

- **Vorher:** 122 Tests
- **Nachher:** 182/182 Tests ✓ | Lint ✓ | Format ✓

## Session: fix-bugs-create-docs-gC9Lq (2026-03-15)

- [x] CLAUDE.md erstellt
- [x] Bug #1: Thread-Safety in `services/encryption.py` behoben
- [x] Bug #2: Schwache Passwort-Erkennung in `validate_env.py` behoben

## Session: improve-install-script-NpvV7 (2026-03-15)

- [x] install.sh v2.0.0 – MariaDB, Domain+SSL, Fail2ban, UFW, Bugfixes

---

## Session: optimize-and-new-features-V3RYE (2026-03-16)

### Aufgaben

- [x] **Performance Attribution Engine** – Hedge-Fund-Style Profit/Loss-Analyse (5 Dimensionen + Kreuz-Attribution)
- [x] **Adaptive Strategy Weighting** – Self-Learning Weights mit Exponential Decay + Regime-Sensitivity
- [x] **FundingRateTracker Optimierung** – `requests.get` → `httpx.get` für konsistentes Connection-Pooling
- [x] **server.py Integration** – Beide Features in weighted_vote(), close_position(), Snapshot
- [x] **4 neue API-Endpunkte** – `/api/v1/performance/attribution`, `/contributors`, `/strategies/weights`
- [x] **49 neue Tests** – test_performance_attribution.py (25) + test_adaptive_weights.py (17) + 1 skipped
- [x] **README.md** – Komplett überarbeitet (korrekte Projektstruktur, alle Services, Python 3.11+)
- [x] **CHANGELOG.md** – v1.2.0 Release dokumentiert
- [x] Lint ✓ | Format ✓ | 249/249 Tests ✓

### Neue Dateien

| Datei | Beschreibung |
|-------|-------------|
| `services/performance_attribution.py` | Performance Attribution Engine – 5-dimensionale Profit/Loss-Analyse |
| `services/adaptive_weights.py` | Adaptive Strategy Weighting – Self-Learning Strategie-Gewichte |
| `tests/test_performance_attribution.py` | 25 Tests für Performance Attribution |
| `tests/test_adaptive_weights.py` | 17 Tests für Adaptive Weights |

### Geänderte Dateien

| Datei | Änderung |
|-------|----------|
| `server.py` | Imports, Initialisierung, weighted_vote() Integration, close_position(), Snapshot, 4 API-Endpunkte |
| `services/risk.py` | `requests` → `httpx` in FundingRateTracker |
| `README.md` | Komplett überarbeitet |
| `CHANGELOG.md` | v1.2.0 Entry |
| `tasks/todo.md` | Session-Dokumentation |

### Ergebnis

- **Vorher:** 182 Tests, fixe Strategie-Gewichte, keine Performance-Analyse
- **Nachher:** 249/249 Tests ✓ | Lint ✓ | Format ✓ | 2 einzigartige Features | README aktuell
