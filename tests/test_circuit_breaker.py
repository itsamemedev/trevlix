"""Tests für services.circuit_breaker."""

from __future__ import annotations

import pytest

from services.circuit_breaker import (
    CircuitBreaker,
    CircuitOpenError,
    CircuitState,
    RetryPolicy,
)


class FakeClock:
    def __init__(self, start: float = 0.0):
        self.t = float(start)

    def __call__(self) -> float:
        return self.t

    def advance(self, delta: float) -> None:
        self.t += float(delta)


class TestCircuitBreaker:
    def test_closed_allows_calls(self):
        cb = CircuitBreaker()
        assert cb.allow_request() is True
        assert cb.state is CircuitState.CLOSED

    def test_opens_after_threshold(self):
        clock = FakeClock()
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=10, clock=clock)
        for _ in range(3):
            cb.record_failure()
        assert cb.state is CircuitState.OPEN
        assert cb.allow_request() is False

    def test_half_open_after_recovery(self):
        clock = FakeClock()
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=5, clock=clock)
        cb.record_failure()
        assert cb.state is CircuitState.OPEN
        clock.advance(6)
        assert cb.state is CircuitState.HALF_OPEN
        assert cb.allow_request() is True

    def test_half_open_closes_on_success(self):
        clock = FakeClock()
        cb = CircuitBreaker(
            failure_threshold=1,
            recovery_timeout=5,
            half_open_successes=2,
            clock=clock,
        )
        cb.record_failure()
        clock.advance(6)
        assert cb.state is CircuitState.HALF_OPEN
        cb.record_success()
        assert cb.state is CircuitState.HALF_OPEN  # still need 1 more
        cb.record_success()
        assert cb.state is CircuitState.CLOSED

    def test_half_open_reopens_on_failure(self):
        clock = FakeClock()
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=5, clock=clock)
        cb.record_failure()
        clock.advance(6)
        assert cb.state is CircuitState.HALF_OPEN
        cb.record_failure()
        assert cb.state is CircuitState.OPEN

    def test_success_resets_failure_count(self):
        clock = FakeClock()
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=5, clock=clock)
        cb.record_failure()
        cb.record_failure()
        cb.record_success()
        cb.record_failure()
        cb.record_failure()
        # Only 2 consecutive failures after the success - still closed.
        assert cb.state is CircuitState.CLOSED

    def test_call_rejects_when_open(self):
        clock = FakeClock()
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=5, clock=clock)
        cb.record_failure()
        with pytest.raises(CircuitOpenError):
            cb.call(lambda: "never")

    def test_call_records_success(self):
        cb = CircuitBreaker()
        assert cb.call(lambda: 42) == 42
        assert cb.state is CircuitState.CLOSED

    def test_call_records_failure(self):
        clock = FakeClock()
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=5, clock=clock)

        def boom():
            raise RuntimeError("nope")

        with pytest.raises(RuntimeError):
            cb.call(boom)
        assert cb.state is CircuitState.OPEN

    def test_reset(self):
        clock = FakeClock()
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=5, clock=clock)
        cb.record_failure()
        cb.reset()
        assert cb.state is CircuitState.CLOSED

    def test_invalid_params(self):
        with pytest.raises(ValueError):
            CircuitBreaker(failure_threshold=0)
        with pytest.raises(ValueError):
            CircuitBreaker(recovery_timeout=0)
        with pytest.raises(ValueError):
            CircuitBreaker(half_open_successes=0)


class TestRetryPolicy:
    def test_succeeds_first_try(self):
        policy = RetryPolicy(max_attempts=3, base_delay=0.01)
        calls = [0]

        def fn():
            calls[0] += 1
            return "ok"

        assert policy.run(fn) == "ok"
        assert calls[0] == 1

    def test_retries_until_success(self):
        policy = RetryPolicy(max_attempts=3, base_delay=0.0, jitter=False, sleep=lambda _: None)
        calls = [0]

        def fn():
            calls[0] += 1
            if calls[0] < 3:
                raise ValueError("flaky")
            return "ok"

        assert policy.run(fn) == "ok"
        assert calls[0] == 3

    def test_raises_after_exhaustion(self):
        policy = RetryPolicy(max_attempts=2, base_delay=0.0, jitter=False, sleep=lambda _: None)

        def fn():
            raise ValueError("broken")

        with pytest.raises(ValueError):
            policy.run(fn)

    def test_compute_delay_no_jitter(self):
        policy = RetryPolicy(
            max_attempts=5,
            base_delay=1.0,
            backoff_factor=2.0,
            jitter=False,
            sleep=lambda _: None,
        )
        assert policy.compute_delay(1) == 0.0
        assert policy.compute_delay(2) == pytest.approx(1.0)
        assert policy.compute_delay(3) == pytest.approx(2.0)
        assert policy.compute_delay(4) == pytest.approx(4.0)

    def test_max_delay_cap(self):
        policy = RetryPolicy(
            max_attempts=10,
            base_delay=1.0,
            max_delay=5.0,
            backoff_factor=2.0,
            jitter=False,
            sleep=lambda _: None,
        )
        assert policy.compute_delay(10) == pytest.approx(5.0)

    def test_retry_on_filter(self):
        policy = RetryPolicy(
            max_attempts=3,
            base_delay=0.0,
            retry_on=(ValueError,),
            jitter=False,
            sleep=lambda _: None,
        )

        def fn():
            raise RuntimeError("not-matched")

        with pytest.raises(RuntimeError):
            policy.run(fn)

    def test_breaker_short_circuit_not_retried(self):
        clock = FakeClock()
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=60, clock=clock)
        cb.record_failure()

        policy = RetryPolicy(max_attempts=5, base_delay=0.0, jitter=False, sleep=lambda _: None)
        calls = [0]

        def fn():
            calls[0] += 1
            return "ok"

        with pytest.raises(CircuitOpenError):
            policy.run(fn, breaker=cb)
        assert calls[0] == 0

    def test_invalid_params(self):
        with pytest.raises(ValueError):
            RetryPolicy(max_attempts=0)
        with pytest.raises(ValueError):
            RetryPolicy(base_delay=-1)
        with pytest.raises(ValueError):
            RetryPolicy(base_delay=10, max_delay=1)
        with pytest.raises(ValueError):
            RetryPolicy(backoff_factor=1.0)
