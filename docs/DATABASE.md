# Trevlix Datenbank-Dokumentation

## 1. Übersicht

Trevlix verwendet **MySQL / MariaDB 8.0+** als relationale Datenbank. Alle Tabellen und
Verbindungen nutzen den Zeichensatz **utf8mb4** mit der Kollation `utf8mb4_unicode_ci`, um
vollständige Unicode-Unterstützung (inkl. Emojis) zu gewährleisten.

Die Datenbank wird beim ersten Start des Docker-Containers automatisch über
`docker/mysql-init.sql` initialisiert. Zusätzlich erstellt die Anwendung dieselben Tabellen
beim Serverstart über `server.py:_init_db_once()`.

Für die Verbindungsverwaltung kommt ein **thread-sicherer Connection-Pool** zum Einsatz
(`services/db_pool.py`), der den Overhead wiederholter Verbindungsaufbauten eliminiert.

---

## 2. Tabellen

### 2.1 `trades` — Geschlossene Trades

Speichert alle ausgeführten und geschlossenen Trades mit PnL, KI-Bewertung und Marktdaten.

| Spalte | Typ | Beschreibung |
|---|---|---|
| `id` | INT AUTO_INCREMENT | Primärschlüssel |
| `user_id` | INT DEFAULT 1 | Zugehöriger Benutzer |
| `symbol` | VARCHAR(20) | Handelspaar (z.B. BTC/USDT) |
| `entry` | DOUBLE | Einstiegspreis |
| `exit_price` | DOUBLE | Ausstiegspreis |
| `qty` | DOUBLE | Handelsmenge |
| `pnl` | DOUBLE | Gewinn/Verlust (absolut) |
| `pnl_pct` | DOUBLE | Gewinn/Verlust (prozentual) |
| `reason` | VARCHAR(80) | Grund für den Trade |
| `confidence` | DOUBLE | Konfidenzwert der Strategie |
| `ai_score` | DOUBLE | KI-Bewertung des Trades |
| `win_prob` | DOUBLE | Geschätzte Gewinnwahrscheinlichkeit |
| `invested` | DOUBLE | Investierter Betrag |
| `opened` | DATETIME | Zeitpunkt der Eröffnung |
| `closed` | DATETIME | Zeitpunkt der Schließung |
| `exchange` | VARCHAR(20) | Börse (z.B. binance, cryptocom) |
| `regime` | VARCHAR(10) | Marktregime (bull/bear/neutral) |
| `trade_type` | VARCHAR(10) DEFAULT 'long' | Trade-Richtung (long/short) |
| `partial_sold` | TINYINT DEFAULT 0 | Teilverkauf durchgeführt |
| `dca_level` | INT DEFAULT 0 | DCA-Stufe (Dollar-Cost-Averaging) |
| `news_score` | DOUBLE DEFAULT 0 | Nachrichten-Bewertung |
| `onchain_score` | DOUBLE DEFAULT 0 | On-Chain-Bewertung |

**Indizes:** `idx_closed (closed)`, `idx_symbol (symbol)`, `idx_user (user_id)`

---

### 2.2 `users` — Benutzer

Benutzerverwaltung mit Authentifizierung, Guthaben und Exchange-Konfiguration.

| Spalte | Typ | Beschreibung |
|---|---|---|
| `id` | INT AUTO_INCREMENT | Primärschlüssel |
| `username` | VARCHAR(50) UNIQUE | Eindeutiger Benutzername |
| `password_hash` | VARCHAR(256) | Gehashtes Passwort |
| `role` | VARCHAR(20) DEFAULT 'user' | Rolle (user/admin) |
| `balance` | DOUBLE DEFAULT 10000.0 | Aktuelles Guthaben |
| `initial_balance` | DOUBLE DEFAULT 10000.0 | Startguthaben |
| `api_key` | VARCHAR(200) | Verschlüsselter API-Key der Börse |
| `api_secret` | VARCHAR(200) | Verschlüsseltes API-Secret der Börse |
| `exchange` | VARCHAR(20) DEFAULT 'cryptocom' | Standard-Börse |
| `created_at` | DATETIME DEFAULT CURRENT_TIMESTAMP | Erstellungszeitpunkt |
| `last_login` | DATETIME | Letzter Login |
| `settings_json` | MEDIUMTEXT | Benutzereinstellungen als JSON |

