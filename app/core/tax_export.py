"""CSV serialisation for tax report rows (extracted from server.py)."""

import csv
import io

# Characters that trigger formula evaluation in Excel/LibreOffice when they
# begin a cell. Values starting with these are prefixed with a single quote so
# the spreadsheet treats them as text (CSV / formula-injection defence).
_CSV_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def csv_safe_cell(value: object) -> str:
    """Neutralise CSV formula-injection by escaping leading dangerous chars."""
    s = "" if value is None else str(value)
    if s and s[0] in _CSV_FORMULA_PREFIXES:
        return "'" + s
    return s


def tax_rows_to_csv(rows: list[dict]) -> str:
    """Serialise tax-report rows to CSV text.

    Args:
        rows: List of flat dicts (already formatted upstream).

    Returns:
        CSV string with a header row, or empty string when ``rows`` is empty.
    """
    rows = rows or []
    if not rows:
        return ""
    all_keys: list[str] = []
    for r in rows:
        all_keys.extend(r.keys())
    all_keys = list(dict.fromkeys(all_keys))
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=all_keys, extrasaction="ignore")
    writer.writeheader()
    writer.writerows({k: csv_safe_cell(v) for k, v in r.items()} for r in rows)
    return buf.getvalue()
