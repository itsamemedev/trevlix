# TREVLIX Services -- Referenzdokumentation

Dieses Dokument beschreibt alle Service-Module im Verzeichnis `services/`.
Jeder Service ist als eigenstaendiges Modul konzipiert und kann unabhaengig importiert werden.

---

## Inhaltsverzeichnis

1. [config.py -- Konfiguration](#configpy--konfiguration)
2. [db_pool.py -- Datenbank-Verbindungspool](#db_poolpy--datenbank-verbindungspool)
3. [encryption.py -- Verschluesselung](#encryptionpy--verschluesselung)
4. [exchange_manager.py -- Exchange-Verwaltung](#exchange_managerpy--exchange-verwaltung)
5. [indicator_cache.py -- Indikator-Cache](#indicator_cachepy--indikator-cache)
6. [knowledge.py -- KI-Wissensbasis](#knowledgepy--ki-wissensbasis)
7. [market_data.py -- Marktdaten](#market_datapy--marktdaten)
8. [notifications.py -- Benachrichtigungen](#notificationspy--benachrichtigungen)
9. [risk.py -- Risikomanagement](#riskpy--risikomanagement)
10. [strategies.py -- Trading-Strategien](#strategiespy--trading-strategien)
11. [smart_exits.py -- Intelligente Exits](#smart_exitspy--intelligente-exits)
12. [trade_dna.py -- Trade-DNA-Fingerprinting](#trade_dnapy--trade-dna-fingerprinting)
13. [cryptopanic.py -- News-Sentiment](#cryptopanicpy--news-sentiment)
14. [utils.py -- Hilfsfunktionen](#utilspy--hilfsfunktionen)

---

## config.py -- Konfiguration

### Zweck

Pydantic-basierte, typsichere Konfigurationsklasse fuer TREVLIX. Ersetzt das globale
CONFIG-Dictionary durch validierte Werte mit automatischer Umgebungsvariablen-Uebernahme.

### Klassen / Funktionen

| Name | Signatur | Beschreibung |
|------|----------|--------------|
| `TrevlixConfig` | `class TrevlixConfig(BaseSettings)` | Zentrale Konfigurationsklasse mit Feldern fuer Exchange, API-Keys, Risikoparameter, DB-Verbindung u.v.m. |
| `TrevlixConfig.from_env` | `@classmethod from_env(cls) -> TrevlixConfig` | Erstellt eine Instanz aus aktuellen Umgebungsvariablen. |
| `TrevlixConfig.to_dict` | `to_dict(self) -> dict[str, Any]` | Serialisiert die Konfiguration als Dictionary. |
| `TrevlixConfig.validate_security` | `validate_security(self) -> list[str]` | Prueft sicherheitsrelevante Einstellungen, gibt Warnungen zurueck. |
| `load_config` | `load_config() -> TrevlixConfig` | Laedt und validiert die Konfiguration aus Umgebungsvariablen. |

### Verwendung

```python
from services.config import TrevlixConfig, load_config

cfg = load_config()
print(cfg.exchange)      # z.B. "binance"
print(cfg.fee_rate)      # z.B. 0.001
print(cfg.paper_trading) # True/False
```

### Konfiguration

Alle Felder werden ueber gleichnamige Umgebungsvariablen gesetzt (Grossbuchstaben).
Wichtige Variablen: `EXCHANGE`, `API_KEY`, `API_SECRET`, `FEE_RATE`, `RISK_PER_TRADE`,
`STOP_LOSS_PCT`, `TAKE_PROFIT_PCT`, `MAX_OPEN_TRADES`, `PAPER_TRADING`,
`MYSQL_HOST`, `MYSQL_USER`, `MYSQL_PASSWORD`, `MYSQL_DB`.

---

## db_pool.py -- Datenbank-Verbindungspool

### Zweck

Thread-sicheres Connection-Pooling fuer MySQL. Ersetzt das Muster "neue Verbindung pro
Aufruf" durch einen wiederverwendbaren Pool mit konfigurierbarer Groesse. Verwendet
einen `_PooledConnection`-Proxy, der `close()` an den Pool weiterleitet, sodass
bestehender Code unveraendert bleibt.

### Klassen / Funktionen

| Name | Signatur | Beschreibung |
|------|----------|--------------|
| `ConnectionPool` | `class ConnectionPool(host, port, user, password, db, ...)` | Hauptklasse des Connection-Pools. |
| `ConnectionPool.acquire` | `acquire(retries=2) -> _PooledConnection` | Holt eine Verbindung aus dem Pool (mit Retry-Logik). |
| `ConnectionPool.release` | `release(conn) -> None` | Gibt eine Verbindung an den Pool zurueck. |
| `ConnectionPool.connection` | `connection() -> ContextManager` | Context-Manager fuer automatisches Acquire/Release. |
| `ConnectionPool.close_all` | `close_all() -> None` | Schliesst alle Verbindungen und leert den Pool. |
| `ConnectionPool.pool_stats` | `pool_stats() -> dict[str, int \| float]` | Gibt Pool-Statistiken zurueck (Groesse, verfuegbar, etc.). |

### Verwendung

```python
from services.db_pool import ConnectionPool

pool = ConnectionPool(host="localhost", port=3306, user="root", password="pw", db="trevlix")

# Variante 1: manuell
conn = pool.acquire()
try:
    with conn.cursor() as c:
        c.execute("SELECT 1")
finally:
    pool.release(conn)

# Variante 2: Context-Manager (empfohlen)
with pool.connection() as conn:
    with conn.cursor() as c:
        c.execute("SELECT * FROM trades")
```

### Konfiguration

Umgebungsvariablen: `MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_USER`, `MYSQL_PASSWORD`, `MYSQL_DB`.

---

## encryption.py -- Verschluesselung

### Zweck

Fernet-basierte Verschluesselung fuer sensible Daten, insbesondere API-Schluessel.
Wird automatisch fuer alle in der Datenbank gespeicherten API-Keys verwendet. Ohne
gesetzten `ENCRYPTION_KEY` wird ein temporaerer Schluessel generiert (nur fuer
Entwicklung, nicht produktionssicher).

### Klassen / Funktionen

| Name | Signatur | Beschreibung |
|------|----------|--------------|
| `encrypt_value` | `encrypt_value(plaintext: str) -> str` | Verschluesselt einen String mit Fernet. Gibt den Ciphertext als String zurueck. |
| `decrypt_value` | `decrypt_value(ciphertext: str) -> str` | Entschluesselt einen Fernet-Ciphertext zurueck zum Klartext. |
| `is_encrypted` | `is_encrypted(value: str) -> bool` | Prueft ob ein Wert bereits verschluesselt ist. |

### Verwendung

```python
from services.encryption import encrypt_value, decrypt_value, is_encrypted

encrypted = encrypt_value("mein-api-key")
original  = decrypt_value(encrypted)
assert is_encrypted(encrypted) is True
```

### Konfiguration

| Variable | Beschreibung |
|----------|--------------|
| `ENCRYPTION_KEY` | 32-Byte URL-safe Base64-kodierter Fernet-Key. Erzeugung: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |

---

## exchange_manager.py -- Exchange-Verwaltung

### Zweck

Verwaltet Multi-Exchange-Konfigurationen fuer Admin und User. Ermoeglicht das
gleichzeitige Betreiben mehrerer Exchanges ueber CCXT. Cached Exchange-Instanzen
pro User/Exchange-Kombination mit Thread-sicherem Zugriff.

### Klassen / Funktionen

| Name | Signatur | Beschreibung |
|------|----------|--------------|
| `ExchangeManager` | `class ExchangeManager(db_manager, config: dict)` | Hauptklasse fuer Multi-Exchange-Betrieb. |
| `.get_user_exchange` | `get_user_exchange(user_id: int, exchange_name: str) -> Any \| None` | Gibt eine CCXT-Instanz fuer einen bestimmten User und Exchange zurueck. |
| `.get_active_exchanges` | `get_active_exchanges(user_id: int) -> list[tuple[str, Any]]` | Gibt alle aktiven Exchanges eines Users als Liste von (Name, Instanz)-Tupeln zurueck. |
| `.get_admin_exchange` | `get_admin_exchange() -> Any \| None` | Gibt die Exchange-Instanz des Admins zurueck. |
| `.invalidate_cache` | `invalidate_cache(user_id: int, exchange_name: str \| None = None) -> None` | Invalidiert gecachte Instanzen (z.B. nach Key-Aenderung). |
| `.get_all_balances` | `get_all_balances(user_id: int) -> dict[str, dict]` | Holt Bilanzen aller aktiven Exchanges eines Users. |

### Verwendung

```python
from services.exchange_manager import ExchangeManager

mgr = ExchangeManager(db, config)
exchanges = mgr.get_active_exchanges(user_id=1)
for name, ex_inst in exchanges:
    balance = ex_inst.fetch_balance()
```

### Konfiguration

Abhaengig von `EXCHANGE`, `API_KEY`, `API_SECRET` in der jeweiligen User-/Admin-Konfiguration.
Exchange-Mapping ueber `services.utils.EXCHANGE_MAP`.

---

## indicator_cache.py -- Indikator-Cache

### Zweck

Verhindert redundante Neuberechnung technischer Indikatoren. Cacht berechnete
Indikatoren pro Symbol und letztem Timestamp. Verwendet LRU-Eviction via
`collections.OrderedDict` mit O(1)-Operationen. Standard-TTL: 55 Sekunden,
maximale Cache-Groesse: 200 Eintraege.

### Klassen / Funktionen

| Name | Signatur | Beschreibung |
|------|----------|--------------|
| `get_cached` | `get_cached(symbol: str, last_timestamp: Any) -> pd.DataFrame \| None` | Gibt gecachte Indikatoren zurueck bei Cache-Hit, sonst `None`. |
| `set_cached` | `set_cached(symbol: str, last_timestamp: Any, df: pd.DataFrame) -> None` | Speichert berechnete Indikatoren im Cache. |
| `invalidate` | `invalidate(symbol: str \| None = None) -> None` | Invalidiert Cache fuer ein Symbol oder den gesamten Cache. |
| `cache_stats` | `cache_stats() -> dict[str, Any]` | Gibt Cache-Statistiken zurueck (Groesse, Hits, Misses). |

### Verwendung

```python
from services.indicator_cache import get_cached, set_cached

cached_df = get_cached("BTC/USDT", last_timestamp="2024-01-01T00:00:00")
if cached_df is None:
    df = compute_indicators(ohlcv_df)
    set_cached("BTC/USDT", last_timestamp="2024-01-01T00:00:00", df=df)
```

### Konfiguration

Modul-Konstanten: `CACHE_TTL_SECONDS = 55`, `MAX_CACHE_SIZE = 200`.

---

## knowledge.py -- KI-Wissensbasis

### Zweck

Zentrales KI-Gemeinschaftswissen fuer alle User. Speichert und teilt Erkenntnisse
aus Trading, KI-Modellen und Marktdaten in der Datenbank. Kann optional ueber eine
lokale LLM-Instanz oder externe APIs angereichert werden.

Unterstuetzte Kategorien: `market_insight`, `strategy_perf`, `symbol_info`,
`risk_pattern`, `model_config`.

### Klassen / Funktionen

| Name | Signatur | Beschreibung |
|------|----------|--------------|
| `KnowledgeBase` | `class KnowledgeBase(db)` | Hauptklasse fuer die KI-Wissensbasis. |
| `.store` | `store(category: str, key: str, data: dict, ...) -> None` | Speichert eine Erkenntnis in der Datenbank. |
| `.get` | `get(category: str, key: str) -> dict \| None` | Holt eine einzelne Erkenntnis anhand Kategorie und Schluessel. |
| `.get_category` | `get_category(category: str, limit: int = 50) -> list[dict]` | Gibt alle Eintraege einer Kategorie zurueck. |
| `.learn_from_trade` | `learn_from_trade(trade: dict) -> None` | Extrahiert Erkenntnisse aus einem abgeschlossenen Trade. |
| `.query_llm` | `query_llm(prompt: str, context: str = "") -> str \| None` | Sendet eine Anfrage an eine optionale LLM-Instanz. |
| `.get_market_summary` | `get_market_summary() -> dict` | Gibt eine Zusammenfassung aller Markt-Erkenntnisse zurueck. |

### Verwendung

```python
from services.knowledge import KnowledgeBase

kb = KnowledgeBase(db)
kb.store("market_insight", "btc_trend", {"direction": "bull", "confidence": 0.85})
insight = kb.get("market_insight", "btc_trend")
```

### Konfiguration

| Variable | Beschreibung |
|----------|--------------|
| `LLM_ENDPOINT` | URL einer OpenAI-kompatiblen LLM-API (optional). |

---

## market_data.py -- Marktdaten

### Zweck

Sammelt externe Marktdaten: Fear & Greed Index, Marktregime-Erkennung,
BTC-Dominanz-Filter, Sentiment- und On-Chain-Daten. Alle Fetcher nutzen
einen internen TTL-Cache, um API-Rate-Limits einzuhalten.

### Klassen / Funktionen

| Name | Signatur | Beschreibung |
|------|----------|--------------|
| `FearGreedIndex` | `class FearGreedIndex(config)` | Holt den Fear & Greed Index von alternative.me. |
| `.update` | `update() -> None` | Aktualisiert den Index. |
| `.is_ok_to_buy` | `is_ok_to_buy() -> bool` | Prueft ob Kaufsignal basierend auf F&G erlaubt ist. |
| `.buy_boost` | `buy_boost() -> float` | Gibt einen Kauf-Boost-Faktor basierend auf dem Index zurueck. |
| `MarketRegime` | `class MarketRegime(config)` | Erkennt das aktuelle Marktregime (bull/bear/range/crash). |
| `.update` | `update(ex) -> None` | Aktualisiert das Regime anhand von Exchange-Daten. |
| `DominanceFilter` | `class DominanceFilter(config)` | Filtert Trades basierend auf BTC-Dominanz und Altcoin-Season. |
| `.update` | `update() -> None` | Aktualisiert die Dominanz-Daten. |
| `.is_ok_to_buy` | `is_ok_to_buy(symbol: str) -> tuple[bool, str]` | Prueft ob ein Kauf des Symbols unter Dominanz-Gesichtspunkten sinnvoll ist. |
| `SentimentFetcher` | `class SentimentFetcher(config)` | Holt Sentiment-Scores aus externen Quellen. |
| `.get_score` | `get_score(symbol: str) -> float` | Gibt einen Sentiment-Score fuer ein Symbol zurueck. |
| `.get_trending` | `get_trending() -> list[str]` | Gibt aktuell trendende Symbole zurueck. |
| `OnChainFetcher` | `class OnChainFetcher(config)` | Holt On-Chain-Metriken (z.B. Whale-Aktivitaet). |
| `.get_score` | `get_score(symbol: str) -> tuple[float, str]` | Gibt On-Chain-Score und Beschreibung zurueck. |

### Verwendung

```python
from services.market_data import FearGreedIndex, MarketRegime, DominanceFilter

fg = FearGreedIndex(config)
fg.update()
if fg.is_ok_to_buy():
    boost = fg.buy_boost()
```

### Konfiguration

CONFIG-Keys: `fear_greed_enabled`, `dominance_filter`, `sentiment_enabled`, `onchain_enabled`.

---

## notifications.py -- Benachrichtigungen

### Zweck

Sendet Benachrichtigungen ueber Discord-Webhooks und Telegram-Bot-API.
Unterstuetzt verschiedene Nachrichtentypen: Kauf/Verkauf, Circuit-Breaker,
Preisalarme, Anomalien, Tagesberichte und Fehler.

### Klassen / Funktionen

| Name | Signatur | Beschreibung |
|------|----------|--------------|
| `DiscordNotifier` | `class DiscordNotifier(config: dict)` | Discord-Webhook-basierte Benachrichtigungen. |
| `.send` | `send(title, description, color, fields, ...)` | Sendet ein Embed an den Discord-Webhook. |
| `.trade_buy` | `trade_buy(symbol, price, invest, ai_score, win_prob)` | Meldet einen Kauf-Trade. |
| `.trade_sell` | `trade_sell(symbol, price, pnl, ...)` | Meldet einen Verkauf-Trade. |
| `.circuit_breaker` | `circuit_breaker(losses, pause_min)` | Meldet Aktivierung des Circuit Breakers. |
| `.daily_report` | `daily_report(report: dict)` | Sendet den taeglichen Bericht. |
| `.error` | `error(msg: str)` | Sendet eine Fehlermeldung. |
| `.smart_exit` | `smart_exit(symbol, sl, tp, regime, atr_pct)` | Meldet Smart-Exit-Anpassungen. |
| `.dna_boost` | `dna_boost(symbol, fingerprint, boost, ...)` | Meldet DNA-basierte Konfidenz-Anpassungen. |
| `TelegramNotifier` | `class TelegramNotifier(config: dict)` | Telegram-Bot-basierte Benachrichtigungen. |
| `.send` | `send(text: str, parse_mode: str = "HTML")` | Sendet eine Nachricht an den Telegram-Chat. |
| `.trade_buy` | `trade_buy(symbol, price, invest, ...)` | Meldet einen Kauf-Trade. |
| `.trade_sell` | `trade_sell(symbol, price, pnl, ...)` | Meldet einen Verkauf-Trade. |

### Verwendung

```python
from services.notifications import DiscordNotifier, TelegramNotifier

discord = DiscordNotifier(config=CONFIG)
discord.trade_buy("BTC/USDT", 42000.0, 500.0, ai_score=0.85, win_prob=0.72)

telegram = TelegramNotifier(config=CONFIG)
telegram.send("Bot gestartet")
```

### Konfiguration

| Variable | Beschreibung |
|----------|--------------|
| `DISCORD_WEBHOOK` | Vollstaendige Discord-Webhook-URL. |
| `DISCORD_ON_SIGNALS` | Schaltet Opportunity-Signal-Notifications (Buy/Sell-Kandidaten) ein/aus. |
| `DISCORD_SIGNAL_COOLDOWN_SEC` | Cooldown in Sekunden pro Symbol/Richtung, um Discord-Spam zu vermeiden. |
| `TELEGRAM_TOKEN` | Telegram-Bot-Token. |
| `TELEGRAM_CHAT_ID` | Telegram-Chat-ID fuer Nachrichten. |

CONFIG-Keys: `discord_on_buy`, `discord_on_sell`, `discord_on_circuit`,
`discord_on_error`, `discord_daily_report` (boolesche Feature-Toggles).

---

## risk.py -- Risikomanagement

### Zweck

Zentrales Risikomanagement mit Circuit Breaker, Korrelationsfilter, Liquiditaetspruefung,
Symbol-Cooldown, Funding-Rate-Tracking und erweiterten Risikometriken (CVaR,
Volatilitaetsprognose, Regime-Klassifikation).

### Klassen / Funktionen

| Name | Signatur | Beschreibung |
|------|----------|--------------|
| `RiskManager` | `class RiskManager(config, discord=None)` | Zentraler Risikomanager mit Circuit Breaker und taeglicher PnL-Ueberwachung. |
| `.reset_daily` | `reset_daily(balance: float) -> None` | Setzt taegliche PnL-Werte bei Tageswechsel zurueck. |
| `.daily_loss_exceeded` | `daily_loss_exceeded(balance) -> bool` | Prueft ob das taegliche Verlustlimit ueberschritten wurde. |
| `.circuit_breaker_active` | `circuit_breaker_active() -> bool` | Prueft ob der Circuit Breaker aktiv ist. |
| `.record_result` | `record_result(won: bool)` | Erfasst Gewinn/Verlust fuer Circuit-Breaker-Logik. |
| `.is_correlated` | `is_correlated(symbol, open_syms) -> bool` | Prueft Preiskorrelation zu offenen Positionen. |
| `.sharpe` | `sharpe(returns, rf=0.0) -> float` | Berechnet die Sharpe-Ratio. |
| `LiquidityScorer` | `class LiquidityScorer()` | Bewertet die Liquiditaet eines Symbols anhand des Orderbuchs. |
| `.check` | `check(ex, symbol) -> tuple[bool, float, str]` | Prueft ob ein Symbol ausreichend liquid ist. |
| `SymbolCooldown` | `class SymbolCooldown(config)` | Sperrt Symbole nach einem Verlust-Trade fuer eine definierte Zeit. |
| `.set_cooldown` | `set_cooldown(symbol, minutes=None)` | Setzt einen Cooldown fuer ein Symbol. |
| `.is_blocked` | `is_blocked(symbol: str) -> bool` | Prueft ob ein Symbol aktuell gesperrt ist. |
| `FundingRateTracker` | `class FundingRateTracker(config)` | Trackt Funding-Rates fuer Short-Positionen. |
| `.update` | `update(ex=None)` | Aktualisiert Funding-Rates von der Exchange. |
| `.is_short_too_expensive` | `is_short_too_expensive(symbol) -> bool` | Prueft ob ein Short zu teuer waere. |
| `AdvancedRiskMetrics` | `class AdvancedRiskMetrics(config)` | Erweiterte Risikometriken: CVaR, Volatilitaetsprognose, Regime-Klassifikation. |
| `.compute_cvar` | `compute_cvar(closed_trades, confidence=0.95) -> dict` | Berechnet Conditional Value at Risk. |
| `.volatility_forecast` | `volatility_forecast(horizon=5) -> dict` | Prognostiziert Volatilitaet fuer n Perioden. |
| `.classify_regime` | `classify_regime(prices, volumes=None) -> str` | Klassifiziert das aktuelle Marktregime. |
| `.conformal_predict` | `conformal_predict(...)` | Konforme Vorhersage-Intervalle. |

### Verwendung

```python
from services.risk import RiskManager, LiquidityScorer, SymbolCooldown

risk = RiskManager(config, discord=discord_notifier)
if not risk.circuit_breaker_active() and not risk.daily_loss_exceeded(balance):
    # Trade ausfuehren
    ...
risk.record_result(won=True)
```

### Konfiguration

CONFIG-Keys: `max_daily_loss_pct`, `max_drawdown_pct`, `circuit_breaker_losses`,
`circuit_breaker_pause`, `cooldown_minutes`, `correlation_threshold`.

---

## strategies.py -- Trading-Strategien

### Zweck

Berechnet technische Indikatoren und fuehrt 9 unabhaengige Trading-Strategien aus,
die per Voting-System ein Kauf-/Verkaufssignal erzeugen.

**Strategien:** EMA-Trend, RSI-Stochastic, MACD-Kreuzung, Bollinger,
Volumen-Ausbruch, OBV-Trend, ROC-Momentum, Ichimoku, VWAP.

### Klassen / Funktionen

| Name | Signatur | Beschreibung |
|------|----------|--------------|
| `compute_indicators` | `compute_indicators(df: pd.DataFrame) -> pd.DataFrame \| None` | Berechnet alle technischen Indikatoren auf einem OHLCV-DataFrame. Benoetigt mindestens 80 Kerzen. |
| `STRATEGY_NAMES` | `list[str]` | Liste der 9 Strategienamen. |
| `STRATEGIES` | `list[Callable]` | Liste der Strategie-Funktionen (jede gibt +1/0/-1 zurueck). |

### Verwendung

```python
from services.strategies import compute_indicators, STRATEGIES, STRATEGY_NAMES

df = compute_indicators(ohlcv_df)
if df is not None:
    row = df.iloc[-1].to_dict()
    prev = df.iloc[-2].to_dict()
    votes = [s(row, prev) for s in STRATEGIES]
```

### Konfiguration

CONFIG-Keys: `min_votes` (Mindestanzahl positiver Votes fuer ein Kaufsignal).

---

## smart_exits.py -- Intelligente Exits

### Zweck

Volatilitaetsadaptive Stop-Loss- und Take-Profit-Engine. Ersetzt fixe SL/TP-Prozentsaetze
durch dynamische, ATR-basierte Level, angepasst an Marktregime und Signalstaerke.

**Regime-Anpassungen:**
- Bull: Enge Stops (1.2x ATR), grosses TP (3:1) -- Trend reiten
- Bear: Weite Stops (2.0x ATR), konservatives TP (1.5:1) -- Noise vermeiden
- Range: Mittlere Stops (1.5x ATR), ausgewogenes TP (2:1)
- Crash: Sehr weite Stops (2.5x ATR), minimales TP (1:1)

Erkennt Volatility Squeezes (enge Bollinger-Baender) fuer Ausbruchs-Trades.

### Klassen / Funktionen

| Name | Signatur | Beschreibung |
|------|----------|--------------|
| `SmartExitEngine` | `class SmartExitEngine(config)` | Hauptklasse fuer dynamische SL/TP-Berechnung. |
| `.enabled` | `@property enabled -> bool` | Prueft ob Smart Exits aktiviert sind. |
| `.compute` | `compute(entry_price, scan_data, regime) -> tuple[float, float]` | Berechnet initiale SL/TP-Level bei Trade-Eroeffnung. |
| `.adapt` | `adapt(position, current_price, scan_data, regime) -> tuple[float, float]` | Passt SL/TP einer bestehenden Position an aktuelle Marktlage an. |
| `.classify_regime_from_scan` | `classify_regime_from_scan(scan: dict) -> str` | Klassifiziert das Regime aus Scan-Daten. |

### Verwendung

```python
from services.smart_exits import SmartExitEngine

smart_exits = SmartExitEngine(config)
sl, tp = smart_exits.compute(entry_price=42000.0, scan_data=scan, regime="bull")
new_sl, new_tp = smart_exits.adapt(position, current_price=43500.0, scan_data=scan, regime="bull")
```

### Konfiguration

CONFIG-Keys: `smart_exits_enabled`, `smart_exits_min_atr_pct`, `smart_exits_max_sl_pct`.

---

## trade_dna.py -- Trade-DNA-Fingerprinting

### Zweck

Erzeugt einen einzigartigen "DNA-Fingerprint" fuer jeden Trade basierend auf den
Marktbedingungen zum Zeitpunkt der Eroeffnung. Das System lernt, welche DNA-Muster
historisch profitabel waren und passt die Konfidenz zukuenftiger Trades an.

**DNA-Dimensionen:**
1. Regime (bull/bear/range/crash)
2. Volatilitaet (low/mid/high/extreme)
3. Fear & Greed Bucket (extreme_fear/fear/neutral/greed/extreme_greed)
4. News Sentiment (negative/neutral/positive)
5. Orderbook Imbalance (sell/balanced/buy)
6. Vote-Konsensus (weak/moderate/strong/unanimous)
7. Tageszeit-Bucket (asia/europe/us/off_hours)

### Klassen / Funktionen

| Name | Signatur | Beschreibung |
|------|----------|--------------|
| `TradeDNA` | `class TradeDNA()` | Hauptklasse fuer DNA-basierte Trade-Analyse. |
| `.compute` | `compute(symbol, scan_data, regime_str) -> dict` | Berechnet den DNA-Fingerprint fuer einen Trade. |
| `.confidence_adjustment` | `confidence_adjustment(dna: dict) -> dict` | Gibt Konfidenz-Anpassung basierend auf historischen DNA-Mustern zurueck. |
| `.record` | `record(dna: dict, won: bool) -> None` | Erfasst Ergebnis eines Trades fuer Musterlernen. |
| `.find_similar` | `find_similar(dna: dict, top_n=5) -> list[dict]` | Findet aehnliche historische DNA-Muster. |
| `.top_patterns` | `top_patterns(n=10) -> list[dict]` | Gibt die profitabelsten DNA-Muster zurueck. |
| `.worst_patterns` | `worst_patterns(n=5) -> list[dict]` | Gibt die verlustreichsten DNA-Muster zurueck. |
| `.load_from_trades` | `load_from_trades(closed_trades: list[dict]) -> int` | Laedt historische Trades in das DNA-System. |
| `.stats` | `stats() -> dict` | Gibt Statistiken ueber das DNA-System zurueck. |

### Verwendung

```python
from services.trade_dna import TradeDNA

dna = TradeDNA()
fingerprint = dna.compute("BTC/USDT", scan_data, "bull")
boost = dna.confidence_adjustment(fingerprint)
# Nach Trade-Abschluss:
dna.record(fingerprint, won=True)
```

### Konfiguration

Keine speziellen Umgebungsvariablen. Lernt automatisch aus historischen Trades.

---

## cryptopanic.py -- News-Sentiment

### Zweck

CryptoPanic API v2 Client fuer News-Sentiment-Analyse. Analysiert Crypto-Nachrichten
auf bullische/baerishe Signale anhand von Wortlisten und API-Sentiment-Daten.
Unterstuetzt die Plans: free, pro, developer.

### Klassen / Funktionen

| Name | Signatur | Beschreibung |
|------|----------|--------------|
| `CryptoPanicClient` | `class CryptoPanicClient(token: str, plan: str = "free")` | API-Client fuer CryptoPanic. |
| `.is_configured` | `@property is_configured -> bool` | Prueft ob ein gueltiger API-Token konfiguriert ist. |
| `.fetch_posts` | `fetch_posts(symbol, ...) -> list` | Holt Nachrichten-Posts von der API. |
| `.analyze_sentiment` | `analyze_sentiment(posts: list) -> tuple[float, str, int]` | Analysiert Sentiment einer Post-Liste: Score, Label, Anzahl. |
| `.get_score` | `get_score(symbol: str, db=None) -> tuple[float, str, int]` | Kombination aus Fetch + Analyse fuer ein Symbol. |

### Verwendung

```python
from services.cryptopanic import CryptoPanicClient

client = CryptoPanicClient(token="mein-token", plan="free")
if client.is_configured:
    score, label, count = client.get_score("BTC")
    # score: -1.0 bis +1.0, label: "bearish"/"neutral"/"bullish"
```

### Konfiguration

| Variable | Beschreibung |
|----------|--------------|
| `CRYPTOPANIC_TOKEN` | API-Auth-Token von CryptoPanic. |
| `CRYPTOPANIC_PLAN` | API-Plan: `free`, `pro` oder `developer`. Standard: `free`. |

---

## utils.py -- Hilfsfunktionen

### Zweck

Gemeinsame Konstanten, Hilfsklassen und Validierungsfunktionen fuer das gesamte Projekt.

### Klassen / Funktionen

| Name | Signatur | Beschreibung |
|------|----------|--------------|
| `SecretStr` | `class SecretStr(str)` | String-Subklasse, die in `__repr__` und `__str__` maskiert wird. Echten Wert via `.reveal()` abrufbar. |
| `make_secret` | `make_secret(val: str) -> SecretStr` | Erstellt ein `SecretStr`-Objekt aus einem normalen String. |
| `validate_symbol` | `validate_symbol(symbol: str) -> bool` | Validiert ein Handelspaar-Format (z.B. `BTC/USDT`). |
| `validate_config` | `validate_config(cfg: dict) -> list[str]` | Validiert CONFIG-Werte, gibt Liste von Fehlermeldungen zurueck (leer = OK). |
| `BOT_NAME` | `str = "TREVLIX"` | Bot-Name. |
| `BOT_VERSION` | `str = "1.6.6"` | Aktuelle Version. |
| `EXCHANGE_MAP` | `dict[str, str]` | Mapping von Exchange-Namen zu CCXT-Klassennamen. |

### Verwendung

```python
from services.utils import SecretStr, validate_config, BOT_NAME, EXCHANGE_MAP

secret = SecretStr("geheim")
print(secret)         # "***"
print(secret.reveal()) # "geheim"

errors = validate_config(my_config)
if errors:
    print("Konfigurationsfehler:", errors)
```

### Konfiguration

Keine eigenen Umgebungsvariablen. Stellt Validierungslogik fuer andere Module bereit.

---

## git_ops.py -- GitHub Updater Service

### Zweck

Kapselt alle Git-Operationen fuer den Admin-Updater (Check, Apply, Rollback)
mit festen Argumentlisten und Repository-gebundenem Arbeitsverzeichnis.
Damit werden Shell-Injection-Risiken minimiert und Fehler kontrolliert
als `GitOperationError` surfaciert.

### Kernlogik (Versionsermittlung)

`get_update_status()` berechnet die Version jetzt robust ueber eine
Fallback-Kette und SemVer-Vergleich:

1. Lokale Git-Tag-Version (`git describe --tags --abbrev=0`)
2. `VERSION.md`
3. `services.utils.BOT_VERSION`
4. Umgebungsvariable `TREVLIX_VERSION` (falls gesetzt)

Fuer `latest_version` wird zusaetzlich versucht, die hoechste Remote-Tag-Version
ueber `git ls-remote --tags --refs origin` zu bestimmen. Falls das fehlschlaegt,
wird auf die lokale Kette zurueckgefallen.

### Wichtige Funktionen

| Name | Signatur | Beschreibung |
|------|----------|--------------|
| `get_update_status` | `() -> UpdateStatus` | Liefert `current_version`, `latest_version`, `update_available`, `repo`, `branch`, `last_check`. |
| `apply_update` | `() -> None` | Fuehrt `git pull --ff-only` aus. |
| `rollback_update` | `() -> bool` | Fuehrt `git stash` aus, gibt Erfolg als Bool zurueck. |
| `_pick_latest_version` | `(candidates: list[str]) -> str` | Waehlt die hoechste gueltige SemVer-Version aus Kandidaten. |
| `_git_latest_remote_tag` | `() -> str` | Liefert die hoechste Remote-Tag-Version, falls verfuegbar. |

### Fehlermodell

- Timeouts/OS-Fehler/Subprocess-Fehler werden in `GitOperationError`
  mit user-sicherer Message + internem Detailtext transformiert.
- Nicht-kritische Teilfehler (z. B. fehlender Tag) degradieren den Status,
  brechen aber nicht den gesamten Update-Check.

---

## i18n Qualitaetssicherung (Dashboard/WebSocket)

### Zweck

Sicherstellen, dass alle WebSocket-Statuskeys (`ws_*`) aus `server.py`
in `static/js/trevlix_translations.js` vorhanden sind und alle
unterstuetzten Sprachen abdecken (`de`, `en`, `es`, `ru`, `pt`).

### Pruefskript

```bash
python scripts/check_i18n_keys.py
```

### Was wird geprueft?

1. **Key-Abdeckung:** Jeder in `server.py` emittierte `ws_*`-Key existiert in den UI-Translations.
2. **Sprach-Abdeckung:** Jeder vorhandene `ws_*`-Eintrag enthaelt alle Pflichtsprachen.

### Empfohlener Einsatz

- Vor jedem Commit mit WebSocket-/Dashboard-Aenderungen.
- Verpflichtend bei Release-/Versions-Bumps.
