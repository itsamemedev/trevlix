"""Tests für services.health_check."""

from __future__ import annotations

import time

import pytest

from services.health_check import (
    HealthCheckRegistry,
    HealthResult,
    HealthStatus,
    db_check,
    exchange_check,
    get_registry,
    llm_check,
)


class TestHealthCheckRegistry:
    def test_register_and_list(self):
        reg = HealthCheckRegistry()
        reg.register("a", lambda: HealthStatus.HEALTHY)
        reg.register("b", lambda: HealthStatus.HEALTHY)
        assert reg.names() == ["a", "b"]

    def test_unregister(self):
        reg = HealthCheckRegistry()
        reg.register("a", lambda: HealthStatus.HEALTHY)
        reg.unregister("a")
        assert reg.names() == []

    def test_all_healthy_aggregate(self):
        reg = HealthCheckRegistry()
        reg.register("db", lambda: HealthStatus.HEALTHY)
        reg.register("exchange", lambda: HealthStatus.HEALTHY)
        report = reg.check()
        assert report["status"] == "healthy"
        assert len(report["checks"]) == 2

    def test_degraded_downgrades_aggregate(self):
        reg = HealthCheckRegistry()
        reg.register("a", lambda: HealthStatus.HEALTHY)
        reg.register("b", lambda: HealthStatus.DEGRADED)
        report = reg.check()
        assert report["status"] == "degraded"

    def test_unhealthy_worst_wins(self):
        reg = HealthCheckRegistry()
        reg.register("a", lambda: HealthStatus.DEGRADED)
        reg.register("b", lambda: HealthStatus.UNHEALTHY)
        report = reg.check()
        assert report["status"] == "unhealthy"

    def test_non_critical_does_not_flip_status(self):
        reg = HealthCheckRegistry()
        reg.register("db", lambda: HealthStatus.HEALTHY)
        reg.register("llm", lambda: HealthStatus.UNHEALTHY, critical=False)
        report = reg.check()
        assert report["status"] == "healthy"

    def test_bool_return_normalized(self):
        reg = HealthCheckRegistry()
        reg.register("a", lambda: True)
        reg.register("b", lambda: False)
        report = reg.check()
        statuses = {c["name"]: c["status"] for c in report["checks"]}
        assert statuses["a"] == "healthy"
        assert statuses["b"] == "unhealthy"

    def test_exception_becomes_unhealthy(self):
        reg = HealthCheckRegistry()

        def boom():
            raise RuntimeError("db down")

        reg.register("db", boom)
        report = reg.check()
        assert report["status"] == "unhealthy"
        assert "RuntimeError" in report["checks"][0]["detail"]

    def test_timeout_surface_as_unhealthy(self):
        reg = HealthCheckRegistry()

        def slow():
            time.sleep(0.5)
            return HealthStatus.HEALTHY

        reg.register("slow", slow, timeout_s=0.05)
        report = reg.check()
        assert report["status"] == "unhealthy"
        assert "timeout" in report["checks"][0]["detail"].lower()

    def test_health_result_preserved(self):
        reg = HealthCheckRegistry()
        reg.register(
            "x",
            lambda: HealthResult(status=HealthStatus.DEGRADED, detail="slow", meta={"k": 1}),
        )
        report = reg.check()
        entry = report["checks"][0]
        assert entry["status"] == "degraded"
        assert entry["detail"] == "slow"
        assert entry["meta"] == {"k": 1}
        assert entry["latency_ms"] >= 0

    def test_invalid_return_marked_unhealthy(self):
        reg = HealthCheckRegistry()
        reg.register("bad", lambda: "not-a-status")
        report = reg.check()
        assert report["checks"][0]["status"] == "unhealthy"
        assert "invalid return type" in report["checks"][0]["detail"]

    def test_only_filter(self):
        reg = HealthCheckRegistry()
        reg.register("a", lambda: HealthStatus.HEALTHY)
        reg.register("b", lambda: HealthStatus.UNHEALTHY)
        report = reg.check(only=["a"])
        names = [c["name"] for c in report["checks"]]
        assert names == ["a"]
        assert report["status"] == "healthy"

    def test_invalid_params(self):
        reg = HealthCheckRegistry()
        with pytest.raises(ValueError):
            reg.register("", lambda: True)
        with pytest.raises(ValueError):
            reg.register("x", lambda: True, timeout_s=0)

    def test_global_singleton(self):
        assert get_registry() is get_registry()


class _FakeCursor:
    def __init__(self):
        self._rows = [(1,)]

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, *_args, **_kwargs):
        pass

    def fetchone(self):
        return self._rows[0] if self._rows else None


class _FakeConn:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def cursor(self):
        return _FakeCursor()


class _FakePool:
    def pool_stats(self):
        return {
            "pool_size": 5,
            "available": 4,
            "in_use": 1,
            "utilization_pct": 20.0,
        }


class _FakeDb:
    def __init__(self, *, broken: bool = False, pool: _FakePool | None = None):
        self._broken = broken
        self._pool = pool

    def _get_conn(self):
        if self._broken:
            raise RuntimeError("no conn")
        return _FakeConn()


class TestDbCheck:
    def test_healthy(self):
        check = db_check(_FakeDb(pool=_FakePool()))
        res = check()
        assert res.status is HealthStatus.HEALTHY
        assert res.meta["utilization_pct"] == 20.0

    def test_unhealthy_on_exception(self):
        check = db_check(_FakeDb(broken=True))
        res = check()
        assert res.status is HealthStatus.UNHEALTHY

    def test_degraded_on_high_utilization(self):
        class Busy:
            def pool_stats(self):
                return {"utilization_pct": 95.0}

        check = db_check(_FakeDb(pool=Busy()))
        res = check()
        assert res.status is HealthStatus.DEGRADED


class _FakeExchange:
    def __init__(self, status: str = "ok", raise_exc: bool = False):
        self._status = status
        self._raise = raise_exc

    def fetch_status(self):
        if self._raise:
            raise ConnectionError("down")
        return {"status": self._status}


class _FakeExchangeManager:
    def __init__(self, current):
        self.current = current


class TestExchangeCheck:
    def test_no_exchange(self):
        check = exchange_check(_FakeExchangeManager(None))
        res = check()
        assert res.status is HealthStatus.UNHEALTHY

    def test_ok(self):
        check = exchange_check(_FakeExchangeManager(_FakeExchange("ok")))
        res = check()
        assert res.status is HealthStatus.HEALTHY

    def test_maintenance_degraded(self):
        check = exchange_check(_FakeExchangeManager(_FakeExchange("maintenance")))
        res = check()
        assert res.status is HealthStatus.DEGRADED

    def test_exception(self):
        check = exchange_check(_FakeExchangeManager(_FakeExchange(raise_exc=True)))
        res = check()
        assert res.status is HealthStatus.UNHEALTHY


class _FakeLlm:
    def __init__(self, ok: bool = True, raises: bool = False):
        self._ok = ok
        self._raises = raises

    def ping(self):
        if self._raises:
            raise RuntimeError("timeout")
        return self._ok


class TestLlmCheck:
    def test_none_degraded(self):
        res = llm_check(None)()
        assert res.status is HealthStatus.DEGRADED

    def test_healthy(self):
        res = llm_check(_FakeLlm(ok=True))()
        assert res.status is HealthStatus.HEALTHY

    def test_ping_returns_false(self):
        res = llm_check(_FakeLlm(ok=False))()
        assert res.status is HealthStatus.DEGRADED

    def test_exception(self):
        res = llm_check(_FakeLlm(raises=True))()
        assert res.status is HealthStatus.UNHEALTHY
