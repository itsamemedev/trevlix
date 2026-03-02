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

- **Multi-Exchange Support** — Crypto.com, Binance, Bybit, OKX, KuCoin gleichzeitig
- **14+ KI-Module** — XGBoost, LightGBM, CatBoost, LSTM, Transformer, Random Forest
- **Grid-Trading** — Automatisierte Grid-Strategien mit konfigurierbaren Levels
- **Monte-Carlo Risikoanalyse** — Portfoliosimulationen mit VaR-Berechnung
- **Telegram-Benachrichtigungen** — Echtzeit-Alerts für alle Trades
- **Audit-Log** — Lückenlose Protokollierung aller Aktionen
- **Break-Even Stop-Loss** — Automatische SL-Anpassung nach Gewinn
- **Symbol-Cooldown** — Sperrt Symbole nach Verlust
- **IP-Whitelist** — Zugangskontrolle per IP
- **News-Sentiment-Filter** — Blockiert Trades bei negativen Nachrichten
- **Funding-Rate-Filter** — Vermeidet teure Short-Positionen
- **Paper-Trading** — Risikofrei testen ohne echtes Kapital
- **Copy-Trading** — Follower empfangen alle Signale in Echtzeit
- **2FA** — Zwei-Faktor-Authentifizierung (TOTP)

---

## ⚡ Schnellinstallation

```bash
# Einzeiler-Installation (Ubuntu/Debian)
curl -O https://raw.githubusercontent.com/DEIN_USER/trevlix/main/install.sh
sudo bash install.sh
```

Oder manuell:

```bash
git clone https://github.com/DEIN_USER/trevlix.git
cd trevlix
pip install -r requirements.txt
cp .env.example .env
nano .env          # API-Keys eintragen
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

## ⚙️ Konfiguration

Alle Einstellungen in `.env`:

```env
# Exchange
EXCHANGE=cryptocom
API_KEY=dein_api_key
API_SECRET=dein_secret

# Multi-Exchange (optional)
BINANCE_ENABLED=true
BINANCE_API_KEY=...
BINANCE_SECRET=...

# Sicherheit
ADMIN_PASSWORD=sicheres_passwort
JWT_SECRET=zufälliger_string

# Trading
PAPER_TRADING=true   # Erst im Paper-Modus starten!
```

Vollständige Anleitung: [INSTALLATION.html](INSTALLATION.html)

---

## 📁 Projektstruktur

```
trevlix/
├── server.py                  # Flask + WebSocket Backend
├── dashboard.html             # Trading Dashboard UI
├── index.html                 # Landing Page
├── ai_engine.py               # KI-Engine (XGBoost, LSTM, ...)
├── trevlix_i18n.py            # Internationalisierung (Python)
├── trevlix_translations.js    # Internationalisierung (JS)
├── requirements.txt           # Python-Abhängigkeiten
├── install.sh                 # Ein-Klick Installer
├── .env.example               # Konfigurationsvorlage
├── Dockerfile                 # Docker-Image
├── docker-compose.yml         # Docker-Compose Setup
├── INSTALLATION.html          # Installationsanleitung
└── docker/
    ├── nginx.conf             # Nginx Reverse-Proxy
    └── mysql-init.sql         # Datenbank-Schema
```

---

## ⚠️ Disclaimer

> **Starte immer mit `PAPER_TRADING=true`!**  
> Der Bot handelt mit echtem Geld. Kryptowährungshandel birgt erhebliche Risiken.  
> Vergangene Performance garantiert keine zukünftigen Ergebnisse.

---

## 📄 Lizenz

MIT License — siehe [LICENSE](LICENSE)
