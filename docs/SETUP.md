# Trevlix – Setup & Deployment Guide

## 1. Systemvoraussetzungen

| Komponente | Mindestanforderung |
|---|---|
| Python | 3.11 oder neuer |
| Datenbank | MySQL 8.0+ oder MariaDB 10.6+ |
| RAM | 2 GB (4 GB empfohlen) |
| Betriebssystem | Linux (Ubuntu 18.04–24.04, Debian 10–12), macOS, Windows (WSL2) |
| Sonstiges | `pip`, `venv`, `git`, `curl` |

---

## 2. Schnellstart

```bash
# 1. Repository klonen
git clone https://github.com/dein-user/trevlix.git
cd trevlix

# 2. Virtuelle Umgebung erstellen und aktivieren
python3 -m venv venv
source venv/bin/activate

# 3. Abhängigkeiten installieren
pip install -r requirements.txt

# 4. Umgebungsvariablen konfigurieren
cp .env.example .env
# Danach .env mit einem Editor anpassen – ALLE Pflichtfelder ausfuellen!

# 5. Datenbank initialisieren (siehe Abschnitt 5)
mysql -u root -p < docker/mysql-init.sql
# Alternativ: Die Anwendung erstellt Tabellen automatisch beim ersten Start.

# 6. Bot starten
python3 server.py
```

Das Dashboard ist danach unter `http://localhost:5000` erreichbar.

---

## 3. Umgebungsvariablen

Alle Variablen werden in der Datei `.env` im Projektverzeichnis konfiguriert. Vorlage kopieren mit `cp .env.example .env`.

### Exchange

| Variable | Pflicht | Beschreibung |
|---|---|---|
| `EXCHANGE` | Ja | Exchange-Name: `cryptocom`, `binance`, `bybit`, `okx`, `kucoin`, `kraken`, `huobi`, `coinbase` |
| `API_KEY` | Ja | API-Schluessel der Exchange |
| `API_SECRET` | Ja | API-Secret der Exchange |

### Datenbank

| Variable | Pflicht | Standard | Beschreibung |
|---|---|---|---|
| `MYSQL_HOST` | Ja | `localhost` | Datenbank-Host |
| `MYSQL_PORT` | Ja | `3306` | Datenbank-Port |
| `MYSQL_USER` | Ja | `trevlix` | Datenbank-Benutzer |
| `MYSQL_PASS` | Ja | – | Datenbank-Passwort (min. 16 Zeichen, komplex) |
| `MYSQL_ROOT_PASS` | Nur Docker | – | MySQL-Root-Passwort (nur fuer Docker-Setup) |
| `MYSQL_DB` | Ja | `trevlix` | Datenbankname |

### Sicherheit

| Variable | Pflicht | Beschreibung |
|---|---|---|
| `ADMIN_PASSWORD` | Ja | Admin-Login-Passwort (min. 12 Zeichen, Gross+Klein+Zahl+Sonderzeichen) |
| `DASHBOARD_SECRET` | Ja | Dashboard-Session-Secret (32 Hex-Zeichen) |
| `JWT_SECRET` | Ja | JWT-Secret fuer API-Tokens (32+ Hex-Zeichen) |
| `SECRET_KEY` | Ja | Flask-Session-Secret-Key (32+ Hex-Zeichen) |
| `ENCRYPTION_KEY` | Ja | Fernet-Key fuer API-Key-Verschluesselung (44 Base64url-Zeichen) |
| `SESSION_TIMEOUT_MIN` | Nein | Session-Timeout in Minuten (Standard: 30) |
| `ALLOWED_ORIGINS` | Nein | Erlaubte CORS-Origins, kommagetrennt (kein Wildcard `*`) |

### Trading

| Variable | Pflicht | Standard | Beschreibung |
|---|---|---|---|
| `PAPER_TRADING` | Nein | `true` | Paper-Trading-Modus aktivieren (siehe Abschnitt 8) |
| `AUTO_START` | Nein | `true` | Bot startet automatisch ohne Admin-Login |
| `ALLOW_REGISTRATION` | Nein | `false` | Oeffentliche Selbst-Registrierung erlauben |

### Benachrichtigungen

