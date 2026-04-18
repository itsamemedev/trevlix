"""Tests für services.feature_flags."""

from __future__ import annotations

import pytest

from services.feature_flags import FeatureFlagStore, get_store, is_enabled


@pytest.fixture
def store() -> FeatureFlagStore:
    return FeatureFlagStore(env_prefix="TEST_FF_")


class TestFlagDefinition:
    def test_define_default_false(self, store):
        store.define("experimental")
        assert store.is_enabled("experimental") is False

    def test_define_default_true(self, store):
        store.define("new_ui", default=True)
        assert store.is_enabled("new_ui") is True

    def test_unknown_flag_returns_false(self, store):
        assert store.is_enabled("never_defined") is False

    def test_redefine_updates_metadata(self, store):
        store.define("f", default=False, description="v1")
        store.define("f", default=True, description="v2")
        snap = store.snapshot()
        assert snap["f"]["description"] == "v2"

    def test_name_is_normalized(self, store):
        store.define("  MyFlag  ", default=True)
        assert store.is_enabled("myflag") is True
        assert store.is_enabled("MYFLAG") is True


class TestGlobalOverride:
    def test_set_overrides_default(self, store):
        store.define("f", default=False)
        store.set("f", True)
        assert store.is_enabled("f") is True

    def test_clear_override_reverts(self, store):
        store.define("f", default=False)
        store.set("f", True)
        store.clear_override("f")
        assert store.is_enabled("f") is False


class TestUserOverrides:
    def test_user_override_beats_global(self, store):
        store.define("f", default=False)
        store.set("f", True)
        store.set_for_user("f", user_id=7, value=False)
        assert store.is_enabled("f") is True  # other users see global
        assert store.is_enabled("f", user_id=7) is False

    def test_user_override_without_global(self, store):
        store.define("f", default=False)
        store.set_for_user("f", user_id=1, value=True)
        assert store.is_enabled("f", user_id=1) is True
        assert store.is_enabled("f", user_id=2) is False

    def test_clear_user_override(self, store):
        store.define("f", default=False)
        store.set_for_user("f", 1, True)
        store.clear_user_override("f", 1)
        assert store.is_enabled("f", user_id=1) is False


class TestEnvOverride:
    def test_env_prefix_override(self, monkeypatch):
        monkeypatch.setenv("TEST_FF_BETA", "true")
        s = FeatureFlagStore(env_prefix="TEST_FF_")
        s.define("beta", default=False)
        assert s.is_enabled("beta") is True

    def test_env_false_values(self, monkeypatch):
        monkeypatch.setenv("TEST_FF_FOO", "no")
        s = FeatureFlagStore(env_prefix="TEST_FF_")
        s.define("foo", default=True)
        assert s.is_enabled("foo") is False


class TestSnapshot:
    def test_snapshot_reports_state(self, store):
        store.define("a", default=True, description="flag a")
        store.define("b", default=False)
        store.set("b", True)
        snap = store.snapshot()
        assert snap["a"]["effective"] is True
        assert snap["b"]["effective"] is True
        assert snap["b"]["override"] is True
        assert snap["a"]["override"] is None


class TestReset:
    def test_reset_clears_everything(self, store):
        store.define("x", default=True)
        store.set("x", False)
        store.set_for_user("x", 1, True)
        store.reset()
        assert store.is_enabled("x") is False
        assert store.snapshot() == {}


class TestModuleSingleton:
    def test_get_store_returns_same_instance(self):
        assert get_store() is get_store()

    def test_module_level_is_enabled(self):
        s = get_store()
        s.reset()
        s.define("module_test", default=True)
        try:
            assert is_enabled("module_test") is True
        finally:
            s.reset()
