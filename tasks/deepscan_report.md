# Trevlix Deep Scan Report

Generated: 2026-04-09 16:11 UTC
Scope: Whole-project static scan + lightweight runtime checks

## Executive Summary

- Scanned **164 files** with **52,996 total lines** (selected source/docs/config extensions).
- Largest hotspot remains `server.py` with **4,373 lines**.
- Server surface area: **35** Socket.IO handlers and **124** app routes in `server.py`.
- Security quick-check now includes project-wide pattern scanning for `eval`, `exec`, `pickle.loads`, `yaml.load`, and `subprocess.run(..., shell=True)`.

## Command Results

| Command | Status | Exit |
|---|---|---|
| `python --version && pip --version && pytest --version` | PASS | 0 |
| `ruff check .` | PASS | 0 |
| `python -m compileall -q services routes ai_engine.py server.py trevlix_i18n.py validate_env.py` | PASS | 0 |
| `python -m pip check` | PASS | 0 |
| `pytest -q` | PASS | 0 |

### Command Output (abridged)

#### `python --version && pip --version && pytest --version`
```text
Python 3.10.19
pip 25.3 from /root/.pyenv/versions/3.10.19/lib/python3.10/site-packages/pip (python 3.10)
pytest 8.4.2
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
============================= test session starts ==============================
platform linux -- Python 3.10.19, pytest-8.4.2, pluggy-1.6.0
rootdir: /workspace/trevlix
configfile: pyproject.toml
testpaths: tests
plugins: anyio-4.13.0, cov-5.0.0
collected 458 items

tests/test_adaptive_weights.py .................                         [  3%]
tests/test_admin_user_validation.py ...                                  [  4%]
tests/test_ai_engine_init.py .....                                       [  5%]
tests/test_alert_escalation.py .............                             [  8%]
tests/test_api.py .....................s                                 [ 13%]
tests/test_app_setup.py ......                                           [ 14%]
tests/test_auth.py .................                                     [ 18%]
tests/test_auto_healing.py ..........                                    [ 20%]
tests/test_bootstrap.py ..                                               [ 20%]
tests/test_cache.py .........                                            [ 22%]
tests/test_cluster_control.py ................                           [ 26%]
tests/test_cryptopanic.py ........................................       [ 34%]
tests/test_dashboard_blueprint.py ..                                     [ 35%]
tests/test_default_config.py ...                                         [ 36%]
tests/test_encryption.py ...........                                     [ 38%]
tests/test_exchange_factory.py .........................                 [ 43%]
tests/test_fetch_markets.py ..                                           [ 44%]
tests/test_improvements.py .....................                         [ 48%]
tests/test_indicators.py ..................                              [ 52%]
tests/test_knowledge.py ............                                     [ 55%]
tests/test_module_wiring.py .....                                        [ 56%]
tests/test_notifications.py ....                    
```

## Size Hotspots (Top 10)

| Lines | File |
|---:|---|
| 4,373 | `server.py` |
| 3,166 | `static/js/dashboard.js` |
| 2,018 | `templates/index.html` |
| 1,862 | `app/core/trading_ops.py` |
| 1,833 | `app/core/db_manager.py` |
| 1,448 | `app/core/ai_engine.py` |
| 1,229 | `static/js/trevlix_translations.js` |
| 1,127 | `services/knowledge.py` |
| 1,076 | `templates/dashboard.html` |
| 1,000 | `CHANGELOG.md` |

## Security Notes

High-risk primitive scan (project-wide):

- `eval(...)`: **0** hit(s)
- `exec(...)`: **0** hit(s)
- `pickle.loads(...)`: **0** hit(s)
- `yaml.load(...)`: **0** hit(s)
- `subprocess.run(..., shell=True)`: **0** hit(s)

`subprocess.run` locations in `server.py`:

- (none)

## Production-Readiness Next Steps

1. Run scan and tests in a Python 3.11 runtime to match project metadata.
2. Ensure dependencies are installed before `pytest` to avoid false-negative CI/local conclusions.
3. Continue decomposing `server.py` into bounded modules (routes, websocket handlers, updater/admin ops).
4. Add stricter audit logs and policy checks around admin-triggered git updater flows.
