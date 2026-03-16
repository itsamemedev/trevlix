# Trevlix Trading-Dokumentation

Umfassende Dokumentation des Trading-Systems, der Strategien, des Risikomanagements
und der einzigartigen Features wie Trade DNA Fingerprinting und Smart Exit Engine.

---

## 1. Voting-System

Trevlix verwendet ein demokratisches **Abstimmungssystem aus 9 unabhaengigen Strategien**.
Jede Strategie analysiert die aktuellen Marktdaten und gibt eine Stimme ab:

- **BUY** -- Long-Signal erkannt
- **SELL** -- Short-Signal erkannt
- **HOLD** -- Kein klares Signal

### Abstimmungsschwelle

Ein Trade wird nur eroeffnet, wenn die **Mehrheit der Strategien** uebereinstimmt.
Der Schwellenwert (Konsensus) ist konfigurierbar und bestimmt, wie viele der 9 Strategien
in dieselbe Richtung stimmen muessen, bevor ein Trade ausgefuehrt wird.

### KI-Gewichtung

Die Stimmen werden nicht gleichmaessig gezaehlt. Die KI-Engine vergibt dynamische Gewichte
basierend auf der historischen Vorhersagekraft jeder Strategie (Feature Importance).
Strategien, die in der Vergangenheit haeufiger korrekt lagen, erhalten ein hoeheres Gewicht.
Schlecht performende Strategien werden automatisch abgewertet.

---

## 2. Die 9 Strategien

### 2.1 EMA-Trend

Exponential Moving Average Crossover. Vergleicht kurzfristige und langfristige EMAs,
um Trendrichtung und Trendstaerke zu bestimmen. Ein Kaufsignal entsteht, wenn die
kurzfristige EMA die langfristige EMA von unten kreuzt (Golden Cross).

### 2.2 RSI-Stochastic

Kombiniert den Relative Strength Index (RSI) mit dem Stochastischen Oszillator.
Der RSI misst Ueberkauft-/Ueberverkauft-Zustaende, waehrend der Stochastic-Indikator
Momentum-Wechsel erkennt. Kaufsignal bei ueberverkauftem RSI + bullischem
Stochastic-Crossover.

### 2.3 MACD-Kreuzung

Moving Average Convergence Divergence. Erkennt Trendwechsel ueber die Kreuzung
der MACD-Linie mit der Signallinie. Zusaetzlich wird das MACD-Histogramm fuer
die Bestimmung der Signalstaerke herangezogen.

### 2.4 Bollinger

Bollinger Bands messen die Volatilitaet und identifizieren ueber-/unterbewertete
Zustaende. Kaufsignal bei Beruehrung oder Unterschreitung des unteren Bands,
Verkaufssignal beim oberen Band. Die Bandbreite (BB-Width) dient zusaetzlich
als Volatilitaetsindikator.

### 2.5 Volumen-Ausbruch

Erkennt signifikante Volumen-Anstiege in Kombination mit Preisbewegungen.
Ein ueberproportionaler Volumen-Anstieg bei gleichzeitigem Kursanstieg deutet
auf einen nachhaltigen Ausbruch hin.

### 2.6 OBV-Trend

On-Balance Volume verfolgt den kumulativen Volumenstrom. Steigende OBV bei steigenden
Preisen bestaetigt den Trend. Divergenzen zwischen OBV und Preis signalisieren
moegliche Trendwenden.

### 2.7 ROC-Momentum

Rate of Change misst die prozentuale Preisveraenderung ueber einen definierten
Zeitraum. Erkennt Beschleunigungs- und Verlangsamungsphasen im Markt.
Positive ROC signalisiert Aufwaertsmomentum, negative ROC Abwaertsmomentum.

### 2.8 Ichimoku

Ichimoku Kinko Hyo (Cloud) liefert ein ganzheitliches Bild aus Trend, Momentum,
Unterstuetzung und Widerstand. Kaufsignal wenn der Preis ueber der Wolke (Kumo)
liegt und Tenkan-Sen die Kijun-Sen kreuzt.

### 2.9 VWAP

