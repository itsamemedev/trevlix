"""Regression tests: API token revocation + weak admin-password detection."""

from __future__ import annotations

import time
from contextlib import contextmanager

import pytest

from app.core import db_manager
from app.core.admin_password_policy import is_admin_password_weak
from app.core.repositories.user_repo import UserRepository

jwt = pytest.importorskip("jwt")

_SECRET = "test-jwt-secret-32-bytes-hex-value"


class _FakeCursor:
    def __init__(self, row):
        self._row = row
        self.executed = None

    def execute(self, query, params=None):
        self.executed = (query, params)

    def fetchone(self):
        return self._row

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class _FakeConn:
    def __init__(self, row):
        self._row = row

    def cursor(self):
        return _FakeCursor(self._row)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class _FakeManager:
    """Minimal stand-in for MySQLManager exposing _get_conn."""

    def __init__(self, row):
        self._row = row

    @contextmanager
    def _get_conn(self):
        yield _FakeConn(self._row)


@pytest.fixture
def jwt_env(monkeypatch):
    import logging

    monkeypatch.setattr(db_manager, "JWT_AVAILABLE", True, raising=False)
    monkeypatch.setattr(db_manager, "pyjwt", jwt, raising=False)
    monkeypatch.setattr(db_manager, "CONFIG", {"jwt_secret": _SECRET}, raising=False)
    monkeypatch.setattr(db_manager, "log", logging.getLogger("test"), raising=False)


def _make_token(uid: int = 1) -> str:
    return jwt.encode({"sub": str(uid), "exp": int(time.time()) + 3600}, _SECRET, algorithm="HS256")


def test_active_token_authenticates(jwt_env):
    repo = UserRepository(_FakeManager({"active": 1}))
    assert repo.verify_api_token(_make_token(1)) == 1


def test_revoked_token_rejected(jwt_env):
    # active=0 row must NOT authenticate even though the JWT is cryptographically valid.
    repo = UserRepository(_FakeManager({"active": 0}))
    assert repo.verify_api_token(_make_token(1)) is None


def test_deleted_token_rejected(jwt_env):
    # No DB row at all (token deleted) -> reject.
    repo = UserRepository(_FakeManager(None))
    assert repo.verify_api_token(_make_token(1)) is None


def test_tampered_token_rejected(jwt_env):
    repo = UserRepository(_FakeManager({"active": 1}))
    assert repo.verify_api_token(_make_token(1) + "x") is None


class TestWeakAdminPassword:
    def test_missing_is_weak(self):
        assert is_admin_password_weak(None) is True
        assert is_admin_password_weak("") is True

    def test_known_defaults_case_insensitive(self):
        for pw in ("admin", "Admin", "ADMIN", "Password", "TREVLIX", " test "):
            assert is_admin_password_weak(pw) is True, pw

    def test_strong_password_ok(self):
        assert is_admin_password_weak("Xy7$kP2mQ9!vR4w") is False
