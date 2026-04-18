"""Observability wiring – registers default health checks and baseline metrics.

Called once during app bootstrap. Keeps all observability registration in one
place so the server.py top-level stays minimal. Failures during registration
are logged and swallowed: observability must never block bot startup.
"""

from __future__ import annotations

import logging
from typing import Any

log = logging.getLogger(__name__)


def register_default_health_checks(
    *,
    db: Any,
    exchange_manager: Any = None,
    llm_provider: Any = None,
    healer: Any = None,
) -> None:
    """Register Trevlix default health checks on the global registry."""
    try:
        from services.health_check import (
            HealthResult,
            HealthStatus,
            db_check,
            exchange_check,
            get_registry,
            llm_check,
        )

        reg = get_registry()

        if db is not None:
            reg.register("database", db_check(db), timeout_s=2.0, critical=True)

        if exchange_manager is not None:
            reg.register(
                "exchange",
                exchange_check(exchange_manager),
                timeout_s=3.0,
                critical=True,
            )

        # LLM is optional – non-critical so its absence does not flip ready=false.
        reg.register(
            "llm",
            llm_check(llm_provider),
            timeout_s=2.0,
            critical=False,
        )

        if healer is not None:

            def _healer_check() -> HealthResult:
                try:
                    snap = healer.health_snapshot() or {}
                except Exception as exc:  # noqa: BLE001
                    return HealthResult(
                        status=HealthStatus.UNHEALTHY,
                        detail=f"snapshot failed: {type(exc).__name__}",
                    )
                incidents = snap.get("incidents", []) or []
                if incidents:
                    return HealthResult(
                        status=HealthStatus.DEGRADED,
                        detail=f"{len(incidents)} open incidents",
                        meta={"incidents": len(incidents)},
                    )
                return HealthResult(status=HealthStatus.HEALTHY)

            reg.register("auto_healer", _healer_check, timeout_s=1.0, critical=False)

        log.info("health checks registered: %s", ", ".join(reg.names()))
    except Exception as exc:  # noqa: BLE001 - observability must not break startup
        log.warning("failed to register default health checks: %s", exc)


def register_default_metrics() -> None:
    """Pre-register baseline metrics so they show up in /metrics immediately."""
    try:
        from services.metrics_collector import get_registry

        reg = get_registry()
        reg.counter("trevlix_http_requests_total", "HTTP requests handled")
        reg.counter("trevlix_http_errors_total", "HTTP requests that returned >=500")
        reg.histogram(
            "trevlix_http_request_duration_seconds",
            "HTTP request latency in seconds",
        )
        reg.counter("trevlix_exchange_calls_total", "Outbound exchange calls")
        reg.counter("trevlix_exchange_errors_total", "Failed exchange calls")
    except Exception as exc:  # noqa: BLE001
        log.warning("failed to register default metrics: %s", exc)


def install_http_metrics_middleware(app) -> None:  # type: ignore[no-untyped-def]
    """Install before/after-request hooks that record HTTP metrics.

    The hooks are deliberately defensive: any exception from the metric layer
    is logged and swallowed so metric bugs cannot cascade into real HTTP
    failures (observability rule #1 – never break the thing you observe).
    """
    try:
        import time

        from flask import g, request

        from services.metrics_collector import get_registry

        reg = get_registry()
        counter_all = reg.counter("trevlix_http_requests_total")
        counter_err = reg.counter("trevlix_http_errors_total")
        histogram = reg.histogram("trevlix_http_request_duration_seconds")

        @app.before_request
        def _metrics_before_request() -> None:  # noqa: ANN202
            g._metrics_start = time.perf_counter()

        @app.after_request
        def _metrics_after_request(response):  # type: ignore[no-untyped-def]
            try:
                start = getattr(g, "_metrics_start", None)
                endpoint = request.endpoint or "unknown"
                status = str(response.status_code)[:3]
                labels = {"endpoint": endpoint, "status": status}
                counter_all.inc(labels=labels)
                if response.status_code >= 500:
                    counter_err.inc(labels=labels)
                if start is not None:
                    histogram.observe(time.perf_counter() - start, labels=labels)
            except Exception as exc:  # noqa: BLE001
                log.debug("metrics middleware failed: %s", exc)
            return response

        log.info("HTTP metrics middleware installed")
    except Exception as exc:  # noqa: BLE001
        log.warning("failed to install HTTP metrics middleware: %s", exc)
