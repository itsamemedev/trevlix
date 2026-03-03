<div align="center">

```
████████╗██████╗ ███████╗██╗   ██╗██╗     ██╗██╗  ██╗
   ██╔══╝██╔══██╗██╔════╝██║   ██║██║     ██║╚██╗██╔╝
   ██║   ██████╔╝█████╗  ██║   ██║██║     ██║ ╚███╔╝
   ██║   ██╔══██╗██╔══╝  ╚██╗ ██╔╝██║     ██║ ██╔██╗
   ██║   ██║  ██║███████╗ ╚████╔╝ ███████╗██║██╔╝ ██╗
   ╚═╝   ╚═╝  ╚═╝╚══════╝  ╚═══╝  ╚══════╝╚═╝╚═╝  ╚═╝
```

**Algorithmic Trading Intelligence — v1.0.4**

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://python.org)
[![Flask](https://img.shields.io/badge/flask-3.0-green.svg)](https://flask.palletsprojects.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

</div>

---

## Features

- **Multi-Exchange Support** — Crypto.com, Binance, Bybit, OKX, KuCoin simultaneously
- **14+ AI Modules** — XGBoost, LightGBM, CatBoost, LSTM, Transformer, Random Forest
- **9 Voting Strategies** — EMA Trend, RSI+Stochastic, MACD, Bollinger, Volume, OBV, ROC, Ichimoku, VWAP
- **Grid Trading** — Automated grid strategies with configurable levels
- **Monte-Carlo Risk Analysis** — Portfolio simulations with VaR calculation
- **Circuit Breaker** — Automatic trading pause after consecutive losses
- **Paper Trading** — Risk-free testing without real capital
- **Copy Trading** — Followers receive all signals in real time
- **Multi-User System** — Multiple portfolios on a single instance, each with their own API keys
- **2FA** — Two-factor authentication (TOTP)
- **5 Languages** — DE, EN, ES, RU, PT
- **Full REST API** — JWT-authenticated API with WebSocket real-time updates

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

## Website & Documentation

TREVLIX comes with a complete documentation website. All pages are interlinked with a consistent navigation bar, footer, and responsive design.

### Pages

| Page | File | Description |
|------|------|-------------|
| **Home** | `index.html` | Landing page with features, comparison, and download |
| **Dashboard** | `dashboard.html` | Real-time trading dashboard with WebSocket updates |
| **Installation** | `INSTALLATION.html` | Step-by-step setup guide (Docker, manual, Raspberry Pi) |
| **Strategies** | `strategies.html` | Detailed explanation of all 9 voting strategies |
| **API Docs** | `api-docs.html` | Complete REST API reference with examples |
| **FAQ** | `faq.html` | 18 frequently asked questions with answers |
| **Security** | `security.html` | Security hardening guide and best practices |
| **Changelog** | `changelog.html` | Visual release history (v1.0.0 — v1.0.4) |
| **Roadmap** | `roadmap.html` | Planned features and development phases |
| **About** | `about.html` | Project info, tech stack, and contributing guide |
| **404** | `404.html` | Custom error page with navigation |

### Shared Assets

| File | Description |
|------|-------------|
| `shared-nav.css` | Shared navigation bar, footer, breadcrumbs, back-to-top button, print styles |
| `trevlix_translations.js` | Frontend i18n translations (5 languages) |
| `sitemap.xml` | SEO sitemap for all pages |
| `robots.txt` | Crawler directives |

### Design Features

- Dark theme with neon green (#00ff88) accent
- Responsive design (mobile-first)
- Fixed site-wide navigation bar
- Breadcrumb navigation on sub-pages
- Back-to-top button
- Skip-to-content accessibility link
- OpenGraph and Twitter Card meta tags
- JSON-LD structured data (index.html)
- Print stylesheet for documentation pages

---

## Project Structure

```
trevlix/
├── server.py                  # Flask + WebSocket Backend (5000+ lines)
├── ai_engine.py               # AI Engine (XGBoost, LSTM, ...)
├── trevlix_i18n.py            # Internationalization (Python)
├── trevlix_translations.js    # Internationalization (JS)
│
├── Website
│   ├── index.html             # Landing Page
│   ├── dashboard.html         # Trading Dashboard UI
│   ├── INSTALLATION.html      # Installation Guide
│   ├── strategies.html        # Trading Strategies Guide
│   ├── api-docs.html          # REST API Documentation
│   ├── faq.html               # FAQ Page
│   ├── security.html          # Security Guide
│   ├── changelog.html         # Changelog
│   ├── roadmap.html           # Feature Roadmap
│   ├── about.html             # About Page
│   ├── 404.html               # Error Page
│   └── shared-nav.css         # Shared Navigation Styles
│
├── Configuration
│   ├── .env.example           # Configuration template (73 variables)
│   ├── requirements.txt       # Python dependencies (47 packages)
│   ├── pyproject.toml         # pytest, coverage, ruff config
│   ├── Makefile               # 15 convenience targets
│   └── install.sh             # One-click installer
│
├── Docker
│   ├── Dockerfile             # Multi-stage Python 3.11 image
│   ├── docker-compose.yml     # 3 services: trevlix, mysql, nginx
│   └── docker/
│       ├── nginx.conf         # Nginx reverse proxy (HTTPS, WebSocket)
│       ├── mysql-init.sql     # 14-table database schema
│       └── ssl/               # SSL certificates
│
├── Services
│   └── services/
│       ├── db_pool.py         # MySQL connection pooling
│       ├── encryption.py      # Fernet API key encryption
│       └── indicator_cache.py # Technical indicator caching
│
├── SEO
│   ├── sitemap.xml            # Sitemap
│   └── robots.txt             # Crawler directives
│
├── Tests
│   └── tests/
│       ├── conftest.py        # pytest fixtures
│       ├── test_encryption.py # Encryption tests
│       ├── test_indicators.py # Indicator tests
│       └── test_risk.py       # Risk management tests
│
├── CHANGELOG.md               # Detailed version history
├── README.md                  # This file
└── LICENSE                    # MIT License
```

---

## Multi-User & API Keys

Each registered user stores their own exchange API keys in the database (Fernet-encrypted). The bot runs trades for each user using their personal credentials — no shared keys, full separation. An admin can manage users and global bot configuration via the admin panel.

---

## Disclaimer

> **Always start with `PAPER_TRADING=true`!**
> The bot trades with real money. Cryptocurrency trading carries substantial risk.
> Past performance does not guarantee future results.

---

## License

MIT License — see [LICENSE](LICENSE)
