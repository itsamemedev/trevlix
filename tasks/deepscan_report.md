# Trevlix Deep Scan Report

Date (UTC): 2026-04-02
Scope: Full repository static and operational scan

## Executive Summary

- Repository is feature-rich and large (42,271 lines over 91 scanned source/docs/config files).
- `server.py` is the dominant hotspot at 9,453 lines and combines many concerns.
- Linting and syntax checks passed in the current environment.
- Test execution is currently blocked by missing runtime dependencies (`numpy`).
- Security quick-scan did not find obvious dangerous patterns (`eval`, `exec`, `shell=True`, unsafe `yaml.load`, `pickle.loads`), but there are multiple `subprocess.run` calls for git-update flows.
- Environment mismatch detected: project metadata requires Python `>=3.11`, environment currently runs Python `3.10.19`.

## Commands Executed

```bash
python --version && pip --version && pytest --version
pytest -q
python -m compileall -q services routes ai_engine.py server.py trevlix_i18n.py validate_env.py
ruff check .
python -m pip check
rg -n "eval\(|exec\(|pickle\.loads|yaml\.load\(|subprocess\.|shell=True|md5\(|sha1\(" services routes ai_engine.py server.py
python - <<'PY'
# file/line distribution script
PY
python - <<'PY'
# decorator count script
PY
```

## Scan Results

### 1) Build/Lint/Syntax Health

- `ruff check .` → **pass**.
- `python -m compileall ...` → **pass**.
- `python -m pip check` → **pass** (no broken installed requirements).

### 2) Test Health

- `pytest -q` fails before collection:
  - `ModuleNotFoundError: No module named 'numpy'` from `tests/conftest.py`.

Interpretation:
- This is an environment/setup issue, not a confirmed code regression.
- The test suite cannot be fully validated until dependencies are installed and Python version aligns with project requirement.

### 3) Codebase Size & Concentration

Measured source/docs/config set:
- **91 files**, **42,271 total lines**.

Largest files:
1. `server.py` — 9,453
2. `static/js/dashboard.js` — 2,272
3. `templates/index.html` — 2,018
4. `static/js/trevlix_translations.js` — 1,217
5. `templates/dashboard.html` — 1,209
6. `services/knowledge.py` — 1,004
7. `routes/auth.py` — 959

Interpretation:
- `server.py` is a high-risk maintenance hotspot and likely a bottleneck for reliability and review velocity.

### 4) Surface Area (Handlers/Routes)

- `server.py` contains:
  - **33** `@socketio.on(...)` handlers
  - **117** Flask route decorators (`@app.route/get/post/...`)
- Blueprints:
  - `routes/auth.py`: 7 route decorators
  - `routes/dashboard.py`: 8 route decorators

Interpretation:
- A major amount of behavior remains centralized in `server.py` despite available `routes/` modules.

### 5) Security-Oriented Pattern Scan (Quick)

Pattern scan across core backend code found:
- No matches for `eval(`, `exec(`, `pickle.loads`, `yaml.load(`, `shell=True`, `md5(`, `sha1(`.
- Matches for `subprocess.run` in update/rollback functionality inside `server.py`.

Interpretation:
- Positive baseline regarding classic injection/deserialization anti-patterns.
- `subprocess.run` use is argument-list based (safer than shell strings), but operational hardening is still advisable:
  - stricter allowlist of git operations
  - structured audit logging for admin-triggered update events
  - explicit privilege boundaries around updater endpoints

### 6) Configuration/Runtime Consistency

- `pyproject.toml` requires Python `>=3.11`.
- Actual runtime during scan: Python `3.10.19`.

Risk:
- Hidden incompatibilities can appear in CI/CD or production promotion if environments are inconsistent.

## Priority Findings (Ranked)

1. **P1 – Monolithic backend core**
   - `server.py` size and mixed responsibilities increase change risk and lower testability.
2. **P1 – Incomplete validation pipeline in current environment**
   - Tests blocked due to missing deps; quality gate is currently partial.
3. **P2 – Runtime version drift**
   - Python version mismatch with declared requirement can cause subtle production issues.
4. **P2 – Git updater attack surface**
   - Admin-only flow exists but still deserves extra hardening and observability.

## Recommended Action Plan

### Next 7 days

- Align local/CI runtime to Python 3.11+.
- Install full dependencies and run:
  - `pytest -q`
  - optional `pytest --cov`
- Add CI job that fails on Python-version drift.

### Next 2–4 weeks

- Begin `server.py` decomposition by bounded context:
  - updater/admin ops
  - websocket trading handlers
  - API routes and utility concerns
- Keep behavior stable by extracting with characterization tests.

### Security hardening

- Add auditable event trail for update/rollback actions.
- Enforce strict admin checks + optional step-up auth (2FA confirm) for updater actions.
- Add explicit command timeout/error telemetry around subprocess invocations.

## Confidence & Limitations

- Confidence: **medium-high** for static structure and environment findings.
- Limitation: full behavioral confidence pending complete dependency installation and successful test execution.
