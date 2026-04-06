"""Tax-report export helpers."""

from __future__ import annotations

import csv
import io


def tax_rows_to_csv(rows: list[dict]) -> str:
    """Convert tax rows into CSV text with dynamic header union."""
    buf = io.StringIO()
    if rows:
        all_keys = list(dict.fromkeys(k for row in rows for k in row.keys()))
        writer = csv.DictWriter(buf, fieldnames=all_keys, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    return buf.getvalue()
