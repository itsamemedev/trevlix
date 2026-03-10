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

## Review

CI-Pipeline würde jetzt alle Stufen bestehen: Lint → Test → Coverage → Docker Build.
