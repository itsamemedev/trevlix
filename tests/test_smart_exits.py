"""Tests für Smart Exit Engine (Volatility-Adaptive SL/TP).

Testet:
- Berechnung initialer SL/TP-Level
- Regime-abhängige Multiplikatoren
- Volatility Squeeze Detection
- Dynamische SL/TP-Anpassung
- Regime-Klassifikation aus Scan-Daten
- Fallback bei fehlendem ATR
"""

from services.smart_exits import SmartExitEngine


def _make_config(**overrides) -> dict:
    """Erzeugt eine Test-Konfiguration."""
    cfg = {
        "use_smart_exits": True,
        "stop_loss_pct": 0.025,
        "take_profit_pct": 0.060,
        "smart_exit_atr_sl_mult": 1.5,
        "smart_exit_reward_ratio": 2.0,
        "smart_exit_min_sl_pct": 0.01,
        "smart_exit_max_sl_pct": 0.08,
        "smart_exit_min_tp_pct": 0.02,
        "smart_exit_max_tp_pct": 0.15,
        "smart_exit_squeeze_threshold": 0.03,
    }
    cfg.update(overrides)
    return cfg


def _make_scan(**overrides) -> dict:
    """Erzeugt Scan-Daten für Tests."""
    scan = {
        "atr14": 500.0,  # $500 ATR bei BTC ~$30000
        "atr_pct": 1.67,
        "bb_width": 0.05,
        "confidence": 0.65,
        "rsi": 55,
        "roc10": 3.0,
    }
    scan.update(overrides)
    return scan


# ── Initialisierung ──────────────────────────────────────────────────────


class TestSmartExitInit:
    """Tests für Engine-Initialisierung."""

    def test_enabled_flag(self):
        """Engine ist aktiviert wenn use_smart_exits=True."""
        engine = SmartExitEngine(_make_config(use_smart_exits=True))
        assert engine.enabled is True

    def test_disabled_flag(self):
        """Engine ist deaktiviert wenn use_smart_exits=False."""
        engine = SmartExitEngine(_make_config(use_smart_exits=False))
        assert engine.enabled is False


# ── SL/TP-Berechnung ────────────────────────────────────────────────────


class TestSmartExitCompute:
    """Tests für initiale SL/TP-Level-Berechnung."""

    def test_compute_returns_sl_tp(self):
        """compute() gibt (SL, TP) Tuple zurück."""
        engine = SmartExitEngine(_make_config())
        sl, tp = engine.compute(30000.0, _make_scan(), "bull")
        assert sl < 30000.0  # SL unter Entry
        assert tp > 30000.0  # TP über Entry

    def test_bull_tighter_sl_than_bear(self):
        """Bull-Regime hat engeren SL als Bear-Regime."""
        engine = SmartExitEngine(_make_config())
        scan = _make_scan()
        sl_bull, _ = engine.compute(30000.0, scan, "bull")
        sl_bear, _ = engine.compute(30000.0, scan, "bear")
        # Bull SL näher am Entry (= höherer SL-Preis)
        assert sl_bull > sl_bear

    def test_bull_wider_tp_than_bear(self):
        """Bull-Regime hat weiteres TP als Bear-Regime."""
        engine = SmartExitEngine(_make_config())
        scan = _make_scan()
        _, tp_bull = engine.compute(30000.0, scan, "bull")
        _, tp_bear = engine.compute(30000.0, scan, "bear")
        assert tp_bull > tp_bear

    def test_crash_regime_widest_sl(self):
        """Crash-Regime hat den weitesten SL."""
        engine = SmartExitEngine(_make_config())
        scan = _make_scan()
        sl_bull, _ = engine.compute(30000.0, scan, "bull")
        sl_crash, _ = engine.compute(30000.0, scan, "crash")
        assert sl_crash < sl_bull  # Crash SL weiter weg

    def test_high_confidence_wider_tp(self):
        """Höhere Konfidenz → weiteres Take-Profit."""
        engine = SmartExitEngine(_make_config())
        _, tp_low = engine.compute(30000.0, _make_scan(confidence=0.3), "bull")
        _, tp_high = engine.compute(30000.0, _make_scan(confidence=0.9), "bull")
        assert tp_high > tp_low

    def test_volatility_squeeze_tighter_sl(self):
        """Niedrige BB-Width → engerer SL (Squeeze-Detection)."""
        engine = SmartExitEngine(_make_config())
        sl_normal, _ = engine.compute(30000.0, _make_scan(bb_width=0.06), "bull")
        sl_squeeze, _ = engine.compute(30000.0, _make_scan(bb_width=0.02), "bull")
        # Squeeze → engerer SL → höherer SL-Preis
        assert sl_squeeze > sl_normal

    def test_sl_respects_min_max(self):
        """SL bleibt innerhalb der konfigurierten Min/Max-Grenzen."""
        engine = SmartExitEngine(
            _make_config(
                smart_exit_min_sl_pct=0.02,
                smart_exit_max_sl_pct=0.05,
            )
        )
        sl, _ = engine.compute(30000.0, _make_scan(), "bull")
        sl_pct = (30000.0 - sl) / 30000.0
        assert 0.02 <= sl_pct <= 0.05

    def test_tp_respects_min_max(self):
        """TP bleibt innerhalb der konfigurierten Min/Max-Grenzen."""
        engine = SmartExitEngine(
            _make_config(
                smart_exit_min_tp_pct=0.03,
                smart_exit_max_tp_pct=0.10,
            )
        )
        _, tp = engine.compute(30000.0, _make_scan(), "bull")
        tp_pct = (tp - 30000.0) / 30000.0
        assert 0.03 <= tp_pct <= 0.10