Volume Weighted Average Price dient als intraday Benchmark. Trades ueber VWAP
signalisieren Kaeufer-Dominanz, unter VWAP Verkaeufer-Dominanz. Besonders
relevant fuer kurzfristige Entries und Exits.

---

## 3. KI-Ensemble

### Modell-Architektur

Trevlix setzt auf ein Ensemble aus drei unterschiedlichen Machine-Learning-Modellen:

| Modell | Typ | Staerke |
|--------|-----|---------|
| **XGBoost** | Gradient Boosting | Erkennung nichtlinearer Zusammenhaenge |
| **RandomForest** | Ensemble von 200 Entscheidungsbaeumen | Robuste Klassifikation |
| **LSTM** | Rekurrentes Neuronales Netz | Zeitreihen-Abhaengigkeiten |

### Funktionsweise

1. **Feature-Extraktion**: Alle 9 Strategie-Signale, normalisierte Indikatoren
   (RSI, ATR, Bollinger-Width, etc.) und Marktdaten werden als Feature-Vektor aufbereitet.

2. **Training**: Ab 20 abgeschlossenen Trades wird das Modell trainiert. Es lernt,
   welche Kombinationen von Signalen und Marktbedingungen historisch zu profitablen
   Trades gefuehrt haben.

3. **Scoring**: Jedes Modell berechnet eine Gewinnwahrscheinlichkeit (0-100%).
   Die Einzelwerte werden kombiniert zu einem Gesamt-Score.

4. **Filter**: Trades mit einer Gewinnwahrscheinlichkeit unter 55% werden blockiert.

5. **Strategie-Gewichtung**: Die Feature Importance des Ensembles wird genutzt,
   um die Gewichte der 9 Strategien dynamisch anzupassen.

6. **Auto-Optimierung**: Alle 15 Trades sucht der Bot automatisch die besten
   SL/TP-Werte basierend auf den letzten Trades.

---

## 4. Trade DNA Fingerprinting

> Einzigartiges Feature von Trevlix

Jeder Trade erhaelt einen einzigartigen **DNA-Fingerprint** basierend auf den exakten
Marktbedingungen zum Zeitpunkt der Trade-Eroeffnung. Das System lernt, welche
DNA-Muster historisch profitabel waren und passt die Konfidenz zukuenftiger Trades
mit aehnlichem Fingerprint an.

### 4.1 Die 7 Dimensionen

| # | Dimension | Beschreibung | Moegliche Werte |
|---|-----------|-------------|-----------------|
| 1 | **Regime** | Aktuelles Marktregime | `bull`, `bear`, `range`, `crash` |
| 2 | **Volatilitaet** | ATR-basierte Schwankungsbreite | `low`, `mid`, `high`, `extreme` |
| 3 | **Fear & Greed** | Marktstimmung (0-100 Index) | `extreme_fear`, `fear`, `neutral`, `greed`, `extreme_greed` |
| 4 | **News** | Nachrichten-Sentiment | `negative`, `neutral`, `positive` |
| 5 | **Orderbook** | Kauf-/Verkaufsdruck im Orderbuch | `sell_pressure`, `balanced`, `buy_pressure` |
| 6 | **Konsensus** | Staerke der Strategie-Uebereinstimmung | `weak`, `moderate`, `strong`, `unanimous` |
| 7 | **Session** | Tageszeit (UTC) | `asia`, `europe`, `us`, `off_hours` |

### 4.2 Bucket-Definitionen

**Volatilitaet** (ATR in %):

| Bucket | Bereich |
|--------|---------|
| `low` | < 0.5% |
| `mid` | 0.5% -- 1.5% |
| `high` | 1.5% -- 3.0% |
| `extreme` | > 3.0% |

**Fear & Greed** (Index 0-100):

| Bucket | Bereich |
|--------|---------|
| `extreme_fear` | 0 -- 19 |
| `fear` | 20 -- 39 |
| `neutral` | 40 -- 59 |
| `greed` | 60 -- 79 |
| `extreme_greed` | 80 -- 100 |

**News-Sentiment** (Score):

| Bucket | Bereich |
|--------|---------|
| `negative` | < -0.2 |
| `neutral` | -0.2 -- 0.2 |
| `positive` | > 0.2 |

