# CLAUDE.md – Workflow & Coding Standards for Trevlix

This file defines the operational guidelines for Claude Code when working on this project.
Review this file at the start of every session.

---

## Workflow Orchestration

### 1. Plan Node Default

- Enter plan mode for **ANY non-trivial task** (3+ steps or architectural decisions)
- If something goes sideways, **STOP and re-plan immediately** – don't keep pushing
- Use plan mode for verification steps, not just building
- Write detailed specs upfront to reduce ambiguity

### 2. Subagent Strategy

- Use subagents liberally to keep main context window clean
- Offload research, exploration, and parallel analysis to subagents
- For complex problems, throw more compute at it via subagents
- One task per subagent for focused execution

### 3. Self-Improvement Loop

- After **ANY correction** from the user: update `tasks/lessons.md` with the pattern
- Write rules for yourself that prevent the same mistake
- Ruthlessly iterate on these lessons until mistake rate drops
- Review lessons at session start for relevant project

### 4. Verification Before Done

- **Never** mark a task complete without proving it works
- Diff behavior between main and your changes when relevant
- Ask yourself: "Would a staff engineer approve this?"
- Run tests, check logs, demonstrate correctness

### 5. Demand Elegance (Balanced)

- For non-trivial changes: pause and ask "is there a more elegant way?"
- If a fix feels hacky: "Knowing everything I know now, implement the elegant solution"
- Skip this for simple, obvious fixes – don't over-engineer
- Challenge your own work before presenting it

### 6. Autonomous Bug Fixing

- When given a bug report: just fix it. Don't ask for hand-holding
- Point at logs, errors, failing tests – then resolve them
- Zero context switching required from the user
- Go fix failing CI tests without being told how

---

## Task Management

1. **Plan First**: Write plan to `tasks/todo.md` with checkable items
2. **Verify Plan**: Check in before starting implementation
3. **Track Progress**: Mark items complete as you go
4. **Explain Changes**: High-level summary at each step
5. **Document Results**: Add review section to `tasks/todo.md`
6. **Capture Lessons**: Update `tasks/lessons.md` after corrections

---

## Core Principles

- **Simplicity First**: Make every change as simple as possible. Impact minimal code.
- **No Laziness**: Find root causes. No temporary fixes. Senior developer standards.
- **Minimal Impact**: Changes should only touch what's necessary. Avoid introducing bugs.

---

## Project-Specific Rules

### Git Workflow

- Always develop on the branch specified in the task description (`claude/...`)
- Branch name must start with `claude/` and match the session ID suffix
- Push with: `git push -u origin <branch-name>`
- Retry push up to 4 times on network failure (backoff: 2s, 4s, 8s, 16s)
- Never push to `main` or `master` directly

### Pre-Commit Checklist

```bash
ruff check .          # Lint – must pass
ruff format --check . # Format – must pass
python3 -m pytest tests/ -q --tb=short  # Tests – all must pass
```

### Code Quality Standards

- Python 3.11+, type hints on all public functions
- Max line length: 100 characters (ruff enforced)
- Docstrings on all public classes and functions
- No bare `except:` – always catch specific exceptions
- No hardcoded secrets – always use environment variables

### Security Rules

- API keys always encrypted via `services/encryption.py`
- Never log sensitive values (passwords, API keys, tokens)
- Input validation at all API boundaries
- Protected config keys in `_PROTECTED_KEYS` frozenset

### Database Rules

- New tables must be added in BOTH:
  1. `server.py:_init_db_once()`
  2. `docker/mysql-init.sql`
- Always use parameterized queries – never string interpolation in SQL
- Always use the connection pool (`services/db_pool.py`)

### Testing Rules

- Every new feature needs at least one test
- Tests must pass before committing
- Use `tests/conftest.py` fixtures for DB/Flask mocking
- Target: maintain 100% of existing tests passing

### Lambda / Loop Variable Capture

- **Never** use `lambda: func(var)` inside a loop
- **Always** use `lambda var=var: func(var)` to capture current value
- Applies to all callbacks, event handlers, and deferred calls

---

## Architecture Overview

```
trevlix/
├── server.py              # Core Flask + WebSocket app (main entry point)
├── ai_engine.py           # ML model reference implementation
├── trevlix_i18n.py        # Internationalization (DE, EN, ES, RU, PT)
├── validate_env.py        # Pre-startup environment validation
│
├── routes/                # Flask Blueprints
│   ├── auth.py            # Auth: login, register, 2FA, admin
│   ├── dashboard.py       # Static page routes
│   └── websocket.py       # WebSocket event handlers
│
├── services/              # Modular business logic
│   ├── config.py          # Pydantic configuration management
│   ├── db_pool.py         # Thread-safe MySQL connection pooling
│   ├── encryption.py      # Fernet API-key encryption
│   ├── exchange_manager.py# Multi-exchange manager (CCXT)
│   ├── indicator_cache.py # Technical indicator caching
│   ├── knowledge.py       # AI knowledge base + LLM integration
│   ├── market_data.py     # Fear/Greed, on-chain data fetchers
│   ├── notifications.py   # Discord & Telegram alerts
│   ├── risk.py            # Risk management + circuit breaker
│   ├── strategies.py      # 9 voting trading strategies
│   └── utils.py           # Shared utilities
│
├── templates/             # Jinja2 HTML templates
├── static/                # CSS, JS, assets
├── tests/                 # Pytest test suite (141 tests)
├── docker/                # Nginx config, MySQL init, SSL
└── tasks/                 # Session tracking (todo.md, lessons.md)
```

---

## Environment Variables Reference

Key variables from `.env.example`:

| Variable | Required | Description |
|----------|----------|-------------|
| `EXCHANGE` | Yes | `cryptocom\|binance\|bybit\|okx\|kucoin` |
| `API_KEY` / `API_SECRET` | Yes | Exchange API credentials |
| `MYSQL_HOST/USER/PASS/DB` | Yes | Database connection |
| `ADMIN_PASSWORD` | Yes | Min 12 chars, mixed case + special |
| `JWT_SECRET` / `SECRET_KEY` | Yes | 32+ hex chars each |
| `ENCRYPTION_KEY` | Yes | Fernet key (44 base64url chars) |
| `PAPER_TRADING` | No | `true` for simulation mode |
| `AUTO_START` | No | Start bot without admin login |
| `LLM_ENDPOINT` | No | OpenAI-compatible LLM URL |
| `DISCORD_WEBHOOK` | No | Discord notifications |
| `TELEGRAM_TOKEN` | No | Telegram notifications |

Generate keys:
```bash
# ENCRYPTION_KEY
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# JWT_SECRET / SECRET_KEY
python -c "import secrets; print(secrets.token_hex(32))"
```
