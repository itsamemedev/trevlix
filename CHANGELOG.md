# Changelog

Alle wichtigen Änderungen an TREVLIX werden in dieser Datei dokumentiert.

Format basiert auf [Keep a Changelog](https://keepachangelog.com/de/1.0.0/).
Versionierung folgt [Semantic Versioning](https://semver.org/lang/de/) — `MAJOR.MINOR.PATCH`.

---

## [1.0.3] – 2026-03-02

### Hinzugefügt

**Registrierung & getrennte Bereiche**
- `GET/POST /register` — Benutzer können sich selbst registrieren (wenn `multi_user=true`)
- Login-Seite zeigt "Noch kein Konto? Jetzt registrieren →" Link
- Neues Dashboard-Panel **👤 Mein Profil** für alle eingeloggten User
- Benutzer können eigene API-Keys (Exchange, API Key, Secret) separat vom Bot-Account speichern
- Nav-Schaltfläche **👤 Profil** (immer sichtbar) und **🛡️ Admin** (nur Admins)

**Sicherheit**
- `update_config` SocketIO-Event: jetzt nur noch für Admins — User können globale Config nicht ändern
- `save_api_keys`: Admin → globaler CONFIG; User → eigener DB-Eintrag
- Neuer SocketIO-Event `save_user_profile` für benutzerspezifische Schlüssel
- Settings ⚙️ und Admin 🛡️ Nav-Items nur für Admins sichtbar

**API**
- `GET /api/v1/profile` — eigenes Profil abrufen
- `POST /api/v1/profile` — eigene API-Keys und Exchange aktualisieren

**Datenbank**
- Neue Methoden: `update_user_profile()`, `get_user_profile()`, `register_user()`

---

## [1.0.2] – 2026-03-02

### Behoben
- **Fehlender Docker-Healthcheck-Endpunkt** — `/api/v1/update/status` und `/api/v1/status` existierten nicht; Docker-Container blieb dauerhaft "unhealthy" und wurde nie gestartet
- **`ta` Library Build-Fehler** — `ta>=0.11.0` in `requirements.txt` schlug beim `docker build` fehl; Paket wird im Code gar nicht verwendet und wurde entfernt
- **Log-Datei im falschen Verzeichnis** — `nexus.log` wurde im Working Directory abgelegt; jetzt wird `logs/trevlix.log` verwendet, das mit dem Docker-Volume `./logs:/app/logs` gemountet ist
- **`send_file` mit relativem Pfad** — `dashboard.html` wird jetzt mit absolutem Pfad (`os.path.abspath(__file__)`) geladen, um CWD-unabhängig zu funktionieren

### Hinzugefügt
- **Healthcheck-Endpunkt** — `GET /api/v1/status` und `GET /api/v1/update/status` geben `{"status": "ok", "version": "...", "running": bool}` zurück
- **API-Docs** — Neue Endpunkte in `/api/v1/docs` dokumentiert

---

## [1.0.1] – 2026-03-02

### Behoben
- **f-Strings ohne Platzhalter** — `f"..."` ohne `{}` in `server.py` (Zeilen 4075, 4836–4838) und `ai_engine.py` (Zeile 352) korrigiert (unnötiges `f`-Prefix entfernt)
- **Ungenutzte Exception-Variablen** — `except Exception as e` wo `e` nie verwendet wurde, geändert zu `except Exception` (`server.py` Zeilen 589, 600, 617, 1304)
- **Doppelter Import** — Lokaler Re-Import von `CalibratedClassifierCV` innerhalb einer Funktion entfernt; nutzt jetzt den globalen Import
- **Fehlende `ai_engine.py` im Dockerfile** — `COPY ai_engine.py .` hinzugefügt; der Container startete zuvor mit `ModuleNotFoundError`

### Entfernt
- **Ungenutzte Imports** — `flask_socketio.disconnect`, `scipy_signal`, `rfft`, `rfftfreq`, `SelectFromModel`, `mutual_info_classif`, `PCA`, `StratifiedKFold`, `QuantileTransformer`, `tensorflow.keras.models.Model`, `LayerNormalization`, `sklearn.ensemble.GradientBoostingClassifier`
- **Ungenutzte lokale Variablen** — `aid`, `r`, `page`, `step`, `reddit_active`, `twitter`, `X_s`, `scan_regime`

### Hinzugefügt
- **`docker/` Verzeichnis** — War vollständig im Repository nicht vorhanden, obwohl `docker-compose.yml` darauf verweist
  - `docker/mysql-init.sql` — Vollständiges Datenbankschema mit allen 14 Tabellen
  - `docker/nginx.conf` — Nginx Reverse-Proxy mit HTTP→HTTPS-Redirect, WebSocket-Unterstützung (Socket.IO) und Security-Headern
  - `docker/ssl/.gitkeep` — Platzhalter für SSL-Zertifikate (`trevlix.crt` / `trevlix.key`)
- **`.gitignore`** — `__pycache__/`, `*.pyc`, `*.pyo`, `.env`, `*.log` werden nun ignoriert

---

## [1.0.0] – 2026-02-01

### Erstveröffentlichung

#### Kern-Engine
- **MySQL-Datenbank** — 14 Tabellen: Trades, Users, AI-Training, Audit-Log, Backtest-Ergebnisse, Price-Alerts, Daily-Reports, Sentiment-Cache, News-Cache, On-Chain-Cache, Genetic-Results, Arbitrage, RL-Episodes, API-Tokens
- **Multi-Exchange-Support** — Crypto.com, Binance, Bybit, OKX, KuCoin gleichzeitig
- **Flask + Socket.IO** — Echtzeit-Dashboard über WebSocket
- **Paper-Trading-Modus** — Risikofrei testen ohne echtes Kapital
- **Multi-User-System** — Mehrere Portfolios auf einer Instanz

#### KI & Machine Learning (14+ Module)
- **Random Forest Classifier** — Basis-Ensemble-Modell
- **XGBoost** — Gradient-Boosting für präzisere Signale
- **LightGBM** — Schnelles Boosting-Verfahren
- **CatBoost** — Kategorische Feature-Unterstützung
- **LSTM Ensemble** — Rekurrentes Netz für Zeitreihen (TensorFlow)
- **Stacking-Ensemble** — Meta-Learner kombiniert alle Basismodelle
- **Isotonic Calibration** — Kalibrierte Wahrscheinlichkeiten (`CalibratedClassifierCV`)
- **Walk-Forward-Optimierung** — Rolling-Window-Training gegen Overfitting
- **Optuna Hyperparameter-Tuning** — Bayessche Optimierung (TPE-Sampler)
- **Anomalie-Erkennung** — Isolation Forest stoppt Bot bei Flash-Crash
- **Genetischer Optimizer** — Evolutionäre Strategie-Entdeckung
- **Reinforcement Learning** — PPO-Agent lernt direkt vom Markt
- **Online-Learning** — Inkrementelles Update ohne vollständiges Retraining
- **Kelly-Sizing** — Optimale Positionsgröße basierend auf Gewinnwahrscheinlichkeit

#### Marktanalyse & Signale
- **Fear & Greed Index** — Alternative.me Daten als Sentiment-Signal
- **Multi-Timeframe-Analyse** — 1m, 5m, 15m, 1h, 4h, 1d
- **Regime-Klassifizierung** — Bull/Bear/Sideways/Hoch-Vola Erkennung
- **BTC-Dominanz-Filter** — Automatische Marktphasen-Erkennung
- **Orderbook-Imbalance** — Bid/Ask-Verhältnis als Signal
- **News-Sentiment** — CryptoPanic Echtzeit-Nachrichten als KI-Signal
- **On-Chain-Daten** — Whale-Alarm, Exchange-Flows (CryptoQuant)
- **Arbitrage-Scanner** — Preisunterschiede zwischen Exchanges erkennen

#### Risikomanagement
- **Circuit Breaker** — Automatische Handelspause bei Verlustreihen
- **Trailing Stop-Loss** — Dynamische SL-Anpassung
- **Break-Even Stop-Loss** — Automatische SL-Anpassung nach Gewinn
- **Korrelations-Filter** — Verhindert überkorrelierende Positionen
- **Liquidity-Check** — Minimales Volumen vor Einstieg prüfen
- **Symbol-Cooldown** — Sperrt Symbole nach Verlust
- **Partial Take-Profit** — Stufenweise Gewinnmitnahme (25/50/100%)
- **DCA-Strategie** — Nachkaufen bei fallenden Positionen
- **Monte-Carlo-Risikoanalyse** — Portfoliosimulationen mit VaR-Berechnung
- **Short-Selling** — Bearish-Trades auf Futures (Binance/Bybit)

#### Dashboard & UI
- **Echtzeit-Dashboard** (`dashboard.html`) — WebSocket-basiert, kein Reload nötig
- **Landing Page** (`index.html`) — Produktpräsentation
- **Backtest-Modul** — Historische Strategietests mit detaillierten Metriken
- **Grid-Trading-UI** — Visuelle Konfiguration der Grid-Levels
- **Audit-Log-Ansicht** — Lückenlose Protokollierung aller Aktionen

#### Sicherheit & Zugang
- **JWT-Authentifizierung** — Sichere API-Token für externe Tools
- **2FA (TOTP)** — Zwei-Faktor-Authentifizierung
- **IP-Whitelist** — Zugangskontrolle per IP
- **BCRYPT-Passwort-Hashing** — Sichere Passwort-Speicherung
- **Session-Management** — Flask-Session mit Secret-Key
- **Role-Based Access Control** — Admin / User Rollen

#### Benachrichtigungen & Reporting
- **Discord-Webhooks** — Echtzeit-Alerts für alle Trades
- **Tages-Report** — Automatischer täglicher Performance-Bericht
- **Auto-Backup** — Regelmäßige Datensicherung

#### Infrastruktur
- **Dockerfile** — Python 3.11 slim Image
- **docker-compose.yml** — Trevlix + MySQL 8 + optionales Nginx (Production-Profil)
- **install.sh** — Ein-Klick-Installer für Ubuntu/Debian
- **REST-API v1** — Vollständige API für externe Integrationen und TradingView-Webhooks
- **Copy-Trading** — Follower empfangen alle Signale in Echtzeit
- **Internationalisierung** — Deutsch/Englisch (`trevlix_i18n.py`, `trevlix_translations.js`)

---

<!-- Vorlage für zukünftige Einträge:

## [X.Y.Z] – YYYY-MM-DD

### Hinzugefügt
- Neue Features

### Geändert
- Änderungen an bestehenden Features

### Behoben
- Bug-Fixes

### Entfernt
- Entfernte Features

### Sicherheit
- Sicherheits-Patches

-->
