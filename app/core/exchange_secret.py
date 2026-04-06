"""Exchange secret and mode helpers extracted from the server entrypoint."""

from __future__ import annotations

from typing import Any


def reveal_and_decrypt(val: Any, *, decrypt_value_fn) -> str:
    """Decrypt SecretStr/str values from config into plain text."""
    if not val:
        return ""
    raw = val.reveal() if hasattr(val, "reveal") else val
    return decrypt_value_fn(raw) if raw else ""


def is_single_exchange_mode(*, env_exchange: str) -> bool:
    """Determine if explicit single-exchange mode is enabled via env."""
    return bool((env_exchange or "").strip())
