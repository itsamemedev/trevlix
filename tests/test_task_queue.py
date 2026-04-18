"""Tests für services.task_queue."""

from __future__ import annotations

import threading
import time

import pytest

from services.task_queue import TaskQueue


class TestTaskQueueBasics:
    def test_submit_runs_task(self):
        q = TaskQueue(workers=1, max_queue=4)
        try:
            handle = q.submit(lambda: 42)
            assert handle is not None
            assert handle.wait(timeout=2.0) is True
            assert handle.state == "done"
            assert handle.result == 42
        finally:
            q.shutdown(timeout=2.0)

    def test_submit_with_args(self):
        q = TaskQueue(workers=1)
        try:
            handle = q.submit(lambda a, b: a + b, 2, 3)
            handle.wait(2.0)
            assert handle.result == 5
        finally:
            q.shutdown(timeout=2.0)

    def test_submit_with_kwargs(self):
        q = TaskQueue(workers=1)
        try:

            def f(a, *, b):
                return a * b

            handle = q.submit(f, 3, b=4)
            handle.wait(2.0)
            assert handle.result == 12
        finally:
            q.shutdown(timeout=2.0)

    def test_failed_task_surfaces_error(self):
        q = TaskQueue(workers=1)
        try:

            def boom():
                raise ValueError("nope")

            handle = q.submit(boom)
            handle.wait(2.0)
            assert handle.state == "failed"
            assert "ValueError" in handle.error
            assert "nope" in handle.error
        finally:
            q.shutdown(timeout=2.0)

    def test_task_name_uses_fn_name(self):
        q = TaskQueue(workers=1)
        try:

            def my_job():
                return 1

            handle = q.submit(my_job)
            assert handle.name == "my_job"
        finally:
            q.shutdown(timeout=2.0)

    def test_custom_task_name(self):
        q = TaskQueue(workers=1)
        try:
            handle = q.submit(lambda: 1, name="custom")
            assert handle.name == "custom"
        finally:
            q.shutdown(timeout=2.0)


class TestBackpressure:
    def test_full_queue_rejects_submissions(self):
        block = threading.Event()

        def slow():
            block.wait(timeout=2.0)
            return 1

        q = TaskQueue(workers=1, max_queue=1)
        try:
            # Worker picks up task, queue is empty again, so submit another.
            q.submit(slow)
            # Give worker a moment to grab the first task.
            time.sleep(0.05)
            # Now queue has 1 slot, fill it and then overflow.
            h1 = q.submit(lambda: 2)
            h2 = q.submit(lambda: 3)  # queue full
            assert h1 is not None
            assert h2 is None
        finally:
            block.set()
            q.shutdown(timeout=2.0)


class TestHandles:
    def test_get_handle(self):
        q = TaskQueue(workers=1)
        try:
            handle = q.submit(lambda: 1)
            handle.wait(2.0)
            looked_up = q.get_handle(handle.task_id)
            assert looked_up is handle
        finally:
            q.shutdown(timeout=2.0)

    def test_get_handle_unknown_returns_none(self):
        q = TaskQueue(workers=1)
        try:
            assert q.get_handle("does-not-exist") is None
        finally:
            q.shutdown(timeout=2.0)

    def test_snapshot_reports_state(self):
        q = TaskQueue(workers=1, max_queue=4, name="pool-x")
        try:
            handle = q.submit(lambda: 1)
            handle.wait(2.0)
            snap = q.snapshot()
            assert snap["name"] == "pool-x"
            assert snap["workers"] == 1
            assert snap["handles"] >= 1
            assert snap["states"].get("done", 0) >= 1
        finally:
            q.shutdown(timeout=2.0)


class TestRetryPolicy:
    def test_retry_policy_invoked(self):
        from services.circuit_breaker import RetryPolicy

        attempts = {"n": 0}

        def flaky():
            attempts["n"] += 1
            if attempts["n"] < 3:
                raise RuntimeError("transient")
            return "ok"

        policy = RetryPolicy(max_attempts=5, base_delay=0.001, jitter=False)
        q = TaskQueue(workers=1)
        try:
            handle = q.submit(flaky, retry_policy=policy)
            handle.wait(5.0)
            assert handle.state == "done"
            assert handle.result == "ok"
            assert handle.attempts == 3
        finally:
            q.shutdown(timeout=2.0)


class TestShutdown:
    def test_shutdown_is_idempotent(self):
        q = TaskQueue(workers=1)
        q.shutdown(timeout=2.0)
        q.shutdown(timeout=2.0)  # second call must not raise

    def test_shutdown_waits_for_in_flight(self):
        q = TaskQueue(workers=1)
        handle = q.submit(lambda: time.sleep(0.05) or "done")
        q.shutdown(wait=True, timeout=2.0)
        assert handle.state == "done"


class TestValidation:
    def test_workers_must_be_positive(self):
        with pytest.raises(ValueError):
            TaskQueue(workers=0)

    def test_max_queue_must_be_positive(self):
        with pytest.raises(ValueError):
            TaskQueue(workers=1, max_queue=0)
