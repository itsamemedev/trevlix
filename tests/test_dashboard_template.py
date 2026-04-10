from __future__ import annotations

import re
from collections import Counter
from pathlib import Path


def test_dashboard_template_has_unique_ids():
    html = Path("templates/dashboard.html").read_text(encoding="utf-8")
    ids = re.findall(r'id="([^"]+)"', html)
    duplicates = {k: v for k, v in Counter(ids).items() if v > 1}
    assert duplicates == {}


def test_dashboard_template_contains_arb_count_and_toggle_ids():
    html = Path("templates/dashboard.html").read_text(encoding="utf-8")
    assert 'id="sArbCount"' in html
    assert 'id="sArb"' in html