**Orderbook-Imbalance** (Bid-Ratio):

| Bucket | Bereich |
|--------|---------|
| `sell_pressure` | < 0.40 |
| `balanced` | 0.40 -- 0.55 |
| `buy_pressure` | > 0.55 |

**Vote-Konsensus** (Confidence):

| Bucket | Bereich |
|--------|---------|
| `weak` | < 0.40 |
| `moderate` | 0.40 -- 0.55 |
| `strong` | 0.55 -- 0.70 |
| `unanimous` | > 0.70 |

**Tageszeit-Session** (UTC-Stunde):

| Bucket | Bereich |
|--------|---------|
| `asia` | 00:00 -- 07:59 |
| `europe` | 08:00 -- 15:59 |
| `us` | 16:00 -- 21:59 |
| `off_hours` | 22:00 -- 23:59 |

### 4.3 Fingerprint-Hash

Alle 7 Dimensionen werden zu einem deterministischen String zusammengefuegt
und per SHA-256 gehasht (16 Zeichen). Identische Marktbedingungen erzeugen
immer denselben Hash.

```
Beispiel-Fingerprint:
consensus=moderate|fear_greed=greed|news=neutral|orderbook=balanced|regime=bull|session=europe|volatility=mid

Hash: a3f7b2c91e4d8f06
```

### 4.4 Pattern Mining -- Win-Rate Tracking

Fuer jeden einzigartigen Fingerprint-Hash werden Gewinn- und Verlusttrades gezaehlt:

- `wins`: Anzahl profitabler Trades mit diesem Fingerprint
- `total`: Gesamtanzahl Trades mit diesem Fingerprint
- `win_rate`: wins / total

Die Engine benoetigt mindestens **5 Matches** (konfigurierbar) bevor sie eine
Konfidenz-Anpassung vornimmt.

### 4.5 Konfidenz-Anpassung

Basierend auf der historischen Win-Rate wird ein Multiplikator berechnet:

| Bedingung | Aktion | Multiplikator |
|-----------|--------|---------------|
| Win-Rate > 65% | **Boost** | 1.0 -- 1.5x (skaliert mit WR) |
| Win-Rate 35% -- 65% | **Neutral** | 1.0x (keine Aenderung) |
| Win-Rate < 35% | **Block** | 0.0 -- 0.5x (skaliert mit WR) |

**Boost-Berechnung**: `min(1.0 + (WR - 0.65) * 2, 1.5)`
- Bei 65% WR: 1.0x
- Bei 80% WR: 1.3x
- Bei 90%+ WR: 1.5x (Maximum)

**Block-Berechnung**: `max(WR / 0.35 * 0.5, 0.0)`
- Bei 35% WR: 0.5x
- Bei 17.5% WR: 0.25x
- Bei 0% WR: 0.0x (Trade wird blockiert)

### 4.6 Aehnlichkeitssuche

Wenn ein exakter Fingerprint-Match nicht genuegend Daten hat, sucht die Engine
nach aehnlichen historischen Trades ueber Dimensionen-Matching:

- Jede uebereinstimmende Dimension zaehlt als 1 Punkt
- Similarity = uebereinstimmende Dimensionen / 7 (Gesamtzahl)
- Mindestens 50% Uebereinstimmung (4/7 Dimensionen) erforderlich
- Die Top-5 aehnlichsten Trades werden zurueckgegeben

---

## 5. Smart Exit Engine

> Einzigartiges Feature von Trevlix

Ersetzt fixe SL/TP-Prozentsaetze durch **dynamische, volatilitaetsbasierte
Stop-Loss- und Take-Profit-Level**. Nutzt ATR, Marktregime und Signal-Staerke
fuer intelligentere Exits.

### 5.1 Kernformel

```
SL = ATR x Base-Multiplikator x Regime-Multiplikator
TP = ATR x Reward-Ratio x Regime-Reward x Signal-Staerke-Faktor
```

### 5.2 ATR-basierte Berechnung

Die Average True Range (ATR, 14 Perioden) bildet die Grundlage fuer beide Level.
Der Base-Multiplikator (Standard: 1.5x ATR fuer SL, 2.0x fuer TP) wird mit dem
Regime-Multiplikator kombiniert.

