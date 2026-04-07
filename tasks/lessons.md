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

## Session: improve-and-optimize-MPdc7 (2026-03-16)

### Lektion 9: Externe API-Aufrufe immer cachen
**Problem:** `FearGreedIndex.update()` und `DominanceFilter.update()` riefen bei jedem Bot-Zyklus die externe API auf, obwohl sich die Daten nur alle 5-10 Minuten ändern.
**Regel:** Externe API-Aufrufe immer mit TTL-Cache versehen. Minimum 5 Minuten für Marktdaten, die sich selten ändern.
**Code:** `services/market_data.py:_TTLCache`

### Lektion 10: In-Memory-Dicts brauchen zeitbasierte Eviction
**Problem:** `_ws_limits` Dict wuchs unbegrenzt, weil Cleanup nur bei >1000 Einträgen stattfand. Bei niedrigem Traffic wurde nie aufgeräumt.
**Regel:** In-Memory-Caches und Rate-Limit-Dicts brauchen zeitbasierte Eviction (z.B. alle 60s), nicht nur größenbasierte. Verhindert schleichende Memory-Leaks.
**Code:** `server.py:_ws_rate_check`, `routes/websocket.py:_ws_rate_check`

### Lektion 11: Bucket-Grenzen in Tests genau prüfen
**Problem:** Test erwartete `confidence=0.8` → "strong", aber Bucket-Grenze für "unanimous" lag bei 0.70. Wert 0.8 >= 0.70 → "unanimous", nicht "strong".
**Regel:** Bei Tests mit Bucketized-Werten immer die exakten Grenzen prüfen. Am besten den Wert so wählen, dass er klar in den gewünschten Bucket fällt (z.B. 0.65 statt 0.8 für "strong" bei Grenze 0.70).
**Code:** `tests/test_trade_dna.py:108`

### Lektion 12: Neue Features non-invasiv integrieren
**Problem:** Trade DNA und Smart Exits mussten in bestehende Trading-Logik integriert werden, ohne Seiteneffekte.
**Regel:** Neue Features immer hinter Config-Flags schalten (`use_trade_dna`, `use_smart_exits`). Fallback auf bestehendes Verhalten wenn deaktiviert. Integration an klar definierten Punkten: open_position() für Initialisierung, close_position() für Recording, manage_positions() für laufende Anpassung.

## Session: optimize-and-new-features-V3RYE (2026-03-16)

### Lektion 13: Normalisierung beeinflusst Tests mit absoluten Werten
**Problem:** Test `test_exponential_decay` erwartete `weights["EMA-Trend"] >= 1.0`, aber Normalisierung (9 Strategien bei Default 1.0, nur 1 angepasst) drückte den absoluten Wert unter 1.0.
**Regel:** Bei normalisierten Gewichten keine absoluten Schwellwerte testen, sondern relative Vergleiche: "Strategie A sollte höher sein als Strategie B". Normalisierung ändert absolute Werte, aber relative Ordnung bleibt erhalten.
**Code:** `tests/test_adaptive_weights.py:test_exponential_decay`

### Lektion 14: `requests` → `httpx` konsistent halten
**Problem:** `FundingRateTracker` nutzte noch `requests.get`, während alle anderen Services bereits `httpx` verwendeten. Inkompatible Error-Handling-Muster.
**Regel:** HTTP-Client einheitlich im Projekt verwenden. Wenn `httpx` der Standard ist, alle Services migrieren. Verhindert Verwirrung bei Exception-Handling (`requests.HTTPError` vs `httpx.HTTPStatusError`).

## Session: update-docs-fix-bugs-NdjFI (2026-03-17)

### Lektion 15: Globale Dicts in Multi-Thread-Umgebungen IMMER mit Lock schützen
**Problem:** `_ws_limits` und `_login_attempts` Dicts wurden von mehreren Threads gleichzeitig gelesen und geschrieben, ohne Lock-Protection. CPython GIL schützt nicht vor logischen Race Conditions (check-then-act).
**Regel:** Jedes globale Dict, das von mehreren Threads geändert wird, braucht einen dedizierten `threading.Lock()`. Check-then-act Muster (read → decide → write) müssen atomar unter einem Lock stattfinden.
**Code:** `server.py:_ws_limits_lock`, `server.py:_login_attempts_lock`

### Lektion 16: Silent Exception Handling kann Security-Checks umgehen
**Problem:** `except (ValueError, TypeError): pass` beim Session-Timeout-Parsing erlaubte, dass eine korrumpierte `last_active` Session-Variable den Timeout-Check komplett überspringt → User bleibt ewig eingeloggt.
**Regel:** Bei Security-relevanten Exception-Handlern nie `pass` verwenden. Im Zweifel die sicherere Aktion wählen (Session invalidieren statt stillschweigend fortfahren).
**Code:** `server.py:_before_request_hooks`

### Lektion 17: i18n-Keys in HTML und JS synchron halten
**Problem:** 85+ `data-i18n` Keys in HTML-Templates hatten keine Entsprechung in `trevlix_translations.js`. Betroffene UI-Elemente zeigten den Key-Name statt übersetztem Text.
**Regel:** Bei Hinzufügen neuer `data-i18n` Attribute in Templates IMMER gleichzeitig die Keys in `trevlix_translations.js` für alle 5 Sprachen (de, en, es, ru, pt) ergänzen.
**Code:** `static/js/trevlix_translations.js`

