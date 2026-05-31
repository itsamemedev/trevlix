"""Regression tests for git_ops rollback + llm_providers cooldown/tokens."""

from __future__ import annotations

import subprocess

import services.git_ops as git_ops


def _cp(returncode=0, stdout="", stderr=""):
    return subprocess.CompletedProcess(
        args=["git"], returncode=returncode, stdout=stdout, stderr=stderr
    )


class TestRollbackUpdate:
    def test_apply_update_records_pre_commit(self, tmp_path, monkeypatch):
        ref = tmp_path / ".trevlix_rollback_ref"
        monkeypatch.setattr(git_ops, "_rollback_ref_path", lambda: ref)
        calls = []

        def fake_run(args, timeout=10, check=False):
            calls.append(args)
            if args[:2] == ["rev-parse", "HEAD"]:
                return _cp(stdout="abc123\n")
            return _cp()

        monkeypatch.setattr(git_ops, "_run_git", fake_run)
        git_ops.apply_update()
        assert ref.read_text().strip() == "abc123"
        assert ["pull", "--ff-only"] in calls

    def test_rollback_resets_to_recorded_commit(self, tmp_path, monkeypatch):
        ref = tmp_path / ".trevlix_rollback_ref"
        ref.write_text("deadbeef", encoding="utf-8")
        monkeypatch.setattr(git_ops, "_rollback_ref_path", lambda: ref)
        seen = {}

        def fake_run(args, timeout=10, check=False):
            seen["args"] = args
            return _cp(returncode=0)

        monkeypatch.setattr(git_ops, "_run_git", fake_run)
        assert git_ops.rollback_update() is True
        # Performs a hard reset to the recorded commit (NOT a no-op git stash).
        assert seen["args"] == ["reset", "--hard", "deadbeef"]
        # Ref file is consumed on success.
        assert not ref.exists()

    def test_rollback_without_recorded_ref_returns_false(self, tmp_path, monkeypatch):
        ref = tmp_path / ".trevlix_rollback_ref"  # does not exist
        monkeypatch.setattr(git_ops, "_rollback_ref_path", lambda: ref)
        monkeypatch.setattr(git_ops, "_run_git", lambda *a, **k: _cp())
        assert git_ops.rollback_update() is False

    def test_rollback_reset_failure_returns_false(self, tmp_path, monkeypatch):
        ref = tmp_path / ".trevlix_rollback_ref"
        ref.write_text("cafe", encoding="utf-8")
        monkeypatch.setattr(git_ops, "_rollback_ref_path", lambda: ref)
        monkeypatch.setattr(git_ops, "_run_git", lambda *a, **k: _cp(returncode=1, stderr="boom"))
        assert git_ops.rollback_update() is False


class TestLLMProviderCooldownAndTokens:
    def _provider_mgr(self, monkeypatch):
        import services.llm_providers as lp

        mgr = lp.MultiLLMProvider.__new__(lp.MultiLLMProvider)
        import threading

        mgr._lock = threading.Lock()
        mgr._providers = [
            {
                "name": "groq",
                "model": "m",
                "supports_tools": False,
                "max_tokens": 800,
                "api_key": "k",
                "endpoint": "https://example/llm",
            }
        ]
        mgr._health = {
            "groq": {
                "available": True,
                "last_success": 0.0,
                "last_error": "",
                "cooldown_until": 0.0,
                "requests": 0,
                "errors": 0,
                "tokens": 0,
            }
        }
        mgr._cache = {}
        return mgr, lp

    def test_transport_error_applies_cooldown(self, monkeypatch):
        mgr, lp = self._provider_mgr(monkeypatch)
        monkeypatch.setattr(mgr, "_get_cached", lambda k: None)

        def boom(*a, **k):
            raise TimeoutError("connect timeout")

        monkeypatch.setattr(mgr, "_call_provider", boom)
        assert mgr.chat("hi") is None
        # Provider must now be in cooldown so it is not re-hit every call.
        assert mgr._is_in_cooldown("groq") is True

    def test_call_provider_accumulates_tokens(self, monkeypatch):
        mgr, lp = self._provider_mgr(monkeypatch)

        class _Resp:
            status_code = 200

            def json(self):
                return {
                    "choices": [{"message": {"content": "hello"}}],
                    "usage": {"total_tokens": 42},
                }

        monkeypatch.setattr(lp.httpx, "post", lambda *a, **k: _Resp())
        out = mgr._call_provider(mgr._providers[0], "p", "", None, 0.3, 100)
        assert out == "hello"
        assert mgr._health["groq"]["tokens"] == 42
