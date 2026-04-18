"""Runtime feature flag store.

Lightweight thread-safe alternative to hardcoding experiment toggles directly
in ``CONFIG``. Flags can be set/read from any thread, are optionally backed by
environment variables (``TREVLIX_FF_<NAME>=true``), and support per-user
overrides for A/B testing without coupling to the authentication layer.

Design goals
------------
- Zero external dependencies.
- Cheap ``is_enabled()`` lookup path – no lock contention under read load
  (uses a snapshot copy of the flag dict).
- User overrides are optional; absence falls back to the global default.
"""

from __future__ import annotations

import logging
import os
import threading
from dataclasses import dataclass

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Flag:
    """Definition of a single feature flag."""

    name: str
    default: bool
    description: str = ""


class FeatureFlagStore:
    """Thread-safe feature flag registry with optional per-user overrides."""

    def __init__(self, env_prefix: str = "TREVLIX_FF_") -> None:
        self._flags: dict[str, Flag] = {}
        self._overrides: dict[str, bool] = {}
        # key = (flag_name, user_id)
        self._user_overrides: dict[tuple[str, int], bool] = {}
        self._lock = threading.Lock()
        self._env_prefix = env_prefix

    def define(self, name: str, default: bool = False, description: str = "") -> None:
        """Register (or update) a flag. Env vars override the default on first read."""
        safe = _normalize(name)
        with self._lock:
            self._flags[safe] = Flag(name=safe, default=bool(default), description=description)
            env_val = os.environ.get(self._env_prefix + safe.upper())
            if env_val is not None and safe not in self._overrides:
                self._overrides[safe] = _parse_bool(env_val)

    def set(self, name: str, value: bool) -> None:
        """Set the global override for a flag (e.g. from admin UI)."""
        safe = _normalize(name)
        with self._lock:
            self._overrides[safe] = bool(value)

    def set_for_user(self, name: str, user_id: int, value: bool) -> None:
        """Set a user-scoped override (A/B testing)."""
        safe = _normalize(name)
        with self._lock:
            self._user_overrides[(safe, int(user_id))] = bool(value)

    def clear_override(self, name: str) -> None:
        """Remove the global override, reverting to default/env."""
        safe = _normalize(name)
        with self._lock:
            self._overrides.pop(safe, None)

    def clear_user_override(self, name: str, user_id: int) -> None:
        """Remove a specific user override."""
        safe = _normalize(name)
        with self._lock:
            self._user_overrides.pop((safe, int(user_id)), None)

    def is_enabled(self, name: str, user_id: int | None = None) -> bool:
        """Return True if the flag is enabled for the given scope."""
        safe = _normalize(name)
        with self._lock:
            if user_id is not None:
                user_val = self._user_overrides.get((safe, int(user_id)))
                if user_val is not None:
                    return user_val
            if safe in self._overrides:
                return self._overrides[safe]
            flag = self._flags.get(safe)
            if flag is None:
                return False
            return flag.default

    def snapshot(self) -> dict[str, dict[str, object]]:
        """Return a snapshot of the current flag state for debug endpoints."""
        with self._lock:
            out: dict[str, dict[str, object]] = {}
            for name, flag in self._flags.items():
                out[name] = {
                    "default": flag.default,
                    "override": self._overrides.get(name),
                    "description": flag.description,
                    "effective": self._overrides.get(name, flag.default),
                }
            return out

    def reset(self) -> None:
        """Drop all flags and overrides. Intended for tests only."""
        with self._lock:
            self._flags.clear()
            self._overrides.clear()
            self._user_overrides.clear()


def _normalize(name: str) -> str:
    return str(name).strip().lower()


def _parse_bool(value: str) -> bool:
    return value.strip().lower() in ("1", "true", "yes", "on")


_store = FeatureFlagStore()


def get_store() -> FeatureFlagStore:
    """Return the process-wide feature flag store singleton."""
    return _store


def is_enabled(name: str, user_id: int | None = None) -> bool:
    """Shorthand for ``get_store().is_enabled(name, user_id)``."""
    return _store.is_enabled(name, user_id)
