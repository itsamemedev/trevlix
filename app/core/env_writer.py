"""Atomic mutation of the project ``.env`` file.

The Flask admin UI lets operators rotate secrets and toggle feature
flags at runtime. Persisting that to disk requires a small amount of
care: regex-validate the key, strip newline injection from the value,
write through a tempfile, then atomic-rename. Kept in its own module
so the dirty I/O does not live in ``server.py``.
"""

from __future__ import annotations

import os
import re
import tempfile
from typing import Any

_ENV_KEY_PATTERN = re.compile(r"^[A-Z_][A-Z0-9_]*$")


def set_env_var(key: str, value: str, *, log: Any, env_path: str = ".env") -> None:
    """Insert or update a single ``KEY=VALUE`` pair in ``env_path``.

    No-op if ``env_path`` does not exist – we never create a fresh
    ``.env`` from inside the running app, that is the operator's job.
    The key is validated against ``[A-Z_][A-Z0-9_]*`` to prevent regex
    injection through user-supplied admin payloads. ``\\n`` and ``\\r``
    are stripped from ``value`` to defend against value-side injection.

    Writes go through ``tempfile.mkstemp`` + ``os.replace`` so a crash
    mid-write cannot leave a half-written ``.env``.
    """
    if not os.path.exists(env_path):
        return
    if not _ENV_KEY_PATTERN.match(key):
        log.warning("set_env_var: invalid key %r", key)
        return
    value = value.replace("\n", "").replace("\r", "")
    with open(env_path) as f:
        txt = f.read()
    escaped_key = re.escape(key)
    if re.search(f"^{escaped_key}=", txt, re.M):
        txt = re.sub(f"^{escaped_key}=.*$", f"{key}={value}", txt, flags=re.M)
    else:
        txt += f"\n{key}={value}"
    env_dir = os.path.dirname(os.path.abspath(env_path))
    fd, tmp_path = tempfile.mkstemp(dir=env_dir, prefix=".env.tmp.")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(txt)
        os.replace(tmp_path, env_path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise
