# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## Workflow Orchestration

### 1. Plan Node Default

- Enter plan mode for **ANY non-trivial task** (3+ steps or architectural decisions)
- If something goes sideways, **STOP and re-plan immediately** – don't keep pushing
- Write detailed specs upfront to reduce ambiguity

### 2. Subagent Strategy

- Use subagents liberally to keep main context window clean
- Offload research, exploration, and parallel analysis to subagents
- One task per subagent for focused execution

### 3. Self-Improvement Loop

- After **ANY correction** from the user: update `tasks/lessons.md` with the pattern
- Review `tasks/lessons.md` at session start for relevant patterns

### 4. Verification Before Done

- **Never** mark a task complete without proving it works
- Run tests, check logs, demonstrate correctness
- Ask yourself: "Would a staff engineer approve this?"

### 5. Autonomous Bug Fixing

- When given a bug report: just fix it
- Point at logs, errors, failing tests – then resolve them

---

## Task Management

1. **Plan First**: Write plan to `tasks/todo.md` with checkable items
2. **Verify Plan**: Check in before starting implementation
3. **Track Progress**: Mark items complete as you go
4. **Document Results**: Add review section to `tasks/todo.md`
5. **Capture Lessons**: Update `tasks/lessons.md` after corrections

---

## Core Principles

- **Simplicity First**: Make every change as simple as possible. Impact minimal code.
- **No Laziness**: Find root causes. No temporary fixes.
- **Minimal Impact**: Changes should only touch what's necessary.

---

## Commands

```bash
# Tests
python3 -m pytest tests/ -q --tb=short          # full suite
python3 -m pytest tests/test_foo.py::TestBar::test_baz -v --tb=short  # single test

# Lint / Format
ruff check .
ruff format --check .
ruff format .                                    # apply formatting

# Dev server
python server.py                                 # requires .env with DB + exchange keys

# Generate secrets
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"  # ENCRYPTION_KEY
python -c "import secrets; print(secrets.token_hex(32))"                                   # JWT_SECRET / SECRET_KEY
```

**Pre-commit checklist** (all must pass):
```bash
ruff check .
ruff format --check .
python3 -m pytest tests/ -q --tb=short
```

Ruff config: line-length=100, target=py311, rules E/W/F/I/B/UP, ignores E501/B008/B904.

---

## Project-Specific Rules

### Git Workflow

- Always develop on the branch specified in the task description (`claude/...`)
- Push with: `git push -u origin <branch-name>`
- Retry push up to 4 times on network failure (backoff: 2s, 4s, 8s, 16s)
- Never push to `main` or `master` directly

### Code Quality Standards

- Python 3.11+, type hints on all public functions
- Docstrings on all public classes and functions
- No bare `except:` – always catch specific exceptions

### Security Rules

- API keys always encrypted via `services/encryption.py`
- Never log sensitive values (passwords, API keys, tokens)
- Input validation at all API boundaries
- Protected config keys in `_PROTECTED_KEYS` frozenset

### Database Rules

- New tables must be added in BOTH:
  1. `server.py:_init_db_once()`
  2. `docker/mysql-init.sql`
- Always use parameterized queries
- Always use the connection pool (`services/db_pool.py`)

### Lambda / Loop Variable Capture

- **Never** `lambda: func(var)` inside a loop
- **Always** `lambda var=var: func(var)` to capture current value

---

## Architecture

### Entry Point & Startup Sequence

`server.py` is the single entry point (~3500 lines). Startup has a strict **two-phase init** to avoid circular dependencies:

**Phase 1 – Early (before class instantiation):**
- `CONFIG` built from env + defaults (`app/core/default_config.py`)
- `init_db_manager()`, `init_ai_engine()`, `init_ml_models()`, `init_trading_classes()` called — these populate module-level globals (`CONFIG`, `log`) in each module

**Phase 2 – Late (after all objects exist):**
- `init_trading_ops()` called at `server.py:~3162` — injects `state`, `discord`, `emit_event`, `ai_engine`, `risk`, `regime`, etc. into `app/core/trading_ops.py` module globals
- `_rehydrate_config_from_admin()` overwrites CONFIG keys from DB (user-persisted settings)

**Rule:** `__init__`-time globals must be set in Phase 1. Runtime-dependency globals belong to Phase 2. See `app/core/trading_ops.py:51-102` for the module-global pattern.

### Blueprint / Route Architecture

Blueprints are registered in `app/core/http_routes.py`:
- `register_system_routes()` — favicon, robots.txt, error handlers (404/429/500)
- `register_default_blueprints()` — auth (`routes/auth.py`) and dashboard (`routes/dashboard.py`)

API blueprints in `routes/api/`:
- `trading.py` — manual buy/sell, close-position, backtest, grid
- `market.py` — OHLCV, heatmap, portfolio optimize
- `ai.py` — VIRGINIE chat, knowledge-base, MCP tools, AI status
- `admin.py` — user management, config update, exchange keys
- `system.py` — health checks, metrics, logs

All API blueprints receive an `AppDeps` container (`routes/api/deps.py`) — a dataclass holding every shared dependency. **Critical:** `deps.close_position` and `deps.create_exchange` are defined as lambda wrappers so `monkeypatch.setattr(server, "close_position", fake)` propagates at call time.

