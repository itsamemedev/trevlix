# Intensive Bug Hunt — v1.9.4 baseline

## RUN 6 — resolved the design/scope backlog (807 passed / 1 skipped, ruff clean)
All previously "deferred — needs spec/judgement" items investigated and fixed:
1. tax_report: now applies the German § 23 EStG 1-year holding-period rule. Gains
   on positions held > 365 days are reported as tax-free (separate `tax_free`
   bucket + `tax_free_gains`/`tax_free_count` summary) and excluded from
   `taxable_gains`. Holding period derived from opened/closed; unparseable dates
   conservatively fall back to taxable. (Round-trip trades already carry realized
   pnl, so no cross-leg FIFO needed at this layer — documented in the module.)
2. backtest: force-close any position still open on the final candle (reason
   "EOD") so total_pnl (realized) equals the mark-to-market final_balance /
   return_pct. Previously they disagreed when a position was open at the end.
3. grid total_trades: now counts completed round-trips (sells) only; added
   separate buy_fills/sell_fills counters (exposed in status()). Previously a
   round-trip counted as 2 trades.
4. risk.is_short_too_expensive: sign was inverted for the Bybit perp convention
   (positive funding = shorts receive, negative = shorts pay). Now blocks shorts
   on strongly NEGATIVE funding (rate < -max_rate) instead of positive.
5. manual_sell (/api/v1/trading/sell): now closes shorts too (covers via
   short_engine.close_short), mirroring close-position; was long-only (404 on a
   symbol held only as a short).

Run-6 tests: test_tax_report.py, test_backtest_consistency.py,
test_grid_trade_count.py, test_funding_rate_filter.py.

## RUN 4 — frontend/untouched-module sweep (787 passed / 1 skipped, ruff clean)
Fixed:
1. HIGH — CSV formula injection in BOTH authenticated CSV download paths
   (app/core/tax_export.py + app/core/repositories/trade_repo.py:export_csv).
   symbol/reason fields written verbatim → cells starting with = + - @ TAB CR run
   as formulas in Excel/LibreOffice (data exfil / RCE on the victim). Added
   csv_safe_cell() (quote-prefix) applied to every exported cell. + tests.
   FOLLOW-UP: the csv_safe_cell import was missing in trade_repo.py (would crash
   export_csv at runtime, F821) — added import + a test that exercises export_csv.
2. HIGH — CSRF missing on 26 state-changing dashboard.js fetch() calls. They sent
   only 'Authorization: Bearer '+(_jwtToken||'') with NO X-CSRFToken; per
   session_guard.py session-cookie POST/PUT/DELETE/PATCH require a CSRF token, so
   these 403'd for every normal cookie-auth user (adjustSL, clearCooldown,
   deleteGrid, saveTelegram, saveIpWhitelist, saveNewsFilter, adminForceSync,
   adminTrainGlobal, saveFundingConfig, runMarkowitz, backtest compare, …).
   Injected 'X-CSRFToken':_csrfToken into the shared header literal (harmless on
   the GETs that share it; backend ignores CSRF for safe methods).
3. MEDIUM — loadChart() dereferenced chartSym/chartTf/tvChart before the try block
   (unlike the guarded style used everywhere else) → whole handler threw on a
   partial render. Added early null guards + guarded the badge write.

Frontend items checked & OK (subagent): esc()/escJS() applied to all dynamic
sinks (no XSS), socket handlers de-duplicated, all setInterval cleared on
beforeunload, no secrets logged. LOW: `clr` local shadows global helper in
_renderVirginieForecastFeed (harmless) — left as-is.

## RUN 5 — cleared the deferred backlog (793 passed / 1 skipped, ruff clean)
Fixed:
1. MEDIUM — llm_providers: transport-level failures (timeout/DNS/conn-refused)
   raised before any HTTP status, so _apply_cooldown never fired and a hard-down
   provider was retried every call (up to ~30s each). Added _cooldown_for() +
   _TRANSPORT_ERROR_COOLDOWN_SECONDS in both chat()/chat_all() except branches;
   chat_all() now also skips providers already in cooldown.
2. MEDIUM — llm_providers: _health["tokens"] was read by status()/analytics but
   never written → dashboard tokens always 0. Now parses usage.total_tokens in
   _call_provider and accumulates under the lock (+ "tokens":0 in health init).
3. LOW — prometheus_metrics: state and db._pool reads now wrapped in try/except so
   a single attribute/state error can't take down the whole /metrics endpoint.
4. LOW — git_ops.rollback_update only `git stash`ed (never reverted the pull).
   apply_update() now records the pre-pull commit to .trevlix_rollback_ref
   (gitignored, survives restart) and rollback_update() does `git reset --hard`
   to it. server.py rollback message updated to match real behaviour.

Run-5 tests: test_git_ops_rollback.py (apply records ref, rollback resets/handles
missing ref/reset failure; llm transport cooldown + token accumulation).


## RUN 3 — deferred items revisited + new domains (782 passed / 1 skipped, ruff clean)
Fixed (verified via grep + ast parse + full suite):
1. performance_attribution.sharpe_ratio: removed invalid sqrt(252) annualization
   applied to per-trade ABSOLUTE pnl (inflated ~15.9x) → correct per-trade Sharpe;
   dropped now-unused math import.
2. config_validation: take_profit_pct bound (0,500]→(0,1.0] (it's a fraction,
   matches Pydantic le=1.0); the 500 bound effectively disabled the TP. + test.
3. services/config.py allow-list drift vs config_validation/utils: added "nonkyc"
   to validate_exchange and "3m"/"8h" to validate_timeframe (would crash
   TrevlixConfig on otherwise-valid input).
4. ml_models genetic seed: min_vote_score fallback 0.3→0.50 to match the
   documented default (genome mutation floor is 0.4). (No duplicate key existed.)
5. trading_classes short smart-exit EXCEPTION fallback used 0.03/0.05; aligned to
   the documented 0.025/0.06 defaults used by the normal path.

False positive — verified NOT a bug:
- monte_carlo span anchor: closed_trades is newest-first (insert(0)), so trades[-1]
  is the OLDEST → span = now - oldest is CORRECT (subagent had ordering backwards).

REAL findings deferred (NOT fixed — larger scope / sensitive):
- tax_report: no real FIFO lot-matching and no German §23 1-year holding-period
  rule (taxable = net>0 regardless of hold time). Sensitive (user tax numbers).
- backtest: confirmed via read — NO force-close at the last candle, so
  final_balance/return_pct (mark-to-market) disagree with total_pnl (closed only)
  when a position is open on the final candle. [MEDIUM]
- grid total_trades increments on both BUY and SELL (a round trip counts as 2);
  reporting-semantics only, PnL is correct. [LOW]
- risk.is_short_too_expensive returns `rate > max_rate`; on standard perps a high
  POSITIVE funding rate favours shorts, so the filter may be inverted —
  exchange-convention dependent, left as-is. [LOW]
- manual_sell is long-only; shorts close via close-position. Plausibly intentional.

Documented, NOT changed (low impact):
- ai_engine allowed_count/blocked_count/brain_state mutated in should_buy() without
  self._lock — but the readers (to_dict/brain_state_snapshot) also don't lock, and
  the GIL makes the dict rebind atomic; only counter += can lose updates. LOW
  (display-only). Left unchanged.
- jwt_secret random fallback when env unset (validate_env already gates this).
- frontend JS/templates: esc()/escJS() helpers exist; a re-run agent is auditing
  the ~8 template-literal innerHTML sinks in dashboard.js.

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
