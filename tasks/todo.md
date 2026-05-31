# Intensive Bug Hunt — v1.9.4 baseline

## RUN 3 — deferred items revisited + new domains (782 passed / 1 skipped, ruff clean)
Fixed (genuine, verified via Read):
1. performance_attribution.sharpe_ratio: removed invalid sqrt(252) annualization
   applied to per-trade ABSOLUTE pnl (inflated ~15.9x) → correct per-trade Sharpe;
   dropped now-unused math import.
2. config_validation: take_profit_pct bound (0,500]→(0,1.0] (it's a fraction,
   matches Pydantic le=1.0); the 500 bound effectively disabled the TP. + test.
3. services/config.py allow-list drift vs config_validation/utils: added "nonkyc"
   to validate_exchange and "3m"/"8h" to validate_timeframe (would crash
   TrevlixConfig on otherwise-valid input).
4. ml_models._seed_genome: duplicate "vote" dict key removed; default 0.3→0.50
   to match documented min_vote_score (genome mutation floor is 0.4).
5. trading_classes short smart-exit EXCEPTION fallback used 0.03/0.05; aligned to
   the documented 0.025/0.06 defaults used by the normal path.

False positives — verified and intentionally NOT changed:
- monte_carlo span anchor: closed_trades is newest-first (insert(0)), so trades[-1]
  is the OLDEST → span = now - oldest is CORRECT (subagent had ordering backwards).
- backtest open-position: already force-closes at the final candle (total_pnl and
  final_balance ARE consistent).
- tax_report holding period: IS applied (taxable = held_days < 365).
- grid total_trades: counts individual fills; a separate completed_round_trips
  exists — the distinction is intentional.
- risk.is_short_too_expensive: already uses `rate < -max_rate` (correct funding
  convention) — run-1 flag was a misread.
- manual_sell long-only: shorts are closed via close-position (handles both) —
  intentional ("sell" = close long).

Documented, NOT changed (low impact / risk vs reward):
- ai_engine allowed_count/blocked_count/brain_state mutated in should_buy() without
  self._lock — LOW impact (display counters; _update_brain is pure). Hot path; not
  touched on unreliable terminal reads this session.
- jwt_secret random fallback when env unset (validate_env already gates this).
- frontend JS/templates subagent hit a session limit before returning — to cover.

---


## RUN 2 — additional bugs found & fixed (782 passed / 1 skipped, ruff clean)
1. HIGH — API token revocation was a no-op: verify_api_token validated the JWT
   only cryptographically, never checking the api_tokens.active flag → revoked
   tokens kept authenticating until JWT exp. Now does a DB lookup, fails closed.
   (app/core/repositories/user_repo.py)
2. HIGH — config_validation coerced bool toggles with bool(raw); bool("false")
   is True, so disabling a feature via a string ENABLED it. → use safe_bool.
   (app/core/config_validation.py)
3. HIGH — stop_loss_pct sanity bound was (0, 50]; it's a FRACTION used as
   price*(1-pct), so any value >= 1 zeroes/inverts the stop loss. The test even
   enshrined 50 as valid. → bound tightened to (0, 0.5] + test corrected.
   (app/core/config_validation.py, tests/test_config_validation.py)
4. MEDIUM — graceful shutdown closed the DB pool BEFORE cleanup_old_data(), which
   then lazily re-opened (leaked) connections. → run cleanup first.
   (app/core/lifecycle.py)
5. MEDIUM — auto_healing _mark_healthy cleared `escalated` but left the failures
   deque populated → a single failure after recovery instantly re-escalated
   (alert storm on flapping services). → clear failures/recovery_attempts on
   recovery. (services/auto_healing.py)
6. MEDIUM — start_exchange/stop_exchange WS handlers had no rate limit (every
   other state-changing handler does). → add _ws_rate_check. (server.py)
7. LOW — Discord/Telegram HTTP-error log paths logged resp.text unredacted
   (except-path used _redact); Telegram double-parsed resp.json(). → redact +
   single parse. (services/notifications.py)
8. LOW — is_admin_password_weak was case-sensitive ("Admin" passed). → normalize
   case + strip. (app/core/admin_password_policy.py)
9. LOW — preflight retry log printed `attempt+1` (1-based off-by-one).
   (app/core/exchange_runtime.py)

Run-2 regression tests: test_token_revocation.py (token active/revoked/deleted/
tampered + weak-password cases), test_recovery_clears_failure_history,
test_bool_key_string_false_disables, corrected stop_loss_pct sanity test.

Considered but NOT changed (design/scope): tax_report FIFO/holding-period not
implemented; performance_attribution Sharpe sqrt(252) on per-trade pnl;
cluster_control get_cluster_metrics not updating node.status; exchange_factory
broad-except; redis fallback gap; revenue break-even counted as win.

---


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
