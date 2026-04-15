# Lessons Learned

## Session: fix-bugs-xtf60 (2026-04-15) – Round 2

### Lektion 48: Externe-Preise Division ohne Guard
**Problem:** `rets = [(closes[i]-closes[i-1]) / closes[i-1] for i in range(1,len)]` in
`api_portfolio_optimize` konnte bei einem `closes[i-1] == 0` (z.B. bei pathologischen
OHLCV-Lücken oder Reverse-Split-ähnlichen Events) in ZeroDivisionError laufen, der
den gesamten Endpoint in einen 500er kippt.
**Regel:** Bei List-Comprehensions mit Division durch externe Werte IMMER mit einem
`if divisor` Guard filtern – der pathologische Fall ist selten, aber wenn er auftritt,
reißt er den ganzen Request mit.
**Code:** `server.py:api_portfolio_optimize` (Returns-Berechnung)

### Lektion 49: Cache-Dicts in Services brauchen Thread-Safety
**Problem:** `CryptoPanicService._cache` wurde von `news_fetcher.get_score()` sowohl
aus Flask-Request-Threads (`server.py:/api/v1/news/...`) als auch aus Bot-Loop-Threads
(`app/core/trading_ops.scan_symbol`) ohne Lock geändert. Das `_is_cache_valid` →
`_cache[key]` Muster konnte mit gleichzeitiger `del self._cache[oldest]` Eviction
kollidieren → KeyError im produktiven Hot-Path.
**Regel:** Jeder Service mit internem `_cache`-Dict, der von Bot-Loop UND API-Routen
aufgerufen wird, MUSS einen `threading.Lock` haben und Read-Check-Write-Pattern
atomar ausführen. Gilt auch, wenn der Service im Konstruktor wie ein Singleton wirkt.
**Code:** `services/cryptopanic.py:_cache_lock`

## Session: fix-bugs-xtf60 (2026-04-15)

### Lektion 44: Guards müssen an jeder Division mit demselben Divisor wiederholt werden
**Problem:** In `run_monte_carlo()` wurde `var_pct` mit `if start_value > 0 else 0` geschützt,
aber 20 Zeilen weiter unten `expected_return` teilte erneut durch `start_value` – diesmal
ohne Guard. Ein Zero-Balance-Szenario (Paper-Trading mit 0 USDT) führt zu ZeroDivisionError.
**Regel:** Jeder Zugriff auf einen potenziell 0-Wert braucht einen eigenen Guard. "Ich habe
oben schon geprüft" zählt nicht, wenn die Operation woanders wiederholt wird.
**Code:** `server.py:run_monte_carlo` (expected_return Zeile)

### Lektion 45: Metrik-Aggregation muss konsistente Skalen haben
**Problem:** In `api_multi_exchange_status` wurde `win_rate` für die active-Exchange mit
Live-Runtime-Wert (Prozent) initialisiert, dann in derselben Loop um 1 pro Win-Trade
erhöht (absolute Zahl). Die spätere Neuberechnung `wins/tc*100` wurde explizit für die
active-Exchange übersprungen → Ergebnis: `runtime_win_rate% + count_of_wins` (Unsinn).
**Regel:** Wenn in einem Dict denselben Feld für unterschiedliche Sources unterschiedliche
Skalen verwendet werden, muss die Aggregation per Condition auf die passenden Einträge
beschränkt werden. Lieber active-Exchange komplett aus der Aggregations-Loop ausschließen.
**Code:** `server.py:api_multi_exchange_status` win_rate-Aggregation

### Lektion 46: Defense-in-Depth bei WebSocket-Auth
**Problem:** `uid = session.get("user_id", 1)` fiel auf `user_id=1` (Admin) zurück, wenn
aus irgendeinem Grund die Session-Variable fehlte – obwohl `_ws_auth_required()` vorher
geprüft hatte. Ebenso `int(... or 0)` → user_id=0, was in DB-Queries als ungültiger,
aber lesender Zugriff landen kann.
**Regel:** Nach `_ws_auth_required()` niemals auf einen Default-User-ID (0, 1, ...)
zurückfallen. Bei fehlender user_id explizit Fehler melden und returnen, auch wenn der
Pfad "unmöglich" erscheint.
**Code:** `server.py:on_virginie_chat`, `server.py:on_add_alert`