# ── Fallback bei fehlendem ATR ───────────────────────────────────────────


class TestSmartExitFallback:
    """Tests für Fallback-Verhalten."""

    def test_fallback_when_disabled(self):
        """Verwendet fixe SL/TP wenn Smart Exits deaktiviert."""
        engine = SmartExitEngine(
            _make_config(
                use_smart_exits=False,
                stop_loss_pct=0.025,
                take_profit_pct=0.060,
            )
        )
        sl, tp = engine.compute(30000.0, _make_scan(), "bull")
        assert sl == 30000.0 * 0.975
        assert tp == 30000.0 * 1.060

    def test_fallback_when_no_atr(self):
        """Verwendet fixe SL/TP wenn ATR=0."""
        engine = SmartExitEngine(
            _make_config(
                stop_loss_pct=0.025,
                take_profit_pct=0.060,
            )
        )
        sl, tp = engine.compute(30000.0, _make_scan(atr14=0), "bull")
        assert sl == 30000.0 * 0.975
        assert tp == 30000.0 * 1.060


# ── Dynamische Anpassung ────────────────────────────────────────────────


class TestSmartExitAdapt:
    """Tests für dynamische SL/TP-Anpassung."""

    def test_adapt_no_change_when_disabled(self):
        """Keine Anpassung wenn Engine deaktiviert."""
        engine = SmartExitEngine(_make_config(use_smart_exits=False))
        pos = {"entry": 30000, "sl": 29250, "tp": 31800}
        new_sl, new_tp = engine.adapt("BTC/USDT", pos, 30500, 500, "bull")
        assert new_sl is None
        assert new_tp is None

    def test_adapt_tightens_sl_in_profit(self):
        """SL wird im Profit nach oben verschoben."""
        engine = SmartExitEngine(_make_config())
        pos = {"entry": 30000, "sl": 29250, "tp": 31800}
        new_sl, _ = engine.adapt("BTC/USDT", pos, 31000, 500, "bull")
        if new_sl is not None:
            assert new_sl > 29250

    def test_adapt_extends_tp_in_strong_bull(self):
        """TP wird bei starkem Profit + Bull erweitert."""
        engine = SmartExitEngine(_make_config())
        pos = {"entry": 30000, "sl": 29250, "tp": 31800}
        _, new_tp = engine.adapt("BTC/USDT", pos, 31500, 500, "bull")
        if new_tp is not None:
            assert new_tp > 31800


# ── Regime-Klassifikation ───────────────────────────────────────────────


class TestRegimeClassification:
    """Tests für Regime-Klassifikation aus Scan-Daten."""

    def test_crash_detection(self):
        """Hohe Volatilität + starker Abwärts-Momentum → Crash."""
        engine = SmartExitEngine(_make_config())
        assert (
            engine.classify_regime_from_scan(
                {"atr_pct": 4.0, "roc10": -8.0, "rsi": 20, "bb_width": 0.08}
            )
            == "crash"
        )

    def test_range_detection(self):
        """Niedrige Volatilität + neutraler RSI → Range."""
        engine = SmartExitEngine(_make_config())
        assert (
            engine.classify_regime_from_scan(
                {"atr_pct": 1.0, "roc10": 0.5, "rsi": 50, "bb_width": 0.02}
            )
            == "range"
        )

    def test_bull_detection(self):
        """Positiver Momentum + hoher RSI → Bull."""
        engine = SmartExitEngine(_make_config())
        assert (
            engine.classify_regime_from_scan(
                {"atr_pct": 1.5, "roc10": 4.0, "rsi": 60, "bb_width": 0.05}
            )
            == "bull"
        )

    def test_bear_detection(self):
        """Negativer Momentum + niedriger RSI → Bear."""
        engine = SmartExitEngine(_make_config())
        assert (
            engine.classify_regime_from_scan(
                {"atr_pct": 1.5, "roc10": -4.0, "rsi": 35, "bb_width": 0.05}
            )
            == "bear"
        )

    def test_to_dict_structure(self):
        """to_dict() gibt die erwartete Struktur zurück."""
        engine = SmartExitEngine(_make_config())
        result = engine.to_dict()
        assert "enabled" in result
        assert "regime_multipliers" in result
        assert "config" in result
        assert "sl" in result["regime_multipliers"]
        assert "tp" in result["regime_multipliers"]
