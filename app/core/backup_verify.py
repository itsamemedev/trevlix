"""Backup verification helper."""

from __future__ import annotations

import os


def verify_latest_backup(*, backup_dir: str, db):
    """Find latest backup file and ask DB layer to verify its checksum."""
    files = [os.path.join(backup_dir, f) for f in os.listdir(backup_dir) if f.endswith((".zip", ".enc"))]
    if not files:
        return None, "Keine Backups vorhanden"
    latest = max(files, key=os.path.getmtime)
    return db.verify_backup(latest), None
