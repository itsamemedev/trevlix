# Trevlix Deep Scan Report

Generated: 2026-04-02 12:35 UTC
Scope: Whole-project static scan + lightweight runtime checks

## Executive Summary

- Scanned **93 files** with **42,534 total lines** (selected source/docs/config extensions).
- Largest hotspot remains `server.py` with **9,453 lines**.
- Server surface area: **33** Socket.IO handlers and **117** app routes in `server.py`.
- Security quick-check: no obvious `eval/exec/shell=True/yaml.load/pickle.loads` patterns found in core scan; `subprocess.run` is present for update/rollback flows.

## Command Results

| Command | Status | Exit |
|---|---|---|
| `python --version && pip --version && pytest --version` | PASS | 0 |
| `ruff check .` | PASS | 0 |
| `python -m compileall -q services routes ai_engine.py server.py trevlix_i18n.py validate_env.py` | PASS | 0 |
| `python -m pip check` | PASS | 0 |
| `pytest -q` | FAIL | 4 |

### Command Output (abridged)

#### `python --version && pip --version && pytest --version`
```text
Python 3.10.19
pip 25.3 from /root/.pyenv/versions/3.10.19/lib/python3.10/site-packages/pip (python 3.10)
pytest 9.0.2
```

#### `ruff check .`
```text
All checks passed!
```

#### `python -m compileall -q services routes ai_engine.py server.py trevlix_i18n.py validate_env.py`
```text
(no output)
```

#### `python -m pip check`
```text
No broken requirements found.
```

#### `pytest -q`
```text
ImportError while loading conftest '/workspace/trevlix/tests/conftest.py'.
tests/conftest.py:13: in <module>
    import numpy as np
E   ModuleNotFoundError: No module named 'numpy'
```

## Size Hotspots (Top 10)

| Lines | File |
|---:|---|
| 9,453 | `server.py` |
| 2,272 | `static/js/dashboard.js` |
| 2,018 | `templates/index.html` |
| 1,217 | `static/js/trevlix_translations.js` |
| 1,209 | `templates/dashboard.html` |
| 1,004 | `services/knowledge.py` |
| 959 | `routes/auth.py` |
| 943 | `templates/INSTALLATION.html` |
| 881 | `static/css/dashboard.css` |
| 799 | `ai_engine.py` |

## Security Notes

`subprocess.run` locations in `server.py`:

- `server.py:7693`
- `server.py:7697`
- `server.py:7701`
- `server.py:7736`
- `server.py:7764`

## Production-Readiness Next Steps

1. Run scan and tests in a Python 3.11 runtime to match project metadata.
2. Ensure dependencies are installed before `pytest` to avoid false-negative CI/local conclusions.
3. Continue decomposing `server.py` into bounded modules (routes, websocket handlers, updater/admin ops).
4. Add stricter audit logs and policy checks around admin-triggered git updater flows.