**Indizes:** UNIQUE auf `username`

---

### 2.3 `ai_training` — KI-Trainingsdaten

Speichert Feature-Vektoren und Labels für das Trainieren des KI-Modells.

| Spalte | Typ | Beschreibung |
|---|---|---|
| `id` | INT AUTO_INCREMENT | Primärschlüssel |
| `features` | TEXT | Feature-Vektor als JSON |
| `label` | TINYINT | Klassifikationslabel (0/1) |
| `regime` | VARCHAR(10) DEFAULT 'bull' | Marktregime |
| `created_at` | DATETIME DEFAULT CURRENT_TIMESTAMP | Erstellungszeitpunkt |

**Indizes:** `idx_regime (regime)`

---

### 2.4 `audit_log` — Audit-Protokoll

Protokolliert sicherheitsrelevante Aktionen aller Benutzer.

| Spalte | Typ | Beschreibung |
|---|---|---|
| `id` | INT AUTO_INCREMENT | Primärschlüssel |
| `user_id` | INT DEFAULT 0 | Benutzer-ID (0 = System) |
| `action` | VARCHAR(80) NOT NULL | Durchgeführte Aktion |
| `detail` | VARCHAR(500) | Zusätzliche Details |
| `ip` | VARCHAR(45) | IP-Adresse (IPv4/IPv6) |
| `created_at` | DATETIME DEFAULT CURRENT_TIMESTAMP | Zeitstempel |

**Indizes:** `idx_user (user_id)`, `idx_action (action)`, `idx_time (created_at)`

---

### 2.5 `backtest_results` — Backtest-Ergebnisse

Speichert Ergebnisse von Strategietests auf historischen Daten.

| Spalte | Typ | Beschreibung |
|---|---|---|
| `id` | INT AUTO_INCREMENT | Primärschlüssel |
| `symbol` | VARCHAR(20) | Getestetes Handelspaar |
| `timeframe` | VARCHAR(10) | Zeitrahmen (z.B. 1h, 4h, 1d) |
| `candles` | INT | Anzahl analysierter Kerzen |
| `total_trades` | INT | Gesamtanzahl simulierter Trades |
| `win_rate` | DOUBLE | Gewinnquote |
| `total_pnl` | DOUBLE | Gesamt-PnL |
| `profit_factor` | DOUBLE | Profit-Faktor |
| `max_drawdown` | DOUBLE | Maximaler Drawdown |
| `result_json` | MEDIUMTEXT | Detailliertes Ergebnis als JSON |
| `created_at` | DATETIME DEFAULT CURRENT_TIMESTAMP | Erstellungszeitpunkt |

**Indizes:** Keine zusätzlichen

---

### 2.6 `price_alerts` — Preisalarme

Benutzerdefinierte Preisalarme für bestimmte Handelspaare.

| Spalte | Typ | Beschreibung |
|---|---|---|
| `id` | INT AUTO_INCREMENT | Primärschlüssel |
| `user_id` | INT DEFAULT 1 | Zugehöriger Benutzer |
| `symbol` | VARCHAR(20) | Handelspaar |
| `target_price` | DOUBLE | Zielpreis |
| `direction` | VARCHAR(10) | Richtung (above/below) |
| `triggered` | TINYINT DEFAULT 0 | Ob der Alarm ausgelöst wurde |
| `created_at` | DATETIME DEFAULT CURRENT_TIMESTAMP | Erstellungszeitpunkt |
| `triggered_at` | DATETIME | Zeitpunkt der Auslösung |

**Indizes:** Keine zusätzlichen

---

### 2.7 `daily_reports` — Tagesberichte

Automatisch generierte tägliche Performance-Berichte.

| Spalte | Typ | Beschreibung |
|---|---|---|
| `id` | INT AUTO_INCREMENT | Primärschlüssel |
| `report_date` | DATE | Berichtsdatum |
| `report_json` | MEDIUMTEXT | Bericht als JSON |
| `sent_at` | DATETIME DEFAULT CURRENT_TIMESTAMP | Versandzeitpunkt |