| Variable | Pflicht | Beschreibung |
|---|---|---|
| `DISCORD_WEBHOOK` | Nein | Discord-Webhook-URL fuer Trade-Benachrichtigungen |
| `TELEGRAM_TOKEN` | Nein | Telegram-Bot-Token |
| `TELEGRAM_CHAT_ID` | Nein | Telegram-Chat-ID fuer Benachrichtigungen |
| `CRYPTOPANIC_TOKEN` | Nein | CryptoPanic API v2 Token fuer News-Sentiment |
| `CRYPTOPANIC_API_PLAN` | Nein | CryptoPanic-Plan: `free`, `pro`, `developer` (Standard: `free`) |
| `BLOCKNATIVE_KEY` | Nein | Blocknative-API-Key fuer Mempool-Monitoring (nicht implementiert) |

### KI / LLM

| Variable | Pflicht | Beschreibung |
|---|---|---|
| `LLM_ENDPOINT` | Nein | OpenAI-kompatible LLM-API-URL (z.B. Ollama: `http://localhost:11434/api/chat`) |
| `LLM_API_KEY` | Nein | API-Key fuer die LLM-API (leer fuer lokale Modelle ohne Auth) |

### Server

| Variable | Pflicht | Standard | Beschreibung |
|---|---|---|---|
| `PORT` | Nein | `5000` | Server-Port |
| `LANGUAGE` | Nein | `de` | Sprache: `de`, `en`, `es`, `ru`, `pt` |
| `LOG_LEVEL` | Nein | `INFO` | Log-Level: `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `JSON_LOGS` | Nein | `false` | Strukturierte JSON-Logs (fuer ELK/Grafana/Loki) |
| `COLOR_LOGS` | Nein | `true` | Farbige Konsolenausgabe (ANSI) |

---

## 4. Schluessel generieren

Alle Sicherheitsschluessel muessen individuell generiert werden. **Niemals die Standardwerte aus `.env.example` verwenden!**

```bash
# ENCRYPTION_KEY (Fernet, 44 Base64url-Zeichen)
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# JWT_SECRET (64 Hex-Zeichen)
python3 -c "import secrets; print(secrets.token_hex(32))"

# SECRET_KEY (64 Hex-Zeichen)
python3 -c "import secrets; print(secrets.token_hex(32))"

# DASHBOARD_SECRET (64 Hex-Zeichen)
python3 -c "import secrets; print(secrets.token_hex(32))"
```

---

## 5. Datenbank einrichten

### Option A: Manuell

```bash
# 1. Datenbank und Benutzer anlegen
mysql -u root -p <<SQL
CREATE DATABASE IF NOT EXISTS trevlix
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

CREATE USER IF NOT EXISTS 'trevlix'@'localhost'
    IDENTIFIED BY 'DEIN_SICHERES_PASSWORT';

GRANT ALL PRIVILEGES ON trevlix.* TO 'trevlix'@'localhost';
FLUSH PRIVILEGES;
SQL

# 2. Schema importieren
mysql -u trevlix -p trevlix < docker/mysql-init.sql
```

### Option B: Automatisch beim Start

Trevlix erstellt alle benoetigten Tabellen automatisch beim ersten Start ueber `server.py:_init_db_once()`. Dafuer muss lediglich die Datenbank und der Benutzer existieren.

### Option C: Docker (empfohlen)

Bei Verwendung von Docker Compose wird die Datenbank vollautomatisch initialisiert (siehe Abschnitt 6).

---

## 6. Docker Deployment

### Schnellstart mit Docker Compose

```bash
# .env konfigurieren (Pflichtfelder setzen!)
cp .env.example .env
# .env bearbeiten ...

# Starten (Bot + MySQL)
docker compose up -d

# Logs verfolgen
docker compose logs -f trevlix

# Stoppen
docker compose down
```

### Produktion mit Nginx und SSL

```bash
# Mit Nginx-Reverse-Proxy starten
docker compose --profile production up -d
```

Dies startet zusaetzlich einen Nginx-Container (Ports 80 und 443). SSL-Zertifikate muessen unter `docker/ssl/` abgelegt werden.

### SSL mit Let's Encrypt

```bash
# Certbot installieren
sudo apt install certbot

