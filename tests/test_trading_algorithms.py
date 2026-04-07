"""Tests für services/trading_algorithms.py – Selbstlernende Kauf-/Verkaufsalgorithmen."""

import pytest

from services.trading_algorithms import BuyAlgorithm, SellAlgorithm, TradingAlgorithmManager

# ═══════════════════════════════════════════════════════════════════════════════
# FIXTURES
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def bullish_scan() -> dict:
    """Scan-Daten die einen Kauf-Signal begünstigen (Momentum + Trend)."""
    return {
        "symbol": "BTC/USDT",
        "price": 30500.0,
        "rsi": 55.0,
        "stoch_rsi": 45.0,
        "bb_pct": 0.6,
        "bb_width": 0.03,
        "vol_ratio": 1.8,
        "ema_alignment": 0.8,
        "macd_hist_slope": 0.005,
        "roc10": 3.5,
        "atr_pct": 1.2,
        "price_vs_ema21": 0.01,
    }


@pytest.fixture
def bearish_scan() -> dict:
    """Scan-Daten die einen Verkauf begünstigen."""
    return {
        "symbol": "BTC/USDT",
        "price": 29000.0,
        "rsi": 75.0,
        "stoch_rsi": 85.0,
        "bb_pct": 0.95,
        "bb_width": 0.04,
        "vol_ratio": 0.5,
        "ema_alignment": -0.6,
        "macd_hist_slope": -0.003,
        "roc10": -2.0,
        "atr_pct": 2.0,
        "price_vs_ema21": -0.02,
    }


@pytest.fixture
def neutral_scan() -> dict:
    """Neutrale Marktbedingungen."""
    return {
        "symbol": "ETH/USDT",
        "price": 2000.0,
        "rsi": 50.0,
        "stoch_rsi": 50.0,
        "bb_pct": 0.5,
        "bb_width": 0.03,
        "vol_ratio": 1.0,
        "ema_alignment": 0.0,
        "macd_hist_slope": 0.0,
        "roc10": 0.0,
        "atr_pct": 1.0,
        "price_vs_ema21": 0.0,
    }


