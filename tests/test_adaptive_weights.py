"""Tests für die Adaptive Strategy Weighting Engine."""

import pytest

from services.adaptive_weights import _DEFAULT_STRATEGIES, AdaptiveWeights


class TestAdaptiveWeights:
    """Tests für die AdaptiveWeights-Klasse."""

    def test_initial_weights_all_one(self):
        aw = AdaptiveWeights()
        weights = aw.get_weights()
        assert all(w == 1.0 for w in weights.values())
        assert len(weights) == len(_DEFAULT_STRATEGIES)

    def test_record_vote(self):
        aw = AdaptiveWeights(min_samples=2)
        aw.record_vote("EMA-Trend", won=True, regime="bull")
        stats = aw.stats()
        assert stats["total_votes"] == 1

    def test_winning_strategy_gets_higher_weight(self):
        aw = AdaptiveWeights(min_samples=5)
        # EMA-Trend gewinnt immer
        for _ in range(20):
            aw.record_vote("EMA-Trend", won=True, regime="bull")
        # RSI verliert immer
        for _ in range(20):
            aw.record_vote("RSI-Stochastic", won=False, regime="bull")
        weights = aw.get_weights()
        assert weights["EMA-Trend"] > weights["RSI-Stochastic"]

    def test_weights_clamped(self):
        aw = AdaptiveWeights(min_samples=3, min_weight=0.3, max_weight=2.5)
        for _ in range(30):
            aw.record_vote("EMA-Trend", won=True)
            aw.record_vote("RSI-Stochastic", won=False)
        weights = aw.get_weights()
        for w in weights.values():
            assert 0.3 <= w <= 2.5

    def test_too_few_samples_no_adaptation(self):
        aw = AdaptiveWeights(min_samples=10)
        for _ in range(5):
            aw.record_vote("EMA-Trend", won=True)
        weights = aw.get_weights()
        # Sollte bei 1.0 bleiben (zu wenig Daten)
        assert weights["EMA-Trend"] == 1.0

    def test_regime_specific_weights(self):
        aw = AdaptiveWeights(min_samples=5)
        # EMA gut in Bull, schlecht in Bear
        for _ in range(15):
            aw.record_vote("EMA-Trend", won=True, regime="bull")
            aw.record_vote("EMA-Trend", won=False, regime="bear")

        bull_w = aw.get_weights(regime="bull")
        bear_w = aw.get_weights(regime="bear")
        assert bull_w["EMA-Trend"] > bear_w["EMA-Trend"]

    def test_window_trimming(self):
        aw = AdaptiveWeights(window_size=10, min_samples=5)
        for _ in range(20):
            aw.record_vote("EMA-Trend", won=True)
        # Sollte nur die letzten 10 behalten
        assert len(aw._global_history["EMA-Trend"]) == 10

    def test_strategy_performance(self):
        aw = AdaptiveWeights(min_samples=3)
        for _ in range(10):
            aw.record_vote("EMA-Trend", won=True)
        for _ in range(5):
            aw.record_vote("EMA-Trend", won=False)
        perf = aw.strategy_performance()
        ema = next(p for p in perf if p["strategy"] == "EMA-Trend")
        assert ema["trades"] == 15
        assert ema["wins"] == 10
        assert ema["win_rate"] == pytest.approx(66.7, abs=0.1)

    def test_regime_performance(self):
        aw = AdaptiveWeights(min_samples=3)
        for _ in range(10):
            aw.record_vote("EMA-Trend", won=True, regime="bull")
        result = aw.regime_performance()
        assert "bull" in result
        assert any(s["strategy"] == "EMA-Trend" for s in result["bull"])

    def test_load_from_trades(self):
        aw = AdaptiveWeights(min_samples=1)
        trades = [
            {"reason": "EMA-Trend+MACD", "pnl": 100.0, "regime": "bull"},
            {"reason": "RSI-Stochastic", "pnl": -50.0, "regime": "bear"},
            {"reason": "unknown_strat", "pnl": 10.0, "regime": "range"},
        ]
        count = aw.load_from_trades(trades)
        # Nur 2 sollten erkannt werden (EMA-Trend und RSI-Stochastic)
        assert count == 2

    def test_extract_strategy(self):
        aw = AdaptiveWeights()
        assert aw._extract_strategy("EMA-Trend+MACD-Kreuzung") == "EMA-Trend"
        assert aw._extract_strategy("RSI-Stochastic") == "RSI-Stochastic"
        assert aw._extract_strategy("unknown") is None

    def test_to_dict(self):
        aw = AdaptiveWeights()
        d = aw.to_dict()
        assert d["enabled"] is True
        assert "weights" in d
        assert "performance" in d
        assert "total_votes" in d

    def test_exponential_decay(self):
        """Neuere Trades sollten stärker gewichtet werden als ältere."""
        aw = AdaptiveWeights(min_samples=5, window_size=20)
        # Erst 10 Losses, dann 10 Wins → Decay-gewichtete WR > 50%
        for _ in range(10):
            aw.record_vote("EMA-Trend", won=False)
        for _ in range(10):
            aw.record_vote("EMA-Trend", won=True)

        # Vergleich: andere Strategie mit erst Wins dann Losses
        for _ in range(10):
            aw.record_vote("RSI-Stochastic", won=True)
        for _ in range(10):
            aw.record_vote("RSI-Stochastic", won=False)

        weights = aw.get_weights()
        # EMA (neuere Wins) sollte höher gewichtet sein als RSI (neuere Losses)
        assert weights["EMA-Trend"] > weights["RSI-Stochastic"]

    def test_normalization(self):
        """Durchschnitt aller Gewichte sollte ~1.0 sein."""
        aw = AdaptiveWeights(min_samples=3)
        for s in _DEFAULT_STRATEGIES:
            for _ in range(10):
                aw.record_vote(s, won=True)
        weights = aw.get_weights()
        avg = sum(weights.values()) / len(weights)
        assert abs(avg - 1.0) < 0.15  # Toleranz wegen Clamping

    def test_stats(self):
        aw = AdaptiveWeights(min_samples=5)
        for _ in range(10):
            aw.record_vote("EMA-Trend", won=True, regime="bull")
        stats = aw.stats()
        assert stats["total_votes"] == 10
        assert stats["strategies_adapted"] == 1
        assert "bull" in stats["regimes_tracked"]

    def test_custom_strategies(self):
        custom = ["Alpha", "Beta", "Gamma"]
        aw = AdaptiveWeights(strategies=custom)
        weights = aw.get_weights()
        assert set(weights.keys()) == set(custom)

    def test_get_weights_unknown_regime(self):
        aw = AdaptiveWeights()
        # Unbekanntes Regime → globale Gewichte
        weights = aw.get_weights(regime="nonexistent")
        assert all(w == 1.0 for w in weights.values())
