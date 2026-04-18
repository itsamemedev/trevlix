"""Bounded background task queue with retry support.

Heavy work in Trevlix (backtests, tax-report generation, auto-healing scans)
currently runs either synchronously inside request handlers or in raw
``threading.Thread`` instances. This module provides a minimal bounded pool
with:

- Capped worker count (no thread explosion under load).
- Capped queue length (backpressure – submit() returns False when full).
- Optional retry policy reuse (``services.circuit_breaker.RetryPolicy``).
- Graceful shutdown with ``wait=True/False``.

Intentionally stays in-process: no Redis/Celery dependency, matching the
project's zero-infra stance.
"""

from __future__ import annotations

import logging
import queue
import threading
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger(__name__)


@dataclass
class TaskHandle:
    """Reference to a submitted task for status introspection."""

    task_id: str
    name: str
    state: str = "queued"  # queued | running | done | failed | retrying
    result: Any = None
    error: str = ""
    attempts: int = 0
    _done: threading.Event = field(default_factory=threading.Event)

    def wait(self, timeout: float | None = None) -> bool:
        """Block until the task finishes. Returns False on timeout."""
        return self._done.wait(timeout=timeout)


@dataclass
class _QueueItem:
    handle: TaskHandle
    fn: Callable[..., Any]
    args: tuple
    kwargs: dict
    retry_policy: Any | None  # services.circuit_breaker.RetryPolicy or None


class TaskQueue:
    """Fixed-size thread pool with bounded FIFO queue."""

    def __init__(
        self,
        workers: int = 2,
        max_queue: int = 64,
        name: str = "trevlix-tasks",
    ) -> None:
        if workers <= 0:
            raise ValueError("workers must be > 0")
        if max_queue <= 0:
            raise ValueError("max_queue must be > 0")
        self.name = str(name)
        self._queue: queue.Queue[_QueueItem | None] = queue.Queue(maxsize=max_queue)
        self._handles: dict[str, TaskHandle] = {}
        self._handles_lock = threading.Lock()
        self._stop = threading.Event()
        self._workers = [
            threading.Thread(
                target=self._run,
                name=f"{self.name}-{i}",
                daemon=True,
            )
            for i in range(workers)
        ]
        for w in self._workers:
            w.start()

    def submit(
        self,
        fn: Callable[..., Any],
        *args: Any,
        name: str | None = None,
        retry_policy: Any | None = None,
        **kwargs: Any,
    ) -> TaskHandle | None:
        """Enqueue a task. Returns ``None`` if the queue is full."""
        handle = TaskHandle(task_id=uuid.uuid4().hex[:12], name=name or fn.__name__)
        item = _QueueItem(
            handle=handle,
            fn=fn,
            args=args,
            kwargs=kwargs,
            retry_policy=retry_policy,
        )
        try:
            self._queue.put_nowait(item)
        except queue.Full:
            log.warning("%s: queue full, rejecting task %s", self.name, handle.name)
            return None
        with self._handles_lock:
            self._handles[handle.task_id] = handle
        return handle

    def get_handle(self, task_id: str) -> TaskHandle | None:
        """Look up a handle by id (for status polling)."""
        with self._handles_lock:
            return self._handles.get(task_id)

    def snapshot(self) -> dict[str, Any]:
        """Return a summary of pool state (queue depth, handle count)."""
        with self._handles_lock:
            states: dict[str, int] = {}
            for h in self._handles.values():
                states[h.state] = states.get(h.state, 0) + 1
        return {
            "name": self.name,
            "queue_depth": self._queue.qsize(),
            "workers": len(self._workers),
            "handles": len(self._handles) if self._handles else 0,
            "states": states,
        }

    def shutdown(self, wait: bool = True, timeout: float | None = None) -> None:
        """Stop the pool. ``wait=True`` blocks until in-flight tasks finish."""
        if self._stop.is_set():
            return
        self._stop.set()
        for _ in self._workers:
            try:
                self._queue.put_nowait(None)
            except queue.Full:
                pass
        if wait:
            for w in self._workers:
                w.join(timeout=timeout)

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                item = self._queue.get(timeout=0.5)
            except queue.Empty:
                continue
            if item is None:
                return
            try:
                self._execute(item)
            finally:
                self._queue.task_done()

    def _execute(self, item: _QueueItem) -> None:
        handle = item.handle
        handle.state = "running"
        try:
            if item.retry_policy is not None:
                # Track attempts via a wrapper so the handle reflects them.
                def wrapped(*a: Any, **kw: Any) -> Any:
                    handle.attempts += 1
                    return item.fn(*a, **kw)

                handle.result = item.retry_policy.run(wrapped, *item.args, **item.kwargs)
            else:
                handle.attempts = 1
                handle.result = item.fn(*item.args, **item.kwargs)
            handle.state = "done"
        except Exception as exc:  # noqa: BLE001 - surfaced via handle
            handle.state = "failed"
            handle.error = f"{type(exc).__name__}: {exc}"
            log.exception("task %s failed", handle.name)
        finally:
            handle._done.set()