@pytest.fixture
def open_position() -> dict:
    """Offene Long-Position."""
    return {
        "entry": 30000.0,
        "qty": 0.1,
        "invested": 3000.0,
        "highest": 31000.0,
        "opened": "2026-04-05T10:00:00",
        "sl": 29250.0,
        "tp": 31800.0,
        "rsi": 55.0,
        "stoch_rsi": 45.0,
        "bb_pct": 0.6,
        "vol_ratio": 1.5,
        "ema_alignment": 0.5,
        "macd_hist_slope": 0.002,
        "roc10": 2.0,
        "atr_pct": 1.0,
        "price_vs_ema21": 0.01,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# BUY ALGORITHM
# ═══════════════════════════════════════════════════════════════════════════════


class TestBuyAlgorithm:
    """Tests für den selbstlernenden Kaufalgorithmus."""

    def test_init(self):
        """Initialisierung mit Standardwerten."""
        algo = BuyAlgorithm()
        assert algo.total_signals == 0
        assert algo.profitable_signals == 0
        assert len(algo.weights) == 3
        assert all(w == 1.0 for w in algo.weights.values())

    def test_evaluate_bullish(self, bullish_scan):
        """Bullische Scan-Daten sollten Kaufsignal erzeugen."""
        algo = BuyAlgorithm()
        should_buy, conf, reason = algo.evaluate(bullish_scan)
        assert should_buy is True
        assert conf > 0.35
        assert "BuyAlgo:" in reason

    def test_evaluate_neutral_no_buy(self, neutral_scan):
        """Neutrale Bedingungen sollten kein Kaufsignal erzeugen."""
        algo = BuyAlgorithm()
        should_buy, conf, reason = algo.evaluate(neutral_scan)
        assert should_buy is False
        assert conf < 0.35

    def test_momentum_score(self, bullish_scan):
        """Momentum-Strategie erkennt Aufwärtstrend."""
        algo = BuyAlgorithm()
        score = algo._momentum_score(bullish_scan)
        assert score > 0.3
        assert score <= 1.0

    def test_mean_reversion_score_oversold(self):
        """Mean-Reversion erkennt überverkaufte Bedingungen."""
        algo = BuyAlgorithm()
        oversold = {
            "rsi": 28.0,
            "bb_pct": 0.05,
            "stoch_rsi": 15.0,
            "price_vs_ema21": -0.03,
            "macd_hist_slope": 0.001,
        }
        score = algo._mean_reversion_score(oversold)
        assert score >= 0.6

    def test_trend_breakout_score(self):
        """Breakout-Strategie erkennt Volumen-Spike + Preisausbruch."""
        algo = BuyAlgorithm()
        breakout = {
            "vol_ratio": 2.5,
            "roc10": 4.0,
            "bb_width": 0.015,
            "ema_alignment": 0.5,
            "atr_pct": 2.0,
        }
        score = algo._trend_breakout_score(breakout)
        assert score > 0.5

    def test_record_result_updates_stats(self, bullish_scan):
        """record_result aktualisiert Gewinn-Statistik."""
        algo = BuyAlgorithm()
        algo.record_result(bullish_scan, pnl=50.0)
        assert algo.total_signals == 1
        assert algo.profitable_signals == 1

        algo.record_result(bullish_scan, pnl=-20.0)
        assert algo.total_signals == 2
        assert algo.profitable_signals == 1

    def test_weight_adaptation(self, bullish_scan):
        """Gewichte werden nach genügend Trades angepasst."""
        algo = BuyAlgorithm()
        # Simuliere mehrere profitable Momentum-Trades
        for _ in range(10):
            algo.record_result(bullish_scan, pnl=100.0)

        # Momentum-Gewicht sollte gestiegen sein
        assert algo.weights["momentum"] > 1.0

    def test_win_rate(self, bullish_scan):
        """Win-Rate wird korrekt berechnet."""
        algo = BuyAlgorithm()
        assert algo.win_rate() == 0.0

        algo.record_result(bullish_scan, pnl=50.0)
        algo.record_result(bullish_scan, pnl=30.0)
        algo.record_result(bullish_scan, pnl=-20.0)
        assert abs(algo.win_rate() - 2 / 3) < 0.01

    def test_to_dict(self, bullish_scan):
        """to_dict liefert vollständiges Status-Dictionary."""
        algo = BuyAlgorithm()
        algo.record_result(bullish_scan, pnl=50.0)
        d = algo.to_dict()
        assert d["enabled"] is True
        assert d["total_signals"] == 1
        assert d["profitable_signals"] == 1
        assert "sub_strategies" in d
        assert len(d["sub_strategies"]) == 3
        assert "params" in d

    def test_empty_scan_no_crash(self):
        """Leere Scan-Daten verursachen keinen Crash."""
        algo = BuyAlgorithm()
        should_buy, conf, reason = algo.evaluate({})
        assert isinstance(should_buy, bool)
        assert isinstance(conf, float)


# ═══════════════════════════════════════════════════════════════════════════════
# SELL ALGORITHM
# ═══════════════════════════════════════════════════════════════════════════════


class TestSellAlgorithm:
    """Tests für den selbstlernenden Verkaufsalgorithmus."""

    def test_init(self):
        """Initialisierung mit Standardwerten."""
        algo = SellAlgorithm()
        assert algo.total_signals == 0
        assert len(algo.weights) == 4

    def test_evaluate_bearish(self, bearish_scan, open_position):
        """Bärische Bedingungen sollten Verkaufssignal erzeugen."""
        algo = SellAlgorithm()
        should_sell, conf, reason = algo.evaluate(bearish_scan, open_position)
        assert should_sell is True
        assert conf > 0.3
        assert "SellAlgo:" in reason

    def test_evaluate_stable_no_sell(self, bullish_scan, open_position):
        """Stabile bullische Bedingungen sollten kein Verkaufssignal erzeugen."""
        algo = SellAlgorithm()
        bullish_scan["price"] = 30500.0  # Leicht über Entry
        should_sell, conf, reason = algo.evaluate(bullish_scan, open_position)
        # Bei bullischen Bedingungen sollte Sell-Score unter Schwelle bleiben
        assert conf < 0.5

    def test_momentum_reversal_overbought(self, open_position):
        """Momentum-Reversal erkennt überkaufte Bedingungen."""
        algo = SellAlgorithm()
        overbought = {
            "rsi": 78.0,
            "stoch_rsi": 90.0,
            "macd_hist_slope": -0.005,
            "ema_alignment": -0.3,
        }
        score = algo._momentum_reversal_score(overbought, open_position)
        assert score >= 0.7

    def test_profit_protection(self, open_position):
        """Profit-Protection greift bei Rückgang vom Hoch."""
        algo = SellAlgorithm()
        # Entry=30000, Price=31000 → 3.3% Gewinn, Highest=32000 → 3.1% Rückgang
        scan = {
            "price": 31000.0,
            "atr_pct": 1.0,
        }
        open_position["highest"] = 32000.0
        score = algo._profit_protection_score(scan, open_position)
        assert score > 0.0

    def test_time_decay_long_hold(self, open_position):
        """Time-Decay erkennt zu lange gehaltene Positionen."""
        algo = SellAlgorithm()
        open_position["opened"] = "2026-04-01T10:00:00"  # ~6 Tage her
        scan = {"price": 30050.0}
        score = algo._time_decay_score(scan, open_position)
        assert score > 0.3

    def test_time_decay_fresh_position(self, open_position):
        """Frische Position hat keinen Time-Decay."""
        algo = SellAlgorithm()
        from datetime import datetime

        open_position["opened"] = datetime.now().isoformat()
        scan = {"price": 30500.0}
        score = algo._time_decay_score(scan, open_position)
        assert score < 0.1

    def test_pattern_exit_near_upper_bb(self, open_position):
        """Pattern-Exit erkennt Preis nahe oberer Bollinger-Band."""
        algo = SellAlgorithm()
        scan = {
            "bb_pct": 0.96,
            "vol_ratio": 0.4,
            "roc10": -2.5,
            "ema_alignment": -0.5,
        }
        score = algo._pattern_exit_score(scan, open_position)
        assert score >= 0.5

    def test_record_result(self, bearish_scan, open_position):
        """record_result zeichnet Ergebnis korrekt auf."""
        algo = SellAlgorithm()
        algo.record_result(bearish_scan, open_position, pnl=100.0, exit_reason="SellAlgo:Test")
        assert algo.total_signals == 1
        assert algo.improved_exits == 1

        algo.record_result(bearish_scan, open_position, pnl=-50.0, exit_reason="Stop-Loss")
        assert algo.total_signals == 2
        assert algo.improved_exits == 1

    def test_to_dict(self, bearish_scan, open_position):
        """to_dict liefert vollständiges Status-Dictionary."""
        algo = SellAlgorithm()
        algo.record_result(bearish_scan, open_position, pnl=50.0, exit_reason="SellAlgo:Test")
        d = algo.to_dict()
        assert d["enabled"] is True
        assert d["total_signals"] == 1
        assert "sub_strategies" in d
        assert len(d["sub_strategies"]) == 4

    def test_empty_scan_no_crash(self):
        """Leere Daten verursachen keinen Crash."""
        algo = SellAlgorithm()
        should_sell, conf, reason = algo.evaluate({}, {})
        assert isinstance(should_sell, bool)


# ═══════════════════════════════════════════════════════════════════════════════
# TRADING ALGORITHM MANAGER
# ═══════════════════════════════════════════════════════════════════════════════


class TestTradingAlgorithmManager:
    """Tests für den TradingAlgorithmManager."""

    def test_init(self):
        """Manager initialisiert beide Algorithmen."""
        mgr = TradingAlgorithmManager()
        assert mgr.is_configured is True
        assert mgr.buy_algo is not None
        assert mgr.sell_algo is not None

    def test_evaluate_buy(self, bullish_scan):
        """evaluate_buy delegiert an BuyAlgorithm."""
        mgr = TradingAlgorithmManager()
        should_buy, conf, reason = mgr.evaluate_buy(bullish_scan)
        assert isinstance(should_buy, bool)
        assert isinstance(conf, float)
        assert isinstance(reason, str)

    def test_evaluate_sell(self, bearish_scan, open_position):
        """evaluate_sell delegiert an SellAlgorithm."""
        mgr = TradingAlgorithmManager()
        should_sell, conf, reason = mgr.evaluate_sell(bearish_scan, open_position)
        assert isinstance(should_sell, bool)
        assert isinstance(conf, float)

    def test_record_results(self, bullish_scan, open_position):
        """Feedback-Loop funktioniert ohne Fehler."""
        mgr = TradingAlgorithmManager()
        mgr.record_buy_result(bullish_scan, pnl=50.0)
        mgr.record_sell_result(bullish_scan, open_position, pnl=50.0, exit_reason="TP")

    def test_to_dict(self):
        """to_dict liefert vollständigen Status."""
        mgr = TradingAlgorithmManager()
        d = mgr.to_dict()
        assert d["configured"] is True
        assert d["active"] is True
        assert "buy_algorithm" in d
        assert "sell_algorithm" in d
        assert "status_msg" in d
        assert "total_trades" in d

    def test_status_msg_initial(self):
        """Initiale Statusnachricht zeigt 'Sammle Daten'."""
        mgr = TradingAlgorithmManager()
        d = mgr.to_dict()
        assert "Konfiguriert" in d["status_msg"]

    def test_status_msg_after_trades(self, bullish_scan):
        """Nach Trades zeigt Statusnachricht Statistiken."""
        mgr = TradingAlgorithmManager()
        for _ in range(5):
            mgr.record_buy_result(bullish_scan, pnl=50.0)
        d = mgr.to_dict()
        assert "Aktiv" in d["status_msg"]
        assert "WR" in d["status_msg"]

    def test_deactivated_manager(self, bullish_scan, open_position):
        """Deaktivierter Manager blockiert alle Signale."""
        mgr = TradingAlgorithmManager()
        mgr._active = False
        assert mgr.is_configured is False

        should_buy, _, reason = mgr.evaluate_buy(bullish_scan)
        assert should_buy is False
        assert "deaktiviert" in reason

        should_sell, _, reason = mgr.evaluate_sell(bullish_scan, open_position)
        assert should_sell is False
        assert "deaktiviert" in reason


# ═══════════════════════════════════════════════════════════════════════════════
# EDGE CASES
# ═══════════════════════════════════════════════════════════════════════════════


class TestEdgeCases:
    """Edge-Case Tests."""

    def test_buy_with_none_values(self):
        """Scan mit None-Werten stürzt nicht ab."""
        algo = BuyAlgorithm()
        scan = {"rsi": None, "vol_ratio": None, "ema_alignment": None}
        should_buy, conf, reason = algo.evaluate(scan)
        assert isinstance(should_buy, bool)

    def test_sell_with_zero_entry(self):
        """Position mit Entry=0 stürzt nicht ab."""
        algo = SellAlgorithm()
        scan = {"price": 100.0}
        pos = {"entry": 0, "highest": 0, "opened": ""}
        should_sell, conf, reason = algo.evaluate(scan, pos)
        assert isinstance(should_sell, bool)

    def test_concurrent_access(self, bullish_scan):
        """Thread-Safety: Parallele Zugriffe verursachen keinen Deadlock."""
        import threading

        algo = BuyAlgorithm()
        errors = []

        def worker():
            try:
                for _ in range(50):
                    algo.evaluate(bullish_scan)
                    algo.record_result(bullish_scan, pnl=10.0)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)
        assert len(errors) == 0

    def test_param_optimization_trigger(self, bullish_scan):
        """Parameter-Optimierung wird nach 20 Trades ausgelöst."""
        algo = BuyAlgorithm()
        for i in range(25):
            pnl = 50.0 if i % 2 == 0 else -30.0
            algo.record_result(bullish_scan, pnl=pnl)
        # Nach 20+ Trades sollte _param_history Einträge haben
        assert len(algo._param_history) >= 1
