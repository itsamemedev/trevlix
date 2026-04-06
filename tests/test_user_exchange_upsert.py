from contextlib import contextmanager

import pytest

server_mod = pytest.importorskip("server", reason="server import not available in this test runtime")
MySQLManager = server_mod.MySQLManager


class _FakeCursor:
    def __init__(self, existing_row):
        self._existing_row = existing_row
        self._executed = []

    def execute(self, query, params=None):
        self._executed.append((query, params))

    def fetchone(self):
        return self._existing_row

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakeConn:
    def __init__(self, cursor):
        self._cursor = cursor

    def cursor(self):
        return self._cursor


def _build_manager_with_cursor(cursor):
    mgr = MySQLManager.__new__(MySQLManager)
    mgr._enc = lambda v: f"enc:{v}" if v else v

    @contextmanager
    def _fake_get_conn():
        yield _FakeConn(cursor)

    mgr._get_conn = _fake_get_conn
    return mgr


def test_upsert_user_exchange_keeps_existing_credentials_when_empty_payload():
    existing = {"id": 7, "api_key": "enc:old_key", "api_secret": "enc:old_secret", "passphrase": "enc:old_pass"}
    cursor = _FakeCursor(existing)
    mgr = _build_manager_with_cursor(cursor)

    ok = mgr.upsert_user_exchange(
        user_id=1,
        exchange="bybit",
        api_key="",
        api_secret="",
        enabled=True,
        is_primary=False,
        passphrase="",
    )

    assert ok is True
    update_query, update_params = cursor._executed[1]
    assert "UPDATE user_exchanges SET api_key=%s, api_secret=%s" in update_query
    assert update_params[0] == "enc:old_key"
    assert update_params[1] == "enc:old_secret"
    assert update_params[2] == "enc:old_pass"


def test_upsert_user_exchange_uses_new_credentials_when_provided():
    existing = {"id": 11, "api_key": "enc:old_key", "api_secret": "enc:old_secret", "passphrase": "enc:old_pass"}
    cursor = _FakeCursor(existing)
    mgr = _build_manager_with_cursor(cursor)

    ok = mgr.upsert_user_exchange(
        user_id=1,
        exchange="okx",
        api_key="new_key",
        api_secret="new_secret",
        enabled=True,
        is_primary=True,
        passphrase="new_pass",
    )

    assert ok is True
    update_query, update_params = cursor._executed[1]
    assert "UPDATE user_exchanges SET api_key=%s, api_secret=%s" in update_query
    assert update_params[0] == "enc:new_key"
    assert update_params[1] == "enc:new_secret"
    assert update_params[2] == "enc:new_pass"
