# TREVLIX v1.6.3 -- Architektur-Dokumentation

## 1. Uebersicht

Trevlix ist ein algorithmischer Krypto-Trading-Bot auf Basis von Flask und WebSockets. Das System kombiniert ein KI-Ensemble (XGBoost, RandomForest, LSTM, Reinforcement Learning, Genetic Optimizer) mit 9 voneinander unabhaengigen Voting-Strategien, um Handelsentscheidungen zu treffen. Multi-Exchange-Unterstuetzung wird ueber CCXT realisiert (Crypto.com, Binance, Bybit, OKX, KuCoin). Ein integriertes Risk-Management mit Circuit-Breaker, Trade-DNA-Fingerprinting und Smart-Exit-Engine schuetzt das Kapital.

---

## 2. Verzeichnisstruktur

```
trevlix/
├── server.py                # Kern-Applikation: Flask + SocketIO, Bot-Lifecycle, DB-Init
├── ai_engine.py             # ML-Ensemble: XGBoost, RandomForest, LSTM, RL, Genetic Optimizer
├── trevlix_i18n.py          # Internationalisierung (DE, EN, ES, RU, PT)
├── validate_env.py          # Umgebungsvariablen-Validierung vor dem Start
│
├── routes/                  # Flask Blueprints
│   ├── auth.py              # Authentifizierung: Login, Registrierung, 2FA, Admin-Routen
│   ├── dashboard.py         # Statische Seiten-Routen (Dashboard, Einstellungen)
│   └── websocket.py         # WebSocket-Event-Handler (Echtzeit-Updates)
│
├── services/                # Modulare Geschaeftslogik
│   ├── config.py            # Pydantic-basierte Konfigurationsverwaltung
│   ├── db_pool.py           # Thread-sicherer MySQL-Connection-Pool
│   ├── encryption.py        # Fernet-Verschluesselung fuer API-Keys
│   ├── exchange_manager.py  # Multi-Exchange-Manager via CCXT
│   ├── indicator_cache.py   # Caching fuer technische Indikatoren (RSI, MACD, BB etc.)
│   ├── knowledge.py         # KI-Wissensbasis + LLM-Integration (OpenAI-kompatibel)
│   ├── market_data.py       # Fear/Greed-Index, On-Chain-Daten
│   ├── notifications.py     # Benachrichtigungen via Discord & Telegram
│   ├── risk.py              # Risk-Management, Circuit-Breaker, Drawdown-Schutz
│   ├── strategies.py        # 9 Voting-Strategien (Konsens-basiert)
│   └── utils.py             # Gemeinsame Hilfsfunktionen und Konstanten
│
├── templates/               # Jinja2 HTML-Templates
├── static/                  # CSS, JavaScript, statische Assets
├── tests/                   # Pytest-Testsuite (141 Tests)
│   └── conftest.py          # Test-Fixtures fuer DB- und Flask-Mocking
├── docker/                  # Deployment-Konfiguration
│   ├── mysql-init.sql       # Datenbank-Schema-Initialisierung
│   └── ...                  # Nginx-Config, SSL-Zertifikate
└── tasks/                   # Session-Tracking (todo.md, lessons.md)
```

---

## 3. Komponenten-Architektur

Die Architektur gliedert sich in vier Schichten:

### 3.1 Web Layer

| Modul | Aufgabe |
|---|---|
| `server.py` | Zentraler Einstiegspunkt. Initialisiert Flask, SocketIO, Datenbank-Tabellen (`_init_db_once()`), Bot-Lifecycle (Start/Stop/Scan-Loop). |
| `routes/auth.py` | Authentifizierung und Autorisierung: Login, Registrierung, 2FA (TOTP), Admin-Verwaltung, JWT-basierte Sessions. |
| `routes/dashboard.py` | Statische Seiten: Dashboard, Einstellungen, Performance-Ansichten. |
| `routes/websocket.py` | Echtzeit-Kommunikation via SocketIO: Live-Trades, Portfolio-Updates, Bot-Status, Log-Streaming. |

### 3.2 Services Layer

