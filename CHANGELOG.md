# Changelog

All notable changes to TREVLIX are documented in this file.

Format based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Versioning follows [Semantic Versioning](https://semver.org/) — `MAJOR.MINOR.PATCH`.

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
