"""Audit-log persistence helper."""

from __future__ import annotations


def write_audit_entry(
    *, db, log, request_obj, action: str, detail: str = "", user_id: int = 0
) -> None:
    """Persist one audit-log entry; failures are debug-only."""
    try:
        try:
            ip = request_obj.remote_addr or "unknown"
        except RuntimeError:
            ip = "system"
        with db._get_conn() as conn:
            with conn.cursor() as c:
                c.execute(
                    "INSERT INTO audit_log (user_id,action,detail,ip) VALUES(%s,%s,%s,%s)",
                    (user_id, str(action)[:80], str(detail)[:500], str(ip)[:45]),
                )
    except Exception as exc:
        log.debug("_audit: %s", exc)
