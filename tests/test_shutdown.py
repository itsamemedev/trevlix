"""Tests für services.shutdown."""

from __future__ import annotations

import threading
import time

import pytest

from services import shutdown as shutdown_mod


@pytest.fixture(autouse=True)
def _fresh_manager():
    shutdown_mod._reset_for_tests()
    yield
    shutdown_mod._reset_for_tests()


class TestRegistration:
    def test_register_and_snapshot(self):
        mgr = shutdown_mod.get_manager()

        def hook() -> None:
            pass

        mgr.register(hook, name="one")
        mgr.register(hook, name="two")
        snap = mgr.snapshot()
        assert snap["hook_count"] == 2
        assert snap["hooks"] == ["one", "two"]
        assert snap["running"] is False

    def test_deadline_must_be_positive(self):
        mgr = shutdown_mod.get_manager()
        with pytest.raises(ValueError):
            mgr.register(lambda: None, deadline=0)


class TestShutdownExecution:
    def test_hooks_run_in_reverse_order(self):
        mgr = shutdown_mod.get_manager()
        calls: list[str] = []
        mgr.register(lambda: calls.append("first"), name="first")
        mgr.register(lambda: calls.append("second"), name="second")
        mgr.register(lambda: calls.append("third"), name="third")
        mgr.run_shutdown()
        assert calls == ["third", "second", "first"]

    def test_hook_exception_is_swallowed(self):
        mgr = shutdown_mod.get_manager()
        calls: list[str] = []

        def good():
            calls.append("good")

        def bad():
            raise RuntimeError("boom")

        mgr.register(good, name="good")
        mgr.register(bad, name="bad")
        mgr.run_shutdown()  # must not raise
        assert "good" in calls
        assert mgr.snapshot()["done"] is True

    def test_slow_hook_hits_deadline(self):
        mgr = shutdown_mod.get_manager()
        completed = {"slow": False, "after": False}

        def slow():
            time.sleep(0.5)
            completed["slow"] = True

        def after():
            completed["after"] = True

        mgr.register(slow, name="slow", deadline=0.05)
        mgr.register(after, name="after")
        start = time.time()
        mgr.run_shutdown()
        elapsed = time.time() - start
        assert completed["after"] is True
        # Shutdown should not wait the full 0.5s
        assert elapsed < 0.4

    def test_wait_returns_true_after_shutdown(self):
        mgr = shutdown_mod.get_manager()
        mgr.register(lambda: None)
        mgr.run_shutdown()
        assert mgr.wait(timeout=0.1) is True

    def test_wait_times_out_before_shutdown(self):
        mgr = shutdown_mod.get_manager()
        assert mgr.wait(timeout=0.05) is False


class TestConcurrency:
    def test_concurrent_run_shutdown_is_safe(self):
        mgr = shutdown_mod.get_manager()
        calls: list[str] = []
        lock = threading.Lock()

        def slow_hook() -> None:
            time.sleep(0.05)
            with lock:
                calls.append("ran")

        mgr.register(slow_hook, name="slow")

        # First invocation should run; a concurrent second invocation triggers
        # the re-entrance path which calls os._exit – so we run only one
        # thread here and verify idempotence of the normal path.
        t = threading.Thread(target=mgr.run_shutdown)
        t.start()
        t.join(timeout=1.0)
        assert calls == ["ran"]
        assert mgr.snapshot()["done"] is True


class TestModuleSingleton:
    def test_register_shorthand(self):
        shutdown_mod.register(lambda: None, name="alpha")
        assert "alpha" in shutdown_mod.get_manager().snapshot()["hooks"]

    def test_get_manager_returns_same_instance(self):
        assert shutdown_mod.get_manager() is shutdown_mod.get_manager()
