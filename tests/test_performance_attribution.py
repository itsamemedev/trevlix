"""Tests für die Performance Attribution Engine."""

from services.performance_attribution import (
    PerformanceAttribution,
    _FactorStats,
    _fg_bucket,
    _hour_to_session,
)


class TestHelpers:
    """Tests für Hilfsfunktionen."""

    def test_hour_to_session_asia(self):
        assert _hour_to_session(0) == "asia"
        assert _hour_to_session(7) == "asia"

    def test_hour_to_session_europe(self):
        assert _hour_to_session(8) == "europe"
        assert _hour_to_session(15) == "europe"

    def test_hour_to_session_us(self):
        assert _hour_to_session(16) == "us"
        assert _hour_to_session(21) == "us"

    def test_hour_to_session_off_hours(self):
        assert _hour_to_session(22) == "off_hours"
        assert _hour_to_session(23) == "off_hours"

    def test_fg_bucket_extreme_fear(self):
        assert _fg_bucket(10) == "extreme_fear"

    def test_fg_bucket_fear(self):
        assert _fg_bucket(30) == "fear"

    def test_fg_bucket_neutral(self):
        assert _fg_bucket(50) == "neutral"

    def test_fg_bucket_greed(self):
        assert _fg_bucket(70) == "greed"

    def test_fg_bucket_extreme_greed(self):
        assert _fg_bucket(90) == "extreme_greed"


class TestFactorStats:
    """Tests für _FactorStats."""

    def test_initial_state(self):
        fs = _FactorStats()
        assert fs.total_trades == 0
        assert fs.total_pnl == 0.0

    def test_record_win(self):
        fs = _FactorStats()
        fs.record(100.0)
        assert fs.wins == 1
        assert fs.losses == 0
        assert fs.total_pnl == 100.0

    def test_record_loss(self):
        fs = _FactorStats()
        fs.record(-50.0)
        assert fs.wins == 0
        assert fs.losses == 1
        assert fs.total_pnl == -50.0

    def test_to_dict(self):
        fs = _FactorStats()
        fs.record(100.0)
        fs.record(-30.0)
        d = fs.to_dict()
        assert d["trades"] == 2
        assert d["wins"] == 1
        assert d["losses"] == 1
        assert d["total_pnl"] == 70.0
        assert d["win_rate"] == 50.0


