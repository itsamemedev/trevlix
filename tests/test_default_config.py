from __future__ import annotations

from app.core.default_config import build_default_config


def test_build_default_config_includes_expected_keys():
    cfg = build_default_config(lambda value: value)

    assert cfg["exchange"] == "cryptocom"
    assert cfg["paper_trading"] is True
    assert cfg["mysql_port"] == 3306
    assert cfg["discord_on_signals"] is True
    assert "partial_tp_levels" in cfg


def test_build_default_config_env_overrides(monkeypatch):
    monkeypatch.setenv("MYSQL_PORT", "4406")
    monkeypatch.setenv("ALLOW_REGISTRATION", "true")
    monkeypatch.setenv("DISCORD_ON_SIGNALS", "0")

    cfg = build_default_config(lambda value: value)

    assert cfg["mysql_port"] == 4406
    assert cfg["allow_registration"] is True
    assert cfg["discord_on_signals"] is False


def test_build_default_config_invalid_int_falls_back(monkeypatch):
    monkeypatch.setenv("MYSQL_PORT", "not-a-number")

    cfg = build_default_config(lambda value: value)

    assert cfg["mysql_port"] == 3306
