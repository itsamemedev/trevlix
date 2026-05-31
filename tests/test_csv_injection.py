"""Regression tests: CSV formula-injection defence on tax/trade exports."""

from __future__ import annotations

from app.core.tax_export import csv_safe_cell, tax_rows_to_csv


def test_csv_safe_cell_escapes_formula_prefixes():
    for dangerous in ("=cmd", "+1", "-1", "@SUM", "\tx", "\rx"):
        out = csv_safe_cell(dangerous)
        assert out.startswith("'"), dangerous
        assert out == "'" + dangerous


def test_csv_safe_cell_leaves_normal_values():
    assert csv_safe_cell("BTC/USDT") == "BTC/USDT"
    assert csv_safe_cell(123) == "123"
    assert csv_safe_cell(-0.5) == "'-0.5"  # leading '-' is escaped
    assert csv_safe_cell(None) == ""


def test_tax_rows_to_csv_neutralises_injection():
    rows = [
        {"symbol": '=HYPERLINK("http://evil")', "reason": "+cmd", "pnl": 10},
        {"symbol": "BTC/USDT", "reason": "TP", "pnl": -5},
    ]
    csv_text = tax_rows_to_csv(rows)
    lines = csv_text.strip().splitlines()
    # header + 2 rows
    assert len(lines) == 3
    # dangerous cells are quote-prefixed; no raw cell starts with = or + at field start
    assert ",'=HYPERLINK" in csv_text or "'=HYPERLINK" in csv_text
    assert "'+cmd" in csv_text
    # benign value untouched
    assert "BTC/USDT" in csv_text


def test_tax_rows_to_csv_empty():
    assert tax_rows_to_csv([]) == ""
    assert tax_rows_to_csv(None) == ""


def test_trade_repo_export_csv_sanitises_and_imports():
    # Guards against the import regression where csv_safe_cell was referenced in
    # export_csv but never imported (would crash at runtime), and confirms the
    # sanitiser is actually applied to trade rows.
    from app.core.repositories.trade_repo import TradeRepository

    repo = TradeRepository.__new__(TradeRepository)
    repo.load_trades = lambda limit=10000, user_id=None: [
        {"id": 1, "symbol": "=cmd|'/c calc'!A1", "reason": "+evil", "pnl": 1.0},
        {"id": 2, "symbol": "BTC/USDT", "reason": "TP", "pnl": -2.0},
    ]
    out = repo.export_csv()
    assert "'=cmd" in out
    assert "'+evil" in out
    assert "BTC/USDT" in out
