<div align="center">

```
████████╗██████╗ ███████╗██╗   ██╗██╗     ██╗██╗  ██╗
   ██╔══╝██╔══██╗██╔════╝██║   ██║██║     ██║╚██╗██╔╝
   ██║   ██████╔╝█████╗  ██║   ██║██║     ██║ ╚███╔╝
   ██║   ██╔══██╗██╔══╝  ╚██╗ ██╔╝██║     ██║ ██╔██╗
   ██║   ██║  ██║███████╗ ╚████╔╝ ███████╗██║██╔╝ ██╗
   ╚═╝   ╚═╝  ╚═╝╚══════╝  ╚═══╝  ╚══════╝╚═╝╚═╝  ╚═╝
```

**Algorithmic Crypto Trading Bot — v1.7.1**

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://python.org)
[![Flask](https://img.shields.io/badge/flask-3.0-green.svg)](https://flask.palletsprojects.com)
[![Socket.io](https://img.shields.io/badge/socket.io-4.7-black.svg)](https://socket.io)
[![Tests](https://img.shields.io/badge/tests-300+-brightgreen.svg)](tests/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-1.7.1-brightgreen.svg)](CHANGELOG.md)

</div>

---

## Features

### Trading Engine
- **Multi-Exchange Support** — Crypto.com, Binance, Bybit, OKX, KuCoin, Kraken, Huobi, Coinbase
- **9 Voting Strategies** — EMA Trend, RSI+Stochastic, MACD, Bollinger, Volume, OBV, ROC, Ichimoku, VWAP
- **Grid Trading** — Automated grid strategies with configurable levels
- **Partial Take-Profit** — Staged profit taking (25/50/100%)
- **DCA Strategy** — Averaging down on falling positions
- **Short-Selling** — Bearish trades on futures (Binance/Bybit)
- **Arbitrage Scanner** — Cross-exchange price spread detection
- **Paper Trading** — Risk-free testing without real capital

### AI & Machine Learning (14+ Models)
- **Random Forest, XGBoost, LightGBM, CatBoost** — Ensemble models
- **LSTM Ensemble** — Recurrent neural networks for time series
- **Stacking Ensemble** — Meta-learner combining all base models
- **Genetic Optimizer** — Evolutionary strategy discovery
- **Reinforcement Learning** — PPO agent learns from market
- **Anomaly Detection** — Isolation Forest stops bot during flash crashes
- **Optuna Hyperparameter Tuning** — Bayesian optimization
- **Kelly Criterion** — Optimal position sizing based on win probability

### Unique Features
- **Trade DNA Fingerprinting** — 7-dimensional fingerprint + pattern mining for each trade
- **Smart Exits** — ATR-based volatility-adaptive SL/TP (regime-dependent)
- **Performance Attribution** — Hedge-fund-style profit/loss analysis by strategy, regime, session, symbol, sentiment
- **Adaptive Strategy Weights** — Self-learning strategy weights with exponential decay and regime-sensitivity
- **KI-Gemeinschaftswissen** — Shared knowledge base with optional LLM integration (Ollama, LM Studio)

### Risk Management
- **Circuit Breaker** — Automatic trading pause after consecutive losses
- **Drawdown Control** — Max portfolio drawdown limit with automatic pause
- **Daily Loss Limit** — Max 5% daily loss, resets at midnight
- **Correlation Filter** — Blocks correlated positions (>0.75)
- **Liquidity Check** — Orderbook spread + minimum volume verification
- **Symbol Cooldown** — Locks symbols after a loss
- **Trailing & Break-Even Stop-Loss** — Dynamic SL adjustment
- **Monte-Carlo Risk Analysis** — Portfolio VaR/CVaR calculation
- **Funding Rate Filter** — Avoids expensive short positions
- **Conformal Prediction** — Guaranteed prediction intervals

### Market Analysis
- **Fear & Greed Index** — Alternative.me sentiment signal
- **Market Regime Detection** — Bull/Bear/Range/Crash classification
- **BTC/USDT Dominance Filter** — Altcoin trade blocking when BTC dominates
- **News Sentiment** — CryptoPanic real-time news as AI signal
- **On-Chain Data** — Whale alerts, exchange flows (CryptoQuant)

### Autonomous Agents (NEW v1.5)
- **Auto-Healing Agent** — Self-healing system: monitors processes, APIs, DB; auto-recovers on failure with escalation
- **Revenue Tracking Agent** — Real PnL tracking after fees, slippage; daily/weekly/monthly summaries; losing strategy detection
- **Multi-Server Control Agent** — Cluster management: remote node monitoring, start/stop/deploy, aggregated metrics

### Infrastructure
- **Real-time Dashboard** — WebSocket-powered live UI with Socket.IO
- **Full REST API** — 85+ JWT-authenticated endpoints
- **Multi-User System** — Multiple portfolios, each with own API keys
- **2FA** — Two-factor authentication (TOTP)
- **5 Languages** — DE, EN, ES, RU, PT
- **Discord & Telegram** — Real-time trade notifications
- **GitHub Updater** — In-dashboard one-click update & rollback
- **Auto-Backup** — Regular data backup with SHA-256 verification
- **Copy Trading** — Followers receive all signals in real time
- **Exchange Compatibility** — Safe ticker fetching for all exchanges including Crypto.com

---

## Quick Installation

```bash
# One-liner install (Ubuntu/Debian)
curl -O https://raw.githubusercontent.com/itsamemedev/Trevlix/main/install.sh
sudo bash install.sh
```

Or manually:

```bash
git clone https://github.com/itsamemedev/Trevlix.git
cd Trevlix
pip install -r requirements.txt
cp .env.example .env
nano .env          # Enter API keys
python server.py
```

Dashboard: **http://localhost:5000**

---

## Docker

```bash
cp .env.example .env
nano .env
docker-compose up -d
```

---

## Configuration

All settings in `.env`:

```env
# Exchange
EXCHANGE=cryptocom
API_KEY=your_api_key
API_SECRET=your_secret

# Security
ADMIN_PASSWORD=secure_password_min_12_chars
JWT_SECRET=random_hex_string_32chars
SECRET_KEY=random_hex_string_32chars
ENCRYPTION_KEY=fernet_key  # python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# CORS (optional — default allows all origins)
# ALLOWED_ORIGINS=https://yourdomain.com,http://localhost:5000

# Trading
PAPER_TRADING=true   # Always start in paper mode first!

# Unique Features
USE_TRADE_DNA=true           # Trade DNA fingerprinting
USE_SMART_EXITS=true         # Volatility-adaptive SL/TP
USE_ADAPTIVE_WEIGHTS=true    # Self-learning strategy weights

# Notifications (optional)
DISCORD_WEBHOOK=https://discord.com/api/webhooks/...
DISCORD_ON_SIGNALS=true
DISCORD_SIGNAL_COOLDOWN_SEC=900
TELEGRAM_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id

# Optional: kostenlose LLM-Provider für KI-Training/Analyse mit Failover
GROQ_API_KEY=...
OPENROUTER_API_KEY=...
HF_API_KEY=...
CEREBRAS_API_KEY=...
```

Full guide: [INSTALLATION.html](templates/INSTALLATION.html)

---

## Project Structure

```
trevlix/
├── server.py                          # Entry Point + Laufzeit-Orchestrierung
├── app/
│   ├── __init__.py
│   └── core/
│       ├── __init__.py
│       ├── bootstrap.py               # Flask/CORS/Socket.IO/Limiter Bootstrap
│       ├── logging_setup.py           # Logging-Konfiguration
│       ├── default_config.py          # Zentrale Default-Konfiguration (CONFIG-Builder)
│       ├── runtime.py                 # Runtime-Startsequenz
│       ├── http_routes.py             # System-Routen + Error-Handling
│       ├── lifecycle.py               # Graceful Shutdown + Signals
│       ├── request_helpers.py         # Sichere Request-Parser + Exchange-Normalisierung
│       ├── websocket_guard.py         # Gemeinsame Socket.IO-Rate-Limiter-Helfer
│       ├── auth_guards.py             # Login-Rate-Limiter + Auth-Decorator-Builder
│       ├── session_guard.py           # Session-Timeout + CSRF-Prüfungen (before_request)
│       ├── socket_emit.py             # Sichere Socket.IO-Emission aus Worker-Threads
│       ├── exchange_secret.py         # Secret-Entschlüsselung + Single-Mode-Helfer
│       ├── admin_exchange.py          # Admin-Exchange-Auswahl/DB-Helfer
│       ├── market_cache.py            # Persistenter Markt-Cache (Disk)
│       ├── exchange_runtime.py        # Exchange-Erzeugung + Preflight/Recovery
│       ├── paper_mode.py              # Erzwingt sicheren Paper-Modus beim Start
│       ├── admin_password_policy.py   # Schwache Admin-Passwort-Erkennung
│       ├── db_request_context.py      # Request-skopierte DB-Connection-Helfer
│       ├── audit_writer.py            # Audit-Log Persistenz-Helfer
│       ├── bot_heartbeat.py           # Heartbeat-basiertes Sleep im Bot-Loop
│       ├── api_docs_schema.py         # API-Dokumentationspayload-Builder
│       ├── websocket_state.py         # WebSocket-State-Snapshot-Helfer
│       ├── socket_error_logger.py     # Einheitliches SocketIO-Error-Logging
│       ├── websocket_authz.py         # WS Auth/Admin-Prüfungen
│       ├── ws_rate_gate.py            # WS Rate-Gate Delegation
│       ├── backup_verify.py           # Backup-Verify-Helfer (latest file)
│       ├── tax_export.py              # Steuerreport-CSV-Konvertierung
│       ├── trade_export.py            # Trade-JSON-Export-Konvertierung
│       ├── startup_view.py            # Startup-Banner Renderer
│       ├── prometheus_metrics.py      # Prometheus-Metrikzeilen-Builder
│       └── security.py                # Security-Header + CSRF-Token-Helfer
├── routes/                            # Flask Blueprints (Auth, Dashboard, WS-Migration)
├── services/                          # Business-Logik (Trading, Risk, AI, Integrationen)
│   └── passwords.py                   # PBKDF2 Passwort-Hashing-Fallback
├── templates/                         # HTML Templates
├── static/                            # Frontend Assets
├── tests/                             # Pytest Test-Suite
├── docs/                              # Technische Dokumentation
├── CHANGELOG.md                       # Versionshistorie
├── VERSION.md                         # Aktuelle Projektversion
├── LAST_WORK.md                       # Letzte Arbeiten + nächste Schritte
├── WORKFLOW_RULES.md                  # Dauerhafte Änderungsregeln
├── PROJECT_STRUCTURE.md               # Struktur-Leitbild
├── TODO.md                            # Offene Refactoring-Aufgaben
└── README.md                          # Einstieg & Bedienung
```

---


## Maintenance Workflow

Bei jeder relevanten Änderung gilt:
- Version prüfen/aktualisieren (`VERSION.md`, `pyproject.toml`, `services/utils.py`)
- `CHANGELOG.md` und `LAST_WORK.md` aktualisieren
- Bei Strukturänderungen zusätzlich `README.md` und `PROJECT_STRUCTURE.md` anpassen
- Neue große Logik **nicht** direkt in `server.py`, sondern in passende Module auslagern

## REST API (85+ Endpoints)

| Category | Endpoints | Description |
|----------|-----------|-------------|
| **Auth** | `/login`, `/register`, `/logout` | Username/password + 2FA |
| **Trading** | `/api/v1/positions`, `/api/v1/trades` | Open/closed positions |
| **Config** | `/api/v1/config`, `/api/v1/status` | Bot configuration |
| **Exchange** | `/api/v1/user/exchanges`, `/api/v1/balance/all` | Multi-exchange management |
| **Knowledge** | `/api/v1/knowledge/*` | AI knowledge base + LLM |
| **Risk** | `/api/v1/risk/cvar`, `/api/v1/risk/volatility` | Risk metrics |
| **DNA** | `/api/v1/trade-dna`, `/api/v1/trade-dna/patterns` | Trade fingerprinting |
| **Smart Exits** | `/api/v1/smart-exits` | Volatility-adaptive exits |
| **Attribution** | `/api/v1/performance/attribution` | Profit/loss breakdown |
| **Weights** | `/api/v1/strategies/weights` | Adaptive strategy weights |
| **Backup** | `/api/v1/backup`, `/api/v1/backup/verify` | Backup & verification |
| **Update** | `/api/v1/update/check`, `/api/v1/update/apply` | GitHub updater |

Full API documentation: [api-docs.html](templates/api-docs.html)

---

## WebSocket Events

| Event | Direction | Description |
|-------|-----------|-------------|
| `start_bot` / `stop_bot` / `pause_bot` | Client → Server | Bot control |
| `update_config` | Client → Server | Save settings |
| `save_api_keys` | Client → Server | Store encrypted exchange keys |
| `close_position` | Client → Server | Manually close a trade |
| `run_backtest` | Client → Server | Start backtest |
| `force_train` / `force_optimize` | Client → Server | Trigger AI training |
| `check_update` / `apply_update` | Client → Server | GitHub updater |
| `start_exchange` / `stop_exchange` | Client → Server | Multi-exchange control |
| `scan_arbitrage` | Client → Server | Find price spreads |
| `create_grid` | Client → Server | Create grid strategy |
| `update` | Server → Client | Full state snapshot |
| `trade` | Server → Client | Trade executed |
| `ai_update` | Server → Client | AI model update |

---

## The 9 Trading Strategies

| # | Strategy | Signal Logic |
|---|----------|-------------|
| 1 | **EMA-Trend** | EMA 8/21/50 alignment + price confirmation |
| 2 | **RSI-Stochastic** | Oversold (<35) / Overbought (>65) oscillator |
| 3 | **MACD-Crossover** | Signal line crossover + zero-line filter |
| 4 | **Bollinger Bands** | Mean reversion near band edges + RSI |
| 5 | **Volume Breakout** | High-volume candle in trend direction |
| 6 | **OBV-Trend** | On-Balance-Volume trend confirmation |
| 7 | **ROC-Momentum** | Rate of Change dual-timeframe threshold |
| 8 | **Ichimoku** | Tenkan-Kijun crossover, cloud confirmation |
| 9 | **VWAP** | Volume-Weighted Average Price deviation + RSI |

All strategies vote: **+1** (buy), **-1** (sell), **0** (neutral). Weighted voting determines the final signal.

---

## Multi-User & API Keys

Each registered user stores their own exchange API keys in the database (Fernet-encrypted). The bot runs trades for each user using their personal credentials — no shared keys, full separation. An admin can manage users and global bot configuration via the admin panel.

---

## Security

- **Fernet Encryption** — All API keys encrypted before storage
- **bcrypt Hashing** — Secure password storage
- **2FA (TOTP)** — Two-factor authentication
- **JWT Authentication** — Secure API tokens
- **CSRF Protection** — Token validation on forms
- **Rate Limiting** — 5 login attempts per IP per 15 min
- **IP Whitelist** — Access control by IP
- **Protected Config** — Sensitive keys only via `.env` (not API)
- **CORS** — Configurable origin restriction
- **Audit Log** — Full action history

---

## Disclaimer

> **Always start with `PAPER_TRADING=true`!**
> The bot trades with real money. Cryptocurrency trading carries substantial risk.
> Past performance does not guarantee future results.

---

## License

MIT License — see [LICENSE](LICENSE)
