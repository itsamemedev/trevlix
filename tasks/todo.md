# Intensive Bug Hunt — v1.9.4 baseline

## Baseline
- Full suite: 29 failed, 739 passed, 1 skipped (fresh checkout)
- Root cause of failures = STALE TESTS left behind by 16th-pass (d8e4484):
  - strat_macd zero-line filter flipped → 2 MACD tests stale
  - VirginieGuardrails default min_score 0.0→0.5 → 1 ai_engine_init test stale
  - CSRF "missing token = violation" fix + @admin gate on trading/control → ~26 test_api tests stale (no CSRF token / admin role)

## Plan
- [x] Fix 3 stale logic tests to match intended new behavior
- [x] Restore test_api baseline (centralized CSRF token client + admin stubs)
- [x] Hunt genuine source bugs (subagents, per-domain)
- [x] Verify: ruff + full pytest green (773 passed, 1 skipped)
- [ ] Commit + push

## Real bugs found & fixed
1. HIGH — Privilege escalation: `POST /api/v1/user/settings` (@auth only) let any
   user flip the GLOBAL trade mode to live via `paper_trading`, bypassing the
   admin guard on `/api/v1/trading/mode`. → admin check added. (routes/api/trading.py)
2. MEDIUM — `toggle_user_exchange` / `delete_user_exchange` returned True even on
   0 rows matched → phantom-success `{"ok":true}` + misleading audit/auto-start.
   → return `c.rowcount > 0`. (app/core/repositories/exchange_repo.py)
3. MEDIUM — `TTLCache.get_or_set` leaked one `threading.Lock` per distinct key
   forever (unbounded `_producer_locks`). → drop per-key lock after produce.
   (services/cache.py)
4. MEDIUM — knowledge.py claimed the LLM throttle slot BEFORE the worker ran; a
   transient failure suppressed market-context (15min) / idle-learn regeneration
   for the full window. → release slot on failure. (services/knowledge.py)
5. MEDIUM — `RiskManager.force_reset_daily` did not re-arm the one-shot
   daily-loss CB latch; after a live-balance re-baseline a fresh breach could not
   re-fire the CB/alert. → reset `_daily_loss_cb_fired`. (services/risk.py)
6. LOW — system.py risk endpoints: clamp lower bounds on n/days/conf/h and guard
   `api_market_regime` against KeyError/missing attr. (routes/api/system.py)

Regression tests added: TestTradeModePrivilege (x2),
test_force_reset_daily_rearms_cb_latch, test_market_context_failure_releases_throttle_slot,
test_get_or_set_does_not_leak_producer_locks.

## Stale-test root cause (baseline was red on fresh checkout)
The 16th-pass (d8e4484) changed source but not tests:
- strat_macd zero-line filter flipped → 2 MACD tests updated
- VirginieGuardrails min_score 0.0→0.5 → 1 ai_engine_init test updated
- CSRF "missing token = violation" + @admin gate → 26 test_api tests fixed via a
  centralized CSRF-aware test client (auto-seeds `_csrf_token` + `X-CSRFToken`) +
  admin stubs on the 2 admin-gated control tests.

## Considered but NOT changed (low confidence / design-dependent)
- manual_sell long-only vs close-position long+short (likely intentional)
- set_primary_exchange 404-vs-500 on DB error (cosmetic)
- db_pool ping(reconnect=True) accounting (muddled, risky)
- ai_engine dashboard counters mutated without lock (LOW impact, hot path)
- funding-rate short filter sign (exchange-convention dependent)

## Review
29 failing tests on fresh checkout were all stale tests left by the prior pass —
fixed without weakening production security. Found + fixed 1 HIGH auth-bypass and
4 MEDIUM correctness/leak bugs via parallel domain subagents, each with a
regression test. Suite: 773 passed / 1 skipped, ruff clean.
