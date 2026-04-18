"""Graceful shutdown coordinator.

Binds SIGTERM/SIGINT handlers to a single ordered list of shutdown callbacks
so the trading bot can flush metrics, close DB connections and stop thread
pools in a deterministic order when the container/orchestrator sends a
termination signal.

Design
------
- One process-wide registry. Callbacks run in reverse registration order so
  high-level subsystems are torn down before low-level ones (mirrors
  ``atexit`` semantics but with an explicit ordering contract).
- Each callback gets a ``deadline`` (seconds). A callback that exceeds its
  deadline is logged and skipped – never blocks the rest of the shutdown.
- Idempotent: a second signal during shutdown triggers a hard exit via
  :func:`os._exit` to avoid hanging forever when operators lose patience.
- No hard signal coupling – ``register`` works even when no signal handler
  is installed (useful in tests and in the Flask dev server).
"""

from __future__ import annotations

import logging
import os
import signal
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

log = logging.getLogger(__name__)

ShutdownFn = Callable[[], Any]


@dataclass
class _Hook:
    name: str
    fn: ShutdownFn
    deadline: float


class ShutdownManager:
    """Orchestrates orderly shutdown of registered subsystems."""

    def __init__(self) -> None:
        self._hooks: list[_Hook] = []
        self._lock = threading.Lock()
        self._running = False
        self._done = threading.Event()
        self._signals_installed = False

    def register(
        self,
        fn: ShutdownFn,
        *,
        name: str | None = None,
        deadline: float = 5.0,
    ) -> None:
        """Register a callback to run during shutdown.

        Later registrations run first (LIFO) – this matches the usual
        "compose up, tear down" lifecycle.
        """
        if deadline <= 0:
            raise ValueError("deadline must be > 0")
        hook = _Hook(name=name or getattr(fn, "__name__", "hook"), fn=fn, deadline=deadline)
        with self._lock:
            self._hooks.append(hook)

    def install_signal_handlers(
        self, signals: tuple[int, ...] = (signal.SIGTERM, signal.SIGINT)
    ) -> None:
        """Bind ``run_shutdown`` to the given signals (SIGTERM+SIGINT by default).

        Safe to call multiple times – second call is a no-op. Signal handlers
        can only be installed from the main thread, matching CPython's rules.
        """
        with self._lock:
            if self._signals_installed:
                return
            self._signals_installed = True
        for sig in signals:
            try:
                signal.signal(sig, self._handle_signal)
            except (ValueError, OSError) as exc:
                # Main-thread-only restriction; log and continue.
                log.debug("cannot install signal %s handler: %s", sig, exc)

    def run_shutdown(self, *, reason: str = "shutdown") -> None:
        """Run all registered hooks in reverse order. Safe to call concurrently."""
        with self._lock:
            if self._running:
                # Second invocation during an active shutdown – force-exit
                # so operators don't have to kill -9.
                log.warning("shutdown re-entered (reason=%s) – forcing exit", reason)
                os._exit(2)
            self._running = True
            hooks = list(reversed(self._hooks))

        log.info("shutdown initiated (reason=%s, hooks=%d)", reason, len(hooks))
        for hook in hooks:
            self._run_one(hook)
        self._done.set()
        log.info("shutdown complete")

    def wait(self, timeout: float | None = None) -> bool:
        """Block until shutdown completes. Returns False on timeout."""
        return self._done.wait(timeout=timeout)

    def snapshot(self) -> dict[str, Any]:
        """Return registry state for debug/monitoring endpoints."""
        with self._lock:
            return {
                "running": self._running,
                "done": self._done.is_set(),
                "hook_count": len(self._hooks),
                "hooks": [h.name for h in self._hooks],
            }

    def _run_one(self, hook: _Hook) -> None:
        log.info("shutdown hook: %s (deadline=%.1fs)", hook.name, hook.deadline)
        result: dict[str, BaseException | None] = {"exc": None}

        def _call() -> None:
            try:
                hook.fn()
            except BaseException as exc:  # noqa: BLE001 - we surface via result
                result["exc"] = exc

        t = threading.Thread(target=_call, daemon=True, name=f"shutdown-{hook.name}")
        t.start()
        t.join(timeout=hook.deadline)
        if t.is_alive():
            log.warning(
                "shutdown hook %s exceeded deadline (%.1fs), skipping",
                hook.name,
                hook.deadline,
            )
            return
        if result["exc"] is not None:
            log.warning("shutdown hook %s raised: %s", hook.name, result["exc"])

    def _handle_signal(self, signum: int, _frame: Any) -> None:
        self.run_shutdown(reason=f"signal_{signum}")


_manager = ShutdownManager()


def get_manager() -> ShutdownManager:
    """Return the process-wide shutdown manager singleton."""
    return _manager


def register(fn: ShutdownFn, *, name: str | None = None, deadline: float = 5.0) -> None:
    """Shorthand for ``get_manager().register(fn, name=name, deadline=deadline)``."""
    _manager.register(fn, name=name, deadline=deadline)


def _reset_for_tests() -> None:
    """Clear registered hooks. Intended for tests only."""
    global _manager
    _manager = ShutdownManager()
    # Give the clock a tick so subsequent tests see a distinct manager.
    time.sleep(0)