### Lektion 47: setInterval-Handles immer für Cleanup zuweisen
**Problem:** `setInterval(fn, 60000)` und `setInterval(..., 10000)` in `dashboard.js`
wurden ohne Variable aufgerufen → kein `clearInterval` möglich. Bei SPA-ähnlichen
Navigationen (z.B. Hot-Reload oder fetch-Redirect) laufen die Timer weiter und führen
zu Memory-Leak + unerwünschten API-Calls.
**Regel:** Jedes `setInterval`/`setTimeout` das länger als eine Seiten-Lebenszeit laufen
kann, MUSS einer Variable zugewiesen und im `beforeunload`-Handler gecleart werden.
Bestehender Handler (ab Lektion 6) sollte entsprechend erweitert werden.
**Code:** `static/js/dashboard.js:_installedKeysInterval`, `_insightsInterval`

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

## Session: stabilize-trading-system-mUHzh (2026-04-12)

### Lektion 28: State-Lock bei WebSocket-Handlern für Position-Operationen
**Problem:** `on_close_exchange_position()` las `state.positions.get(symbol)` ohne Lock, während bot_loop gleichzeitig Positionen modifizieren konnte → Race Condition führt zu Doppel-Sells oder Sells auf nicht-existierende Positionen.
**Regel:** Jeder WebSocket-Handler der `state.positions` oder `state.short_positions` liest, MUSS `with state._lock:` verwenden. Besonders kritisch bei Operationen die auf dem gelesenen Wert eine Exchange-Order auslösen.
**Code:** `server.py:on_close_exchange_position`

### Lektion 29: Silent Exception-Handler in Live-Trading sind gefährlich
**Problem:** `TradeExecutionService.execute_buy()` fing Balance-Check-Fehler mit `except Exception: pass` ab. Bei API-Timeout wurde die Order trotzdem platziert, ohne den echten Kontostand zu kennen → Margin-Risiko.
**Regel:** In Live-Trading-Pfaden NIEMALS Exceptions stillschweigend schlucken. Bei fehlgeschlagener Balance-Prüfung die Order blockieren und loggen. Paper-Trading darf toleranter sein, Live-Trading nicht.
**Code:** `services/trade_execution.py:execute_buy`

### Lektion 30: Rate-Limiter mit clear-all bei Overflow erlaubt Burst-Angriffe
**Problem:** `WsRateLimiter` löschte bei >5000 Einträgen ALLE Limits mit `.clear()`. Ein Angreifer konnte viele IDs registrieren → Overflow → alle Limits gelöscht → ungebremster Burst.
**Regel:** Bei Rate-Limit-Overflow LRU-Eviction (älteste 20% entfernen) statt clear-all. So bleiben aktive Limits erhalten und nur inaktive werden entfernt.
**Code:** `app/core/websocket_guard.py:WsRateLimiter.check`

### Lektion 31: fetch().json() ohne .ok-Check crasht bei HTTP-Fehlern
**Problem:** 6 Stellen im Dashboard verwendeten `await(await fetch(url)).json()` ohne Status-Prüfung. Bei 404/500 Responses ist `.json()` undefined → TypeError → Section bricht ab.
**Regel:** JEDER fetch-Aufruf braucht `if(!r.ok) throw/return` vor `.json()`. Pattern: `const r=await fetch(url); if(!r.ok) throw new Error('HTTP '+r.status); const data=await r.json();`
**Code:** `static/js/dashboard.js:loadHeatmap, openChart, loadBtHistory, loadTaxReport`

### Lektion 32: CONFIG-Werte müssen Range-validiert werden
**Problem:** `on_update_config()` validierte Typen (int/float/bool), aber nicht Wertebereiche. `max_open_trades=-5` oder `stop_loss_pct=0` passierte die Validierung, führte aber zu absurdem Bot-Verhalten.
**Regel:** Für alle numerischen Trading-Parameter Ober- und Untergrenzen definieren. Reject statt Clamp, damit der User explizites Feedback bekommt.

## Session: stabilize-trading-system-5fY6A (2026-04-13)