**Indizes:** UNIQUE KEY `uq_date (report_date)`

---

### 2.8 `sentiment_cache` — Sentiment-Cache

Zwischenspeicher für Sentiment-Analysen pro Handelspaar.

| Spalte | Typ | Beschreibung |
|---|---|---|
| `symbol` | VARCHAR(20) | Handelspaar (Primärschlüssel) |
| `score` | DOUBLE | Sentiment-Score |
| `source` | VARCHAR(20) | Datenquelle |
| `updated_at` | DATETIME DEFAULT CURRENT_TIMESTAMP | Letzte Aktualisierung |

**Indizes:** PRIMARY KEY auf `symbol`

---

### 2.9 `news_cache` — Nachrichten-Cache

Zwischenspeicher für Nachrichtenanalysen pro Handelspaar.

| Spalte | Typ | Beschreibung |
|---|---|---|
| `symbol` | VARCHAR(20) | Handelspaar (Primärschlüssel) |
| `score` | DOUBLE | Nachrichten-Score |
| `headline` | VARCHAR(500) | Relevanteste Schlagzeile |
| `article_count` | INT DEFAULT 0 | Anzahl analysierter Artikel |
| `updated_at` | DATETIME DEFAULT CURRENT_TIMESTAMP | Letzte Aktualisierung |

**Indizes:** PRIMARY KEY auf `symbol`

---

### 2.10 `onchain_cache` — On-Chain-Daten-Cache

Zwischenspeicher für On-Chain-Analysedaten (Whale-Aktivität, Kapitalflüsse).

| Spalte | Typ | Beschreibung |
|---|---|---|
| `symbol` | VARCHAR(20) | Handelspaar (Primärschlüssel) |
| `whale_score` | DOUBLE | Whale-Aktivitäts-Score |
| `flow_score` | DOUBLE | Kapitalfluss-Score |
| `net_score` | DOUBLE | Netto-Score |
| `detail` | VARCHAR(500) | Detailinformationen |
| `updated_at` | DATETIME DEFAULT CURRENT_TIMESTAMP | Letzte Aktualisierung |

**Indizes:** PRIMARY KEY auf `symbol`

---

### 2.11 `genetic_results` — Genetischer Algorithmus

Ergebnisse der genetischen Optimierung von Handelsstrategien.

| Spalte | Typ | Beschreibung |
|---|---|---|
| `id` | INT AUTO_INCREMENT | Primärschlüssel |
| `generation` | INT | Generationsnummer |
| `fitness` | DOUBLE | Fitnesswert des Genoms |
| `genome_json` | TEXT | Genom-Parameter als JSON |
| `created_at` | DATETIME DEFAULT CURRENT_TIMESTAMP | Erstellungszeitpunkt |

**Indizes:** Keine zusätzlichen

---

### 2.12 `arb_opportunities` — Arbitrage-Möglichkeiten

Erkannte Preisunterschiede zwischen Börsen für Arbitrage-Handel.

| Spalte | Typ | Beschreibung |
|---|---|---|
| `id` | INT AUTO_INCREMENT | Primärschlüssel |
| `symbol` | VARCHAR(20) | Handelspaar |
| `exchange_buy` | VARCHAR(20) | Kaufbörse |
| `price_buy` | DOUBLE | Kaufpreis |
| `exchange_sell` | VARCHAR(20) | Verkaufsbörse |
| `price_sell` | DOUBLE | Verkaufspreis |
| `spread_pct` | DOUBLE | Spread in Prozent |
| `executed` | TINYINT DEFAULT 0 | Ob ausgeführt |
| `profit` | DOUBLE DEFAULT 0 | Erzielter Gewinn |
| `found_at` | DATETIME DEFAULT CURRENT_TIMESTAMP | Erkennungszeitpunkt |

**Indizes:** Keine zusätzlichen

---

### 2.13 `rl_episodes` — Reinforcement-Learning-Episoden

Speichert Zustände, Aktionen und Belohnungen des RL-Agenten.

| Spalte | Typ | Beschreibung |
|---|---|---|
| `id` | INT AUTO_INCREMENT | Primärschlüssel |
| `episode` | INT | Episodennummer |
| `reward` | DOUBLE | Erhaltene Belohnung |
| `state_json` | TEXT | Zustandsvektor als JSON |
| `action` | INT | Gewählte Aktion |
| `created_at` | DATETIME DEFAULT CURRENT_TIMESTAMP | Erstellungszeitpunkt |

