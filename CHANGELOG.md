# Changelog

All notable changes to TREVLIX are documented in this file.

Format based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Versioning follows [Semantic Versioning](https://semver.org/) — `MAJOR.MINOR.PATCH`.

---

## [1.3.2] – 2026-03-18

### Fixed — Bugfixes & Robustheit

- **`config.py` MYSQL_PORT Crash** — `int(os.getenv("MYSQL_PORT"))` crashte bei nicht-numerischem Wert (z.B. `"abc"`). Neue `_safe_port()` Funktion fängt `ValueError`/`TypeError` ab und fällt auf Port 3306 zurück
- **`ai_engine.py` None-Guard für recent_trades** — `recent_trades[-10:]` crashte mit `TypeError` wenn `None` übergeben wurde. Jetzt wird `None` zu leerer Liste konvertiert
- **Discord Embed Fields IndexError** — `f[0]`/`f[1]` Zugriff in `notifications.py` und `server.py` Discord-Embed-Builder konnte bei Tupeln mit < 2 Elementen crashen. Filter `if len(f) >= 2` hinzugefügt
- **OrderbookImbalance leere Bids/Asks** — `sum(b[1] * b[0] for b in ob["bids"])` crashte wenn Exchange leeres Orderbook lieferte. Expliziter Empty-Check vor Berechnung
- **`risk.py` Korrelation Exception-Handling** — `except Exception: pass` zu breit, verschluckte echte Fehler. Eingeschränkt auf `(ValueError, TypeError, IndexError)`
- **SQL Backup Identifier-Quoting** — Table-Name in Backup-Query verwendet jetzt Backtick-Quoting (`` `table` ``) für Defense-in-Depth

### Changed — Versionssynchronisierung

- **BOT_VERSION** auf `1.3.2` aktualisiert (`services/utils.py`)
- **pyproject.toml** von `1.1.1` auf `1.3.2` synchronisiert
- **Dockerfile** Versionskommentar von `v1.1.0` auf `v1.3.2` aktualisiert
- **Alle Templates** (10 Dateien) von hardcoded `v1.3.0` auf `v1.3.2` aktualisiert

---

## [1.3.1] – 2026-03-17

### Added — Autonome LLM-Optimierungsanfragen

#### KI-Engine: Autonome LLM-Integration (`services/knowledge.py`, `server.py`)
- **Post-Trade LLM-Analyse** — Nach jedem abgeschlossenen Trade wird automatisch eine LLM-Analyse gestartet (async, non-blocking), die Gewinn-/Verlustursachen identifiziert und als `trade_pattern` im Gemeinschaftswissen speichert
- **Periodische Marktanalyse** — Alle ~60 Iterationen generiert die LLM eine gecachte Marktanalyse mit Regime-Bewertung, Fear&Greed-Einschätzung und Handlungsempfehlung (15-Minuten-Cache)
- **Training-Ergebnisse Interpretation** — Nach jedem 3. KI-Training analysiert die LLM Feature-Importance, Accuracy-Werte und Schwellwerte auf Overfitting und Optimierungspotenzial
- **SL/TP-Optimierungs-Bewertung** — Nach jeder Grid-Search-Optimierung bewertet die LLM die Risk/Reward-Änderungen und speichert die Analyse als `risk_pattern`
- **LLM-Response Cache** — 15-Minuten-Cache für LLM-Antworten verhindert redundante Anfragen
- **`/api/v1/knowledge/llm-status`** — Neuer API-Endpunkt zeigt LLM-Status, gecachte Analyse und Anzahl gespeicherter Insights
- **`llm_enabled` Property** — Schnelle Prüfung ob LLM-Endpunkt konfiguriert und verfügbar ist
- **Alle LLM-Aufrufe sind async** — Threading-basiert, blockieren weder Bot-Loop noch Trading-Entscheidungen
- **Graceful Degradation** — Funktioniert ohne LLM-Endpunkt, alle Aufrufe sind optional und fehlerresistent

### Fixed — Bugfixes

- **`get_market_summary()` KeyError-Risiko** — Dict-Zugriff in Top-Symbole und Strategie-Ranking verwendet jetzt konsistent `.get()` statt direktem Bracket-Zugriff (`v["total_trades"]` → `v.get("total_trades", 0)`), verhindert `KeyError` bei korrupten/unvollständigen Daten
- **`get_market_summary()` None-Safety** — `s.get("value")` wird jetzt mit `or {}` abgesichert, da `.get("value", {})` bei explizitem `None`-Wert nicht den Default zurückgibt
- **`_optimize()` fehlende Vorher/Nachher-Referenz** — SL/TP-Werte vor der Optimierung werden jetzt korrekt in `prev_sl`/`prev_tp` gespeichert, um sinnvolle Delta-Berechnung für die LLM-Analyse zu ermöglichen
- **Fourier-Analyse IndexError** — `freqs[1:]` Bounds-Check hinzugefügt, verhindert `np.argmax()` auf leerem Array wenn FFT-Ergebnis zu kurz ist (`server.py:extract_features`)
- **DCA Division-by-Zero** — `total_qty <= 0` Guard vor Durchschnittspreis-Berechnung verhindert Division durch Null bei Edge Cases (`server.py:try_dca`)
- **`manage_positions()` TypeError** — `ticker.get("last")` statt `ticker["last"]` mit None-Check, verhindert `float(None)` Crash wenn Exchange keinen Last-Price liefert
- **Heatmap Race Condition** — `_heatmap_cache` wird jetzt als Kopie unter Lock zurückgegeben, verhindert gleichzeitige Lese-/Schreibzugriffe aus verschiedenen Threads
- **`LiquidityScorer` KeyError** — `config.get("max_spread_pct", 0.5)` statt `config["max_spread_pct"]` verhindert KeyError bei fehlendem Config-Schlüssel (`services/risk.py`)
- **`smart_exits.adapt()` KeyError** — `pos.get("entry")` mit None/Zero-Guard statt `pos["entry"]`, verhindert KeyError und Division-by-Zero bei unvollständigen Position-Daten (`services/smart_exits.py`)
- **`ai_engine.py` Thread-Safety** — `model.classes_` wird jetzt innerhalb des Locks gelesen statt außerhalb, verhindert Race Condition wenn Modell während Prediction ersetzt wird
- **`snapshot()` Division-by-Zero** — `p["entry"]` Division in Long- und Short-PnL-Berechnung mit Zero-Guard geschützt, verhindert Crash wenn Entry-Price fehlt oder 0 ist
- **`close_position()` Division-by-Zero** — `pos["entry"]` Division abgesichert, verwendet Fallback auf aktuellen Preis
- **`close_short()` Division-by-Zero** — Gleicher Fix für Short-Positionen
- **`update_shorts()` Division-by-Zero** — Short-PnL-Berechnung gegen Zero-Entry geschützt
- **`manage_positions()` Division-by-Zero** — Break-Even, Smart-Exit ATR-Schätzung und Partial-TP verwenden jetzt sichere `pos_entry`-Variable mit Fallback
- **`run_backtest()` Division-by-Zero** — Backtest-Simulation prüft `pos.get("entry")` vor Division
- **Grid-Engine Float-als-Boolean** — `if price:` → `if price is not None:`, verhindert stille Fehler wenn Preis exakt 0.0 ist (falsy in Python)
- **SHA256-Backup IndexError** — `f.read().split()[0]` mit Leer-Check geschützt, verhindert Crash bei leerer/korrupter Checksum-Datei
- **LSTM `evaluate()` IndexError** — `lstm.evaluate()[1]` mit Längenprüfung geschützt, verhindert Crash wenn LSTM weniger Metriken zurückgibt als erwartet

---

## [1.3.0] – 2026-03-17

### Added — Production-Ready Upgrade

#### Installer v3.0.0 (`install.sh`)
- **Admin Username/Password Prompt** — Interaktive Eingabe von Admin-Benutzername und -Passwort bei der Installation
- **CLI-Flags** — `--admin-user NAME` und `--admin-pass PASS` für nicht-interaktive Installationen
- **Broad Linux OS Support** — Debian, Ubuntu, Raspberry Pi OS, Linux Mint, CentOS Stream, Rocky Linux, AlmaLinux, RHEL, Fedora, openSUSE, Arch Linux
- **Package Manager Detection** — apt-get, dnf, yum, zypper, pacman mit OS-spezifischen Paketnamen
- **Auto-MOTD Installation** — motd.sh wird automatisch am Ende der Installation eingerichtet
- **Credentials-Datei** — Passwörter werden in `.credentials` (chmod 600) gespeichert statt im Terminal angezeigt
- **requirements.txt First** — Python-Pakete werden primär aus requirements.txt installiert
- **Repo URL** — Korrekter GitHub-Link: `github.com/itsamemedev/Trevlix`

#### MOTD v2.0.0 (`motd.sh`)
- **Broad Linux Support** — Debian/Ubuntu via update-motd.d, RHEL/CentOS/Fedora/openSUSE/Arch via profile.d
- **Raspberry Pi Detection** — Hardware-Modell, CPU-Temperatur mit Warnung bei >75°C
- **Multi-Exchange Anzeige** — Liest `EXCHANGES_ENABLED` aus .env
- **Domain-Aware Dashboard URL** — Erkennt Domain aus ALLOWED_ORIGINS
- **CPU-Info & Architektur** — Prozessor-Modell und Kernanzahl
- **RAM-Warnung** — Visueller Indikator bei >80% Auslastung
- **Robuste IP-Erkennung** — 3 Fallback-Methoden (hostname/ip/ifconfig)
- **TREVLIX_DIR Support** — Benutzerdefiniertes Installationsverzeichnis

#### Professional Login & Registration UI
- **Glassmorphism Redesign** — Login/Register/Admin-Login komplett neu gestaltet mit modernem Glassmorphism-Design
- **Animated Gradient Background** — Subtile, animierte Gradient-Mesh-Hintergründe
- **Inline i18n Engine** — Standalone-Sprachauswahl direkt auf der Login-Seite (5 Sprachen)
- **Password Visibility Toggle** — Eye-Icon zum Anzeigen/Verbergen des Passworts
- **Responsive Design** — Optimiert für Desktop und Mobile
- **Google Fonts Integration** — Barlow Font-Family konsistent mit Dashboard

#### Comprehensive Multi-Exchange `.env.example`
- **Multi-Exchange Konfiguration** — `EXCHANGES_ENABLED` für gleichzeitigen Betrieb aller 5 Exchanges
- **Individuelle API-Credentials** — Separate Blöcke für Crypto.com, Binance, Bybit, OKX (mit Passphrase), KuCoin (mit Passphrase)
- **LLM-Konfiguration** — `LLM_ENDPOINT`, `LLM_API_KEY`, `LLM_MODEL`, `LLM_MAX_TOKENS`, `LLM_TEMPERATURE`
- **Performance-Tuning** — `INDICATOR_CACHE_TTL`, `MARKET_DATA_CACHE_TTL`
- **Backup-Konfiguration** — `BACKUP_INTERVAL_HOURS`, `BACKUP_KEEP_DAYS`
- **Zweisprachige Dokumentation** — Alle Kommentare auf Deutsch und Englisch
- **Secret-Generator-Script** — Python-Einzeiler für alle Schlüssel am Ende der Datei

#### Extended i18n Coverage (24+ neue Keys)
- **Backend (`trevlix_i18n.py`)** — 24 neue Übersetzungskeys: Auth, Orders, Grid Trading, Copy-Trade, Updates, Webhooks, Smart Exit, DNA Pattern, Adaptive Weights, Attribution Report
- **Dashboard (`trevlix_translations.js`)** — Neue Keys für Login-UI, Wizard-Buttons, Loading-Labels
- **Static Pages (`page_i18n.js`)** — Login/Register-Seite Keys, Auth-Messages, Navigation, Footer-Erweiterungen

### Changed
- **Version** — 1.2.0 → 1.3.0 in allen Templates, Dashboard, Auth-Seiten
- **Dashboard** — Hardcoded German strings durch `data-i18n` Attribute ersetzt (Wizard-Buttons, Loading-Label, Paper-Hint)
- **Alle Website-Templates** — Version-Bump auf v1.3.0 (index, about, api-docs, changelog, faq, installation, roadmap, security, strategies)

---

## [1.2.0] – 2026-03-16

### Added — 2 New Unique Features + Optimizations

#### Feature 1: Performance Attribution Engine (`services/performance_attribution.py`)
- **Hedge-Fund-Style Attribution** — Analysiert WOHER Gewinne/Verluste kommen
- **5 Dimensionen** — Aufschlüsselung nach Strategie, Marktregime, Tageszeit, Symbol, Fear & Greed Bucket
- **Kreuz-Attribution** — Regime × Strategy Matrix zeigt welche Strategie in welchem Regime am besten performt
- **Globale Metriken** — Profit Factor, Expectancy, Sharpe Ratio, Win-Rate
- **Top/Worst Contributors** — Identifiziert profitabelste und verlustreichste Faktoren
- **API-Endpunkt** — `GET /api/v1/performance/attribution` (vollständiger Report)
- **API-Endpunkt** — `GET /api/v1/performance/contributors` (Top/Worst-Performer)

#### Feature 2: Adaptive Strategy Weighting (`services/adaptive_weights.py`)
- **Self-Learning Weights** — Strategie-Gewichte passen sich automatisch an Performance an
- **Exponential Decay** — Neuere Trades zählen exponentiell stärker (configurable decay factor)
- **Regime-Sensitivity** — Separate Gewichte pro Marktregime (Bull/Bear/Range/Crash)
- **Gewichts-Clamping** — Begrenzt auf 0.3x–2.5x (verhindert Über-/Untergewichtung)
- **Normalisierung** — Durchschnittliches Gewicht bleibt bei 1.0
- **Rolling Window** — Nur die letzten N Trades zählen (Default: 50)
- **Integration in weighted_vote()** — Adaptive Gewichte ersetzen fixe Gewichte wenn aktiviert
- **API-Endpunkt** — `GET /api/v1/strategies/weights` (Gewichte + Performance)

#### Optimizations
- **FundingRateTracker: `requests` → `httpx`** — Konsistente HTTP-Client-Nutzung, besser für Connection-Pooling
- **Dashboard Snapshot** — Adaptive Weights + Performance Attribution im State-Snapshot integriert
- **Close-Position Integration** — Beide Features zeichnen automatisch bei Trade-Close auf

### Changed
- **README.md** — Komplett überarbeitet: korrekte Projektstruktur (15 Service-Module statt 5), alle Features dokumentiert, Python 3.11+ Badge, 200+ Tests Badge, korrekte Zeilenanzahl (7400+)
- **CHANGELOG.md** — v1.2.0 Release dokumentiert
- **Version** — 1.1.1 → 1.2.0

### Tests
- **35+ neue Tests** — `test_performance_attribution.py` (25 Tests) + `test_adaptive_weights.py` (18 Tests)
- **Alle Tests bestehen** — 200+ Tests ✓ | Lint ✓ | Format ✓

---

## [1.1.1] – 2026-03-09

### Fixed — 40+ Bug Fixes

#### Critical: Connection & Memory Leaks
- **Connection-Leaks behoben** — `_get_conn()` Context-Manager in MySQLManager eingeführt; alle 25+ Methoden auf `with self._get_conn() as conn:` umgestellt; Pool-Semaphore wird nun immer freigegeben
- **Double-Release ConnectionPool** — `_PooledConnection` verhindert jetzt doppelte Semaphore-Freigabe
- **WS-Memory-Leak** — Unbegrenztes Wachstum von `_ws_limits` Dict bereinigt (max 1000 Einträge)
- **Memory-Leak in `_login_attempts`** — Dict wuchs unbegrenzt für jede IP; periodische Bereinigung bei >10.000 Einträgen

#### Security
- **CSRF-Schutz mit Wirkung** — CSRF-Verletzung wurde nur geloggt aber nicht abgelehnt; `abort(403)` nach Audit-Log hinzugefügt
- **XSS-Sanitization** — HTML-Escaping (`esc()`) für innerHTML mit externen Daten (News, Logs, Errors)
- **Security Headers** — `X-XSS-Protection` (deprecated) entfernt, `Permissions-Policy` hinzugefügt

#### Trading Logic
- **weighted_vote() erzeugte nie Signal -1** — `sell_w` wurde nie gezählt, Short-Selling war komplett deaktiviert
- **Partial-TP Level 2+ wurde nie ausgelöst** — `partial_sold == 0` verhinderte nach dem ersten Teilverkauf jeden weiteren
- **Break-Even Stop nie implementiert** — Logik fehlte komplett in `manage_positions()`, jetzt eingefügt
- **N_FEATURES Konstante falsch** — 47 statt 48; `market_vec` hat 30 Elemente, nicht 29

#### Thread-Safety
- **Race-Condition in AIEngine._train** — `self.scaler.fit_transform(X)` mutierte außerhalb des Locks; jetzt lokale Scaler mit atomarer Zuweisung
- **AnomalyDetector Race-Condition** — Training läuft jetzt mit lokalem Scaler unter Lock-Schutz
- **ShortEngine._get_ex() Thread-Safety** — `threading.Lock()` verhindert Race Condition bei parallelen Calls

#### Bug Fixes
- **vol_ratio NameError** — Fehlende Initialisierung wenn CoinGecko-Marktdaten fehlen
- **timedelta.seconds → total_seconds()** an 5 Stellen (Retraining, Cache, Circuit-Breaker, Heatmap, FundingRate)
- **SecretStr nicht an CCXT übergeben** — `.reveal()` aufgerufen statt `str()` das "***" liefert
- **Exchange-Map unvollständig** — kraken, huobi, coinbase fehlten in `EXCHANGE_MAP`
- **datetime.utcnow() → datetime.now(timezone.utc)** in server.py und notifications.py
- **verify_password Fallback** — Kein Fallback wenn bcrypt verfügbar aber Hash ist SHA-256
- **Backup: Secrets nicht ausgeschlossen** — `telegram_token` und `discord_webhook` wurden mit exportiert
- **state.open_trades → state.positions** — `AttributeError` in `/api/v1/health` und `/metrics`
- **Uptime-Berechnung** — `BotState._start_time` hinzugefügt
- **FundingTracker** — `funding_tracker.update(ex)` wird jetzt alle 60 Iterationen aufgerufen
- **API Auth** — `@api_auth_required` Decorator zu `api_audit_log` hinzugefügt
- **ccxt Exchange-Lookup** — `ccxt.__dict__[ex_name]` → `getattr(ccxt, ex_name, None)`
- **Naming: NEXUS/QUANTRA → TREVLIX** — Alle Referenzen in server.py, notifications.py, Exporten korrigiert
- **Lint-Fehler behoben** — B023 (Lambda Loop-Variable), UP017 (datetime.UTC), UP037 (quoted type annotation)

### Changed
- **Navigation** — Login/Register Buttons und Features-Link zu allen Unterseiten hinzugefügt
- **Projektinfo** — QUANTRA → TREVLIX, quantra.com → trevlix.dev, Version synchronisiert

---

## [1.1.0] – 2026-03-08

### 50 Improvements — Architecture, Frontend, Trading & Visual Upgrade

#### Architecture
- **Flask Blueprints** — `server.py` aufgeteilt in `routes/auth.py` und `routes/dashboard.py`
- **Pydantic BaseSettings** — Typ-validierte Konfiguration in `services/config.py`
- **Flask g Dependency Injection** — DB-Verbindungen werden per Request automatisch zurückgegeben

#### Database
- **Composite Index** — `idx_user_time(user_id, created_at)` auf `audit_log` für schnellere Queries

#### Trading
- **Exchange-spezifische Gebühren** — `EXCHANGE_DEFAULT_FEES` Dict + `get_exchange_fee_rate()` mit 1h Cache
- **Aggregierter Balance** — `fetch_aggregated_balance()` über alle konfigurierten Exchanges
- **Korrelationsfilter** — `is_correlated()` mit detailliertem Logging

#### Frontend
- **Dashboard CSS extrahiert** — 390 Zeilen Inline-CSS nach `static/css/dashboard.css`
- **Dashboard JS extrahiert** — 1823 Zeilen Inline-JS nach `static/js/dashboard.js`
- **FOUC Fix** — Inline-Script im `<head>` setzt Theme vor CSS-Laden
- **Keyboard Shortcuts** — `.nav-kbd` Badges in allen Navigations-Items
- **Responsive Tables** — CSS `.table-responsive` mit Shadow-Indikator bei Overflow
- **Loading Overlay** — CSS Skeleton Animation + `#pageLoadOverlay` Spinner

#### Visual Upgrade (v1.1.0)
- **shared-nav.css** — Gradient Nav-Border, Logo-Glow, Gradient CTA-Button, Glassmorphism Mobile Nav
- **index.html** — Gradient Buttons, Card-Glow on Hover, Hero Stat Cards mit Glassmorphism
- **dashboard.css** — Gradient Header-Border, Card-Hover Glow, Gradient Start/Stop-Buttons
- **Alle Doc-Pages** — Gradient H2-Underlines, FAQ Items mit Open-State-Glow, 404 Gradient-Button

#### Infrastructure
- **httpx statt requests** — In `DiscordNotifier` und `CryptoPanicClient` (Performance)
- **SecretStr-Klasse** — Maskiert `api_key`/`jwt_secret`/`mysql_pass` in Logs
- **DB Startup Retry** — Exponentieller Backoff (5 Versuche, 2-32s) in `_init_db()`
- **BotState Thread-Safety** — `threading.RLock` + `collections.deque`
- **ccxt Exception-Handling** — `RateLimitExceeded`, `NetworkError`, `ExchangeNotAvailable`
- **validate_config()** — Prüft Ranges, Pflichtfelder, Abhängigkeiten beim Start
- **WS Rate-Limiting** — `_ws_rate_check()` für `start/stop/pause/close_position`
- **Backup SHA-256 Checksums** — `/api/v1/backup/verify` Endpoint
- **validate_env.py** — Prüft MYSQL_PASS, JWT_SECRET, ENCRYPTION_KEY vor Server-Start
- **CI Workflows** — Trigger auf `claude/**` Branches, Lint-Fehler behoben

#### New Endpoints
- `GET /api/v1/fees` — Exchange-spezifische Gebühren
- `GET /api/v1/balance/all` — Aggregierter Multi-Exchange Balance
- `GET /api/v1/backup/verify` — Backup-Integrität prüfen

---

## [1.0.5] – 2026-03-06

### Added
- **10 Improvements** — httpx, SecretStr, DB-Retry, Thread-Safety, ccxt-Exceptions, Modularisierung, Config-Validierung, WS-Rate-Limiting, Backup-Checksums, validate_env.py
- **Socket.io Stabilität** — `ping_timeout=60`, `ping_interval=25`, `manage_session=True`; `auth_error` Event statt stummer Ablehnung; `request_state` Handler für Reconnects
- **Dashboard Reconnection** — `connect_error` + Reconnection-Optionen; HTTP-Fallback lädt State via `/api/v1/state` vor WS-Connect
- **services/notifications.py** — `DiscordNotifier` als standalone Modul
- **routes/websocket.py** — WebSocket Handler-Registrierung (Migration vorbereitet)

---

## [1.0.4] – 2026-03-02

### 25 Improvements – Installation, Infrastructure & Repository Cleanup

#### Installation (`install.sh`)
1. **Version bump** — Banner updated from `v1.0.0` to `v1.0.4`
2. **`ENCRYPTION_KEY` auto-generation** — Fernet key is now automatically generated and written to `.env` during installation (was missing before, causing unencrypted API key storage)
3. **`MYSQL_ROOT_PASS` auto-generation** — Root password is now generated and added to `.env` (required by `docker-compose.yml` but previously missing)
4. **Pre-flight disk check** — Installation warns if less than 2 GB free disk space is available
5. **Pre-flight RAM check** — Installation warns if less than 512 MB RAM is available
6. **`--help` / `-h` flag** — New `--help` flag documents all available options
7. **`--no-tf`, `--no-shap`, `--yes` flags** — Non-interactive mode for CI/CD pipelines; optional packages can be skipped without prompts
8. **Failure cleanup trap** — `trap cleanup_on_error ERR` automatically rolls back the systemd service on installation failure, preventing broken partial installs

#### Dependencies (`requirements.txt`)
9. **`optuna>=3.5.0` added** — Was used in `ai_engine.py` for Bayesian hyperparameter optimization but missing from `requirements.txt`, causing `ImportError` on fresh installs
10. **`httpx>=0.26.0` added** — Modern async-capable HTTP client as complement to `requests`
11. **Upper version bounds** — All packages now have upper bounds (e.g., `flask>=3.0.0,<4.0.0`) to prevent breaking changes from major upgrades

#### Docker / Infrastructure
12. **Multi-stage Dockerfile** — Separate `builder` and runtime stages; final image contains no build tools (`gcc`, etc.), reducing attack surface and image size
13. **Non-root user in Docker** — Container now runs as `trevlix` user (not `root`), following security best practices
14. **`.dockerignore` created** — Excludes `.env`, `venv/`, `logs/`, `backups/`, `models/`, IDE files, and OS artifacts from the build context
15. **`SECRET_KEY` & `ENCRYPTION_KEY` in `docker-compose.yml`** — Both were missing from the environment block, causing runtime errors
16. **`SESSION_TIMEOUT_MIN` & `TELEGRAM_*` vars** — Added missing environment variables to `docker-compose.yml`
17. **Log rotation** — All three Docker services now have `json-file` logging with `max-size: 10m / max-file: 5` to prevent disk exhaustion
18. **Nginx waits for healthy Trevlix** — Changed `depends_on: trevlix` to use `condition: service_healthy`

#### `.env.example`
19. **`DASHBOARD_SECRET` added** — Was required by `docker-compose.yml` but missing from the template
20. **`MYSQL_ROOT_PASS` added** — Required by `docker-compose.yml` but missing from the template
21. **`SESSION_TIMEOUT_MIN`, `TELEGRAM_*` vars added** — Complete documentation of all supported variables

#### Repository Cleanup
22. **`.gitignore` expanded** — Now covers `venv/`, `models/`, `backups/`, `*.pkl`, `*.db`, `.DS_Store`, IDE files, `optuna.db`, and more
23. **`Makefile` created** — Convenience targets: `make install`, `make dev`, `make docker-up`, `make test`, `make test-cov`, `make lint`, `make format`, `make keys`, `make backup`, `make clean`
24. **`pyproject.toml` created** — Project metadata, `pytest`, `coverage`, and `ruff` configuration in a single file; replaces ad-hoc tool configs
25. **`.editorconfig` created** — Enforces consistent indentation and line endings across Python, JS, HTML, YAML, SQL, and Makefile

### Also Added
- **`services/__init__.py`** — Proper package exports for `ConnectionPool`, `encrypt_value`, `decrypt_value`, `is_encrypted`, `get_cached`, `set_cached`, `invalidate`, `cache_stats`
- **`routes/__init__.py`** — Blueprint structure documentation for future route extraction
- **`tests/conftest.py`** — Shared pytest fixtures: `sample_ohlcv`, `small_ohlcv`, `sample_trade`, `sample_trades`, `encryption_key`, `set_test_env`

---

## [1.0.3] – 2026-03-02

### Added
- **Login & Register buttons** — Navigation bar on the landing page now includes Login and Register buttons with full i18n support (5 languages)
- **Translation keys** — `web_nav_login` and `web_nav_register` added to all five languages (de, en, es, ru, pt)
- **Fixed QT object structure** — Orphaned translation keys that were outside the `QT` object in `trevlix_translations.js` have been moved inside the object (bug fix)
- **GitHub URL** — All placeholder `DEIN_USER/trevlix` links replaced with the correct repository URL `itsamemedev/Trevlix`
- **Multi-user note** — README updated to document per-user API key architecture

### Changed
- **README.md** — Rewritten in English; correct GitHub repository URL
- **CHANGELOG.md** — Rewritten in English

---

## [1.0.2] – 2026-03-02

### Fixed
- **Missing Docker healthcheck endpoint** — `/api/v1/update/status` and `/api/v1/status` did not exist; Docker container stayed permanently "unhealthy" and never started
- **`ta` library build failure** — `ta>=0.11.0` in `requirements.txt` failed during `docker build`; package is not used in code and has been removed
- **Log file in wrong directory** — `nexus.log` was written to the working directory; now uses `logs/trevlix.log` mounted via Docker volume `./logs:/app/logs`
- **`send_file` with relative path** — `dashboard.html` is now loaded with an absolute path (`os.path.abspath(__file__)`) to work regardless of CWD

### Added
- **Healthcheck endpoint** — `GET /api/v1/status` and `GET /api/v1/update/status` return `{"status": "ok", "version": "...", "running": bool}`
- **API docs** — New endpoints documented at `/api/v1/docs`

---

## [1.0.1] – 2026-03-02

### Fixed
- **f-strings without placeholders** — `f"..."` without `{}` in `server.py` (lines 4075, 4836–4838) and `ai_engine.py` (line 352) corrected (unnecessary `f` prefix removed)
- **Unused exception variables** — `except Exception as e` where `e` was never used, changed to `except Exception` (`server.py` lines 589, 600, 617, 1304)
- **Duplicate import** — Local re-import of `CalibratedClassifierCV` inside a function removed; now uses the global import
- **Missing `ai_engine.py` in Dockerfile** — `COPY ai_engine.py .` added; container previously failed with `ModuleNotFoundError`

### Removed
- **Unused imports** — `flask_socketio.disconnect`, `scipy_signal`, `rfft`, `rfftfreq`, `SelectFromModel`, `mutual_info_classif`, `PCA`, `StratifiedKFold`, `QuantileTransformer`, `tensorflow.keras.models.Model`, `LayerNormalization`, `sklearn.ensemble.GradientBoostingClassifier`
- **Unused local variables** — `aid`, `r`, `page`, `step`, `reddit_active`, `twitter`, `X_s`, `scan_regime`

### Added
- **`docker/` directory** — Was completely missing from the repository despite `docker-compose.yml` referencing it
  - `docker/mysql-init.sql` — Full database schema with all 14 tables
  - `docker/nginx.conf` — Nginx reverse proxy with HTTP→HTTPS redirect, WebSocket support (Socket.IO), and security headers
  - `docker/ssl/.gitkeep` — Placeholder for SSL certificates (`trevlix.crt` / `trevlix.key`)
- **`.gitignore`** — `__pycache__/`, `*.pyc`, `*.pyo`, `.env`, `*.log` are now excluded

---

## [1.0.0] – 2026-02-01

### Initial Release

#### Core Engine
- **MySQL database** — 14 tables: Trades, Users, AI Training, Audit Log, Backtest Results, Price Alerts, Daily Reports, Sentiment Cache, News Cache, On-Chain Cache, Genetic Results, Arbitrage, RL Episodes, API Tokens
- **Multi-exchange support** — Crypto.com, Binance, Bybit, OKX, KuCoin simultaneously
- **Flask + Socket.IO** — Real-time dashboard via WebSocket
- **Paper trading mode** — Risk-free testing without real capital
- **Multi-user system** — Multiple portfolios on a single instance, each with their own API keys

#### AI & Machine Learning (14+ Modules)
- **Random Forest Classifier** — Base ensemble model
- **XGBoost** — Gradient boosting for more precise signals
- **LightGBM** — Fast boosting method
- **CatBoost** — Categorical feature support
- **LSTM Ensemble** — Recurrent network for time series (TensorFlow)
- **Stacking Ensemble** — Meta-learner combining all base models
- **Isotonic Calibration** — Calibrated probabilities (`CalibratedClassifierCV`)
- **Walk-Forward Optimization** — Rolling window training against overfitting
- **Optuna Hyperparameter Tuning** — Bayesian optimization (TPE sampler)
- **Anomaly Detection** — Isolation Forest stops bot during flash crashes
- **Genetic Optimizer** — Evolutionary strategy discovery
- **Reinforcement Learning** — PPO agent learns directly from the market
- **Online Learning** — Incremental updates without full retraining
- **Kelly Sizing** — Optimal position sizing based on win probability

#### Market Analysis & Signals
- **Fear & Greed Index** — Alternative.me data as sentiment signal
- **Multi-timeframe analysis** — 1m, 5m, 15m, 1h, 4h, 1d
- **Regime classification** — Bull/Bear/Sideways/High-Volatility detection
- **BTC dominance filter** — Automatic market phase detection
- **Orderbook imbalance** — Bid/Ask ratio as signal
- **News sentiment** — CryptoPanic real-time news as AI signal
- **On-chain data** — Whale alerts, exchange flows (CryptoQuant)
- **Arbitrage scanner** — Detects price differences across exchanges

#### Risk Management
- **Circuit Breaker** — Automatic trading pause on losing streaks
- **Trailing Stop-Loss** — Dynamic SL adjustment
- **Break-Even Stop-Loss** — Automatic SL adjustment after profit
- **Correlation filter** — Prevents over-correlated positions
- **Liquidity check** — Minimum volume check before entry
- **Symbol cooldown** — Locks symbols after a loss
- **Partial Take-Profit** — Staged profit taking (25/50/100%)
- **DCA strategy** — Averaging down on falling positions
- **Monte-Carlo risk analysis** — Portfolio simulations with VaR calculation
- **Short selling** — Bearish trades on futures (Binance/Bybit)

#### Dashboard & UI
- **Real-time dashboard** (`dashboard.html`) — WebSocket-based, no reload needed
- **Landing page** (`index.html`) — Product presentation
- **Backtest module** — Historical strategy tests with detailed metrics
- **Grid trading UI** — Visual configuration of grid levels
- **Audit log view** — Full action history

#### Security & Access
- **JWT authentication** — Secure API tokens for external tools
- **2FA (TOTP)** — Two-factor authentication
- **IP whitelist** — Access control by IP
- **bcrypt password hashing** — Secure password storage
- **Session management** — Flask session with secret key
- **Role-based access control** — Admin / User roles

#### Notifications & Reporting
- **Discord webhooks** — Real-time alerts for all trades
- **Daily report** — Automatic daily performance summary
- **Auto-backup** — Regular data backup

#### Infrastructure
- **Dockerfile** — Python 3.11 slim image
- **docker-compose.yml** — Trevlix + MySQL 8 + optional Nginx (production profile)
- **install.sh** — One-click installer for Ubuntu/Debian
- **REST API v1** — Full API for external integrations and TradingView webhooks
- **Copy trading** — Followers receive all signals in real time
- **Internationalization** — 5 languages: German, English, Spanish, Russian, Portuguese

---

<!-- Template for future entries:

## [X.Y.Z] – YYYY-MM-DD

### Added
- New features

### Changed
- Changes to existing features

### Fixed
- Bug fixes

### Removed
- Removed features

### Security
- Security patches

-->