### Lektion 33: Cooldown muss VOR dem Exchange-Call gesetzt werden
**Problem:** `create_market_buy_order()` kann eine Exception werfen, NACHDEM die Order beim Exchange angenommen wurde (z.B. Netzwerk-Timeout auf der Response). Wenn `mark_order()` erst bei Erfolg aufgerufen wird, steht kein Cooldown – der Bot kann beim nächsten Tick denselben Symbol erneut kaufen → Duplicate Order.
**Regel:** In Live-Execution den Cooldown IMMER vor dem Exchange-Call setzen. Lieber ein paar Sekunden „verlorenes" Trade-Window als eine Doppelorder.
**Code:** `services/trade_execution.py:execute_buy, execute_sell`

### Lektion 34: Eager-Pop + Sell-Fail = verlorene Position
**Problem:** `close_position` hat die Position vor dem Sell aus `state.positions` entfernt, um Double-Close zu verhindern. Wenn der Sell danach fehlschlägt, verliert der Bot die Tracking-Referenz – die Coins liegen noch auf dem Exchange, aber niemand überwacht sie.
**Regel:** Bei Eager-Pop Patterns IMMER einen Restore-Pfad bei Fehler einbauen: bei Sell-Failure die Position unter dem Lock zurückschreiben.
**Code:** `app/core/trading_ops.py:close_position`

### Lektion 35: Silent 1e-12 Fallback bei Division ist gefährlich
**Problem:** `qty = invest / max(price, 1e-12)` schützt zwar vor Division-by-Zero, erzeugt aber bei price=0 eine astronomisch große qty, die dann an den Exchange gesendet werden kann.
**Regel:** Eingaben am Systemrand explizit validieren (`if price <= 0: return error`). Nie auf ein Epsilon-Fallback verlassen, wenn der Fallback einen sinnlosen Wert produziert.
**Code:** `services/trade_execution.py:execute_buy`

### Lektion 36: DB-Deletes IMMER mit Owner-Scope
**Problem:** `delete_alert(aid)` löschte Preis-Alerts rein per ID ohne user_id-Filter. Jeder authentifizierte User konnte Alerts fremder User löschen (IDOR).
**Regel:** Jeder DELETE/UPDATE auf einer multi-user-Tabelle muss einen `WHERE user_id=%s`-Filter haben, außer der Aufrufer ist nachweislich Admin. API-Layer muss user_id aus Session/JWT ziehen und an DB durchreichen.
**Code:** `app/core/db_manager.py:delete_alert`, `server.py:on_delete_alert`

### Lektion 37: Snapshot-then-Overwrite ist Balance-Diebstahl auf Thread-Ebene
**Problem:** `bot_loop` hat im Grid-Block `bal_ref = [state.balance]` außerhalb des Locks gesetzt und am Ende `state.balance = bal_ref[0]` geschrieben. Wenn parallel ein `close_position` oder `execute_buy` die Balance geändert hat, ging diese Änderung verloren – die Balance wurde auf einen veralteten Wert "zurückgesetzt".
**Regel:** Bei mutablen Share-Variablen in Multi-Thread-Code NIE mit Snapshot überschreiben. Stattdessen Delta berechnen und unter Lock additiv anwenden: `state.X += delta`.
**Code:** `app/core/trading_ops.py:bot_loop` (Grid-Block)

## Session: trading-dashboard-production-QB4Sj (2026-04-13)

