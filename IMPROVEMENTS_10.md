# TREVLIX – 10 Neue Verbesserungsvorschläge

Aufbauend auf den bestehenden 50 Verbesserungen in `IMPROVEMENTS.md` folgen hier
10 weitere, priorisierte Vorschläge für mehr Stabilität, Sicherheit und Wartbarkeit.

---

## 1. Async HTTP-Client für externe API-Aufrufe nutzen

**Problem:** Alle externen API-Aufrufe (CryptoPanic, CoinGecko, Discord-Webhooks,
Exchange-Ticker) nutzen synchrones `requests.post()`/`requests.get()` mit Threads.
`httpx` ist bereits in `requirements.txt`, wird aber nicht verwendet. Synchrone
Aufrufe blockieren den Thread-Pool und können bei Timeouts den Bot verlangsamen.

**Lösung:** Die vorhandene `httpx`-Dependency nutzen und schrittweise die
`requests`-Aufrufe migrieren. Besonders für Batch-Aufrufe wie den Arbitrage-Scanner
(`ArbitrageScanner.scan`) oder News-Sentiment-Abfragen bringt `httpx.AsyncClient`
mit Connection-Pooling und HTTP/2-Support erhebliche Performance-Vorteile.

**Betroffene Stellen:**
- `DiscordNotifier.send()` (Zeile ~1536) – `requests.post(url, ...)`
- `ArbitrageScanner.scan()` – `ex.fetch_tickers()` über ccxt
- CryptoPanic-Client in `services/cryptopanic.py`

**Priorität:** Mittel (Performance)

---

## 2. Secret-Werte aus CONFIG-Dict entfernen / lazy laden

**Problem:** Das globale `CONFIG`-Dict (Zeile 300–460 in `server.py`) enthält
Klartext-API-Keys und Passwörter (`api_key`, `secret`, `admin_password`,
`jwt_secret`, `short_api_key`, `short_secret`). Diese Werte sind über den
gesamten Prozess-Lebenszyklus im Speicher und könnten bei einem Memory-Dump
oder Debug-Endpoint versehentlich exponiert werden.

**Lösung:**
1. Secrets nicht im CONFIG speichern, sondern bei Bedarf direkt aus
   `os.getenv()` lesen (Lazy Loading).
2. Alternativ: Eigene `SecretStr`-Klasse, die `__repr__` und `__str__`
   maskiert (`"***"`), damit Secrets nicht in Logs/Tracebacks auftauchen.
3. Den `/api/v1/config`-Endpoint (falls vorhanden) prüfen und sicherstellen,
   dass niemals Secret-Felder im Response enthalten sind.

**Priorität:** Hoch (Sicherheit)

---

## 3. Graceful Degradation bei fehlender MySQL-Verbindung

**Problem:** Wenn MySQL beim Start nicht erreichbar ist, schlägt `_init_db()`
fehl und der gesamte Bot ist nicht funktionsfähig. Es gibt keinen Reconnect-
Mechanismus auf Anwendungsebene – nur den Pool-Level `ping(reconnect=True)`.

**Lösung:**
1. Startup-Retry: Bei fehlgeschlagener DB-Verbindung bis zu 5x mit
   exponentiellem Backoff (2s, 4s, 8s, 16s, 32s) wiederholen.
2. Health-Check (`/api/v1/status`) sollte den DB-Status klar als `"degraded"`
   melden, statt einen 500-Error zu werfen.
3. Paper-Trading-Modus könnte auch ohne DB funktionieren (In-Memory Fallback
   für Trade-History), damit der Bot nicht komplett ausfällt.

**Priorität:** Hoch (Zuverlässigkeit)

---

## 4. Thread-Safety im BotState verbessern

**Problem:** Die `BotState`-Klasse verwaltet Listen und Dicts, die von
mehreren Threads gleichzeitig gelesen und geschrieben werden (Bot-Loop,
WebSocket-Handler, API-Endpoints). Operationen wie `state.arb_log.insert(0, ...)`
gefolgt von `state.arb_log = state.arb_log[:20]` (Zeile ~4272-4282) sind
nicht atomar und können bei Race Conditions zu Datenverlust führen.

**Lösung:**
1. Einen `threading.RLock()` in BotState einführen und für alle
   Lese-/Schreibzugriffe auf shared State nutzen.
