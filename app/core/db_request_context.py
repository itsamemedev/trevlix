"""Flask request-context DB connection helpers."""

from __future__ import annotations


def get_request_db_conn(*, flask_g, db, log):
    """Return request-scoped DB connection, creating it on first access."""
    try:
        if "db_conn" not in flask_g:
            flask_g.db_conn = db._conn()  # type: ignore[attr-defined]
        return flask_g.db_conn
    except RuntimeError:
        log.debug("get_db() außerhalb Request-Kontext – verwende db._get_conn() stattdessen")
        return db._conn()  # type: ignore[attr-defined]


def close_request_db_conn(*, flask_g, log) -> None:
    """Close and clear request-scoped DB connection."""
    conn = flask_g.pop("db_conn", None)
    if conn is not None:
        try:
            conn.close()
        except Exception as exc:
            log.debug("close_db_connection: %s", exc)
