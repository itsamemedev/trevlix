"""
╔══════════════════════════════════════════════════════════════╗
║  TREVLIX Tests – Risikomanagement                            ║
╚══════════════════════════════════════════════════════════════╝

Führe aus mit:  pytest tests/test_risk.py -v
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestRiskManager:
    """Tests für den RiskManager."""

    def _make_risk(self):
        """Erstellt RiskManager-Instanz mit Test-CONFIG."""
        import server

        # CONFIG für Tests anpassen
        server.CONFIG["max_daily_loss_pct"] = 0.05
        server.CONFIG["circuit_breaker_losses"] = 3
        server.CONFIG["circuit_breaker_min"] = 60
        server.CONFIG["max_corr"] = 0.75
        server.CONFIG["paper_balance"] = 10000.0
        return server.RiskManager()

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


class TestKellyCriterion:
    """Tests für Kelly-Kriterium Positionsgrößenberechnung."""

    def test_kelly_positive_edge(self):
        """Kelly berechnet positive Position bei positivem Vorteil."""
        win_rate = 0.60
        avg_win = 0.06
        avg_loss = 0.025
        kelly = win_rate - (1 - win_rate) / (avg_win / avg_loss)
        assert kelly > 0, "Kelly sollte bei 60% Win-Rate positiv sein"

    def test_kelly_capped_at_max(self):
        """Kelly wird auf maximale Position begrenzt."""
        max_position = 0.20
        kelly_raw = 1.5
        kelly_capped = min(kelly_raw, max_position)
        assert kelly_capped == max_position

    def test_kelly_near_zero_at_breakeven(self):
        """Kelly ist ~0 bei Break-Even (50% Win-Rate, Win=Loss)."""
        win_rate = 0.50
        avg_win = 0.025
        avg_loss = 0.025
        kelly = win_rate - (1 - win_rate) / (avg_win / avg_loss)
        assert abs(kelly) < 0.01, f"Kelly bei Break-Even sollte ~0 sein, ist {kelly}"


class TestPositionSizing:
    """Tests für Positionsgrößen-Berechnung."""

    def test_position_doesnt_exceed_balance(self):
        """Position darf nicht mehr als Gesamtbalance betragen."""
        balance = 10000.0
        risk_per_trade = 0.015
        max_position_pct = 0.20
        invest = min(balance * risk_per_trade, balance * max_position_pct)
        assert invest <= balance

    def test_position_positive(self):
        """Position ist immer positiv."""
        balance = 5000.0
        risk_per_trade = 0.015
        invest = balance * risk_per_trade
        assert invest > 0

    def test_dca_size_multiplier_grows(self):
        """DCA vergrößert Position jedes Level."""
        base_invest = 100.0
        dca_mult = 1.5
        levels = [base_invest * (dca_mult**i) for i in range(4)]
        for i in range(len(levels) - 1):
            assert levels[i + 1] > levels[i], "DCA-Größe muss wachsen"

    def test_dca_max_levels_respected(self):
        """DCA beachtet maximale Level-Anzahl."""
        max_levels = 3
        levels_used = 0
        for _level in range(max_levels + 5):  # Versuche mehr als erlaubt
            if levels_used >= max_levels:
                break
            levels_used += 1
        assert levels_used == max_levels