2. Alternativ: `collections.deque(maxlen=20)` statt manueller Listen-
   Truncation – `deque` ist thread-safe für append/pop.
3. Für Dashboard-Daten: Snapshot-Pattern einsetzen (periodisch einen
   immutable Snapshot erzeugen, den die API-Endpoints lesen).

**Priorität:** Hoch (Stabilität)

---

## 5. Exchange-API-Fehler differenziert behandeln

**Problem:** Exchange-Interaktionen über ccxt werden pauschal mit
`except Exception` gefangen. Es gibt keine Unterscheidung zwischen
Rate-Limit-Fehlern (`ccxt.RateLimitExceeded`), Netzwerk-Fehlern
(`ccxt.NetworkError`), oder Exchange-seitigen Fehlern (`ccxt.ExchangeError`).

**Lösung:**
1. Differenzierte Exception-Behandlung:
   - `ccxt.RateLimitExceeded` → Exponentieller Backoff + Retry
   - `ccxt.NetworkError` → Retry mit Timeout-Erhöhung
   - `ccxt.InsufficientFunds` → Position-Sizing-Logik korrigieren
   - `ccxt.ExchangeNotAvailable` → Circuit Breaker für Exchange
2. Retry-Decorator mit konfigurierbarem Backoff für alle ccxt-Aufrufe.
3. Exchange-spezifische Fehler-Metriken im Dashboard anzeigen.

**Priorität:** Hoch (Zuverlässigkeit im Live-Trading)

---

## 6. server.py in Module aufteilen (>7000 Zeilen)

**Problem:** `server.py` hat inzwischen über 7000 Zeilen und enthält alles:
Flask-App, Konfiguration, DB-Manager, BotState, Trading-Logik, Strategien,
AI-Engine-Integration, ArbitrageScanner, ShortEngine, Discord-Notifier,
WebSocket-Handler, REST-API-Routen und den Bot-Loop. Dies macht Code-Reviews,
Testing und Debugging extrem schwierig.

**Lösung:** Schrittweise Aufspaltung in fokussierte Module:
```
services/
  trading_engine.py   – BotState, Trade-Execution, Position-Management
  strategies.py       – Alle 9 Strategien
  arbitrage.py        – ArbitrageScanner
  short_engine.py     – ShortEngine
  notifications.py    – DiscordNotifier + Telegram
  market_data.py      – OHLCV-Fetching, Orderbook, Fear&Greed
routes/
  auth.py             – Login, Register, Session (bereits vorhanden)
  api.py              – REST-API (bereits vorhanden)
  websocket.py        – Socket.io-Handler
```
Jedes Modul bekommt einen eigenen Logger und eigene Tests. Die Migration
kann pro Modul erfolgen, ohne den laufenden Betrieb zu stören.

**Priorität:** Mittel (Wartbarkeit – langfristig kritisch)

---

## 7. Konfigurationsvalidierung beim Start

**Problem:** CONFIG-Werte werden ohne Validierung übernommen. Ungültige
Werte wie `stop_loss_pct: -0.5`, `max_open_trades: 0` oder
`scan_interval: 0` führen zu schwer debugbaren Laufzeitfehlern.

**Lösung:**
1. Validierungsfunktion `validate_config(config: dict) -> list[str]`
   die beim Start aufgerufen wird und alle Werte prüft:
   - Numerische Ranges: `0 < stop_loss_pct < 1`, `scan_interval >= 10`
   - Pflicht-Felder: `exchange` muss in `EXCHANGE_MAP` sein
   - Logische Konsistenz: `take_profit_pct > stop_loss_pct`
   - Gegenseitige Abhängigkeiten: `use_shorts=True` erfordert
     `short_api_key` und `short_secret`
2. Bei Validierungsfehlern: Klare Fehlermeldung + Bot startet nicht
   (statt still falsch zu laufen).
3. Optional: Pydantic `BaseSettings` für typsichere Konfiguration.

**Priorität:** Mittel (Fehlerprävention)

---

## 8. Rate-Limiting für WebSocket-Events

