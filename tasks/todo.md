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

---

## Session: fix-bugs-update-versions-xno0f (2026-03-18)

### Aufgaben

- [x] Codebase auf Bugs durchsucht (2 Subagents parallel)
- [x] 6 Bugs behoben (config.py, ai_engine.py, notifications.py, server.py, risk.py)
- [x] Versionsnummern synchronisiert (utils.py, pyproject.toml, Dockerfile, 10 Templates)
- [x] CHANGELOG.md v1.3.2 Eintrag hinzugefügt
- [x] Lint ✓ | Format ✓ | 249/249 Tests ✓

### Behobene Bugs

| # | Datei | Problem | Fix |
|---|-------|---------|-----|
| 1 | `services/config.py:178/224` | `int(MYSQL_PORT)` crasht bei nicht-numerischem Wert | `_safe_port()` mit try/except |
| 2 | `ai_engine.py:197` | `recent_trades[-10:]` crasht bei None | None-Guard hinzugefügt |
| 3 | `services/notifications.py:81` | Discord fields-Tupel < 2 Elemente → IndexError | `if len(f) >= 2` Filter |
| 4 | `server.py:2069` | Gleicher fields-Tupel-Bug (duplizierter Code) | `if len(f) >= 2` Filter |
| 5 | `server.py:3858` | OrderbookImbalance crasht bei leerem Orderbook | Empty bids/asks Check |
| 6 | `services/risk.py:137` | `except Exception: pass` zu breit | `(ValueError, TypeError, IndexError)` |
| 7 | `server.py:1698` | SQL Table-Name ohne Quoting | Backtick-Quoting hinzugefügt |

### Version-Sync

| Datei | Vorher | Nachher |
|-------|--------|---------|
| `services/utils.py` | 1.2.0 | 1.3.2 |
| `pyproject.toml` | 1.1.1 | 1.3.2 |
| `Dockerfile` | v1.1.0 | v1.3.2 |
| 10 Templates | v1.3.0 (hardcoded) | v1.3.2 |

### Ergebnis

- **Vorher:** 6 Bugs, Versionen inkonsistent (1.1.1 / 1.2.0 / v1.3.0)
- **Nachher:** 249/249 Tests ✓ | Lint ✓ | Format ✓ | Alle Versionen auf 1.3.2

### Phase 2: Tiefgehende Bug-Suche (15+ weitere Bugs)

- [x] 3 Subagents parallel: server.py, services/, routes+ai_engine
- [x] 15+ Bugs in 10 Dateien behoben

| # | Datei | Problem | Fix |
|---|-------|---------|-----|
| 1 | `server.py` (7x) | `float(data.get(...))` ohne Validierung | `_safe_float()` Hilfsfunktion |
| 2 | `server.py` | `payload["sub"]` KeyError in JWT | `.get("sub")` mit None-Check |
| 3 | `server.py` | `r["features"]` KeyError in Training-Daten | `.get()` mit Fallback |
| 4 | `server.py` | DataFrame mit < 2 Zeilen → IndexError | `len(df) < 2` Guard |
| 5 | `ai_engine.py` | `self.scaler` None bei Prediction | `is not None` Check |
| 6 | `ai_engine.py` | `strat_importances.mean()` doppelt berechnet, div-by-zero | Zwischenvariable |
| 7 | `ai_engine.py` | `predictions_made += 1` außerhalb Lock | In Lock verschoben |
| 8 | `routes/auth.py` (3x) | CSRF Token Timing-Attack | `hmac.compare_digest()` |
| 9 | `services/risk.py` | NaN von `np.corrcoef()` nicht gehandelt | Expliziter NaN-Check |
| 10 | `services/knowledge.py` | Unbegrenztes Cache-Wachstum (Memory Leak) | `_evict_cache()` + Max-Size |
| 11 | `services/market_data.py` | `or 50` maskiert legitimem 0-Wert | Explizite None-Prüfung |
| 12 | `services/exchange_manager.py` | `ex_data["exchange"]` KeyError | `.get("exchange", "unknown")` |
| 13 | `services/smart_exits.py` | `compute()` ohne entry_price Guard | Guard am Funktionsanfang |

- **Ergebnis:** 249/249 Tests ✓ | Lint ✓ | Format ✓