| Modul | Aufgabe |
|---|---|
| `config.py` | Pydantic-Modell fuer typsichere Konfiguration. Geschuetzte Keys (`_PROTECTED_KEYS`) koennen nicht ueber die UI geaendert werden. |
| `db_pool.py` | Thread-sicherer MySQL-Connection-Pool mit automatischem Reconnect. Alle DB-Zugriffe laufen ueber diesen Pool. |
| `encryption.py` | Fernet-basierte symmetrische Verschluesselung. Alle API-Keys werden verschluesselt in der DB gespeichert. |
| `exchange_manager.py` | Abstraktionsschicht fuer CCXT. Verwaltet Verbindungen zu mehreren Exchanges, Order-Routing, Balance-Abfragen. |
| `indicator_cache.py` | Berechnet und cached technische Indikatoren (RSI, MACD, Bollinger Bands, ATR etc.), um redundante Berechnungen zu vermeiden. |
| `knowledge.py` | KI-Wissensbasis mit LLM-Integration. Verbindet sich mit OpenAI-kompatiblen Endpoints fuer Marktanalysen. |
| `market_data.py` | Abrufen externer Marktdaten: Fear/Greed-Index, On-Chain-Metriken, Sentiment-Daten. |
| `notifications.py` | Benachrichtigungssystem: Discord-Webhooks und Telegram-Bot fuer Trade-Alerts und Systemwarnungen. |
| `risk.py` | Risk-Management-Engine: Positionsgroessen-Berechnung, Circuit-Breaker bei Drawdown-Limits, Exposure-Kontrolle. |
| `strategies.py` | 9 unabhaengige Trading-Strategien, die per Voting-Mechanismus einen Konsens bilden. Jede Strategie liefert BUY/SELL/HOLD. |
| `utils.py` | Gemeinsame Konstanten (`BOT_NAME`, `BOT_VERSION`), Validierungsfunktionen, Hilfsklassen wie `SecretStr`. |

### 3.3 KI Engine (`ai_engine.py`)

Das ML-Ensemble kombiniert fuenf Modelltypen:

- **XGBoost** -- Gradient-Boosted Trees fuer Feature-basierte Vorhersagen
- **RandomForest** -- Ensemble aus Entscheidungsbaeumen fuer robuste Klassifikation
- **LSTM** -- Rekurrentes neuronales Netz fuer Zeitreihen-Muster
- **Reinforcement Learning** -- Adaptive Strategie-Optimierung basierend auf Reward-Signalen
- **Genetic Optimizer** -- Evolutionaere Parameteroptimierung ueber Generationen

Die Modelle liefern jeweils einen Score, der gewichtet aggregiert wird. Das Ergebnis fliesst als KI-Score in die Trade-Entscheidung ein.

### 3.4 Datenhaltung

- **MySQL** -- Primaere Datenbank fuer Trades, Konfiguration, Benutzer, DNA-Records
- **`db_pool.py`** -- Thread-sicherer Connection-Pool; alle Queries sind parametrisiert (kein String-Interpolation)
- **`encryption.py`** -- Fernet-Verschluesselung fuer sensitive Daten (API-Keys, Secrets)
- **Schema-Management** -- Tabellen werden in `server.py:_init_db_once()` und `docker/mysql-init.sql` parallel definiert

---

## 4. Datenfluss eines Trades

```
Scan               Marktdaten von der Exchange abrufen (Candlesticks, Orderbook, Ticker)
  │
  ▼
Indicators         Technische Indikatoren berechnen (RSI, MACD, BB, ATR etc.)
  │                Ergebnisse im indicator_cache ablegen
  ▼
Strategies Vote    9 Strategien bewerten unabhaengig: BUY / SELL / HOLD
  │                Konsens wird per Mehrheitsvotum gebildet
  ▼
AI Score           ML-Ensemble bewertet das Setup (XGBoost, RF, LSTM, RL, Genetic)
  │                Gewichteter Konfidenz-Score wird berechnet
  ▼
Risk Check         Positionsgroesse berechnen, Drawdown-Limits pruefen
  │                Circuit-Breaker kann den Trade blockieren
  ▼
DNA Check          Trade-DNA-Fingerprint berechnen (7 Dimensionen)
  │                Historische DNA-Muster abgleichen: Boost oder Block
  ▼
Smart Exits        ATR-basierte Stop-Loss/Take-Profit berechnen
  │                Regime-Multiplikatoren anwenden
  ▼
Execute            Order an die Exchange senden (via exchange_manager)
  │                Benachrichtigung via Discord/Telegram
  ▼
Monitor            Position ueberwachen, Smart Exits dynamisch anpassen
  │                Volatility-Squeeze-Erkennung, Trailing-Stops
  ▼
Close              Position schliessen bei SL/TP oder Signal-Umkehr
  │
  ▼
DNA Record         Ergebnis im DNA-System speichern fuer zukuenftige Muster-Erkennung
```