### Lektion 18: Lambda-Captures in Threads innerhalb von Loops
**Problem:** `lambda: self.db.save_ai_sample(p["features"], won, regime_str)` in einem Thread innerhalb einer Loop bindet `p` per Referenz. Wenn der Thread startet, hat die Loop `p` möglicherweise schon überschrieben.
**Regel:** Bei `threading.Thread(target=lambda: ...)` innerhalb von Loops IMMER Default-Parameter verwenden: `lambda f=p["features"], w=won: self.db.save_ai_sample(f, w)`.
**Code:** `server.py:3580`

### Lektion 19: Globale Caches brauchen Locks, nicht nur globale Dicts
**Problem:** `_fee_cache` und `_heatmap_cache` hatten check-then-act Patterns ohne Lock (if cached → return cached, else compute → set cache). Concurrent requests konnten veraltete oder inkonsistente Werte lesen.
**Regel:** Jeder globale Cache mit zeitbasierter Invalidierung braucht einen Lock um das Read-Check-Write-Pattern atomar zu machen.
**Code:** `server.py:_fee_cache_lock`, `server.py:_heatmap_lock`

### Lektion 20: Versionsnummern zentral verwalten
**Problem:** `routes/auth.py` Templates enthielten hardcoded `v1.3.0`, während `services/utils.py:BOT_VERSION` und README `v1.2.0` zeigten.
**Regel:** Versionsnummern NIE in Templates/HTML hardcoden. Immer aus einer zentralen Quelle (`BOT_VERSION`) referenzieren. Bei jeder Version-Bump alle Stellen prüfen: `grep -r "v1\." --include="*.py" --include="*.html"`.

### Lektion 21: Klassen in server.py vs. services/ synchron halten
**Problem:** `DiscordNotifier` in `server.py` fehlten `dna_boost()` und `smart_exit()` Methoden, die in `services/notifications.py` existierten. Aufruf verursachte `AttributeError` bei jedem Trade mit DNA/Smart Exits.
**Regel:** Bei duplizierten Klassen (server.py vs. services/) IMMER prüfen ob alle aufgerufenen Methoden in BEIDEN Versionen existieren. Langfristig: Duplikate eliminieren.
**Code:** `server.py:DiscordNotifier`, `services/notifications.py:DiscordNotifier`

### Lektion 22: WebSocket-Handler dürfen nicht blockieren
**Problem:** `on_force_genetic()` rief `genetic.evolve()` synchron auf, was den WebSocket-Thread blockierte und die UI einfroren lies.
**Regel:** Heavy Operations in WebSocket-Handlern IMMER in `threading.Thread(target=..., daemon=True).start()` wrappen. Alle anderen Handler (`force_train`, `manual_backup`) machen das bereits korrekt.
**Code:** `server.py:on_force_genetic`

### Lektion 23: Request-Parameter IMMER validieren
**Problem:** 11 API-Routes verwendeten `int(request.args.get(...))` ohne Fehlerbehandlung. Ungültige Eingaben (z.B. `?limit=abc`) verursachten unbehandelte `ValueError`.
**Regel:** Request-Parameter nie direkt mit `int()` konvertieren. Immer `_safe_int(val, default)` oder try/except verwenden. Gilt für alle Typen: int, float, etc.
**Code:** `server.py:_safe_int`

### Lektion 24: Lock-Symmetrie bei Read/Write
**Problem:** `is_correlated()` las `_price_history` ohne Lock, während `update_prices()` unter Lock schrieb. Race Condition bei gleichzeitigem Scan und Update.
**Regel:** Wenn eine Methode unter Lock SCHREIBT, müssen alle Methoden die denselben State LESEN ebenfalls den Lock halten. Snapshot-Pattern: unter Lock kopieren, außerhalb berechnen.

## Session: refactor-modularize-repo-r6fhS (2026-04-07)

### Lektion 25: Module-Globals Init-Pattern für Extraction
**Problem:** Extrahierte Klassen aus server.py referenzieren globale Variablen (CONFIG, db, state, etc.).
**Lösung:** `init_*()` Funktionen pro Modul, die Runtime-Globals injizieren. Zwei Phasen: 1) Early init (CONFIG, log) vor Instanz-Erstellung, 2) Late init (state, discord, etc.) nach allen Instanzen.
**Regel:** Bei jeder Klassen-Extraktion prüfen: welche Globals werden im `__init__` vs. in Methoden referenziert? `__init__`-Globals müssen VOR der Instanziierung gesetzt werden.

### Lektion 26: Fehlende Imports bei Extraktion
**Problem:** Beim Extrahieren von Klassen aus server.py fehlten Standard-Library-Imports (`os`, `deque`, `json`, etc.), weil sie im Original-File am Dateianfang standen.
**Regel:** Nach jeder Extraktion sofort `python3 -c "import ast; ast.parse(open(file).read())"` UND Tests laufen lassen. Proaktiv alle `import`-Abhängigkeiten der Klasse prüfen (grep nach stdlib-Symbolen).

### Lektion 27: Inline-Imports nicht vergessen
**Problem:** `TaxReportGenerator` wurde inline importiert (`from services.tax_report import TaxReportGenerator`) innerhalb eines entfernten Abschnitts und war danach nicht mehr verfügbar.
**Regel:** Vor dem Entfernen eines Abschnitts immer `grep` für `from ... import` und `import ...` innerhalb dieses Abschnitts ausführen, um inline-Imports zu identifizieren.
