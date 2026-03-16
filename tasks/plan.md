# Plan: Verbesserungen + 2 Einzigartige Features

## Feature 1: Trade DNA Fingerprinting & Pattern Mining
**Einzigartigkeit:** Kein Open-Source-Bot hat das. Jeder Trade bekommt einen
"DNA-Fingerprint" aus den exakten Marktbedingungen (Regime, Volatilität, News,
Strategie-Votes, OB-Imbalance). Das System lernt, welche DNA-Muster historisch
profitabel waren und boosted/blockt zukünftige Trades mit ähnlichem Fingerprint.

### Implementierung:
- Neue Klasse `TradeDNA` in `services/trade_dna.py`
- DNA-Vektor: [regime, vol_bucket, fg_bucket, news_bucket, ob_bucket, vote_pattern, hour_bucket]
- Historischer Match: Cosine-Similarity der letzten N Trades
- Confidence-Boost: +20% wenn DNA-Match-WinRate > 65%, Block wenn < 35%
- DB-Tabelle `trade_dna` für persistente DNA-Historie
- API-Endpunkt `/api/v1/trade-dna` für Dashboard-Anzeige
- Discord-Notification bei DNA-Match

## Feature 2: Volatility-Adaptive Dynamic SL/TP (Smart Exits)
**Einzigartigkeit:** ATR-Daten werden bereits berechnet aber nie für SL/TP
genutzt. Dieses Feature passt SL/TP dynamisch an die aktuelle Volatilität +
Regime + Signal-Stärke an, statt fixe Prozentsätze zu verwenden.

### Implementierung:
- Neue Klasse `SmartExitEngine` in `services/smart_exits.py`
- SL = ATR × Multiplikator (regime-abhängig: Bull=1.2, Bear=2.0, Crash=2.5)
- TP = ATR × Reward-Ratio × Signal-Stärke
- Dynamische Anpassung: SL/TP werden bei manage_positions() neu berechnet
- Volatility Squeeze Detection: Bollinger Width < Threshold → engere Stops
- Integration in open_position() und manage_positions()
- CONFIG-Keys: use_smart_exits, smart_exit_atr_mult, smart_exit_reward_ratio

## Optimierungen:
- Batch-Decryption für Exchange-Keys statt Loop pro Row
- Spezifischere Exception-Typen in kritischen DB-Methoden
