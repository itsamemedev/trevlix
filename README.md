<div align="center">

```
████████╗██████╗ ███████╗██╗   ██╗██╗     ██╗██╗  ██╗
   ██╔══╝██╔══██╗██╔════╝██║   ██║██║     ██║╚██╗██╔╝
   ██║   ██████╔╝█████╗  ██║   ██║██║     ██║ ╚███╔╝
   ██║   ██╔══██╗██╔══╝  ╚██╗ ██╔╝██║     ██║ ██╔██╗
   ██║   ██║  ██║███████╗ ╚████╔╝ ███████╗██║██╔╝ ██╗
   ╚═╝   ╚═╝  ╚═╝╚══════╝  ╚═══╝  ╚══════╝╚═╝╚═╝  ╚═╝
```

**Algorithmic Crypto Trading Bot — v1.5.0**

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://python.org)
[![Flask](https://img.shields.io/badge/flask-3.0-green.svg)](https://flask.palletsprojects.com)
[![Socket.io](https://img.shields.io/badge/socket.io-4.7-black.svg)](https://socket.io)
[![Tests](https://img.shields.io/badge/tests-250+-brightgreen.svg)](tests/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-1.5.0-brightgreen.svg)](CHANGELOG.md)

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
TELEGRAM_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

Full guide: [INSTALLATION.html](templates/INSTALLATION.html)

---

## Project Structure

```
trevlix/
├── server.py                          # Flask + WebSocket Backend (7400+ lines)
├── ai_engine.py                       # AI Engine reference (XGBoost, LSTM, ...)
├── trevlix_i18n.py                    # Internationalization (Python)
├── validate_env.py                    # Pre-startup environment validation
│
├── routes/                            # Flask Blueprints
│   ├── auth.py                        # Login, register, 2FA, admin
│   ├── dashboard.py                   # Static page routes
│   └── websocket.py                   # WebSocket event handlers
│
├── services/                          # Modular business logic (19 modules)
│   ├── adaptive_weights.py            # Self-learning strategy weights
│   ├── auto_healing.py                # Auto-Healing Agent (system recovery) [NEW v1.5]
│   ├── cluster_control.py             # Multi-Server Control Agent [NEW v1.5]
│   ├── config.py                      # Pydantic BaseSettings configuration
│   ├── cryptopanic.py                 # CryptoPanic news sentiment client
│   ├── db_pool.py                     # Thread-safe MySQL connection pooling
│   ├── encryption.py                  # Fernet API key encryption
│   ├── exchange_manager.py            # Multi-exchange manager (CCXT)
│   ├── indicator_cache.py             # Technical indicator TTL caching
│   ├── knowledge.py                   # AI knowledge base + LLM integration
│   ├── market_data.py                 # FearGreed, dominance, sentiment, on-chain
│   ├── notifications.py               # Discord & Telegram alerts
│   ├── performance_attribution.py     # Profit/loss factor analysis
│   ├── revenue_tracking.py            # Revenue Tracking Agent (PnL/ROI) [NEW v1.5]
│   ├── risk.py                        # Circuit breaker, VaR, correlation filter
│   ├── smart_exits.py                 # Volatility-adaptive SL/TP
│   ├── strategies.py                  # 9 voting trading strategies
│   ├── trade_dna.py                   # Trade DNA fingerprinting
│   └── utils.py                       # Shared utilities & constants
│
├── templates/                         # Jinja2 HTML templates (11 pages)
│   ├── index.html                     # Landing page
│   ├── dashboard.html                 # Real-time trading dashboard
│   ├── INSTALLATION.html              # Setup guide
│   ├── strategies.html                # Strategy documentation
│   ├── api-docs.html                  # REST API reference
│   ├── faq.html, security.html        # FAQ & security
│   ├── changelog.html, roadmap.html   # History & roadmap
│   ├── about.html, 404.html           # About & error page
│
├── static/                            # Frontend assets
│   ├── css/shared-nav.css             # Shared navigation styles
│   ├── css/dashboard.css              # Dashboard styles
│   ├── js/dashboard.js                # Dashboard logic (1823 lines)
│   ├── js/trevlix_translations.js     # i18n (5 languages)
│   └── js/page_i18n.js               # Page translator
│
├── tests/                             # Pytest test suite (250+ tests)
│   ├── conftest.py                    # Shared fixtures
│   ├── test_adaptive_weights.py       # Adaptive weights tests [NEW]
│   ├── test_performance_attribution.py # Attribution tests [NEW]
│   ├── test_trade_dna.py              # DNA fingerprinting tests
│   ├── test_smart_exits.py            # Smart exit tests
│   └── ... (14 test modules, 250+ tests total)
│
├── docker/                            # Docker infrastructure
│   ├── Dockerfile                     # Multi-stage Python 3.11 image
│   ├── docker-compose.yml             # 3 services: trevlix, mysql, nginx
│   ├── mysql-init.sql                 # 17-table database schema
│   └── nginx.conf                     # Reverse proxy (HTTPS, WebSocket)
│
├── docs/                              # Extended documentation
│   ├── API.md, ARCHITECTURE.md        # API & architecture docs
│   ├── DATABASE.md, SECURITY.md       # DB schema & security
│   ├── SERVICES.md, SETUP.md          # Services & setup guide
│   └── TRADING.md                     # Trading strategies & config
│
├── CHANGELOG.md                       # Detailed version history
├── CLAUDE.md                          # Claude Code workflow guidelines
├── README.md                          # This file
└── LICENSE                            # MIT License
```

---

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
