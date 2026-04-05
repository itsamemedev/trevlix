# Changelog

All notable changes to TREVLIX are documented in this file.

Format based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Versioning follows [Semantic Versioning](https://semver.org/) — `MAJOR.MINOR.PATCH`.

---

## [1.5.3] – 2026-04-05

### Fixed — Exchange Integration & Passphrase Bug

#### Critical Bug Fixes
- **OKX / KuCoin / Crypto.com could not authenticate as primary exchange**: `create_exchange()` in `server.py` never passed the API passphrase, so all three exchanges (which require a passphrase in addition to key/secret) silently failed authentication. Now fixed via the new `exchange_factory` module — passphrase is correctly passed as CCXT's `password` parameter in all code paths.
- **`safe_fetch_tickers` had no fallback for non-`cryptocom` exchanges**: If `ex.fetch_tickers(symbols)` failed for Kraken, Huobi, Coinbase (or any other exchange), the entire scan crashed. Now implements a 3-stage robust fallback chain: `batch(symbols) → batch() + client-filter → per-symbol fetch`.

#### New — Centralized Exchange Factory (`services/exchange_factory.py`)
- `create_ccxt_exchange()` — single source of truth for CCXT instance creation across all 8 supported exchanges (cryptocom, binance, bybit, okx, kucoin, kraken, huobi, coinbase).
- `safe_fetch_tickers()` — robust ticker fetching with automatic fallback strategies.
- `get_fee_rate()` — cached per-exchange fee rate lookup (1h TTL).
- `EXCHANGE_DEFAULT_FEES`, `PASSPHRASE_REQUIRED` constants.
- **4 places deduplicated**: `create_exchange()`, `ArbitrageScanner._get_ex()`, `ShortEngine._get_ex()`, `ExchangeManager._create_instance()` all now delegate to the factory.

#### Configuration
- **New env var `API_PASSPHRASE`**: Required for OKX, KuCoin, Crypto.com when used as primary exchange. Added to `CONFIG` dict and `services/config.py` `_PROTECTED_KEYS`.
- **New env var `SHORT_PASSPHRASE`**: For the short-selling exchange (if passphrase-protected).
- **`.env.example` updated**: Now documents all 8 supported exchanges (previously only 5). Added sections for Kraken, Huobi/HTX and Coinbase Advanced Trade.
- `EXCHANGES_ENABLED` example extended with all 8 exchanges.

#### Testing
- **25 new tests** in `tests/test_exchange_factory.py` verify:
  - All 8 exchanges instantiate without errors
  - Passphrase is correctly passed as `password` for OKX/KuCoin/Crypto.com
  - `safe_fetch_tickers` fallback strategy (batch fails → filter strategy kicks in)
  - Empty-symbols edge case
  - Fee cache invalidation
- Total tests: **297 passing** (272 existing + 25 new).

#### Modularization
- Removed duplicated `EXCHANGE_DEFAULT_FEES`, `_fee_cache`, `_fee_cache_lock`, `_SINGLE_TICKER_EXCHANGES` from `server.py` (~50 lines deleted — now imported from `services/exchange_factory`).
- Introduced `_reveal_and_decrypt()` helper to eliminate repeated SecretStr-to-plaintext unwrap code.

---

## [1.5.2] – 2026-03-31

### Fixed — Bug Fixes, i18n Completeness & Code Hardening

#### Bug Fixes
- **JSON parsing in `load_ai_samples()`**: Added per-row error handling with type validation (`isinstance(feats, list)`) to prevent crashes from malformed JSON in `ai_training` table. Invalid rows are now skipped with a warning instead of crashing the entire load.
- **JSON parsing in `get_user_settings()`**: Added `JSONDecodeError` handling and type validation to prevent crashes from corrupted `settings_json` in the users table.
- **Subprocess return code checks in GitHub Updater**: `on_check_update()` now checks `returncode` on all three git subprocess calls (`git remote get-url`, `git rev-parse`, `git describe`) instead of blindly using stdout. Falls back to sensible defaults (empty string, "main", BOT_VERSION) on failure.
- **Rollback handler (`on_rollback_update`)**: `git stash` return code now checked and logged on failure instead of silently ignored.

#### Internationalization (i18n)
- **404 page fully internationalized**: 13 new translation keys added for the 404 error page in all 5 languages (DE/EN/ES/RU/PT):
  - `err404_suggestions`, `err404_all_pages`, `err404_terminal` — static text
  - `err404_security`, `err404_about` — navigation links
  - `err404_page_strategies`, `err404_page_api`, `err404_page_install`, `err404_page_faq`, `err404_page_security`, `err404_page_changelog`, `err404_page_roadmap`, `err404_page_about` — suggestion labels
- **Hardcoded German removed from 404.html**: "Meintest du vielleicht...?", "Alle Seiten", "Seite nicht gefunden. Bot laeuft weiterhin...", page suggestion labels, and navigation links now use `data-i18n` attributes and `QI18n.t()` with fallbacks.

#### Documentation & Versioning
- Version bumped to 1.5.2 across: `pyproject.toml`, `services/utils.py`, `README.md`, `trevlix_translations.js`, `docs/ARCHITECTURE.md`, `docs/SERVICES.md`, `docs/API.md`
- README.md: Updated test count badge from 250+ to 300+ (actual: 303 collected, 284 passed, 19 skipped)
- Full codebase audit performed: linting clean, all 284 tests passing

---

## [1.5.1] – 2026-03-23

### Fixed — Dashboard Bugs, i18n & Code Quality

#### WebSocket & Dashboard Fixes
- **Admin role not transmitted**: `user_role` was missing from WebSocket snapshot — admin buttons were invisible. Fixed by injecting `user_role` into `on_connect` and `on_request_state` handlers.
- **`applyStateToRole()` never called**: Function existed but was never invoked from the `update` event handler. Admin UI was permanently hidden.
- **`pool_status()` → `pool_stats()`**: Wrong method name in analytics handler caused runtime error.
- **Missing WebSocket listeners**: `healing_update`, `revenue_update`, `cluster_update` events emitted by server but never handled by frontend.
- **Null reference errors in dashboard.js**: Added null-safety checks to `logPauseBtn`, `hReturn`, `updateGoal()`, and `updateCB()`.

#### Internationalization (i18n)
- **45 hardcoded German emit messages internationalized**: All `emit("status", ...)` calls in server.py now include a `key` field for frontend translation via `QI18n.t()`.
- **55+ new translation keys** added to `trevlix_translations.js` in all 5 languages (de/en/es/ru/pt): bot control, settings, AI operations, position management, exchange operations, validation errors, grid trading, updates, backups.
- **40 duplicate translation keys removed**: JS object key shadowing caused first definitions to be silently overridden. Cleaned up to single canonical definitions.
- **Hardcoded German in dashboard.js replaced**: `updateGoal()` ("Ziel", "erreicht") and `updateCB()` ("Verluste", "Pause noch") now use `QI18n.t()`.
- **3 missing JS translation keys added**: `err_min2_symbols`, `err_min1_symbol`, `mtf_label2`.
- **`market_regime` i18n**: Changed from hardcoded emoji strings to translatable `label_bullish`/`label_bearish` keys.
- **Server-side `status` handler updated**: `socket.on('status')` now supports `key` field for progressive i18n migration.

#### Admin Analytics Tab
- **New `sec-analytics` section** in dashboard with 11 metric panels: System Info, API Status, LLM Status, Database, AI Engine, Risk Management, Revenue Tracking, Performance Attribution, Strategy Weights, Indicator Cache, Auto-Healing.
- **New `request_system_analytics` WebSocket handler** aggregating data from all service modules.

#### Documentation & Versioning
- Updated version references in `docs/ARCHITECTURE.md`, `docs/SERVICES.md`, `docs/API.md` from 1.2.0 to 1.5.1.

---

## [1.5.0] – 2026-03-22

### Added — Autonomous Agents & System Improvements

#### New Agents
- **Auto-Healing Agent** (`services/auto_healing.py`) — Monitors trading processes, APIs, database, and notification services. Auto-recovers on failure with soft recovery first, escalation after 3 failures. Background health-check thread with configurable interval.
- **Revenue Tracking Agent** (`services/revenue_tracking.py`) — Real PnL calculation after fees and slippage. Daily/weekly/monthly aggregation, ROI tracking, drawdown monitoring, and losing strategy detection.
- **Multi-Server Control Agent** (`services/cluster_control.py`) — Register and manage remote TREVLIX nodes via API. Health-check, start/stop/deploy, aggregated cluster-wide metrics.

#### Full Server Integration
- All 3 agents initialized in `server.py` with database, config, and notifier
- `healer.heartbeat()` wired into main bot loop for liveness detection
- `revenue_tracker.record_trade()` wired into `close_position()` and `close_short()` for real PnL tracking
- `healer.start()` on startup, `healer.stop()` + `cluster_ctrl.shutdown()` on graceful shutdown
- WebSocket events: `healing_update`, `revenue_update`, `cluster_update` emitted every 10 iterations

#### Alert Escalation Manager (Bonus)
- **Alert Escalation** (`services/alert_escalation.py`) — Tiered alert system (INFO → WARNING → CRITICAL → EMERGENCY). Auto-escalation on repeated failures. Alert acknowledgement, auto-resolve after silence, history tracking.

#### REST API Endpoints (25+ new)
- `/api/v1/health/basic` — Cluster node health check
- `/api/v1/health/snapshot` — Auto-Healing status
- `/api/v1/health/incidents` — Incident history
- `/api/v1/revenue/snapshot|daily|weekly|monthly` — Revenue tracking
- `/api/v1/revenue/strategies|losing` — Strategy performance & detection
- `/api/v1/cluster/snapshot|nodes|metrics` — Cluster management
- `/api/v1/cluster/nodes/<name>/start|stop|restart|deploy` — Remote node control
- `/api/v1/alerts/active|history|snapshot` — Alert escalation
- `/api/v1/alerts/<id>/acknowledge|resolve` — Alert lifecycle
- `/api/v1/metrics` — Local node metrics for cluster aggregation

#### Database Schema
- 4 new tables: `revenue_trades`, `healing_incidents`, `cluster_nodes`, `alert_escalations`
- Added to both `server.py:_init_db_once()` and `docker/mysql-init.sql`

#### Tests
- 52 new tests across 4 test modules (test_auto_healing, test_revenue_tracking, test_cluster_control, test_alert_escalation)
- Total: 282 passing, 19 skipped

#### Bugfixes
- **crypto.com fetchTickers() Fix** — crypto.com only supports single-symbol fetchTickers. Added `safe_fetch_tickers()` helper that auto-detects exchange limitations and fetches all tickers then filters, preventing the "symbols argument cannot contain more than 1 symbol" error.
- **Socket.IO Dashboard Connection** — Added JWT auth fallback for Socket.IO connect handler. Dashboard buttons now work even when session cookies aren't forwarded (e.g. behind reverse proxy). Client passes JWT token via `auth` parameter and `withCredentials: true`.

#### Translations
- Added 35+ missing dashboard translation keys (confirmations, toasts, status labels, agent UI) in all 5 languages (DE, EN, ES, RU, PT)
- Added translations for new agents (Auto-Healing, Revenue Tracking, Cluster Control)

#### Version Updates
- Bumped version from 1.4.0 → 1.5.0 across all files (server.py, pyproject.toml, README.md, templates, routes, static assets, Docker config)

---

## [1.3.8] – 2026-03-18

### Fixed — Bugfixes Runde 8: Short-Engine, Trade-Execution, Snapshot (7 Fixes)

#### Funktionale Fehler
- **ShortEngine API-Keys nicht entschlüsselt** — `_get_ex()` übergab verschlüsselte Keys direkt an ccxt statt `decrypt_value()` aufzurufen → Short-Trades funktionierten nie im Live-Modus. `decrypt_value()` hinzugefügt (analog zu `create_exchange()`)
- **`open_position()` price=0 Div-by-Zero** — `qty = (invest - fee) / price` crashte bei ungültigem Preis. Guard `price <= 0` mit Early-Return
- **`open_short()` price=0 Div-by-Zero** — `qty = invest / price` gleicher Bug. Guard hinzugefügt

#### Snapshot Division-by-Zero
- **Long-Positionen pnl_pct** — `/ p["entry"]` bei `p.get("entry")` prüfte nur Existenz (True für 0), nicht Wert > 0. Umgestellt auf `p.get("entry", 0) > 0`
- **Short-Positionen pnl_pct** — Gleicher Bug bei Short-Position PnL-Berechnung

#### Robustheit
- **Backtest STRATEGIES leer** — `/ len(STRATEGIES)` Div-by-Zero wenn Strategie-Liste leer. Guard hinzugefügt
- **partial_tp_levels KeyError** — `level["pct"]` und `level["sell_ratio"]` bei fehlformatierten Config-Einträgen. Umgestellt auf `.get()` mit Defaults
- **login_attempts Memory-Leak** — Timestamp-Liste pro IP wuchs unbegrenzt. Begrenzt auf letzte 50 Einträge

## [1.3.7] – 2026-03-18

### Fixed — Bugfixes Runde 7: ML-Engine, DB-Pool, LLM-Integration (7 Fixes)

#### ML-Engine (ai_engine.py) – 4 Fixes
- **predict_proba IndexError (2 Stellen)** — `proba[win_idx]` ohne Bounds-Check konnte IndexError auslösen wenn Klasse 1 nicht in Proba-Array. Guard `0 <= win_idx < len(proba)` hinzugefügt
- **CalibratedClassifierCV Klassen-Balance** — Kalibrierung mit `cv=3` crashte bei extrem unbalanciertem Datensatz (alle Trades Gewinner oder alle Verlierer). Mindestens 5 Samples pro Klasse erforderlich
- **Genetischer Optimizer Score-Overflow** — `sim_pnl / 10000.0` konnte unbegrenzt wachsen → Overfitting. `np.clip(-1, 1)` für Normalisierung

#### DB-Pool (db_pool.py) – 2 Fixes
- **Semaphore-Leak bei release()** — Wenn `_is_alive()` Exception warf, wurde Semaphore nie freigegeben → Pool-Erschöpfung. Umstrukturiert mit try/finally
- **last_err = None → TypeError** — `raise None` nach allen Retry-Fehlschlägen warf TypeError statt sinnvoller Fehlermeldung. Initialisiert mit TimeoutError-Default

#### LLM-Integration (knowledge.py) – 1 Fix
- **choices[0] AttributeError** — LLM-API-Antwort konnte `choices[0]` als Non-Dict liefern → `.get()` crashte. isinstance(dict) Prüfung hinzugefügt

### Changed
- **README.md** — Version 1.2.0 → 1.3.7 (wurde seit v1.2.0 nicht mehr aktualisiert)

## [1.3.6] – 2026-03-18

### Fixed — Tiefenanalyse Phase 2: 5 Bugfixes in services/ & ai_engine

- **`market_data.py` FearGreed KeyError** — `d["value"]` und `d["value_classification"]` crashten bei geändertem API-Format. Umgestellt auf `.get()` mit Fallback
- **`ai_engine.py` recent_wr Division-Bug** — Win-Rate wurde immer durch 10 geteilt statt durch tatsächliche Anzahl der Recent-Trades. Fix: `len(recent_slice)` als Divisor
- **`knowledge.py` Cache-Eviction unvollständig** — `sorted(ts_dict, ...)` evizierte nur Einträge die auch in `ts_dict` vorhanden waren, Cache-Only-Einträge wuchsen unbegrenzt. Fix: Sortierung über `cache.keys()`
- **`risk.py` NaN-Check fragil** — `corr != corr` idiom für NaN-Check. Umgestellt auf explizites `np.isnan(corr)` für Klarheit und Sicherheit
- **`strategies.py` strat_vol close=0** — `close > prev_close * 1.005` konnte bei `close=0` ein falsches Signal erzeugen. Guard `close <= 0` hinzugefügt

## [1.3.5] – 2026-03-18

### Fixed — Tiefenanalyse: 14 Bugfixes in server.py

#### Backtest-Engine (4 Fixes)
- **Drawdown Division-by-Zero** — `(peak - value) / peak * 100` crashte bei `peak=0`. Guard `if peak > 0` hinzugefügt
- **Return-Prozent Division-by-Zero** — `(cap - start) / start * 100` crashte bei `start=0`. Guard hinzugefügt
- **Leerer DataFrame** — `df.index[0]` crashte bei leerem/kurzem DataFrame nach `compute_indicators()`. Check `len(df) < 3` hinzugefügt
- **Entry-Price Division-by-Zero** — `(price - pos["entry"]) / pos["entry"]` crashte bei entry=0. Guard `pos["entry"] > 0` hinzugefügt

#### Thread-Safety & Race Conditions (4 Fixes)
- **`del state.positions[symbol]` KeyError** — Ungesicherte Löschung bei gleichzeitigem Zugriff. Umgestellt auf `state.positions.pop(symbol, None)`
- **`del state.short_positions[symbol]` KeyError** — Gleicher Bug bei Short-Positionen. Umgestellt auf `.pop(symbol, None)`
- **Grid-Engine Race Condition** — `update()` modifizierte `balance_ref[0]` ohne Lock → Overdraft bei parallelen Threads. Lock hinzugefügt via `_update_locked()`
- **`manage_positions()` SL/TP nach Partial-TP** — `pos["sl"]` Zugriff auf gelöschte Position nach `close_position()`. Re-Fetch mit `state.positions.get()` vor SL/TP-Check

#### Sicherheit (3 Fixes)
- **`getattr(ccxt, ex_name)` Injection** — Beliebige ccxt-Attribute per User-Input aufrufbar. Jetzt Whitelist-Prüfung gegen EXCHANGE_MAP
- **Audit-Log ohne User-ID** — 3 API-Endpunkte (exchange_upsert, api_keys_update, config_update) loggten keine `user_id`. Parameter hinzugefügt
- **`close_exchange_position` leere API-Keys** — `decrypt_value("")` bei fehlender Exchange-Config. Explizite Prüfung vor Decrypt

#### Input-Validierung (3 Fixes)
- **`update_discord` int(report_hour)** — `int(data["report_hour"])` crashte bei nicht-numerischem Wert. Umgestellt auf `_safe_int()` + Bounds 0-23
- **`update_config` Typ-Validierung** — CONFIG-Werte wurden ohne Typ-Prüfung direkt zugewiesen. Neue Typ-Validierung: float für Prozente, int für Zähler, bool für Flags
- **`update_shorts` s_entry Division-by-Zero** — `(s_entry - price) / s_entry` bei s_entry=0. Guard `s_entry > 0` hinzugefügt

## [1.3.4] – 2026-03-18

### Fixed — Bugfixes Runde 5 (5 Fixes)

#### API-Robustheit
- **`market_data.py` FearGreed IndexError** — `r.json()["data"][0]` crashte bei leerer API-Antwort. Umgestellt auf `.get("data", [])` mit Leerprüfung
- **`market_data.py` Trending KeyError** — `c['item']['symbol']` in List-Comprehension crashte bei fehlenden Keys. Umgestellt auf `.get()` mit Filter
- **`cryptopanic.py` posts[0] IndexError** — `posts[0].get("title")` wurde aufgerufen obwohl `posts` leer sein konnte. Guard `if scores and posts` hinzugefügt

#### Prediction & Notifications
- **`risk.py` Conformal-Predict IndexError** — `model.predict_proba(X_test)[:, 1][0]` crashte bei leerem X_test. Shape-Prüfung vor Zugriff hinzugefügt
- **`notifications.py` split()[0] IndexError** — `self._bot_full.split()[0]` in Discord `error()` und Telegram `error()` ohne Fallback bei leerem String. `(split() or ['TREVLIX'])[0]` Schutz hinzugefügt (2 Stellen)

## [1.3.3] – 2026-03-18

### Fixed — Bugfixes Runde 4 (10 Fixes)

#### Snapshot & Portfolio
- **Goal ETA negative Tage** — `snapshot()` berechnete negative `days` wenn Portfolio-Wert bereits über Ziel lag → negative Datumsangabe im Frontend. Jetzt: "✅ Ziel erreicht!" wenn `remaining <= 0`
- **`portfolio_value()` stale Shorts** — `pnl_unrealized` in `short_positions` konnte fehlen oder ungültiger Typ sein. Umgestellt auf `_safe_float()` + Guard für `qty > 0` bei Longs

#### Input-Validierung
- **Heatmap float-Conversion** — `float(t.get("percentage", 0) or 0)` in `get_heatmap_data()` crashte bei nicht-numerischen Ticker-Werten. Umgestellt auf `_safe_float()`, negative Volumen auf 0 normalisiert
- **`close_position()` Entry-Price** — `entry <= 0` führte zu Division-by-Zero in PnL-Berechnung. Guard hinzugefügt: Fallback auf aktuellen Preis

#### Validierung & Sicherheit
- **`validate_env.py` Whitespace ENCRYPTION_KEY** — Führende/nachfolgende Leerzeichen in `.env` führten zu falsch-positivem Fernet-Key-Fehler. `.strip()` hinzugefügt
- **`validate_env.py` Schwache Passwort-Erkennung** — Nur exakte Matches ("password") wurden erkannt, nicht Varianten ("password123"). Substring-Check mit `any(weak in val_lower ...)` hinzugefügt
- **`risk.py` Sharpe NaN/Inf** — `sharpe()` konnte NaN/Inf zurückgeben wenn alle Returns NaN waren. Explizite `np.all(np.isnan())` und `np.isfinite()` Guards

#### Stabilität
- **`manage_positions()` Partial-TP Stale Ref** — Nach `close_position()` mit `partial_ratio` konnte `pos` auf gelöschte Position zeigen → `pos["partial_tp_done"]` KeyError. Re-Fetch mit `state.positions.get(symbol)` nach Close
- **`bot_loop()` Exchange-Fehler** — `create_exchange()` Fehler ließ `ex=None` und crashte in nächster Iteration. Try/except mit 30s Backoff + `continue`
- **`validate_env.py` Passwort-Variablen `.strip()`** — Whitespace in Passwort-Variablen führte zu falschen Längenprüfungen. `.strip()` vor Validierung

## [1.3.2] – 2026-03-18

### Fixed — Bugfixes & Robustheit (52 Fixes gesamt, 3 Runden)

#### Input-Validierung & Type-Safety
- **`config.py` MYSQL_PORT Crash** — `int(os.getenv("MYSQL_PORT"))` crashte bei nicht-numerischem Wert. Neue `_safe_port()` Funktion mit Fallback auf 3306
- **`server.py` Unguarded float()/int() auf User-Input** — 7 Stellen in API- und WebSocket-Handlern (Backtest, Alert, User-Create) verwendeten `float(data.get(...))` ohne Try/Except. Neue `_safe_float()` Hilfsfunktion eingeführt, alle Stellen auf `_safe_float()`/`_safe_int()` umgestellt
- **`server.py` JWT Payload KeyError** — `payload["sub"]` in `verify_api_token()` crashte bei fehlendem `sub`-Claim. Umgestellt auf `payload.get("sub")` mit None-Check
- **`server.py` Training-Daten KeyError** — `r["features"]`, `r["label"]`, `r["regime"]` in `load_ai_samples()` crashten bei fehlenden DB-Spalten. Umgestellt auf `.get()` mit Fallback-Werten

#### Null-Safety & Division-by-Zero
- **`ai_engine.py` None-Guard für recent_trades** — `recent_trades[-10:]` crashte bei `None`. Konvertiert zu leerer Liste
- **`ai_engine.py` Scaler None-Check** — `self.scaler.transform()` in `register_trade_open()` und `predict_win_probability()` crashte wenn Scaler nicht initialisiert. Explizite `self.scaler is not None` Prüfung hinzugefügt
- **`ai_engine.py` strat_importances Division-by-Zero** — `strat_importances / strat_importances.mean()` wurde zweimal aufgerufen (redundant + Race). Zwischenvariable `mean_val` eingeführt, Division nur wenn `mean_val > 0`
- **`smart_exits.py` entry_price Guard** — `compute()` hatte keinen Guard für `entry_price <= 0`, was zu Division-by-Zero in SL/TP-Berechnung führte. Guard am Funktionsanfang hinzugefügt
- **`server.py` DataFrame Length-Check** — `df.iloc[-1]`/`df.iloc[-2]` in `scan_symbol()` konnte bei zu kurzem DataFrame nach `compute_indicators()` crashen. Check `len(df) < 2` hinzugefügt
- **Discord Embed Fields IndexError** — Tupel-Zugriff in `notifications.py` und `server.py` ohne Längenprüfung. Filter `if len(f) >= 2` hinzugefügt
- **OrderbookImbalance leere Bids/Asks** — Crash bei leerem Orderbook. Expliziter Empty-Check vor Berechnung

#### Sicherheit
- **CSRF Timing-Attack** — `csrf_submitted != session.get("_csrf_token")` in `routes/auth.py` (Login, Register, Admin-Login) verwendete String-Vergleich statt konstantzeit-Vergleich. Umgestellt auf `hmac.compare_digest()` gegen Timing-basierte Token-Leaks
- **SQL Backup Identifier-Quoting** — Backtick-Quoting für Defense-in-Depth

#### Thread-Safety & Race Conditions
- **`ai_engine.py` predictions_made Race Condition** — `self.predictions_made += 1` außerhalb des Locks in `predict_win_probability()`. In Lock verschoben
- **`risk.py` NaN-Handling in Korrelation** — `np.corrcoef()` bei identischen Preisserien gibt NaN zurück, `NaN > threshold` ist False → stille Fehler. Expliziter NaN-Check hinzugefügt

#### Memory & Performance
- **`knowledge.py` Unbegrenztes Cache-Wachstum** — `_cache` und `_llm_cache` hatten keine Größenbeschränkung → Memory-Leak bei 24/7-Betrieb. `_evict_cache()` Methode + Max-Size (500/100 Einträge) hinzugefügt
- **`market_data.py` Falscher `or 50` Fallback** — `cd.get("sentiment_votes_up_percentage", 50) or 50` maskierte legitime `0`-Werte. Umgestellt auf explizite `None`-Prüfung

#### Sonstiges
- **`risk.py` Exception-Handling** — `except Exception: pass` zu breit. Eingeschränkt auf `(ValueError, TypeError, IndexError)`
- **`exchange_manager.py` KeyError** — `ex_data["exchange"]` direkter Zugriff ohne `.get()`. Umgestellt auf `.get("exchange", "unknown")`

#### Runde 3: Tiefgehende Analyse (30 weitere Fixes)

**server.py Input-Validierung:**
- **CONFIG `mysql_port`** — `int(os.getenv("MYSQL_PORT"))` am Modul-Level crashte bei ungültigem Wert. Inline-Validierung mit `.isdigit()` Fallback
- **`get_sentiment()` float(row["score"])** — Crashte bei NULL-Wert in DB. Explizite `row.get("score") is not None` Prüfung
- **`save_onchain()` None-Arithmetik** — `(whale_score + flow_score) / 2` crashte wenn Score None war. None→0.0 Konvertierung
- **`_fitness()` pnl_pct None** — `t.get("pnl_pct", 0) / 100` crashte bei explizitem None-Wert. Umgestellt auf `(t.get("pnl_pct") or 0)`
- **Grid-Trading API** — 4× `float()`/`int()` auf User-Input in `/api/v1/grid` ohne Validierung → `_safe_float()`/`_safe_int()`
- **Grid-Trading WebSocket** — 4× gleicher Bug in `ws_create_grid` Socket-Handler
- **CVaR API** — `float(request.args.get("conf"))` ohne Validierung → `_safe_float()`
- **News-Filter Config** — 2× `float(d.get(...))` in `/api/v1/config/news-filter` → `_safe_float()`
- **Funding-Rate Config** — `float(d.get("max_rate"))` → `_safe_float()`
- **Tax-Report** — `float(t.get("pnl", 0))` und `float(t.get("invested", 0))` crashten bei None. Umgestellt auf `or 0`
- **SESSION_TIMEOUT_MIN** — `int(os.getenv(...))` am Modul-Level crashte bei ungültigem Wert. Try/except hinzugefügt

**server.py Division-by-Zero & Null-Safety:**
- **`_detect_concept_drift()`** — Division durch `half=0` bei `len(trades) < 2`. Expliziter Zero-Guard
- **`_train()` norm[i] Bounds** — `norm[i]` IndexError wenn Feature-Importance-Array kürzer als STRATEGY_NAMES. Längenprüfung + Zwischenvariable `mean_sfi`
- **`_predict()` regime.is_bull** — `regime.is_bull` AttributeError wenn regime None/uninitialisiert. `hasattr()` Guard
- **`_predict()` bull/bear_scaler None** — `self.bull_scaler.transform()` crashte ohne Scaler. `is not None` Prüfung für beide

**server.py Sicherheit:**
- **verify_password SHA-256 Fallback** — Timing-Attack auf Legacy-SHA-256-Hash-Vergleich. Umgestellt auf `hmac.compare_digest()` + Log-Warning für Migration

**services/ Fixes:**
- **`performance_attribution.py` profit_factor** — Gab 0.0 zurück wenn nur Gewinne (keine Verluste). Jetzt korrekt: gibt `gross_profit` zurück
- **`trade_dna.py` np.mean() auf leerer Liste** — `np.mean([])` gibt NaN zurück. Explizite leere-Liste-Prüfung
- **`cryptopanic.py` votes Typ-Check** — `votes.get()` crashte wenn votes kein Dict (z.B. String/None). `isinstance()` Guard
- **`notifications.py` split()[0] IndexError** — `self._bot_full.split()[0]` crashte bei leerem String. Fallback auf `['TREVLIX']`
- **`knowledge.py` TypeError in JSON-Parse** — `json.loads()` fängt nur JSONDecodeError, nicht TypeError bei Nicht-String-Input
- **`adaptive_weights.py` np.sum(weights) Zero** — Division durch Null bei Weights-Summe = 0. Expliziter Zero-Guard
- **`db_pool.py` Exception-Masking** — `conn.close()` im finally-Block maskierte Original-Exception. Try/except mit Logging
- **`market_data.py` Nested-Dict-Annahme** — `.get("usd")` crashte wenn API flache statt verschachtelte Struktur lieferte. `isinstance(dict)` Check
- **`smart_exits.py` Dead Code** — Ungenutzte Variablen `sl_pct`/`tp_pct` vor `return 0.0, 0.0` entfernt
- **`risk.py` conformal_predict Shape** — `predict_proba()[:, 1]` crashte bei < 2 Klassen. Shape-Validierung + X_test-Leer-Check

**Schema & Security:**
- **`mysql-init.sql`** — `api_tokens` und `user_exchanges` Tabellen fehlten (nur in server.py erstellt). Per CLAUDE.md müssen Tabellen in BEIDEN Dateien existieren
- **`routes/auth.py` Passwort-Länge DoS** — Kein Max-Length-Check auf Passwort vor Regex (1MB+ String → CPU-Spike). Limit auf 128 Zeichen
- **`routes/auth.py` Passwort-Vergleich** — `password != password2` statt `hmac.compare_digest()`. Timing-Attack auf Passwort-Bestätigung

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
