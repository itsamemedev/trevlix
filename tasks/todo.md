# Bug: Crypto.com balance + trades not working

## Report (DE)
- "Symbol Validierung fehlgeschlagen"
- Crypto.com lädt weder App- noch Spot-Wallet-Guthaben → zeigt Paper-Guthaben
- Trades werden in keinem Modus ausgeführt

## Root causes
1. **Symbol validation hard-fails when markets aren't loaded** on the exchange
   instance. `TradeExecutionService._validate_symbol` calls `ex.market(symbol)`
   which raises if `load_markets()` was never called on *that* instance. This
   happens because OHLCV is served from the shared `market_cache`, so
   `scan_symbol` never triggers ccxt's implicit `load_markets`; and a
   freshly-reconnected primary instance keeps the old `state.markets` symbol
   list without reloading. Validation runs BEFORE the paper/live branch, so it
   blocks BOTH paper and live trades -> "no trades in any mode" + the literal
   "Symbol-Validierung fehlgeschlagen" message.
2. **Per-exchange `mode=live` is ignored by the balance paths** — they gate on
   the GLOBAL `paper_trading` flag, so an exchange set to live while the global
   switch is still paper shows the simulated paper balance instead of its real
   wallet:
   - `routes/api/market.py` per-exchange snapshot: `... and not paper`
   - `routes/api/trading.py` single-exchange balance route: passes global flag
   - `app/core/trading_ops.py:fetch_aggregated_balance` short-circuits to paper

## Plan
- [x] Fix `_validate_symbol`/`_validate_precision`: load markets once on miss
- [x] market.py: gate live-balance fetch on effective per-exchange mode
- [x] trading.py: per-exchange balance route uses effective mode
- [x] trading_ops.py: fetch_aggregated_balance honors per-exchange live mode
- [x] Regression tests
- [x] ruff + pytest green (824 passed, 1 skipped)
- [ ] commit + push

## Review
Four targeted fixes, no behavioural change for users already on a fully-global
paper/live setup:

1. `services/trade_execution.py` — new `_lookup_market()` helper used by both
   `_validate_symbol` and `_validate_precision`. On the first `ex.market()`
   miss it calls `ex.load_markets()` once and retries, so validation only fails
   for genuinely unknown symbols / unreachable exchanges. Fixes "Symbol-
   Validierung fehlgeschlagen" blocking ALL trades (paper + live), since
   validation runs before the paper/live branch.
2. `routes/api/market.py` — dashboard per-exchange snapshot now fetches the live
   wallet when the EFFECTIVE per-exchange mode is live (was gated on the global
   `paper` flag); same for the "API-Keys erforderlich" hint.
3. `routes/api/trading.py` — single-exchange balance route resolves the
   effective per-exchange mode instead of passing the global flag.
4. `app/core/trading_ops.py` — `fetch_aggregated_balance` only short-circuits to
   the simulated paper balance when NO exchange runs live; explicitly-live
   exchanges report their real wallet even while the global switch is paper.

Tests: `tests/test_trade_execution_safety.py` (+3 lazy-markets cases),
`tests/test_aggregated_balance.py` (new, 3 cases).