# Zertifikat generieren
sudo certbot certonly --standalone -d deine-domain.com

# Zertifikate in das Projektverzeichnis kopieren
sudo cp /etc/letsencrypt/live/deine-domain.com/fullchain.pem docker/ssl/
sudo cp /etc/letsencrypt/live/deine-domain.com/privkey.pem docker/ssl/

# Nginx-Konfiguration anpassen
# In docker/nginx.conf die Domain und SSL-Pfade eintragen

# Neustart
docker compose --profile production up -d
```

### Dienste im Ueberblick

| Dienst | Container | Port | Beschreibung |
|---|---|---|---|
| `trevlix` | `trevlix` | 5000 (nur lokal) | Trading-Bot + Dashboard |
| `mysql` | `trevlix_mysql` | 3306 (nur lokal) | MySQL 8.0 Datenbank |
| `nginx` | `trevlix_nginx` | 80, 443 | Reverse Proxy (nur mit `--profile production`) |

---

## 7. Installer (automatisiertes Setup)

Fuer Ubuntu/Debian-Server steht ein vollautomatischer Installer bereit:

```bash
sudo bash install.sh
```

Der Installer richtet folgende Komponenten ein:

- Python 3.11+ mit virtualenv
- MariaDB/MySQL mit Datenbank und Benutzer
- Nginx als Reverse Proxy
- Let's Encrypt SSL-Zertifikate
- Fail2ban fuer Brute-Force-Schutz
- UFW-Firewall (nur Ports 22, 80, 443 offen)
- Systemd-Service fuer automatischen Neustart

**Optionen:**

```bash
sudo bash install.sh --help          # Hilfe anzeigen
sudo bash install.sh --no-tf         # Ohne TensorFlow (kein LSTM)
sudo bash install.sh --no-shap       # Ohne SHAP
sudo bash install.sh --dir /pfad     # Eigenes Installationsverzeichnis
sudo bash install.sh -y              # Optionale Pakete automatisch ablehnen
```

Unterstuetzte Systeme: Ubuntu 18.04–24.04, Debian 10–12.

---

## 8. Paper Trading

Trevlix unterstuetzt einen Paper-Trading-Modus, in dem alle Trades simuliert werden, ohne echtes Kapital einzusetzen. **Es wird dringend empfohlen, neue Konfigurationen zuerst im Paper-Modus zu testen.**

```bash
# In der .env-Datei setzen:
PAPER_TRADING=true
```

Im Paper-Modus:

- Werden keine echten Orders an die Exchange gesendet
- Wird ein virtuelles Startguthaben verwendet (Standard: 10.000 USD)
- Werden alle Trades vollstaendig protokolliert und im Dashboard angezeigt
- Koennen Strategien und Parameter risikofrei getestet werden

Um auf Live-Trading umzuschalten:

```bash
PAPER_TRADING=false
```

> **Warnung:** Beim Wechsel zu Live-Trading sicherstellen, dass gueltige API-Schluessel mit Handelsberechtigungen konfiguriert sind.

---

## 9. Unterstuetzte Exchanges

Trevlix unterstuetzt die folgenden Kryptowaehrungs-Exchanges ueber die CCXT-Bibliothek:

| Exchange | Wert fuer `EXCHANGE` | Webseite |
|---|---|---|
| Crypto.com | `cryptocom` | https://crypto.com/exchange |
| Binance | `binance` | https://www.binance.com |
| Bybit | `bybit` | https://www.bybit.com |
| OKX | `okx` | https://www.okx.com |
| KuCoin | `kucoin` | https://www.kucoin.com |
| Kraken | `kraken` | https://www.kraken.com |
| Huobi (HTX) | `huobi` | https://www.htx.com |
| Coinbase | `coinbase` | https://www.coinbase.com |

**Konfiguration:**

```bash
# Exchange in .env setzen
EXCHANGE=binance
API_KEY=dein-api-key
API_SECRET=dein-api-secret
```

> **Hinweis:** API-Schluessel werden verschluesselt in der Datenbank gespeichert (Fernet-Verschluesselung ueber `services/encryption.py`). Niemals API-Schluessel im Klartext in Logs oder Konfigurationsdateien speichern.
