from datetime import datetime


def test_backup_scheduler_runs_once_per_day(monkeypatch):
    from app.core import trading_classes as tc

    monkeypatch.setitem(tc.CONFIG, "backup_enabled", True)
    tc.BackupScheduler._last_backup_day = None

    first = datetime(2026, 4, 10, 3, 1, 0)
    second = datetime(2026, 4, 10, 3, 2, 0)

    assert tc.BackupScheduler._should_run_now(first) is True
    assert tc.BackupScheduler._should_run_now(second) is False


def test_backup_scheduler_allows_next_day(monkeypatch):
    from app.core import trading_classes as tc

    monkeypatch.setitem(tc.CONFIG, "backup_enabled", True)
    tc.BackupScheduler._last_backup_day = None

    day_one = datetime(2026, 4, 10, 3, 1, 0)
    day_two = datetime(2026, 4, 11, 3, 1, 0)

    assert tc.BackupScheduler._should_run_now(day_one) is True
    assert tc.BackupScheduler._should_run_now(day_two) is True
