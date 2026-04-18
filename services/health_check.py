"""Dependency health check registry.

Lets individual services register a lightweight ``check()`` callable; the
registry runs all checks (with a per-check timeout) and returns a structured
report suitable for ``/health``, ``/ready`` and ``/live`` style endpoints or
for inclusion in the existing ``/status`` response.

Each check returns either a :class:`HealthStatus` enum value or a
:class:`HealthResult` if it wants to attach a ``detail`` string. Exceptions
are caught and mapped to ``UNHEALTHY`` – a misbehaving check never crashes
the registry.
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum

log = logging.getLogger(__name__)


class HealthStatus(StrEnum):
    """Coarse health state for a dependency."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


# Order from best → worst for aggregation.
_STATUS_ORDER = {
    HealthStatus.HEALTHY: 0,
    HealthStatus.DEGRADED: 1,
    HealthStatus.UNHEALTHY: 2,
}


@dataclass
class HealthResult:
    """Outcome of a single check."""

    status: HealthStatus
    detail: str = ""
    latency_ms: float = 0.0
    name: str = ""
    meta: dict[str, object] = field(default_factory=dict)


CheckReturn = HealthStatus | HealthResult | bool
CheckFn = Callable[[], CheckReturn]


def _coerce(name: str, raw: CheckReturn, latency_ms: float) -> HealthResult:
    """Normalize arbitrary check return types into a :class:`HealthResult`."""
    if isinstance(raw, HealthResult):
        raw.name = name
        raw.latency_ms = latency_ms
        return raw
    if isinstance(raw, HealthStatus):
        return HealthResult(status=raw, latency_ms=latency_ms, name=name)
    if isinstance(raw, bool):
        return HealthResult(
            status=HealthStatus.HEALTHY if raw else HealthStatus.UNHEALTHY,
            latency_ms=latency_ms,
            name=name,
        )
    return HealthResult(
        status=HealthStatus.UNHEALTHY,
        detail=f"invalid return type: {type(raw).__name__}",
        latency_ms=latency_ms,
        name=name,
    )


@dataclass
class _CheckEntry:
    name: str
    fn: CheckFn
    timeout_s: float
    critical: bool


class HealthCheckRegistry:
    """Registry of named dependency checks."""

    def __init__(self) -> None:
        self._checks: dict[str, _CheckEntry] = {}
        self._lock = threading.Lock()

    def register(
        self,
        name: str,
        check: CheckFn,
        *,
        timeout_s: float = 2.0,
        critical: bool = True,
    ) -> None:
        """Register (or replace) a check under ``name``.

        A *critical* check contributes to the aggregate readiness status;
        non-critical checks are reported but never flip the top-level state
        to UNHEALTHY.
        """
        if not name:
            raise ValueError("name must not be empty")
        if timeout_s <= 0:
            raise ValueError("timeout_s must be > 0")
        with self._lock:
            self._checks[name] = _CheckEntry(
                name=name,
                fn=check,
                timeout_s=float(timeout_s),
                critical=bool(critical),
            )

    def unregister(self, name: str) -> None:
        """Remove a previously registered check."""
        with self._lock:
            self._checks.pop(name, None)

    def clear(self) -> None:
        """Drop all registered checks. Intended for tests."""
        with self._lock:
            self._checks.clear()

    def names(self) -> list[str]:
        """Return the names of all registered checks."""
        with self._lock:
            return sorted(self._checks)

    def _run_one(self, entry: _CheckEntry) -> HealthResult:
        start = time.perf_counter()
        result_holder: list[HealthResult] = []

        def _runner() -> None:
            try:
                raw = entry.fn()
                result_holder.append(
                    _coerce(entry.name, raw, (time.perf_counter() - start) * 1000.0)
                )
            except Exception as exc:  # noqa: BLE001 - surfaced as UNHEALTHY
                log.exception("health check %s raised", entry.name)
                result_holder.append(
                    HealthResult(
                        status=HealthStatus.UNHEALTHY,
                        detail=f"{type(exc).__name__}: {exc}",
                        latency_ms=(time.perf_counter() - start) * 1000.0,
                        name=entry.name,
                    )
                )

        thread = threading.Thread(target=_runner, daemon=True)
        thread.start()
        thread.join(entry.timeout_s)
        if thread.is_alive():
            return HealthResult(
                status=HealthStatus.UNHEALTHY,
                detail=f"timeout after {entry.timeout_s:.1f}s",
                latency_ms=entry.timeout_s * 1000.0,
                name=entry.name,
            )
        return result_holder[0]

    def check(self, only: list[str] | None = None) -> dict[str, object]:
        """Run all (or a filtered subset of) checks and return a report.

        The returned dict has ``status`` (aggregate), ``checks`` (list of
        per-check results) and ``timestamp`` (wall-clock epoch seconds).
        """
        with self._lock:
            entries = [e for e in self._checks.values() if only is None or e.name in only]

        results: list[HealthResult] = []
        aggregate = HealthStatus.HEALTHY
        for entry in entries:
            res = self._run_one(entry)
            results.append(res)
            if entry.critical and _STATUS_ORDER[res.status] > _STATUS_ORDER[aggregate]:
                aggregate = res.status

        return {
            "status": aggregate.value,
            "checks": [
                {
                    "name": r.name,
                    "status": r.status.value,
                    "detail": r.detail,
                    "latency_ms": round(r.latency_ms, 2),
                    "meta": dict(r.meta),
                }
                for r in results
            ],
            "timestamp": time.time(),
        }


