<div align="center">

```
████████╗██████╗ ███████╗██╗   ██╗██╗     ██╗██╗  ██╗
   ██╔══╝██╔══██╗██╔════╝██║   ██║██║     ██║╚██╗██╔╝
   ██║   ██████╔╝█████╗  ██║   ██║██║     ██║ ╚███╔╝
   ██║   ██╔══██╗██╔══╝  ╚██╗ ██╔╝██║     ██║ ██╔██╗
   ██║   ██║  ██║███████╗ ╚████╔╝ ███████╗██║██╔╝ ██╗
   ╚═╝   ╚═╝  ╚═╝╚══════╝  ╚═══╝  ╚══════╝╚═╝╚═╝  ╚═╝
```

**Algorithmic Trading Intelligence**

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://python.org)
[![Flask](https://img.shields.io/badge/flask-3.0-green.svg)](https://flask.palletsprojects.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

</div>

---

## 🚀 Features

- **Multi-Exchange Support** — Crypto.com, Binance, Bybit, OKX, KuCoin simultaneously
- **14+ AI Modules** — XGBoost, LightGBM, CatBoost, LSTM, Transformer, Random Forest
- **Grid Trading** — Automated grid strategies with configurable levels
- **Monte-Carlo Risk Analysis** — Portfolio simulations with VaR calculation
- **Telegram Notifications** — Real-time alerts for all trades
- **Audit Log** — Full action history with timestamps
- **Break-Even Stop-Loss** — Automatic SL adjustment after profit
- **Symbol Cooldown** — Locks symbols after a loss
- **IP Whitelist** — Access control by IP address
- **News Sentiment Filter** — Blocks trades on negative news
- **Funding Rate Filter** — Avoids expensive short positions
- **Paper Trading** — Risk-free testing without real capital
- **Copy Trading** — Followers receive all signals in real time
- **2FA** — Two-factor authentication (TOTP)
- **Multi-User System** — Multiple portfolios on a single instance, each with their own API keys

---

## ⚡ Quick Installation

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

## 🐳 Docker

```bash
cp .env.example .env
nano .env
docker-compose up -d
```

---

## ⚙️ Configuration

All settings in `.env`:

```env
# Exchange
EXCHANGE=cryptocom
API_KEY=your_api_key
API_SECRET=your_secret

# Multi-Exchange (optional)
BINANCE_ENABLED=true
BINANCE_API_KEY=...
BINANCE_SECRET=...

# Security
ADMIN_PASSWORD=secure_password
JWT_SECRET=random_string

# Trading
PAPER_TRADING=true   # Always start in paper mode first!
```

Full guide: [INSTALLATION.html](INSTALLATION.html)

---

## 📁 Project Structure

```
trevlix/
├── server.py                  # Flask + WebSocket Backend
├── dashboard.html             # Trading Dashboard UI
├── index.html                 # Landing Page
├── ai_engine.py               # AI Engine (XGBoost, LSTM, ...)
├── trevlix_i18n.py            # Internationalization (Python)
├── trevlix_translations.js    # Internationalization (JS)
├── requirements.txt           # Python dependencies
├── install.sh                 # One-click installer
├── .env.example               # Configuration template
├── Dockerfile                 # Docker image
├── docker-compose.yml         # Docker Compose setup
├── INSTALLATION.html          # Installation guide
└── docker/
    ├── nginx.conf             # Nginx reverse proxy
    └── mysql-init.sql         # Database schema
```

---

## 👤 Multi-User & API Keys

Each registered user stores their own exchange API keys in the database. The bot runs trades for each user using their personal credentials — no shared keys, full separation. An admin can manage users and global bot configuration via the admin panel.

---

## ⚠️ Disclaimer

> **Always start with `PAPER_TRADING=true`!**
> The bot trades with real money. Cryptocurrency trading carries substantial risk.
> Past performance does not guarantee future results.

---

## 📄 License

MIT License — see [LICENSE](LICENSE)
