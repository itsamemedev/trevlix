# Lessons Learned

## Session: follow-instructions-VGCsp (2026-03-09)

### Lektion 1: Loop-Variable Capture in Lambdas (B023)
**Problem:** `lambda: func(ex)` in einer Loop – `ex` wird per Referenz gebunden, nicht per Wert.
**Regel:** Immer `lambda ex=ex: func(ex)` verwenden, um den aktuellen Wert zu binden.
**Code:** `server.py:5363`

### Lektion 2: CI schlägt bei Lint fehl, obwohl Tests lokal grün sind
**Problem:** `ruff check` und `ruff format --check` laufen separat in CI. Tests können grün sein, aber CI scheitert trotzdem an der Lint-Stufe.
**Regel:** Immer zuerst `ruff check .` und `ruff format --check .` ausführen, bevor committed wird.

### Lektion 3: Fehlendes Modul = alle abhängigen Tests schlagen fehl
**Problem:** Ein einziges fehlendes Modul (`ccxt`) blockiert den Import von `server.py` und lässt 41 Tests fehlschlagen.
**Regel:** Bei `ModuleNotFoundError` zuerst alle fehlenden Deps auf einen Schlag installieren, dann erneut testen.
