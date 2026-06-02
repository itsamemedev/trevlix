# Todo: Crypto.com Auth + Daten-Persistenz beim Neustart

## Problem (DE)
1. **Crypto.com Authentifizierung fehlgeschlagen** – Balance-Abruf scheitert.
2. **Daten weg beim Neustart** – offene Positionen & Paper-Balance werden
   nicht aus der DB wiederhergestellt (nur geschlossene Trades).

## Root Cause
1. `safe_fetch_balance()` (services/exchange_factory.py): Crypto.com ruft den
   v1 Unified-Trading-Account-Endpoint. Für reine Spot-Wallet-Accounts wirft
   dieser eine Auth-/Permission-Exception. Der vorhandene v2-Spot-Fallback
   greift NUR bei leerem Ergebnis, NICHT bei einer Exception → Auth-Fehler,
   obwohl gültige Spot-Keys via v2 funktionieren würden.
2. `BotState.__init__` lädt via `_load_trades()` nur `closed_trades`. Offene
   Positionen (`trade_positions` mit `status='open'`) und die Paper-Balance
   werden nie rehydriert → `state.positions={}`, Balance = Default beim Start.

## Plan
- [x] `safe_fetch_balance`: bei Crypto.com auch nach einer Exception den
      v2-Spot-Fallback versuchen, bevor der Fehler weitergereicht wird.
- [x] `BotState._rehydrate_open_positions()` hinzufügen: offene Positionen aus
      DB laden, in das Primärkonto schreiben (long/short), Paper-Balance
      konsistent rekonstruieren (Startkapital + realisierte PnL − gebundenes
      Kapital). In `__init__` nach `_load_trades()` aufrufen.
- [x] `import json` in trading_classes.py ergänzen (meta_json parsen).
- [x] Tests ergänzen (Persistenz-Rehydration + cryptocom Fallback-on-error).
- [x] ruff check/format + pytest grün (838 passed, 1 skipped).
- [x] commit + push

## Review
Zwei gezielte Fixes, minimaler Eingriff:

1. **services/exchange_factory.py – `safe_fetch_balance`**: Bei `cryptocom`
   wird der v2-Spot-Endpoint jetzt auch dann versucht, wenn der v1
   Unified-Account-Endpoint eine Exception wirft (typisch für reine
   Spot-Wallet-Accounts). Liefert der Fallback Guthaben, wird es genutzt;
   sonst wird der Original-Fehler weitergereicht (echte ungültige Keys
   werden NICHT maskiert). Behebt "Authentifizierung fehlgeschlagen" für
   Spot-only Crypto.com-Konten.

2. **app/core/trading_classes.py – `BotState._rehydrate_open_positions`**:
   Beim Start werden offene Positionen aus `trade_positions`
   (`status='open'`) ins Primärkonto geladen (long → `positions`,
   short → `short_positions`). `_position_from_db_row` mappt DB-Spalten
   auf die vom Sell-Algorithmus erwarteten Keys; fehlende Felder fallen
   auf `.get()`-Defaults zurück. Im Paper-Modus wird die Balance konsistent
   rekonstruiert (`Startkapital + realisierte PnL − gebundenes Kapital`);
   im Live-Modus bleibt sie unberührt (kommt aus dem echten Wallet via
   Reconciliation). Behebt "Daten weg beim Neustart".

Tests: `tests/test_position_rehydration.py` (9 neu), `tests/test_exchange_factory.py`
(+3: v1-Auth-Fehler→Spot-Fallback, Re-raise ohne Fallback, non-cryptocom Re-raise).

Hinweis an den User: Wenn die DB selbst nicht persistent läuft (z. B. MySQL
ohne Docker-Volume), wären die Daten weiterhin weg — die committed
docker-compose-Configs nutzen aber benannte Volumes (`mysql_data`).
