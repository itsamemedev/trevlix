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

## Session: admin-settings-trading-bot-qur3J (2026-03-10)

### Lektion 4: Sensible Config-Felder schützen
**Problem:** `api_admin_config_update` erlaubte das Ändern von `admin_password` über die API.
**Regel:** Immer eine `_PROTECTED_KEYS` frozenset verwenden und sensible Felder (Secrets, DB-Credentials) NUR über .env änderbar machen.

### Lektion 5: Neue DB-Tabellen auch in mysql-init.sql hinzufügen
**Problem:** `CREATE TABLE IF NOT EXISTS` in `_init_db_once()` erstellt Tabellen zur Laufzeit, aber Docker-Setup nutzt `mysql-init.sql`.
**Regel:** Neue Tabellen IMMER an beiden Stellen hinzufügen: `server.py:_init_db_once()` UND `docker/mysql-init.sql`.

### Lektion 6: Exchanges default deaktiviert
**Problem:** Neue Exchange-Konfigurationen sollten nicht automatisch aktiv sein.
**Regel:** `enabled TINYINT DEFAULT 0` in der Tabelle, `enabled=False` als Parameter-Default. User muss explizit aktivieren.

## Session: fix-bugs-create-docs-gC9Lq (2026-03-15)

### Lektion 7: Lock-Scope bei Thread-Safety beachten
**Problem:** `_get_fernet._temp_key` wurde innerhalb des Locks gesetzt, aber `Fernet(key)` wurde außerhalb des Locks aufgerufen. In einer Race Condition kann ein Thread den Key lesen, bevor er vollständig gesetzt wurde (obwohl CPython GIL das in der Praxis selten trifft).
**Regel:** Alle Operationen, die auf einer im Lock gesetzten Variable basieren, müssen INNERHALB des Lock-Kontexts stattfinden. `return`-Statements in `with lock:` Blöcken sind erlaubt und korrekt.
**Code:** `services/encryption.py:54-57`

### Lektion 8: Set-Membership vs. Substring-Prüfung bei Passwort-Validation
**Problem:** `val in weak_set` prüft nur exakte Übereinstimmung. "password123" wäre nicht erkannt, obwohl es ein schwaches Muster enthält.
**Regel:** Für Passwort-Schwäche-Checks immer BEIDE prüfen: `val in weak_set or any(w in val for w in weak_set)`. Achtung auf False Positives (z.B. "administration" enthält "admin") – für Security-Checks ist ein strengerer Ansatz vertretbar.
**Code:** `validate_env.py:174-178`