### 5.3 Regime-Multiplikatoren

| Regime | SL-Multiplikator | TP-Multiplikator | Logik |
|--------|:----------------:|:----------------:|-------|
| **Bull** | 1.2x | 3.0x | Enge Stops, grosses TP -- Trend reiten |
| **Bear** | 2.0x | 1.5x | Weite Stops, konservatives TP -- Noise vermeiden |
| **Range** | 1.5x | 2.0x | Ausgewogene Stops und TP |
| **Crash** | 2.5x | 1.0x | Sehr weite Stops, minimales TP -- oder kein Trade |

### 5.4 Signal-Staerke-Faktor

Die Konfidenz des Signals beeinflusst das Take-Profit-Ziel:

```
Signal-Faktor = 0.8 + (Confidence x 0.4)
```

| Confidence | Faktor | Wirkung |
|:----------:|:------:|---------|
| 0% | 0.80x | Konservativeres TP |
| 50% | 1.00x | Neutrales TP |
| 100% | 1.20x | Erweitertes TP |

### 5.5 Volatility Squeeze Detection

Wenn die Bollinger-Bandbreite (BB-Width) unter den Schwellenwert von **0.03** faellt,
wird ein bevorstehender Ausbruch erwartet:

- Die Stops werden um **20% enger** gesetzt (`sl_distance *= 0.8`)
- Ziel: Engerer SL vor dem Ausbruch, groesseres Gewinnpotential nach dem Ausbruch

### 5.6 Dynamische Anpassung

Die Smart Exit Engine passt bestehende Positionen laufend an:

**SL-Trailing im Profit:**
- Aktiviert ab 1% unrealisiertem Gewinn
- Der SL wird enger nachgezogen: `trailing_distance = ATR x Regime-Mult x 0.8`
- SL wird nur nach oben verschoben (nie zurueck)

**TP-Extension bei Bull + starkem Profit:**
- Aktiviert ab 3% unrealisiertem Gewinn im Bull-Regime
- Das TP wird erweitert: `extended_tp = current_price + ATR x Regime-Reward x 1.2`
- TP wird nur nach oben verschoben

### 5.7 Min/Max-Grenzen

Alle SL/TP-Werte werden auf konfigurierbare Grenzen begrenzt:

| Parameter | Min | Max | Konfiguration |
|-----------|:---:|:---:|---------------|
| **Stop-Loss** | 1% | 8% | `smart_exit_min_sl_pct`, `smart_exit_max_sl_pct` |
| **Take-Profit** | 2% | 15% | `smart_exit_min_tp_pct`, `smart_exit_max_tp_pct` |

---

## 6. Risikomanagement

### 6.1 Circuit Breaker

Automatische Notbremse bei Verlustserien:

- **Verlust-Circuit-Breaker**: Nach N aufeinanderfolgenden Verlusten (Standard: 3)
  wird der Handel fuer eine konfigurierbare Zeitspanne ausgesetzt (Standard: 30 Minuten).
- **Drawdown-Circuit-Breaker**: Wenn der maximale Drawdown den Schwellenwert
  ueberschreitet (Standard: 10%), wird der Handel fuer die doppelte Zeitspanne ausgesetzt.
- Nach Ablauf der Sperrzeit werden die Verlustzaehler zurueckgesetzt.

### 6.2 Max Daily Loss

Der maximale taegliche Verlust wird auf einen konfigurierbaren Prozentsatz begrenzt
(Standard: 5% des Tages-Startbalance). Bei Ueberschreitung werden keine neuen
Trades eroeffnet. Die Zaehler werden taeglich um Mitternacht zurueckgesetzt.

### 6.3 Kelly Sizing

Positionsgroessen werden nach dem **Kelly-Kriterium** berechnet:

```
Kelly = ((Gewinnwahrscheinlichkeit x Odds - Verlustwahrscheinlichkeit) / Odds) x 0.5
Position = Balance x Kelly x Volatilitaets-Anpassung x FG-Boost
```

- **Half-Kelly**: Der Faktor 0.5 (Half-Kelly) reduziert das Risiko gegenueber
  dem vollen Kelly-Kriterium.
