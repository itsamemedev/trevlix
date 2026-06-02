# Todo: Crypto.com live_sell_failed + Portfolio lädt nicht

## Problem (DE)
1. **`live_sell_failed`** – Live-Verkäufe auf Crypto.com schlagen fehl. Häufigste
   Ursache: Die im Position-State gespeicherte `qty` ist minimal größer als das
   tatsächlich im Wallet freie Basis-Guthaben (die Kauf-Taker-Fee wird in der
   Basiswährung abgezogen). Crypto.com lehnt die Order dann mit
   `INSUFFICIENT_BALANCE` ab. Der Fehler wurde zudem nur als opaker Token
   `live_sell_failed` ausgegeben – ohne Ursache.
2. **Portfolio lädt nicht** – hängt am selben Balance-Pfad
   (`safe_fetch_balance`). Solange Fehler nur als `live_sell_failed`/generisch
   erschienen, war die Ursache (Auth vs. Guthaben vs. Netzwerk) nicht erkennbar.

## Plan
- [x] `TradeExecutionService.execute_sell`: Live-Verkaufsmenge vor dem Senden auf
      das **freie Basis-Guthaben** der Exchange deckeln (`_clamp_to_free_base`),
      auf den Lot-Step abgerundet. Schrumpft nur – blockiert nie einen legitimen
      Verkauf (Balance nicht lesbar / Asset fehlt → Originalmenge).
- [x] Generische `live_sell_failed` / `live_buy_failed` mit einer **sanitisierten
      Ursache** anreichern (`_sanitize_exchange_error`): Guthaben / Timeout /
      Auth / Rate-Limit / Netzwerk / Mindestgröße. Voller Fehler bleibt nur im
      Server-Log (kann API-Key-Fragmente/IPs enthalten).
- [x] Tests: Clamp auf freies Guthaben, kein Hochskalieren bei genug Guthaben,
      Ursache wird im Reason sichtbar.
- [x] ruff check/format + pytest grün.
- [x] commit + push

## Review
Minimaler, gezielter Eingriff in `services/trade_execution.py`:

1. **`_clamp_to_free_base(ex, symbol, qty)`** – liest via `safe_fetch_balance`
   (nutzt für Crypto.com bereits den v1→v2-Spot-Fallback) das freie
   Basis-Guthaben und deckelt die Verkaufsmenge darauf, abgerundet auf den
   Lot-Step. Nur Verkleinerung: ist das Wallet nicht lesbar oder listet das
   Asset nicht, bleibt die angeforderte Menge unverändert (kein False-Negative).
   Behebt die häufigste `live_sell_failed`-Ursache (Fee-Overshoot).

2. **`_sanitize_exchange_error(exc)`** – mappt rohe ccxt-Exceptions auf kurze,
   benutzerlesbare Ursachen. `execute_sell`/`execute_buy` melden jetzt
   `live_sell_failed: <Ursache>` statt nur des Tokens. Der Substring
   `live_sell_failed` bleibt erhalten (bestehende Tests + Log-Filter).

Tests: `tests/test_trade_execution_safety.py` (+3: Clamp, kein Hochskalieren,
Ursache sichtbar) → 24 passed im File, gesamte trade/exchange-Suite grün.
