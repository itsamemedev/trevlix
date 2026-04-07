from app.core.app_setup import parse_session_timeout_minutes


def test_parse_session_timeout_minutes_default(monkeypatch):
    monkeypatch.delenv("SESSION_TIMEOUT_MIN", raising=False)
    assert parse_session_timeout_minutes() == 30


def test_parse_session_timeout_minutes_invalid_fallback(monkeypatch):
    monkeypatch.setenv("SESSION_TIMEOUT_MIN", "invalid")
    assert parse_session_timeout_minutes(default=45) == 45


def test_parse_session_timeout_minutes_valid(monkeypatch):
    monkeypatch.setenv("SESSION_TIMEOUT_MIN", "12")
    assert parse_session_timeout_minutes() == 12


def test_parse_session_timeout_minutes_clamps_too_small(monkeypatch):
    monkeypatch.setenv("SESSION_TIMEOUT_MIN", "0")
    assert parse_session_timeout_minutes() == 1


def test_parse_session_timeout_minutes_clamps_too_large(monkeypatch):
    monkeypatch.setenv("SESSION_TIMEOUT_MIN", "99999")
    assert parse_session_timeout_minutes() == 24 * 60


def test_parse_session_timeout_minutes_clamps_invalid_default(monkeypatch):
    monkeypatch.delenv("SESSION_TIMEOUT_MIN", raising=False)
    assert parse_session_timeout_minutes(default=-999) == 1
