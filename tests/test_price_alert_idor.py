"""Tests for price-alert IDOR protection (user-scoped delete/get)."""

from unittest.mock import MagicMock

from app.core.db_manager import MySQLManager


def _make_db_with_mock_cursor():
    """Create an MySQLManager instance with its DB calls replaced by mocks
    so we can inspect the exact SQL + parameters issued."""
    db = MySQLManager.__new__(MySQLManager)  # avoid real DB init
    cursor = MagicMock()
    cursor.rowcount = 1
    cursor.fetchall.return_value = []

    conn_cm = MagicMock()
    conn_cm.__enter__.return_value = MagicMock()
    conn_cm.__enter__.return_value.cursor.return_value.__enter__.return_value = cursor
    conn_cm.__exit__.return_value = False
    db._get_conn = lambda: conn_cm  # type: ignore[attr-defined]
    return db, cursor


class TestDeleteAlertIdor:
    def test_delete_without_user_id_is_unscoped(self):
        db, cur = _make_db_with_mock_cursor()
        ok = db.delete_alert(42)
        assert ok is True
        sql, params = cur.execute.call_args[0]
        assert "user_id" not in sql
        assert params == (42,)

    def test_delete_with_user_id_is_scoped(self):
        db, cur = _make_db_with_mock_cursor()
        ok = db.delete_alert(42, user_id=7)
        assert ok is True
        sql, params = cur.execute.call_args[0]
        assert "user_id=%s" in sql
        assert params == (42, 7)

    def test_delete_returns_false_when_no_row_matched(self):
        db, cur = _make_db_with_mock_cursor()
        cur.rowcount = 0
        assert db.delete_alert(99, user_id=7) is False


class TestGetAllAlertsScope:
    def test_unscoped_query(self):
        db, cur = _make_db_with_mock_cursor()
        db.get_all_alerts()
        sql = cur.execute.call_args[0][0]
        assert "user_id" not in sql

    def test_scoped_query(self):
        db, cur = _make_db_with_mock_cursor()
        db.get_all_alerts(user_id=7)
        args = cur.execute.call_args[0]
        sql, params = args
        assert "user_id=%s" in sql
        assert params == (7,)