**Problem:** Flask-Limiter schützt nur HTTP-Endpoints. Die WebSocket-
Verbindungen (`@socketio.on(...)`) haben kein Rate-Limiting. Ein Client
könnte z.B. `/start_bot` oder `/force_sell` Events in schneller Folge
senden und damit den Bot destabilisieren.

**Lösung:**
1. Einfaches In-Memory-Rate-Limiting für Socket.io-Events:
   ```python
   _ws_limits: dict[str, float] = {}  # sid -> last_action_time
   def ws_rate_check(sid, action, min_interval=2.0):
       ...
   ```
2. Kritische Events (`start_bot`, `stop_bot`, `force_sell`, `update_config`)
   sollten mindestens 2 Sekunden Abstand haben.
3. Bonus: Authentifizierung für WebSocket-Events prüfen (Session-Validierung
   bei jedem Event, nicht nur bei `connect`).

**Priorität:** Mittel (Sicherheit)

---

## 9. Backup-Integrität und Wiederherstellungstest

**Problem:** Backups werden erstellt und optional verschlüsselt
(Verbesserung #49), aber es gibt keinen automatischen Integritätscheck.
Wenn der Fernet-Key sich ändert oder das Backup korrupt ist, fällt das
erst bei einer echten Wiederherstellung auf – im schlimmsten Fall zu spät.

**Lösung:**
1. Nach jedem Backup: SHA-256-Checksum in einer separaten `.sha256`-Datei
   speichern.
2. Automatischer Verify-Step: Backup entpacken (im Temp-Dir) und Checksum
   validieren. Bei Fehler → Alert über Discord/Telegram.
3. `/api/v1/backup/verify/<id>` Endpoint, der ein Backup auf Integrität
   prüft, ohne es wiederherzustellen.
4. Regelmäßiger Test (z.B. wöchentlich): Letztes Backup im Dry-Run-Modus
   wiederherstellen und Ergebnis loggen.

**Priorität:** Mittel (Datensicherheit)

---

## 10. Umgebungsvariablen-Validierung beim Docker-Start

**Problem:** Obwohl `docker-compose.yml` korrekt `${VAR:?Fehlermeldung}`
für Pflichtfelder nutzt, gibt es keine inhaltliche Prüfung. Ein User kann
`MYSQL_PASS=test` oder `JWT_SECRET=abc` setzen und der Container startet
ohne Warnung mit schwachen Credentials.

**Lösung:**
1. `install.sh` oder ein neues `validate_env.py`-Script, das vor dem
   Bot-Start geprüft wird:
   - `MYSQL_PASS`: Min. 16 Zeichen
   - `JWT_SECRET`: Min. 32 Hex-Zeichen
   - `ENCRYPTION_KEY`: Gültiger Fernet-Key (44 Zeichen, base64)
   - `ADMIN_PASSWORD`: Passwort-Policy (wie bei User-Registrierung)
2. Dockerfile: `ENTRYPOINT ["python", "validate_env.py", "&&", "python", "server.py"]`
   oder als Health-Check-Vorbedingung.
3. Warnungen als farbige Ausgabe + Exit-Code 1 bei kritischen Fehlern.

**Priorität:** Mittel (Sicherheit / DevOps)

---

## Zusammenfassung

| # | Verbesserung | Kategorie | Priorität |
|---|---|---|---|
| 1 | Async HTTP-Client (httpx) | Performance | Mittel |
| 2 | Secrets aus CONFIG entfernen | Sicherheit | Hoch |
| 3 | Graceful Degradation bei DB-Ausfall | Zuverlässigkeit | Hoch |
| 4 | Thread-Safety in BotState | Stabilität | Hoch |
| 5 | Differenzierte Exchange-Fehlerbehandlung | Zuverlässigkeit | Hoch |
| 6 | server.py modularisieren (>7000 Zeilen) | Wartbarkeit | Mittel |
| 7 | Konfigurationsvalidierung beim Start | Fehlerprävention | Mittel |
| 8 | Rate-Limiting für WebSocket-Events | Sicherheit | Mittel |
| 9 | Backup-Integrität und Wiederherstellungstest | Datensicherheit | Mittel |
| 10 | Umgebungsvariablen-Validierung (Docker) | Sicherheit / DevOps | Mittel |

**Empfohlene Reihenfolge:** 2 → 4 → 5 → 3 → 8 → 7 → 1 → 6 → 10 → 9