class TestPerformanceAttribution:
    """Tests für die PerformanceAttribution-Klasse."""

    def test_record_trade(self):
        pa = PerformanceAttribution()
        pa.record_trade("BTC/USDT", 150.0, strategy="EMA-Trend", regime="bull", hour=10)
        stats = pa.stats()
        assert stats["total_trades"] == 1
        assert stats["total_pnl"] == 150.0

    def test_attribution_by_strategy(self):
        pa = PerformanceAttribution()
        pa.record_trade("BTC/USDT", 100.0, strategy="EMA-Trend", hour=10)
        pa.record_trade("ETH/USDT", -50.0, strategy="RSI-Stochastic", hour=10)
        result = pa.attribution_by("strategy")
        assert "EMA-Trend" in result
        assert "RSI-Stochastic" in result
        assert result["EMA-Trend"]["total_pnl"] == 100.0
        assert result["RSI-Stochastic"]["total_pnl"] == -50.0

    def test_attribution_by_regime(self):
        pa = PerformanceAttribution()
        pa.record_trade("BTC/USDT", 100.0, regime="bull", hour=10)
        pa.record_trade("BTC/USDT", -50.0, regime="bear", hour=10)
        result = pa.attribution_by("regime")
        assert result["bull"]["total_pnl"] == 100.0
        assert result["bear"]["total_pnl"] == -50.0

    def test_attribution_by_session(self):
        pa = PerformanceAttribution()
        pa.record_trade("BTC/USDT", 100.0, hour=10)  # europe
        pa.record_trade("BTC/USDT", 50.0, hour=18)  # us
        result = pa.attribution_by("session")
        assert "europe" in result
        assert "us" in result

    def test_attribution_by_symbol(self):
        pa = PerformanceAttribution()
        pa.record_trade("BTC/USDT", 200.0, hour=10)
        pa.record_trade("ETH/USDT", -80.0, hour=10)
        result = pa.attribution_by("symbol")
        assert result["BTC/USDT"]["total_pnl"] == 200.0

    def test_attribution_by_fg(self):
        pa = PerformanceAttribution()
        pa.record_trade("BTC/USDT", 100.0, fg_value=15, hour=10)  # extreme_fear
        pa.record_trade("BTC/USDT", -50.0, fg_value=85, hour=10)  # extreme_greed
        result = pa.attribution_by("fg")
        assert "extreme_fear" in result
        assert "extreme_greed" in result

    def test_attribution_invalid_dimension(self):
        pa = PerformanceAttribution()
        assert pa.attribution_by("invalid") == {}

    def test_profit_factor(self):
        pa = PerformanceAttribution()
        pa.record_trade("BTC/USDT", 300.0, hour=10)
        pa.record_trade("ETH/USDT", -100.0, hour=10)
        assert pa.profit_factor() == 3.0

    def test_profit_factor_no_losses(self):
        pa = PerformanceAttribution()
        pa.record_trade("BTC/USDT", 100.0, hour=10)
        # Keine Verluste → profit_factor gibt 999.99 zurück (JSON-safe cap)
        assert pa.profit_factor() == 999.99

    def test_expectancy(self):
        pa = PerformanceAttribution()
        pa.record_trade("BTC/USDT", 100.0, hour=10)
        pa.record_trade("ETH/USDT", -50.0, hour=10)
        assert pa.expectancy() == 25.0

    def test_expectancy_empty(self):
        pa = PerformanceAttribution()
        assert pa.expectancy() == 0.0

    def test_sharpe_ratio_few_trades(self):
        pa = PerformanceAttribution()
        pa.record_trade("BTC/USDT", 100.0, hour=10)
        assert pa.sharpe_ratio() == 0.0

    def test_sharpe_ratio_with_data(self):
        pa = PerformanceAttribution()
        for i in range(20):
            pa.record_trade("BTC/USDT", 10.0 + i, hour=10)
        sr = pa.sharpe_ratio()
        assert sr > 0

    def test_full_report_structure(self):
        pa = PerformanceAttribution()
        pa.record_trade("BTC/USDT", 100.0, strategy="EMA-Trend", regime="bull", hour=10)
        report = pa.full_report()
        assert "summary" in report
        assert "by_strategy" in report
        assert "by_regime" in report
        assert "by_session" in report
        assert "by_symbol" in report
        assert "by_fear_greed" in report
        assert "regime_strategy_matrix" in report
        assert "top_contributors" in report

    def test_regime_strategy_matrix(self):
        pa = PerformanceAttribution()
        pa.record_trade("BTC/USDT", 100.0, strategy="EMA-Trend", regime="bull", hour=10)
        matrix = pa.regime_strategy_matrix()
        assert "bull:EMA-Trend" in matrix

    def test_top_contributors(self):
        pa = PerformanceAttribution()
        for _ in range(5):
            pa.record_trade("BTC/USDT", 50.0, strategy="EMA-Trend", regime="bull", hour=10)
            pa.record_trade("ETH/USDT", -30.0, strategy="RSI-Stochastic", regime="bear", hour=3)
        result = pa.top_contributors(3)
        assert len(result["best"]) > 0
        assert result["best"][0]["total_pnl"] > 0

    def test_load_from_trades(self):
        pa = PerformanceAttribution()
        trades = [
            {"symbol": "BTC/USDT", "pnl": 100.0, "reason": "EMA-Trend", "regime": "bull"},
            {"symbol": "ETH/USDT", "pnl": -50.0, "reason": "MACD", "regime": "bear"},
        ]
        count = pa.load_from_trades(trades)
        assert count == 2
        assert pa.stats()["total_trades"] == 2

    def test_to_dict(self):
        pa = PerformanceAttribution()
        d = pa.to_dict()
        assert d["enabled"] is True
        assert "total_trades" in d
        assert "profit_factor" in d

    def test_max_trades_limit(self):
        pa = PerformanceAttribution(max_trades=5)
        for i in range(10):
            pa.record_trade(f"SYM{i}/USDT", 10.0, hour=10)
        assert len(pa._trades) == 5
