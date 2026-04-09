# Trevlix Deep Scan Report

Generated: 2026-04-09 15:51 UTC
Scope: Whole-project static scan + lightweight runtime checks

## Executive Summary

- Scanned **163 files** with **52,883 total lines** (selected source/docs/config extensions).
- Largest hotspot remains `server.py` with **4,373 lines**.
- Server surface area: **35** Socket.IO handlers and **124** app routes in `server.py`.
- Security quick-check: no obvious `eval/exec/shell=True/yaml.load/pickle.loads` patterns found in core scan; `subprocess.run` is present for update/rollback flows.

## Command Results

| Command | Status | Exit |
|---|---|---|
| `python --version && pip --version && pytest --version` | PASS | 0 |
| `ruff check .` | FAIL | 1 |
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
I001 [*] Import block is un-sorted or un-formatted
 --> app/core/admin_password_policy.py:3:1
  |
1 | """Helpers for weak admin password detection."""
2 |
3 | from __future__ import annotations
  | ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  |
help: Organize imports

UP017 [*] Use `datetime.UTC` alias
    --> app/core/db_manager.py:1334:33
     |
1332 |             "sub": user_id,
1333 |             "label": label,
1334 |             "exp": datetime.now(timezone.utc) + timedelta(hours=CONFIG["jwt_expiry_hours"]),
     |                                 ^^^^^^^^^^^^
1335 |             "iat": datetime.now(timezone.utc),
1336 |         }
     |
help: Convert to `datetime.UTC` alias

UP017 [*] Use `datetime.UTC` alias
    --> app/core/db_manager.py:1335:33
     |
1333 |             "label": label,
1334 |             "exp": datetime.now(timezone.utc) + timedelta(hours=CONFIG["jwt_expiry_hours"]),
1335 |             "iat": datetime.now(timezone.utc),
     |                                 ^^^^^^^^^^^^
1336 |         }
1337 |         token = pyjwt.encode(payload, CONFIG["jwt_secret"], algorithm="HS256")
     |
help: Convert to `datetime.UTC` alias

UP017 [*] Use `datetime.UTC` alias
    --> app/core/db_manager.py:1347:42
     |
1345 |                             token[:500],
1346 |                             label,
1347 |                             datetime.now(timezone.utc)
     |                                          ^^^^^^^^^^^^
1348 |                             + timedelta(hours=CONFIG["jwt_expiry_hours"]),
1349 |                         ),
     |
help: Convert to `datetime.UTC` alias

UP017 [*] Use `datetime.UTC` alias
   --> routes/auth.py:579:49
    |
577 |                             "user_id": user["id"],
578 |                             "username": user["username"],
579 |                             "exp": datetime.now(timezone.utc) + timedelta(hours=8),
    |                                                 ^^^^^^^^^^^^
580 |                         },
581 |      
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
| 1,832 | `app/core/db_manager.py` |
| 1,448 | `app/core/ai_engine.py` |
| 1,229 | `static/js/trevlix_translations.js` |
| 1,127 | `services/knowledge.py` |
| 1,076 | `templates/dashboard.html` |
| 1,000 | `CHANGELOG.md` |

## Security Notes

`subprocess.run` locations in `server.py`:

- (none)

## Production-Readiness Next Steps

1. Run scan and tests in a Python 3.11 runtime to match project metadata.
2. Ensure dependencies are installed before `pytest` to avoid false-negative CI/local conclusions.
3. Continue decomposing `server.py` into bounded modules (routes, websocket handlers, updater/admin ops).
4. Add stricter audit logs and policy checks around admin-triggered git updater flows.

## Priorisierte Fehler- und Problemliste (nummeriert)

1. **Ruff-Linting schlägt fehl (Import-Reihenfolge)** in `app/core/admin_password_policy.py` (`I001`).
2. **Veraltete Datetime-API-Nutzung (`timezone.utc`)** in mehreren Stellen (u. a. `app/core/db_manager.py`, `routes/auth.py`) führt zu `UP017`-Verstößen.
3. **Python-Version im Laufzeitscan ist 3.10.19**, während laut Projektausrichtung 3.11 als Ziel empfohlen wird (potenziell versteckte Inkompatibilitäten).
4. **`server.py` bleibt ein Monolith (4.373 Zeilen)** mit hoher Routen-/Handler-Dichte (124 HTTP-Routen, 35 Socket-Handler) und entsprechendem Refactoring-Risiko.
5. **Sehr große Frontend- und Core-Dateien** (`static/js/dashboard.js`, `app/core/trading_ops.py`, `app/core/db_manager.py`) erhöhen Wartungsaufwand und Fehlerwahrscheinlichkeit.
6. **Sicherheits-Quickcheck ist nur heuristisch** (Pattern-Scan), es fehlt eine tiefergehende Security-Analyse (z. B. SAST-Regelsatz, Threat-Review).
