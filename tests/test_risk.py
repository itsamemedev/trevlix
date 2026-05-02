"""
╔══════════════════════════════════════════════════════════════╗
║  TREVLIX Tests – Risikomanagement                            ║
╚══════════════════════════════════════════════════════════════╝

Führe aus mit:  pytest tests/test_risk.py -v
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestRiskManager:
    """Tests für den RiskManager."""

    def _make_risk(self):
        """Erstellt RiskManager-Instanz mit Test-CONFIG."""
        from services.risk import RiskManager

        config = {
            "max_daily_loss_pct": 0.05,
            "circuit_breaker_losses": 3,
            "circuit_breaker_min": 60,
            "max_corr": 0.75,
            "paper_balance": 10000.0,
        }
        return RiskManager(config)

    def test_daily_loss_not_exceeded_initially(self):
        """Frisch erstellter RiskManager hat kein Tageslimit überschritten."""
        rm = self._make_risk()
        assert rm.daily_loss_exceeded(10000.0) is False

    def test_circuit_breaker_not_active_initially(self):
        """Circuit Breaker startet inaktiv."""
        rm = self._make_risk()
        assert rm.circuit_breaker_active() is False

    def test_circuit_breaker_activates_after_losses(self):
        """Circuit Breaker aktiviert nach 3 Verlusten."""
        rm = self._make_risk()
        # record_result(won=False) registriert einen Verlust
        rm.record_result(False)
        rm.record_result(False)
        assert rm.circuit_breaker_active() is False  # noch nicht (2 < 3)
        rm.record_result(False)
        assert rm.circuit_breaker_active() is True  # jetzt (3 >= 3)

    def test_circuit_breaker_resets_on_win(self):
        """Verlust-Zähler wird bei Gewinn zurückgesetzt."""
        rm = self._make_risk()
        rm.record_result(False)
        rm.record_result(False)
        rm.record_result(True)  # Gewinn → Reset
        assert rm.consecutive_losses == 0

    def test_reset_circuit_breaker_manually(self):
        """Circuit Breaker kann manuell zurückgesetzt werden."""
        rm = self._make_risk()
        rm.record_result(False)
        rm.record_result(False)
        rm.record_result(False)
        assert rm.circuit_breaker_active() is True
        rm.circuit_breaker_until = None
        rm.consecutive_losses = 0
        assert rm.circuit_breaker_active() is False

    def test_daily_loss_exceeded_after_big_loss(self):
        """Tageslimit wird überschritten bei großem Verlust."""
        rm = self._make_risk()
        rm.daily_start = 10000.0
        # 6% Verlust > 5% Limit
        assert rm.daily_loss_exceeded(9400.0) is True

    def test_daily_loss_not_exceeded_small_loss(self):
        """Kleiner Verlust überschreitet Limit nicht."""
        rm = self._make_risk()
        rm.daily_start = 10000.0
        # 2% Verlust < 5% Limit
        assert rm.daily_loss_exceeded(9800.0) is False

    def test_consecutive_losses_counter(self):
        """Verlust-Zähler zählt korrekt hoch."""
        rm = self._make_risk()
        for _i in range(2):
            rm.record_result(False)
        assert rm.consecutive_losses == 2

    def test_circuit_status_returns_dict(self):
        """circuit_status gibt Dict mit erwarteten Keys zurück."""
        rm = self._make_risk()
        status = rm.circuit_status()
        assert isinstance(status, dict)
        assert "active" in status
        assert "losses" in status
        assert "limit" in status
        assert "remaining_min" in status

    def test_sharpe_zero_without_trades(self):
        """Sharpe-Ratio ist 0 bei weniger als 3 Trades."""
        rm = self._make_risk()
        assert rm.sharpe([]) == 0.0
        assert rm.sharpe([0.01]) == 0.0


class TestDrawdownBreaker:
    """Tests für Drawdown Circuit Breaker und Peak-Tracking."""

    def _make_risk(self, max_dd_pct=0.10):
        from services.risk import RiskManager

        return RiskManager(
            {
                "paper_balance": 10000.0,
                "circuit_breaker_losses": 5,
                "circuit_breaker_min": 30,
                "max_drawdown_pct": max_dd_pct,
            }
        )

    def test_update_peak_tracks_high(self):
        """update_peak setzt das Peak auf den Höchstwert."""
        rm = self._make_risk()
        rm.update_peak(12000.0)
        assert rm.peak == 12000.0
        rm.update_peak(11000.0)
        assert rm.peak == 12000.0  # Peak darf nicht fallen

    def test_update_peak_records_drawdown(self):
        """update_peak berechnet max_drawdown korrekt."""
        rm = self._make_risk()
        rm.update_peak(10000.0)
        rm.update_peak(9000.0)
        assert rm.max_drawdown == pytest.approx(10.0, abs=0.01)

    def test_drawdown_breaker_inactive_below_limit(self):
        """Drawdown-Breaker löst bei kleinem Drawdown nicht aus."""
        rm = self._make_risk(max_dd_pct=0.10)
        rm.update_peak(10000.0)
        assert rm.drawdown_breaker_active(9500.0) is False

    def test_drawdown_breaker_triggers_above_limit(self):
        """Drawdown-Breaker löst bei >10% Drawdown aus."""
        rm = self._make_risk(max_dd_pct=0.10)
        rm.update_peak(10000.0)
        assert rm.drawdown_breaker_active(8000.0) is True


class TestCorrelationFilter:
    """Tests für den Korrelationsfilter in is_correlated."""

    def _make_risk(self):
        from services.risk import RiskManager

        return RiskManager({"paper_balance": 10000.0, "max_corr": 0.75})

    def test_no_positions_not_correlated(self):
        """Kein offenes Symbol → kein Korrelations-Block."""
        rm = self._make_risk()
        assert rm.is_correlated("BTC/USDT", []) is False

    def test_insufficient_history_not_correlated(self):
        """Zu wenig Preis-History → kein Block."""
        rm = self._make_risk()
        for p in range(5):
            rm.update_prices("BTC/USDT", 30000.0 + p)
            rm.update_prices("ETH/USDT", 2000.0 + p)
        assert rm.is_correlated("BTC/USDT", ["ETH/USDT"]) is False

    def test_identical_series_handled_gracefully(self):
        """Identische Preisserien (NaN-Korrelation) werden ohne Absturz behandelt."""
        rm = self._make_risk()
        price = 30000.0
        for _ in range(25):
            rm.update_prices("BTC/USDT", price)
            rm.update_prices("ETH/USDT", price)
        result = rm.is_correlated("BTC/USDT", ["ETH/USDT"])
        assert isinstance(result, bool)


class TestDailyPnlAccumulation:
    """Tests für tägliche PnL-Akkumulation in record_result."""

    def _make_risk(self):
        from services.risk import RiskManager

        return RiskManager(
            {"paper_balance": 10000.0, "circuit_breaker_losses": 5, "circuit_breaker_min": 30}
        )

    def test_record_result_accumulates_pnl(self):
        rm = self._make_risk()
        rm.record_result(True, 50.0)
        rm.record_result(False, -30.0)
        assert rm.daily_pnl == 20.0

    def test_record_result_default_pnl_zero(self):
        rm = self._make_risk()
        rm.record_result(True)
        assert rm.daily_pnl == 0.0

    def test_daily_pnl_resets_on_day_change(self):
        from datetime import date

        rm = self._make_risk()
        rm.record_result(True, 100.0)
        rm._day = date(2000, 1, 1)
        rm.reset_daily(9500.0)
        assert rm.daily_pnl == 0.0


class TestDailyLossCircuitBreaker:
    """Tests für automatische Circuit-Breaker-Aktivierung bei Tageslimit-Überschreitung."""

    def _make_risk(self):
        from services.risk import RiskManager

        return RiskManager(
            {"paper_balance": 10000.0, "max_daily_loss_pct": 0.05, "circuit_breaker_min": 30}
        )

    def test_daily_loss_exceeded_activates_circuit_breaker(self):
        rm = self._make_risk()
        rm.daily_start = 10000.0
        exceeded = rm.daily_loss_exceeded(9400.0)
        assert exceeded
        assert rm.circuit_breaker_active()

    def test_daily_loss_cb_fires_only_once(self):
        rm = self._make_risk()
        rm.daily_start = 10000.0
        rm.daily_loss_exceeded(9400.0)
        first_until = rm.circuit_breaker_until
        rm.daily_loss_exceeded(9300.0)
        assert rm.circuit_breaker_until == first_until

    def test_daily_loss_within_limit_no_cb(self):
        rm = self._make_risk()
        rm.daily_start = 10000.0
        exceeded = rm.daily_loss_exceeded(9700.0)
        assert not exceeded
        assert not rm.circuit_breaker_active()

    def test_daily_loss_cb_flag_resets_on_day_change(self):
        from datetime import date

        rm = self._make_risk()
        rm.daily_start = 10000.0
        rm.daily_loss_exceeded(9400.0)
        assert rm._daily_loss_cb_fired
        rm._day = date(2000, 1, 1)
        rm._reset_daily_unlocked(10000.0)
        assert not rm._daily_loss_cb_fired