### Lektion 38: Greenfield-Prompts gegen maturen Codebase prüfen
**Problem:** Der Session-Prompt las sich wie ein kompletter Rewrite-Auftrag
(„Erstelle ein modernes Trading-Dashboard...", „VOLLSTÄNDIGER CODE keine
Kürzungen"). Der Codebase war aber bereits v1.7.1, 476 Tests grün, 100+ Fixes
in den letzten Sessions, Ruff clean. Ein blinder Rewrite hätte Wochen von
Security-Hardening (IDOR, XSS, Race Conditions, Cooldown-Ordering) zerstört.
**Regel:** Vor jedem „baue X" erst `tasks/todo.md`, `tasks/lessons.md`,
`LAST_WORK.md`, `PROJECT_STRUCTURE.md` lesen und Tests/Lint-Status prüfen.
Bei Konflikt zwischen Prompt und Ist-Zustand AskUserQuestion nutzen, nicht
den Prompt wörtlich nehmen.

### Lektion 39: Jinja-Include für Nav/Footer ist risikoarm extrahierbar
**Problem:** 9 statische Templates hatten dupliziert/driftend dieselbe
Navigation und denselben Footer. Data-i18n-Keys waren je Template
unterschiedlich komplett (manche hatten `data-i18n` auf `/Home`, andere nicht).
**Lösung:** `templates/_partials/{site_nav,site_mobile_nav,site_footer}.html`
mit `{% with active='x' %}{% include ... %}{% endwith %}`-Pattern. Die
Partials standardisieren den i18n-Stand auf das jeweils vollständigste Template.
**Regel:** Vor Extract: `awk '/<pattern>/,/<endtag>/' | md5sum` über alle
Kandidaten, um Drift zu quantifizieren. Bei >2 Varianten auf die i18n-vollste
normalisieren, nicht die erste Datei.

### Lektion 40: i18n-Key-Lint als Regressionsschutz
**Problem:** Lektion 17 warnte, dass 85+ `data-i18n`-Keys keine Entsprechung
in `trevlix_translations.js` hatten. Ohne automatisierten Check schleicht sich
diese Drift bei jedem Template-Edit zurück.
**Lösung:** `tests/test_i18n_sync.py` parst beide JS-Dicts (`QT`, `PT`) mit
Regex, extrahiert alle `data-i18n`-Keys aus `templates/**/*.html` und failt,
sobald ein Key fehlt oder weniger als 5 Sprachen hat. Läuft in <200 ms.
**Regel:** Sobald eine Lessons-Learned-Regel eine menschliche
Checkliste vorschreibt, mit einem Test automatisieren — sonst wird sie
vergessen.

### Lektion 42: `send_from_directory`/`send_file` rendert kein Jinja
**Problem:** `routes/dashboard.py` lieferte statische HTML-Seiten via
`send_from_directory(template_dir, filename)` aus, obwohl die Templates
Jinja-Direktiven wie `{% include '_partials/site_footer.html' %}` und
`{{ csrf_token() }}` enthielten. Diese Tags wurden im Browser als
Literal-Text ausgeliefert – Partials wurden nie eingebunden und der
CSRF-Meta-Tag enthielt den String `{{ csrf_token() }}` statt des Tokens.
**Regel:** Sobald ein Template irgendeine Jinja-Syntax (`{%`, `{{`) enthält,
MUSS der View `render_template(name)` verwenden. `send_file`/`send_from_directory`
sind nur für reine statische Assets gedacht (Bilder, PDFs, JS). Prüfstein
vor Commit: `grep -l '{%\|{{' templates/*.html` und dann sicherstellen,
dass die Routen dieser Templates `render_template` nutzen.
**Code:** `routes/dashboard.py`, `routes/auth.py:index`

### Lektion 41: Pre-existing Test-Failures nicht stillschweigend als grün melden
**Problem:** `test_eight_exchanges_supported` erwartet 8 Exchanges, seit
Commit 83139e0 sind es 11. Test war beim Start der Session bereits rot.
Versuchung: einfach ignorieren und `497 passed` behaupten.
**Regel:** Baseline-Tests vor der Arbeit ausführen. Pre-existing Fails
mit `--deselect` dokumentieren und im Abschlussbericht explizit als
„pre-existing, außerhalb Scope" markieren — niemals als „alle grün" melden.

## Session: fix-cryptopanic-api-PVU5n (2026-04-15)

### Lektion 42: Fallback-Ketten vollständig durchreichen
**Problem:** `services/cryptopanic.py:fetch_posts` hatte zwei 404-Fallback-
Pfade (currencies-Filter entfernen **oder** v2→v1 wechseln), aber sie
waren alternativ statt verkettet. Wenn das v2-Endpoint sowohl mit als
auch ohne currencies 404 lieferte (Logs: `developer/v2/posts/...` 404
für RENDER, BBSOL, DBR, SCR, …), wurde der v1-Legacy-Fallback nie
angestoßen — kein Hard-Fail wurde zu einem stillen „keine News".
**Regel:** Mehrstufige Fallback-Logik explizit als Matrix modellieren
(hier: `{v2, v1} × {mit currencies, ohne currencies}`) und in einer
Schleife durchlaufen, statt Spezialfälle ineinander zu verschachteln.
Jeder 404-Zweig muss entscheiden, ob er *weiter* oder *abbrechen* soll —
niemals „Fallback fehlgeschlagen" ohne die nächste Option zu testen.
**Code:** `services/cryptopanic.py:_request_posts`, `fetch_posts`
