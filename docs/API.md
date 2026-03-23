# TREVLIX REST API Dokumentation

> **Version:** 1.5.1
> **Base-URL:** `http://localhost:5000/api/v1`
> Alle Endpunkte erfordern einen `Authorization: Bearer <JWT>` Header, sofern nicht anders angegeben.

---

## Inhaltsverzeichnis

1. [Authentifizierung](#1-authentifizierung)
2. [Status & System](#2-status--system)
3. [Trading](#3-trading)
4. [KI & Analyse](#4-ki--analyse)
5. [Trade DNA (NEU in v1.2.0)](#5-trade-dna-neu-in-v120)
6. [Smart Exits (NEU in v1.2.0)](#6-smart-exits-neu-in-v120)
7. [Marktdaten](#7-marktdaten)
8. [Konfiguration](#8-konfiguration)
9. [WebSocket Events](#9-websocket-events)
10. [Rate Limits](#10-rate-limits)
11. [Fehlercodes](#11-fehlercodes)

---

## 1. Authentifizierung

TREVLIX nutzt JWT (JSON Web Tokens) zur Authentifizierung. Nach dem Login erhalten Sie einen Token, der bei jedem API-Request im `Authorization`-Header mitgesendet wird.

### POST /api/v1/login

Benutzer-Authentifizierung und Token-Ausgabe.

| Eigenschaft | Wert |
|---|---|
| **Methode** | `POST` |
| **Pfad** | `/api/v1/login` |
| **Auth erforderlich** | Nein |

**Request Body:**

```json
{
  "username": "admin",
  "password": "your_password",
  "totp": "123456"          // optional, nur wenn 2FA aktiviert
}
```

**Response (200):**

```json
{
  "token": "eyJhbGci...",
  "role": "admin",
  "expires_in": 1800
}
```

### POST /api/v1/token

Token erneuern (Refresh).

| Eigenschaft | Wert |
|---|---|
| **Methode** | `POST` |
| **Pfad** | `/api/v1/token` |
| **Auth erforderlich** | Ja |

**Response (200):**

```json
{
  "token": "eyJhbGci...",
  "label": "dashboard"
}
```

### Token-Verwendung

Den JWT-Token bei jedem Request als Header mitsenden:

```
Authorization: Bearer eyJhbGci...
```

---

## 2. Status & System

| Methode | Pfad | Auth | Beschreibung |
|---|---|---|---|
| `GET` | `/api/v1/status` | Ja | Bot-Status, Version, Uptime |
| `POST` | `/api/v1/start` | Ja | Bot starten |
| `POST` | `/api/v1/stop` | Ja | Bot stoppen |
| `GET` | `/api/v1/health` | Ja | Health Check (DB, Exchange) |
| `GET` | `/api/v1/version` | Ja | Aktuelle Version |

### GET /api/v1/status

**Response (200):**

```json
{
  "status": "running",
  "version": "1.2.0",
  "uptime": 3600,
  "exchange": "binance",
  "paper_trading": true
}
```

### GET /api/v1/health

**Response (200):**

```json
{
  "db": "ok",
  "exchange": "ok",
  "ai_engine": "ok"
}
```

### GET /api/v1/version

**Response (200):**

```json
{
  "version": "1.2.0"
}
```

---

## 3. Trading

| Methode | Pfad | Auth | Beschreibung |
|---|---|---|---|
| `GET` | `/api/v1/portfolio` | Ja | Aktuelles Portfolio mit Bilanz |
| `GET` | `/api/v1/positions` | Ja | Offene Positionen |
| `GET` | `/api/v1/trades` | Ja | Trade-Historie (paginiert) |
| `POST` | `/api/v1/order` | Ja | Manuellen Trade platzieren |
| `DELETE` | `/api/v1/order/:id` | Ja | Order stornieren |
| `POST` | `/api/v1/close/:symbol` | Ja | Position schliessen |
| `POST` | `/api/v1/close-all` | Ja | Alle Positionen schliessen |

### POST /api/v1/order

Manuellen Trade platzieren.

| Eigenschaft | Wert |
|---|---|
| **Methode** | `POST` |
| **Pfad** | `/api/v1/order` |
| **Auth erforderlich** | Ja |

**Request Body:**

```json
{
  "symbol": "BTC/USDT",
  "side": "buy",
  "amount": 0.001,
  "type": "limit",
  "price": 92000
}
```

| Feld | Typ | Pflicht | Beschreibung |
|---|---|---|---|
| `symbol` | string | Ja | Handelspaar (z.B. `BTC/USDT`) |
| `side` | string | Ja | `buy` oder `sell` |
| `amount` | number | Ja | Menge |
| `type` | string | Ja | `limit` oder `market` |
| `price` | number | Nur bei `limit` | Limit-Preis |

**Response (200):**

```json
{
  "order_id": "abc123",
  "symbol": "BTC/USDT",
  "side": "buy",
  "amount": 0.001,
  "status": "placed"
}
```

### DELETE /api/v1/order/:id

Order anhand der ID stornieren.

| Eigenschaft | Wert |
|---|---|
| **Methode** | `DELETE` |
| **Pfad** | `/api/v1/order/:id` |
| **Auth erforderlich** | Ja |

### POST /api/v1/close/:symbol

Einzelne Position nach Symbol schliessen.

| Eigenschaft | Wert |
|---|---|
| **Methode** | `POST` |
| **Pfad** | `/api/v1/close/:symbol` |
| **Auth erforderlich** | Ja |

### POST /api/v1/close-all

Alle offenen Positionen sofort schliessen.

| Eigenschaft | Wert |
|---|---|
| **Methode** | `POST` |
| **Pfad** | `/api/v1/close-all` |
| **Auth erforderlich** | Ja |

---

## 4. KI & Analyse

| Methode | Pfad | Auth | Beschreibung |
|---|---|---|---|
| `GET` | `/api/v1/ai/status` | Ja | KI-Modell Status & Accuracy |
| `POST` | `/api/v1/ai/retrain` | Ja | KI-Modell neu trainieren |
| `GET` | `/api/v1/ai/features` | Ja | Feature Importance |
| `GET` | `/api/v1/signals` | Ja | Aktuelle Trading-Signale |
| `GET` | `/api/v1/backtest` | Ja | Backtest starten |
| `GET` | `/api/v1/indicators/:sym` | Ja | Technische Indikatoren fuer ein Symbol |

### GET /api/v1/ai/status

**Response (200):**

```json
{
  "model_loaded": true,
  "accuracy": 0.73,
  "last_trained": "2026-03-15T14:30:00Z"
}
```

### POST /api/v1/ai/retrain

Startet ein erneutes Training des KI-Modells.

| Eigenschaft | Wert |
|---|---|
| **Methode** | `POST` |
| **Pfad** | `/api/v1/ai/retrain` |
| **Auth erforderlich** | Ja |

### GET /api/v1/signals

**Response (200):**

```json
{
  "signals": [
    {
      "symbol": "BTC/USDT",
      "signal": "buy",
      "confidence": 0.82,
      "strategies_agree": 7
    }
  ]
}
```

### GET /api/v1/indicators/:sym

Technische Indikatoren fuer das angegebene Symbol abrufen.

| Eigenschaft | Wert |
|---|---|
| **Methode** | `GET` |
| **Pfad** | `/api/v1/indicators/:sym` |
| **Auth erforderlich** | Ja |

**Beispiel:** `GET /api/v1/indicators/BTC_USDT`

---

## 5. Trade DNA (NEU in v1.2.0)

Die Trade DNA Engine erkennt wiederkehrende Muster in Ihren Trades und bewertet deren Erfolgsrate.

### GET /api/v1/trade-dna

Engine-Status und Gesamtstatistiken abrufen.

| Eigenschaft | Wert |
|---|---|
| **Methode** | `GET` |
| **Pfad** | `/api/v1/trade-dna` |
| **Auth erforderlich** | Ja |

**Response (200):**

```json
{
  "enabled": true,
  "total_patterns": 42,
  "total_trades": 318,
  "avg_win_rate": 0.61,
  "top_patterns": [
    { "fingerprint": "RSI_OB+MACD_CROSS", "win_rate": 0.78, "wins": 18, "total": 23 }
  ],
  "worst_patterns": [
    { "fingerprint": "VOL_SPIKE+FOMO", "win_rate": 0.22, "wins": 2, "total": 9 }
  ]
}
```

| Feld | Typ | Beschreibung |
|---|---|---|
| `enabled` | boolean | Ob die Trade DNA Engine aktiv ist |
| `total_patterns` | integer | Anzahl erkannter Muster |
| `total_trades` | integer | Gesamtzahl analysierter Trades |
| `avg_win_rate` | float | Durchschnittliche Gewinnrate (0.0 - 1.0) |
| `top_patterns` | array | Erfolgreichste Muster |
| `worst_patterns` | array | Schlechteste Muster |

### GET /api/v1/trade-dna/patterns

Top- und Worst-DNA-Muster mit detaillierten Win-Rates abrufen.

| Eigenschaft | Wert |
|---|---|
| **Methode** | `GET` |
| **Pfad** | `/api/v1/trade-dna/patterns` |
| **Auth erforderlich** | Ja |

**Response (200):**

```json
{
  "top_patterns": [
    { "fingerprint": "RSI_OB+MACD_CROSS", "win_rate": 0.78, "wins": 18, "total": 23 }
  ],
  "worst_patterns": [
    { "fingerprint": "VOL_SPIKE+FOMO", "win_rate": 0.22, "wins": 2, "total": 9 }
  ]
}
```

| Feld (Pattern-Objekt) | Typ | Beschreibung |
|---|---|---|
| `fingerprint` | string | Eindeutiger Muster-Fingerprint |
| `win_rate` | float | Gewinnrate des Musters (0.0 - 1.0) |
| `wins` | integer | Anzahl gewonnener Trades |
| `total` | integer | Gesamtzahl Trades mit diesem Muster |

---

## 6. Smart Exits (NEU in v1.2.0)

Smart Exits passen Stop-Loss und Take-Profit dynamisch an das aktuelle Marktregime an.

### GET /api/v1/smart-exits

Engine-Konfiguration und letzte Anpassungen abrufen.

| Eigenschaft | Wert |
|---|---|
| **Methode** | `GET` |
| **Pfad** | `/api/v1/smart-exits` |
| **Auth erforderlich** | Ja |

**Response (200):**

```json
{
  "enabled": true,
  "regime_multipliers": {
    "sl": { "trending": 1.2, "ranging": 0.8, "volatile": 1.5 },
    "tp": { "trending": 1.5, "ranging": 0.9, "volatile": 1.3 }
  },
  "config": {
    "atr_sl_mult": 2.0,
    "reward_ratio": 2.5
  },
  "last_adjustments": []
}
```

| Feld | Typ | Beschreibung |
|---|---|---|
| `enabled` | boolean | Ob Smart Exits aktiv sind |
| `regime_multipliers.sl` | object | Stop-Loss-Multiplikatoren pro Marktregime |
| `regime_multipliers.tp` | object | Take-Profit-Multiplikatoren pro Marktregime |
| `config.atr_sl_mult` | float | ATR-basierter Stop-Loss-Multiplikator |
| `config.reward_ratio` | float | Reward-Ratio (TP/SL-Verhaeltnis) |
| `last_adjustments` | array | Liste der letzten Anpassungen |

**Marktregime-Typen:**

| Regime | Beschreibung |
|---|---|
| `trending` | Starker Trend (aufwaerts oder abwaerts) |
| `ranging` | Seitwaerts-Markt mit geringer Volatilitaet |
| `volatile` | Hohe Volatilitaet ohne klaren Trend |

---

## 7. Marktdaten

| Methode | Pfad | Auth | Beschreibung |
|---|---|---|---|
| `GET` | `/api/v1/market/fear-greed` | Ja | Fear & Greed Index |
| `GET` | `/api/v1/market/dominance` | Ja | BTC/USDT Dominanz |
| `GET` | `/api/v1/market/news` | Ja | News-Sentiment (CryptoPanic) |
| `GET` | `/api/v1/market/onchain` | Ja | On-Chain Daten (CoinGecko) |
| `GET` | `/api/v1/market/heatmap` | Ja | Markt-Heatmap |
| `GET` | `/api/v1/arbitrage` | Ja | Arbitrage-Chancen (Cross-Exchange) |

### GET /api/v1/market/fear-greed

**Response (200):**

```json
{
  "value": 72,
  "label": "Greed",
  "timestamp": "2026-03-16T12:00:00Z"
}
```

### GET /api/v1/market/dominance

**Response (200):**

```json
{
  "btc_dominance": 54.3,
  "usdt_dominance": 6.1
}
```

### GET /api/v1/market/heatmap

**Response (200):**

```json
{
  "heatmap": [
    { "symbol": "BTC/USDT", "change_24h": 2.4 },
    { "symbol": "ETH/USDT", "change_24h": -1.2 }
  ]
}
```

---

## 8. Konfiguration

### Allgemeine Einstellungen

| Methode | Pfad | Auth | Beschreibung |
|---|---|---|---|
| `GET` | `/api/v1/settings` | Ja | Aktuelle Bot-Einstellungen |
| `PUT` | `/api/v1/settings` | Ja | Einstellungen aktualisieren |
| `GET` | `/api/v1/exchanges` | Ja | Konfigurierte Exchanges |
| `POST` | `/api/v1/exchanges` | Ja | Exchange hinzufuegen |

### PUT /api/v1/settings

**Request Body (Beispiel):**

```json
{
  "paper_trading": true,
  "trade_amount": 100,
  "stop_loss": 3.0
}
```

### Admin-Endpunkte

> **Hinweis:** Admin-Endpunkte erfordern die Rolle `admin`. Normale User haben keinen Zugriff.

| Methode | Pfad | Auth (Rolle) | Beschreibung |
|---|---|---|---|
| `GET` | `/api/v1/admin/users` | Admin | Alle User auflisten |
| `POST` | `/api/v1/admin/users` | Admin | Neuen User anlegen |
| `DELETE` | `/api/v1/admin/users/:id` | Admin | User loeschen |
| `GET` | `/api/v1/admin/audit` | Admin | Audit-Log |
| `POST` | `/api/v1/admin/backup` | Admin | Datenbank-Backup erstellen |
| `POST` | `/api/v1/admin/update` | Admin | GitHub Auto-Update ausloesen |

---

## 9. WebSocket Events

TREVLIX nutzt Socket.IO fuer Echtzeit-Updates im Dashboard.

**Verbindung herstellen:**

```javascript
const socket = io('http://localhost:5000', {
  auth: { token: 'eyJhbGci...' }
});
```

### Events (Server -> Client)

| Event | Beschreibung |
|---|---|
| `status_update` | Bot-Status (Running / Stopped / Paused) |
| `portfolio_update` | Portfolio-Daten mit Balance |
| `trade_update` | Neuer Trade ausgefuehrt |
| `signal_update` | Neues Trading-Signal |
| `ai_update` | KI-Modell Status-Update |
| `error` | Fehlermeldung |

### Events (Client -> Server)

| Event | Beschreibung |
|---|---|
| `connect` | Verbindung herstellen |

### Beispiel

```javascript
socket.on('portfolio_update', (data) => {
  console.log('Balance:', data.total_balance);
  console.log('P&L:', data.pnl_percent + '%');
});

socket.on('trade_update', (trade) => {
  console.log('Neuer Trade:', trade.symbol, trade.side, trade.amount);
});
```

---

## 10. Rate Limits

| Endpunkt-Gruppe | Limit | Fenster |
|---|---|---|
| Login / Register | 5 Requests | pro Minute |
| Trading (Order/Close) | 30 Requests | pro Minute |
| Allgemeine API | 60 Requests | pro Minute |
| Admin-Endpunkte | 30 Requests | pro Minute |

Bei Ueberschreitung wird ein `429 Too Many Requests` Status zurueckgegeben. Warten Sie das Zeitfenster ab oder erhoehen Sie das Limit in der `.env`-Datei.

**Response bei Rate Limit (429):**

```json
{
  "error": "Too Many Requests",
  "retry_after": 60
}
```

---

## 11. Fehlercodes

| Code | Bedeutung | Loesung |
|---|---|---|
| `401` | Nicht authentifiziert | JWT Token erneuern oder neu einloggen |
| `403` | Keine Berechtigung | Admin-Rolle erforderlich |
| `404` | Nicht gefunden | Endpunkt oder Ressource pruefen |
| `422` | Validierungsfehler | Request-Body pruefen |
| `429` | Rate Limit ueberschritten | Weniger Requests senden, Zeitfenster abwarten |
| `500` | Interner Server-Fehler | Logs pruefen, ggf. GitHub Issue erstellen |
| `503` | Exchange nicht erreichbar | Exchange-API Status pruefen |

**Standard-Fehler-Response:**

```json
{
  "error": "Beschreibung des Fehlers",
  "code": 401
}
```