**Indizes:** Keine zusätzlichen

---

### 2.14 `api_tokens` — API-Tokens

Verwaltung von API-Zugangstoken für die REST-Schnittstelle.

| Spalte | Typ | Beschreibung |
|---|---|---|
| `id` | INT AUTO_INCREMENT | Primärschlüssel |
| `user_id` | INT | Zugehöriger Benutzer |
| `token` | VARCHAR(500) | Token-Wert |
| `label` | VARCHAR(100) | Beschreibung/Name des Tokens |
| `created_at` | DATETIME DEFAULT CURRENT_TIMESTAMP | Erstellungszeitpunkt |
| `last_used` | DATETIME | Letzte Verwendung |
| `expires_at` | DATETIME | Ablaufdatum |
| `active` | TINYINT DEFAULT 1 | Ob der Token aktiv ist |

**Indizes:** Keine zusätzlichen

---

### 2.15 `user_exchanges` — Benutzer-Börsen (Multi-Exchange)

Ermöglicht jedem Benutzer mehrere Börsen-Anbindungen mit eigenen API-Credentials.

| Spalte | Typ | Beschreibung |
|---|---|---|
| `id` | INT AUTO_INCREMENT | Primärschlüssel |
| `user_id` | INT NOT NULL | Zugehöriger Benutzer |
| `exchange` | VARCHAR(20) NOT NULL | Börsenname |
| `api_key` | VARCHAR(500) | Verschlüsselter API-Key |
| `api_secret` | VARCHAR(500) | Verschlüsseltes API-Secret |
| `enabled` | TINYINT DEFAULT 0 | Ob die Anbindung aktiv ist |
| `is_primary` | TINYINT DEFAULT 0 | Ob dies die Hauptbörse ist |
| `created_at` | DATETIME DEFAULT CURRENT_TIMESTAMP | Erstellungszeitpunkt |

**Indizes:** UNIQUE KEY `uq_user_exchange (user_id, exchange)`, `idx_user (user_id)`, `idx_enabled (user_id, enabled)`

---

### 2.16 `trade_dna` — Trade-DNA-Fingerabdrücke

Speichert multidimensionale Fingerabdrücke von Trades zur Mustererkennung.

| Spalte | Typ | Beschreibung |
|---|---|---|
| `id` | INT AUTO_INCREMENT | Primärschlüssel |
| `symbol` | VARCHAR(20) | Handelspaar |
| `dna_hash` | VARCHAR(16) | Kurz-Hash des Fingerabdrucks |
| `fingerprint` | VARCHAR(500) | Fingerabdruck-String |
| `dimensions_json` | TEXT | Dimensionen als JSON |
| `raw_values_json` | TEXT | Rohwerte als JSON |
| `won` | TINYINT | Ob der Trade gewonnen hat |
| `pnl` | DOUBLE DEFAULT 0 | Gewinn/Verlust |
| `dna_boost` | DOUBLE DEFAULT 1.0 | DNA-Boost-Faktor |
| `created_at` | DATETIME DEFAULT CURRENT_TIMESTAMP | Erstellungszeitpunkt |

**Indizes:** `idx_hash (dna_hash)`, `idx_symbol (symbol)`, `idx_time (created_at)`

---

### 2.17 `shared_knowledge` — Geteiltes KI-Wissen

Gemeinsame Wissensbasis der KI-Agenten, kategorisiert nach Themenbereich.

| Spalte | Typ | Beschreibung |
|---|---|---|
| `id` | INT AUTO_INCREMENT | Primärschlüssel |
| `category` | VARCHAR(50) NOT NULL | Wissenskategorie |
| `key_name` | VARCHAR(100) NOT NULL | Schlüsselname innerhalb der Kategorie |
| `value_json` | MEDIUMTEXT | Wissenswert als JSON |
| `confidence` | DOUBLE DEFAULT 0.5 | Konfidenzwert (0.0 - 1.0) |
| `source` | VARCHAR(50) DEFAULT 'ai' | Quelle (ai/user/system) |
| `created_at` | DATETIME DEFAULT CURRENT_TIMESTAMP | Erstellungszeitpunkt |
| `updated_at` | DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE | Letzte Aktualisierung |

