"""Generic circuit breaker + retry policy.

Complements ``services/risk.py`` which holds trading-specific portfolio
circuit-breakers. This module is a low-level reliability primitive for
outbound calls (exchange REST, news APIs, LLM providers): it tracks
consecutive failures, opens the circuit for a cooldown window, transitions to
half-open for a probe, and closes again on success.

Includes :class:`RetryPolicy` with exponential backoff + jitter so retry logic
stops getting re-invented across ``services/*``.
"""

from __future__ import annotations

import logging
import random
import threading
import time
from collections.abc import Callable
from enum import StrEnum
from typing import TypeVar

log = logging.getLogger(__name__)

T = TypeVar("T")


class CircuitState(StrEnum):
    """Possible circuit breaker states."""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitOpenError(Exception):
    """Raised when a call is short-circuited because the breaker is open."""


class CircuitBreaker:
    """Three-state breaker with cooldown + half-open probe.

    Parameters
    ----------
    failure_threshold:
        Consecutive failures that trip the breaker into OPEN.
    recovery_timeout:
        Seconds the breaker stays OPEN before transitioning to HALF_OPEN.
    half_open_successes:
        Successful probes required in HALF_OPEN before CLOSED is restored.
    name:
        Optional label used in log output.
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        half_open_successes: int = 1,
        name: str = "breaker",
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if failure_threshold <= 0:
            raise ValueError("failure_threshold must be > 0")
        if recovery_timeout <= 0:
            raise ValueError("recovery_timeout must be > 0")
        if half_open_successes <= 0:
            raise ValueError("half_open_successes must be > 0")
        self.failure_threshold = int(failure_threshold)
        self.recovery_timeout = float(recovery_timeout)
        self.half_open_successes = int(half_open_successes)
        self.name = str(name)
        self._clock = clock
        self._state = CircuitState.CLOSED
        self._failures = 0
        self._successes = 0
        self._opened_at = 0.0
        self._lock = threading.Lock()

    @property
    def state(self) -> CircuitState:
        """Return the current state, transitioning OPEN→HALF_OPEN if due."""
        with self._lock:
            self._maybe_half_open()
            return self._state

    def _maybe_half_open(self) -> None:
        if (
            self._state is CircuitState.OPEN
            and self._clock() - self._opened_at >= self.recovery_timeout
        ):
            log.info("circuit %s: OPEN -> HALF_OPEN (probe)", self.name)
            self._state = CircuitState.HALF_OPEN
            self._successes = 0

    def allow_request(self) -> bool:
        """Return True if a call may proceed under the current state."""
        with self._lock:
            self._maybe_half_open()
            return self._state in (CircuitState.CLOSED, CircuitState.HALF_OPEN)

    def record_success(self) -> None:
        """Register a successful call."""
        with self._lock:
            if self._state is CircuitState.HALF_OPEN:
                self._successes += 1
                if self._successes >= self.half_open_successes:
                    log.info("circuit %s: HALF_OPEN -> CLOSED (recovered)", self.name)
                    self._state = CircuitState.CLOSED
                    self._failures = 0
                    self._successes = 0
            else:
                self._failures = 0

    def record_failure(self) -> None:
        """Register a failed call."""
        with self._lock:
            if self._state is CircuitState.HALF_OPEN:
                log.warning("circuit %s: HALF_OPEN -> OPEN (probe failed)", self.name)
                self._state = CircuitState.OPEN
                self._opened_at = self._clock()
                self._successes = 0
                return
            self._failures += 1
            if self._state is CircuitState.CLOSED and self._failures >= self.failure_threshold:
                log.warning(
                    "circuit %s: CLOSED -> OPEN after %d failures",
                    self.name,
                    self._failures,
                )
                self._state = CircuitState.OPEN
                self._opened_at = self._clock()

    def call(self, func: Callable[..., T], *args: object, **kwargs: object) -> T:
        """Invoke ``func`` under the breaker; raise CircuitOpenError if OPEN."""
        if not self.allow_request():
            raise CircuitOpenError(f"circuit {self.name} is OPEN")
        try:
            result = func(*args, **kwargs)
        except Exception:
            self.record_failure()
            raise
        self.record_success()
        return result

    def reset(self) -> None:
        """Force the breaker back to CLOSED. Intended for tests / admin ops."""
        with self._lock:
            self._state = CircuitState.CLOSED
            self._failures = 0
            self._successes = 0
            self._opened_at = 0.0


class RetryPolicy:
    """Exponential backoff with full jitter.

    Usage::

        policy = RetryPolicy(max_attempts=4, base_delay=0.5)
        result = policy.run(exchange.fetch_ohlcv, symbol)
    """

    def __init__(
        self,
        max_attempts: int = 3,
        base_delay: float = 0.5,
        max_delay: float = 30.0,
        backoff_factor: float = 2.0,
        jitter: bool = True,
        retry_on: tuple[type[BaseException], ...] = (Exception,),
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if max_attempts <= 0:
            raise ValueError("max_attempts must be > 0")
        if base_delay < 0:
            raise ValueError("base_delay must be >= 0")
        if max_delay < base_delay:
            raise ValueError("max_delay must be >= base_delay")
        if backoff_factor <= 1.0:
            raise ValueError("backoff_factor must be > 1.0")
        self.max_attempts = int(max_attempts)
        self.base_delay = float(base_delay)
        self.max_delay = float(max_delay)
        self.backoff_factor = float(backoff_factor)
        self.jitter = bool(jitter)
        self.retry_on = retry_on
        self._sleep = sleep

    def compute_delay(self, attempt: int) -> float:
        """Compute the delay in seconds before the given ``attempt`` (1-indexed)."""
        if attempt <= 1:
            return 0.0
        raw = self.base_delay * (self.backoff_factor ** (attempt - 2))
        capped = min(raw, self.max_delay)
        if self.jitter:
            return random.uniform(0, capped)
        return capped

    def run(
        self,
        func: Callable[..., T],
        *args: object,
        breaker: CircuitBreaker | None = None,
        **kwargs: object,
    ) -> T:
        """Execute ``func`` with retries; honor an optional breaker."""
        last_exc: BaseException | None = None
        for attempt in range(1, self.max_attempts + 1):
            if attempt > 1:
                delay = self.compute_delay(attempt)
                if delay > 0:
                    self._sleep(delay)
            try:
                if breaker is not None:
                    return breaker.call(func, *args, **kwargs)
                return func(*args, **kwargs)
            except CircuitOpenError:
                # Breaker is open – no point retrying synchronously.
                raise
            except self.retry_on as exc:
                last_exc = exc
                log.debug(
                    "retry attempt %d/%d failed: %s",
                    attempt,
                    self.max_attempts,
                    exc,
                )
        assert last_exc is not None  # noqa: S101  (defensive: loop always assigns)
        raise last_exc