- **Volatilitaets-Anpassung**: Bei hoher ATR wird die Position reduziert.
- **Fear & Greed Boost**: Die Marktstimmung kann die Positionsgroesse beeinflussen.
- **Grenzen**: Kelly wird auf 1% -- 25% des Portfolios begrenzt.

### 6.4 Korrelationsfilter

Verhindert die gleichzeitige Eroeffnung stark korrelierter Positionen:

- Berechnet Pearson-Korrelation der Preisrenditen (letzte 100 Datenpunkte)
- Blockiert neue Trades, wenn die Korrelation mit einer offenen Position
  den Schwellenwert ueberschreitet (Standard: 0.75)
- Benoetigt mindestens 20 Datenpunkte fuer eine zuverlaessige Berechnung

### 6.5 Symbol-Cooldown

Nach einem Verlust-Trade wird das betroffene Symbol fuer eine konfigurierbare
Zeitspanne gesperrt (Standard: 60 Minuten). Dies verhindert emotionales
Re-Entry und gibt dem Markt Zeit, sich zu stabilisieren.

### 6.6 Liquiditaetspruefung

Vor jedem Trade wird der Orderbook-Spread geprueft. Ueberschreitet der Spread
den konfigurierten Schwellenwert (`max_spread_pct`), wird der Trade nicht ausgefuehrt.

---

## 7. Marktregime-Erkennung

### Regime-Typen

| Regime | Erkennung | Trading-Verhalten |
|--------|-----------|-------------------|
| **Bull** | ROC > 2% und RSI > 50 | Aggressive Entries, Trend reiten, enge Stops |
| **Bear** | ROC < -2% und RSI < 50 | Defensive Entries, weite Stops, konservatives TP |
| **Range** | BB-Width < 0.03 und 35 < RSI < 65 | Ausgewogene Parameter, Mean-Reversion |
| **Crash** | ATR > 3.0% und ROC < -5% | Minimales Trading, sehr weite Stops oder Pause |

### Auswirkungen auf das Trading

- **Smart Exits**: Regime bestimmt SL/TP-Multiplikatoren (siehe Abschnitt 5.3)
- **Positionsgroesse**: Im Crash-Regime werden Positionen reduziert oder ausgesetzt
- **Strategie-Gewichtung**: Die KI passt Gewichte regime-abhaengig an
- **Trade DNA**: Regime ist eine der 7 Fingerprint-Dimensionen

---

## 8. Order-Typen

### 8.1 Market Order

Sofortige Ausfuehrung zum aktuellen Marktpreis. Wird fuer schnelle Entries
und Exits bei hoher Liquiditaet verwendet.

### 8.2 Limit Order

Order wird nur zum festgelegten Preis oder besser ausgefuehrt.
Bietet bessere Preise bei ausreichend Liquiditaet, aber keine garantierte Ausfuehrung.

### 8.3 Trailing Stop

Dynamischer Stop-Loss, der dem Preis in Gewinnrichtung folgt.
Haelt einen festen Abstand zum Hoechst-/Tiefstkurs seit Eroeffnung.
Die Smart Exit Engine berechnet den Abstand regime-abhaengig.

### 8.4 Break-Even Stop

Automatische Verschiebung des Stop-Loss auf den Einstiegspreis,
sobald ein definierter Mindestgewinn erreicht wurde. Eliminiert das
Verlustrisiko fuer die Position.

### 8.5 Partial Take-Profit

Teilweiser Gewinnausstieg bei Erreichen eines Zwischenziels:

- Ein konfigurierbarer Anteil der Position wird geschlossen
- Der verbleibende Teil laeuft mit einem angepassten Trailing-Stop weiter
- Sichert Gewinne bei gleichzeitiger Chancenwahrung

### 8.6 DCA (Dollar Cost Averaging)

Nachkauf bei Kursrueckgaengen innerhalb einer bestehenden Position:

- Wird nur bei starkem Signal und ausreichendem Risiko-Budget aktiviert
- Senkt den durchschnittlichen Einstiegspreis
- Maximale Nachkauf-Stufen sind konfigurierbar
- Erhoehtes Risiko -- wird vom Risikomanagement ueberwacht