### CONFIG Flow

```
env vars → build_default_config() → CONFIG dict → Phase 2: _rehydrate_config_from_admin() (DB overrides)
```

CONFIG is a plain `dict[str, Any]` passed by reference to all services. Dashboard settings are persisted to DB and reloaded on restart. Protected keys (secrets, DB credentials) can only be changed via `.env`, not the API.

### WebSocket Layer

- Rate-limiting wrapper via `WsRateLimiter` in `routes/websocket.py:65`
- Auth guards: `ws_auth_required()` / `ws_admin_required()` in `app/core/websocket_authz.py`
- Handlers still primarily in `server.py`; `routes/websocket.py` is the migration target (incremental)
- Events emitted via `emit_event(name, payload)` — wraps `socketio.emit()`

### Trading Bot Loop (`app/core/trading_ops.py:bot_loop`)

Each iteration (~60 s):
1. Exchange reconciliation — connect/drop exchanges from DB config
2. `manage_positions()` — SL/TP checks, trailing stop, smart exits
3. `fetch_markets()` — symbol list refresh every 10 iterations
4. Per-symbol scan pipeline:
   - `compute_indicators()` → RSI, EMA, MACD, ATR, OBV, Bollinger
   - 9-strategy vote → `vote_confidence`
   - `ai_engine.should_buy()` — ML filter (Random Forest + XGBoost + LSTM blended)
   - VIRGINIE decision — `VirginieOrchestrator.execute(AgentTask(...))`
   - Risk checks — circuit breaker, daily loss limit, correlation filter
   - `open_position()` / `close_position()`

### VIRGINIE AI System (`services/virginie.py`)

Self-learning autonomous agent layered on top of the ML pipeline:

- **Opportunity scoring:** `EV = P(success) × expected_profit − cost − risk_penalty`
- **Guardrails:** `min_score` and `max_risk_penalty` hard limits
- **Bandit LLM routing:** per-model, per-task reward tracking → prefer highest-reward LLM
- **Startup examples:** built-in `LearningExample` set (EV formula, bear/bull playbooks, signal quality, exit rules) loaded at init; sorted by `quality_score` descending — the EV-formula example has the highest score (0.90) and must stay top-ranked
- **Slash commands** (`/status`, `/plan`, `/edge`) handled inline in `routes/api/ai.py:_generate_reply` — never routed to LLM
- Integrated in `app/core/ai_engine.py` as `VirginieCore` + `VirginieOrchestrator` inside `AIEngine.should_buy()`; blending formula: `blended_prob = autonomy_w × model_prob + (1 − autonomy_w) × vote_conf`

### Services Layer

| Service | Key responsibility |
|---|---|
| `services/knowledge.py` | LLM integration, market knowledge base, MCP tool registry |
| `services/mcp_tools.py` | Tool registry for LLM tool-use (thread-safe cache with Lock) |
| `services/strategies.py` | 9 voting strategies returning buy/sell confidence |
| `services/risk.py` | Circuit breaker, position sizing, daily loss tracking |
| `services/encryption.py` | Fernet key wrapping for stored API credentials |
| `services/db_pool.py` | Thread-safe MySQL connection pool |
| `services/market_data.py` | Fear/Greed index, dominance filter, on-chain data (all TTL-cached) |
| `services/shutdown.py` | LIFO graceful shutdown hooks with per-hook deadline |
| `services/structured_logger.py` | JSON log formatter with request-ID injection |
| `services/cache.py` | TTL+LRU cache with per-key thundering-herd protection |
| `services/task_queue.py` | Bounded thread pool with backpressure |

### Environment Variables

| Variable | Required | Description |
|---|---|---|
| `EXCHANGE` | Yes | `cryptocom\|binance\|bybit\|okx\|kucoin\|...` |
| `API_KEY` / `API_SECRET` | Yes | Exchange credentials |
| `MYSQL_HOST/USER/PASS/DB` | Yes | Database connection |
| `ADMIN_PASSWORD` | Yes | Min 12 chars, mixed case + special; **RuntimeError in prod if missing** |
| `JWT_SECRET` / `SECRET_KEY` | Yes | 32+ hex chars |
| `ENCRYPTION_KEY` | Yes | Fernet key (44 base64url chars) |
| `PAPER_TRADING` | No | `true` for simulation |
| `LLM_ENDPOINT` | No | OpenAI-compatible URL for VIRGINIE |
| `DISCORD_WEBHOOK` / `TELEGRAM_TOKEN` | No | Alert channels |

Validation runs at startup via `validate_env.py`. Known weak values ("test", "admin", "password", etc.) are hard-blocked. Run `python validate_env.py --strict` to check before deploying.

### Test Fixtures (`tests/conftest.py`)

- `set_test_env` (autouse) — sets `ENCRYPTION_KEY`, `JWT_SECRET`, `PAPER_TRADING=true`
- `sample_ohlcv()` — 200-candle BTC-like DataFrame
- `small_ohlcv()` — 50-candle slice
- `sample_trade()` / `sample_trades()` — pre-built trade dicts (BTC/USDT, 6 wins / 4 losses pattern)
- `app_client` (in `test_api.py`) — Flask test client; skips if DB unavailable
