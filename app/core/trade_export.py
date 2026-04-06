"""Trade export formatting helpers."""

from __future__ import annotations

import json


def trades_to_json(trades: list[dict]) -> str:
    """Serialize trade list with UTF-8 friendly output."""
    return json.dumps(trades, ensure_ascii=False)
