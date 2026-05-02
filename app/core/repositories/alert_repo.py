"""Price alert repository extracted from MySQLManager.

Per-row CRUD for the ``price_alerts`` table: add/list-active/trigger/
delete/get-all (with optional user-scoping for IDOR protection).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.core.db_manager import MySQLManager


def _module():
    from app.core import db_manager as _m

    return _m


class AlertRepository:
    """Per-row CRUD for price_alerts."""

    def __init__(self, manager: MySQLManager) -> None:
        self._m = manager

    def add_alert(self, symbol: str, target: float, direction: str, user_id: int = 1) -> int:
        log = _module().log
        try:
            with self._m._get_conn() as conn:
                with conn.cursor() as c:
                    c.execute(
                        "INSERT INTO price_alerts (user_id,symbol,target_price,direction) "
                        "VALUES(%s,%s,%s,%s)",
                        (user_id, symbol, target, direction),
                    )
                    aid = c.lastrowid
            return aid
        except Exception as e:
            log.error(f"add_alert: {e}")
            return -1

    def get_active_alerts(self) -> list[dict]:
        log = _module().log
        try:
            with self._m._get_conn() as conn:
                with conn.cursor() as c:
                    c.execute("SELECT * FROM price_alerts WHERE triggered=0 LIMIT 500")
                    rows = c.fetchall()
            return [dict(r) for r in rows]
        except Exception as e:
            log.error(f"get_active_alerts: {e}")
            return []

    def trigger_alert(self, aid: int):
        log = _module().log
        try:
            with self._m._get_conn() as conn:
                with conn.cursor() as c:
                    c.execute(
                        "UPDATE price_alerts SET triggered=1,triggered_at=NOW() WHERE id=%s",
                        (aid,),
                    )
        except Exception as e:
            log.error(f"trigger_alert({aid}): {e}")

    def delete_alert(self, aid: int, user_id: int | None = None) -> bool:
        """Delete a price alert. ``user_id`` scope = IDOR protection."""
        log = _module().log
        try:
            with self._m._get_conn() as conn:
                with conn.cursor() as c:
                    if user_id is not None:
                        c.execute(
                            "DELETE FROM price_alerts WHERE id=%s AND user_id=%s",
                            (aid, user_id),
                        )
                    else:
                        c.execute("DELETE FROM price_alerts WHERE id=%s", (aid,))
                    return bool(c.rowcount)
        except Exception as e:
            log.error(f"delete_alert({aid}): {e}")
            return False

    def get_all_alerts(self, user_id: int | None = None) -> list[dict]:
        """Return recent price alerts (optional user scope)."""
        log = _module().log
        try:
            with self._m._get_conn() as conn:
                with conn.cursor() as c:
                    if user_id is not None:
                        c.execute(
                            "SELECT * FROM price_alerts WHERE user_id=%s "
                            "ORDER BY created_at DESC LIMIT 50",
                            (user_id,),
                        )
                    else:
                        c.execute(
                            "SELECT * FROM price_alerts ORDER BY created_at DESC LIMIT 50"
                        )
                    rows = c.fetchall()
            result = []
            for r in rows:
                d = dict(r)
                for k in ("created_at", "triggered_at"):
                    if k in d and hasattr(d.get(k), "isoformat"):
                        d[k] = d[k].isoformat() if d[k] else None
                result.append(d)
            return result
        except Exception as e:
            log.error(f"get_all_alerts: {e}")
            return []