---

## 5. Besondere Features

### 5.1 Trade-DNA-Fingerprinting

Jeder Trade wird anhand von 7 Dimensionen charakterisiert:

| Dimension | Beschreibung |
|---|---|
| `regime` | Marktregime (Bull, Bear, Range, Crash) |
| `volatility` | Aktuelle Volatilitaets-Stufe |
| `fear_greed` | Fear/Greed-Index zum Zeitpunkt des Trades |
| `news` | Nachrichten-Sentiment |
| `orderbook` | Orderbook-Imbalance (Kauf-/Verkaufsdruck) |
| `consensus` | Strategie-Konsens-Staerke |
| `session` | Trading-Session (Asia, Europe, US) |

Aus diesen Dimensionen wird ein **SHA-256-Hash** erzeugt, der als eindeutiger Fingerprint dient. Das System fuehrt Pattern-Mining ueber historische DNA-Records durch:

- **Confidence Boost**: Wenn ein DNA-Muster historisch profitabel war, wird der Konfidenz-Score erhoeht
- **Confidence Block**: Wenn ein Muster historisch verlustreich war, wird der Trade blockiert

### 5.2 Smart Exit Engine

Die Smart-Exit-Engine berechnet dynamische Stop-Loss- und Take-Profit-Levels basierend auf ATR (Average True Range).

**Regime-Multiplikatoren (SL / TP):**

| Regime | Stop-Loss | Take-Profit | Logik |
|---|---|---|---|
| Bull | 1.2x ATR | 3.0x ATR | Enge Stops, weite Gewinne -- Trend laufen lassen |
| Bear | 2.0x ATR | 1.5x ATR | Weite Stops, schnelle Gewinnmitnahme |
| Range | 1.5x ATR | 2.0x ATR | Ausgewogenes Verhaeltnis |
| Crash | 2.5x ATR | 1.0x ATR | Maximaler Schutz, minimale Exposure |

Zusaetzliche Mechanismen:

- **Volatility-Squeeze-Erkennung**: Erkennt Phasen komprimierter Volatilitaet und passt die Exits praeventiv an
- **Dynamische Anpassung**: SL/TP werden waehrend der Laufzeit eines Trades basierend auf neuen Marktdaten angepasst

---

## 6. Konfiguration

Alle Konfigurationsparameter werden ueber Umgebungsvariablen gesteuert. Referenz: `.env.example`

**Wichtige Gruppen:**

| Gruppe | Variablen | Beschreibung |
|---|---|---|
| Exchange | `EXCHANGE`, `API_KEY`, `API_SECRET` | Exchange-Auswahl und API-Credentials |
| Datenbank | `MYSQL_HOST`, `MYSQL_USER`, `MYSQL_PASS`, `MYSQL_DB` | MySQL-Verbindungsdaten |
| Sicherheit | `ADMIN_PASSWORD`, `JWT_SECRET`, `SECRET_KEY`, `ENCRYPTION_KEY` | Authentifizierung und Verschluesselung |
| Trading | `PAPER_TRADING`, `AUTO_START` | Paper-Trading-Modus, Auto-Start |
| KI/LLM | `LLM_ENDPOINT` | OpenAI-kompatibler LLM-Endpoint |
| Benachrichtigungen | `DISCORD_WEBHOOK`, `TELEGRAM_TOKEN` | Discord- und Telegram-Integration |

Schluessel generieren:

```bash
# ENCRYPTION_KEY (Fernet, 44 Zeichen Base64URL)
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# JWT_SECRET / SECRET_KEY (32 Byte Hex)
python -c "import secrets; print(secrets.token_hex(32))"
```