**Indizes:** UNIQUE KEY `uq_cat_key (category, key_name)`, `idx_category (category)`

---

## 3. Connection Pool

Der Connection-Pool (`services/db_pool.py`) stellt thread-sichere, wiederverwendbare
Datenbankverbindungen bereit.

### Konfiguration

| Parameter | Standard | Beschreibung |
|---|---|---|
| `pool_size` | 5 | Maximale Anzahl gleichzeitiger Verbindungen |
| `timeout` | 10s | Wartezeit auf freie Verbindung |
| `connect_timeout` | 10s | Timeout beim Verbindungsaufbau |
| `read_timeout` | 30s | Timeout bei Leseoperationen |
| `write_timeout` | 30s | Timeout bei Schreiboperationen |

### Verwendung

```python
from services.db_pool import ConnectionPool

# Context-Manager (empfohlen)
with pool.connection() as conn:
    with conn.cursor() as c:
        c.execute("SELECT * FROM trades WHERE symbol = %s", ("BTC/USDT",))
        rows = c.fetchall()

# Manuell
conn = pool.acquire()
try:
    with conn.cursor() as c:
        c.execute(...)
finally:
    conn.close()  # Gibt die Verbindung an den Pool zurück
```

### Monitoring

```python
stats = pool.pool_stats()
# Ergebnis:
# {
#     "pool_size": 5,
#     "available": 3,
#     "in_use": 2,
#     "utilization_pct": 40.0
# }
```

Der Pool gibt eine Warnung aus, wenn die letzte verfügbare Verbindung vergeben wird
(`DB-Pool erschöpft`), und erstellt bei Bedarf neue Verbindungen on-demand.

---

## 4. Sicherheit

### Parametrisierte Abfragen

Alle SQL-Abfragen **müssen** parametrisiert sein. String-Interpolation in SQL ist
**ausnahmslos verboten**, um SQL-Injection zu verhindern.

```python
# Korrekt
cursor.execute("SELECT * FROM users WHERE username = %s", (username,))

# VERBOTEN - niemals verwenden
cursor.execute(f"SELECT * FROM users WHERE username = '{username}'")
```

### Verschlüsselte API-Keys

API-Schlüssel in den Tabellen `users` und `user_exchanges` werden **niemals im Klartext**
gespeichert. Die Ver- und Entschlüsselung erfolgt über `services/encryption.py` mittels
**Fernet** (symmetrische Verschlüsselung, AES-128-CBC). Der `ENCRYPTION_KEY` wird
ausschließlich über Umgebungsvariablen bereitgestellt.

### Pool-Erschöpfungs-Warnungen

Der Connection-Pool protokolliert Warnungen bei:
- **Letzte Verbindung vergeben:** `DB-Pool erschöpft: letzte Verbindung vergeben`
- **Pool leer:** `DB-Pool leer: erstelle neue Verbindung on-demand`

Diese Warnungen sollten überwacht werden, um rechtzeitig die `pool_size` zu erhöhen.

---

## 5. Migration

Neue Tabellen müssen **immer an zwei Stellen** hinzugefügt werden:

1. **`server.py:_init_db_once()`** — `CREATE TABLE IF NOT EXISTS`-Statement für den
   Anwendungsstart
2. **`docker/mysql-init.sql`** — Identisches Statement für die Docker-Initialisierung

Beide Definitionen müssen synchron gehalten werden. Wird nur eine Stelle aktualisiert,
kann es je nach Startmethode (Docker vs. direkt) zu fehlenden Tabellen kommen.

---

## 6. Backup

Trevlix verfügt über eine integrierte Auto-Backup-Funktionalität für die Datenbank.
Details zur Konfiguration und Wiederherstellung sind in der Server-Dokumentation zu finden.

Für manuelle Backups kann `mysqldump` verwendet werden:

```bash
mysqldump -u $MYSQL_USER -p$MYSQL_PASS $MYSQL_DB > trevlix_backup_$(date +%Y%m%d).sql
```