_registry = HealthCheckRegistry()


def get_registry() -> HealthCheckRegistry:
    """Return the process-wide health check registry singleton."""
    return _registry


# ---------------------------------------------------------------------------
# Ready-made check factories for the three dependencies Trevlix cares about.
# ---------------------------------------------------------------------------


def db_check(db) -> CheckFn:  # type: ignore[no-untyped-def]
    """Return a health check for the MySQL pool."""

    def _run() -> HealthResult:
        try:
            with db._get_conn() as conn:
                with conn.cursor() as c:
                    c.execute("SELECT 1")
                    c.fetchone()
        except Exception as exc:  # noqa: BLE001
            return HealthResult(
                status=HealthStatus.UNHEALTHY,
                detail=f"{type(exc).__name__}: {exc}",
            )
        meta: dict[str, object] = {}
        pool = getattr(db, "_pool", None)
        stats_fn = getattr(pool, "pool_stats", None) if pool else None
        if callable(stats_fn):
            try:
                meta = dict(stats_fn())
            except Exception:  # noqa: BLE001 - stats are optional
                meta = {}
        status = HealthStatus.HEALTHY
        util = meta.get("utilization_pct")
        if isinstance(util, (int, float)) and util >= 90:
            status = HealthStatus.DEGRADED
        return HealthResult(status=status, meta=meta)

    return _run


def exchange_check(exchange_manager) -> CheckFn:  # type: ignore[no-untyped-def]
    """Return a health check for the current exchange."""

    def _run() -> HealthResult:
        try:
            ex = getattr(exchange_manager, "current", None)
            if ex is None:
                getter = getattr(exchange_manager, "get_current", None)
                if callable(getter):
                    ex = getter()
            if ex is None:
                return HealthResult(status=HealthStatus.UNHEALTHY, detail="no active exchange")
            fetch_status = getattr(ex, "fetch_status", None)
            if callable(fetch_status):
                st = fetch_status()
                if isinstance(st, dict):
                    state = str(st.get("status", "")).lower()
                    if state in ("ok", "up", "healthy"):
                        return HealthResult(status=HealthStatus.HEALTHY, detail=state)
                    if state in ("maintenance", "shutdown"):
                        return HealthResult(status=HealthStatus.DEGRADED, detail=state)
            return HealthResult(status=HealthStatus.HEALTHY)
        except Exception as exc:  # noqa: BLE001
            return HealthResult(
                status=HealthStatus.UNHEALTHY,
                detail=f"{type(exc).__name__}: {exc}",
            )

    return _run


def llm_check(llm_provider) -> CheckFn:  # type: ignore[no-untyped-def]
    """Return a health check for the configured LLM provider.

    LLM is optional – absence yields DEGRADED rather than UNHEALTHY.
    """

    def _run() -> HealthResult:
        if llm_provider is None:
            return HealthResult(status=HealthStatus.DEGRADED, detail="no LLM provider configured")
        ping = getattr(llm_provider, "ping", None)
        if callable(ping):
            try:
                ok = bool(ping())
            except Exception as exc:  # noqa: BLE001
                return HealthResult(
                    status=HealthStatus.UNHEALTHY,
                    detail=f"{type(exc).__name__}: {exc}",
                )
            return HealthResult(
                status=HealthStatus.HEALTHY if ok else HealthStatus.DEGRADED,
            )
        return HealthResult(status=HealthStatus.HEALTHY, detail="no ping() available")

    return _run
