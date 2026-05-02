"""Per-domain database repositories.

Each repository takes a ``MySQLManager`` reference at construction so
it can use the manager's pooled-connection helper (``_get_conn``) and
its Fernet encryption helpers (``_enc`` / ``_dec``) without
duplicating that code. The manager keeps thin delegation wrappers on
its public API, so existing callers (``db.get_user(...)`` etc.) keep
working unchanged.
"""
