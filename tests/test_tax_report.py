"""Tests for the tax report generator (§ 23 EStG holding-period handling)."""

from __future__ import annotations

from services.tax_report import TaxReportGenerator


def _trade(symbol, pnl, opened, closed, invested=1000.0):
    return {
        "symbol": symbol,
        "pnl": pnl,
        "invested": invested,
        "opened": opened,
        "closed": closed,
        "entry": 100.0,
        "exit": 110.0,
        "qty": 10,
    }


def test_short_held_gain_is_taxable():
    gen = TaxReportGenerator(fee_rate=0.0)
    rows = [_trade("BTC/USDT", 500.0, "2024-01-01 00:00:00", "2024-03-01 00:00:00")]
    rep = gen.generate(rows, 2024)
    assert rep["summary"]["taxable_gains"] == 500.0
    assert rep["summary"]["tax_free_gains"] == 0.0
    assert rep["gains"][0]["taxable"] is True


def test_long_held_gain_is_tax_free():
    # Held > 365 days → § 23 EStG: gain is tax-free, excluded from taxable_gains.
    gen = TaxReportGenerator(fee_rate=0.0)
    rows = [_trade("ETH/USDT", 800.0, "2022-01-01 00:00:00", "2024-02-01 00:00:00")]
    rep = gen.generate(rows, 2024)
    assert rep["summary"]["taxable_gains"] == 0.0
    assert rep["summary"]["tax_free_gains"] == 800.0
    assert rep["summary"]["tax_free_count"] == 1
    assert rep["tax_free"][0]["tax_free"] is True


def test_long_held_loss_is_still_a_loss():
    # A loss on a long-held position is not "tax free" — stays in losses.
    gen = TaxReportGenerator(fee_rate=0.0)
    rows = [_trade("ETH/USDT", -300.0, "2022-01-01 00:00:00", "2024-02-01 00:00:00")]
    rep = gen.generate(rows, 2024)
    assert rep["summary"]["tax_free_gains"] == 0.0
    assert rep["summary"]["loss_count"] == 1
    assert rep["summary"]["total_losses"] == -300.0


def test_mixed_year_filtering_and_holding():
    gen = TaxReportGenerator(fee_rate=0.0)
    rows = [
        _trade("BTC/USDT", 100.0, "2024-01-01", "2024-02-01"),  # taxable
        _trade("ETH/USDT", 200.0, "2022-01-01", "2024-06-01"),  # tax-free (long)
        _trade("SOL/USDT", -50.0, "2024-03-01", "2024-04-01"),  # loss
        _trade("OLD/USDT", 999.0, "2023-01-01", "2023-06-01"),  # different year
    ]
    rep = gen.generate(rows, 2024)
    assert rep["summary"]["trade_count"] == 3  # 2023 trade excluded
    assert rep["summary"]["taxable_gains"] == 50.0  # 100 gain - 50 loss
    assert rep["summary"]["tax_free_gains"] == 200.0


def test_unparseable_dates_default_to_taxable():
    # If we can't determine holding period, be conservative → treat gain as taxable.
    gen = TaxReportGenerator(fee_rate=0.0)
    rows = [_trade("BTC/USDT", 400.0, None, "2024-05-01")]
    rep = gen.generate(rows, 2024)
    assert rep["summary"]["taxable_gains"] == 400.0
    assert rep["summary"]["tax_free_gains"] == 0.0


def test_empty_year():
    gen = TaxReportGenerator()
    rep = gen.generate([], 2024)
    assert rep["summary"]["trade_count"] == 0
    assert rep["summary"]["tax_free_gains"] == 0
    assert rep["tax_free"] == []
