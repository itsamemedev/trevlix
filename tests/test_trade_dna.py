"""Tests für Trade DNA Fingerprinting & Pattern Mining.

Testet:
- DNA-Berechnung (Fingerprint-Erzeugung)
- Confidence-Anpassung (Boost/Block/Neutral)
- Pattern-Recording und Win-Rate-Tracking
- Ähnlichkeitssuche (find_similar)
- Statistik-Funktionen (top_patterns, worst_patterns)
- Historischen Trade-Import (load_from_trades)
"""

from services.trade_dna import TradeDNA, _bucketize, _hour_bucket

# ── Bucket-Funktionen ────────────────────────────────────────────────────


class TestBucketFunctions:
    """Tests für Bucket-Hilfsfunktionen."""

    def test_bucketize_first_bucket(self):
        """Wert fällt in den ersten Bucket."""
        buckets = [(10, "low"), (20, "mid"), (float("inf"), "high")]
        assert _bucketize(5, buckets) == "low"

    def test_bucketize_last_bucket(self):
        """Wert fällt in den letzten Bucket."""
        buckets = [(10, "low"), (20, "mid"), (float("inf"), "high")]
        assert _bucketize(25, buckets) == "high"

    def test_bucketize_boundary(self):
        """Wert auf der Grenze fällt in den nächsten Bucket."""
        buckets = [(10, "low"), (20, "mid"), (float("inf"), "high")]
        assert _bucketize(10, buckets) == "mid"

    def test_hour_bucket_asia(self):
        """Stunden 0-7 UTC → Asia."""
        assert _hour_bucket(3) == "asia"
        assert _hour_bucket(0) == "asia"

    def test_hour_bucket_europe(self):
        """Stunden 8-15 UTC → Europe."""
        assert _hour_bucket(10) == "europe"

    def test_hour_bucket_us(self):
        """Stunden 16-21 UTC → US."""
        assert _hour_bucket(18) == "us"

    def test_hour_bucket_off_hours(self):
        """Stunden 22-23 UTC → Off-Hours."""
        assert _hour_bucket(23) == "off_hours"


# ── DNA-Berechnung ───────────────────────────────────────────────────────


class TestTradeDNACompute:
    """Tests für DNA-Fingerprint-Berechnung."""

    def _make_scan(self, **overrides) -> dict:
        scan = {
            "atr_pct": 1.5,
            "news_score": 0.1,
            "ob_ratio": 0.6,
            "confidence": 0.65,
        }
        scan.update(overrides)
        return scan

    def test_compute_returns_required_keys(self):
        """compute() gibt alle erwarteten Schlüssel zurück."""
        dna = TradeDNA()
        result = dna.compute("BTC/USDT", self._make_scan(), "bull", fg_value=55)
        assert "hash" in result
        assert "fingerprint" in result
        assert "dimensions" in result
        assert "raw_values" in result
        assert "symbol" in result
        assert result["symbol"] == "BTC/USDT"

    def test_compute_deterministic(self):
        """Gleiche Eingaben → gleicher Fingerprint."""
        dna = TradeDNA()
        scan = self._make_scan()
        r1 = dna.compute("ETH/USDT", scan, "bull", fg_value=55)
        r2 = dna.compute("ETH/USDT", scan, "bull", fg_value=55)
        assert r1["hash"] == r2["hash"]
        assert r1["fingerprint"] == r2["fingerprint"]

    def test_compute_different_regime_different_hash(self):
        """Verschiedene Regime → verschiedene Fingerprints."""
        dna = TradeDNA()
        scan = self._make_scan()
        r_bull = dna.compute("BTC/USDT", scan, "bull", fg_value=50)
        r_bear = dna.compute("BTC/USDT", scan, "bear", fg_value=50)
        assert r_bull["hash"] != r_bear["hash"]

    def test_compute_dimensions_correct(self):
        """Dimensionen werden korrekt berechnet."""
        dna = TradeDNA()
        scan = self._make_scan(atr_pct=0.3, news_score=-0.5, ob_ratio=0.3, confidence=0.8)
        result = dna.compute("BTC/USDT", scan, "bear", fg_value=15)
        dims = result["dimensions"]
        assert dims["regime"] == "bear"
        assert dims["volatility"] == "low"
        assert dims["fear_greed"] == "extreme_fear"
        assert dims["news"] == "negative"
        assert dims["orderbook"] == "sell_pressure"
        assert dims["consensus"] == "unanimous"


# ── Confidence-Anpassung ─────────────────────────────────────────────────


class TestConfidenceAdjustment:
    """Tests für Konfidenz-Boost/Block-Logik."""

    def _make_scan(self) -> dict:
        return {"atr_pct": 1.5, "news_score": 0.1, "ob_ratio": 0.6, "confidence": 0.65}

    def test_neutral_when_no_data(self):
        """Neutral wenn zu wenig historische Daten."""
        dna = TradeDNA(min_matches=5)
        result = dna.compute("BTC/USDT", self._make_scan(), "bull")
        adj = dna.confidence_adjustment(result)
        assert adj["action"] == "neutral"
        assert adj["multiplier"] == 1.0

    def test_boost_on_high_win_rate(self):
        """Boost wenn historische Win-Rate hoch."""
        dna_engine = TradeDNA(min_matches=3, boost_threshold=0.65)
        scan = self._make_scan()
        dna = dna_engine.compute("BTC/USDT", scan, "bull")
        # 5 Wins, 1 Loss → 83% WR → Boost
        for _ in range(5):
            dna_engine.record(dna, won=True)
        dna_engine.record(dna, won=False)
        adj = dna_engine.confidence_adjustment(dna)
        assert adj["action"] == "boost"
        assert adj["multiplier"] > 1.0
        assert adj["win_rate"] > 65

    def test_block_on_low_win_rate(self):
        """Block wenn historische Win-Rate niedrig."""
        dna_engine = TradeDNA(min_matches=3, block_threshold=0.35)
        scan = self._make_scan()
        dna = dna_engine.compute("BTC/USDT", scan, "bull")
        # 1 Win, 5 Losses → 17% WR → Block
        dna_engine.record(dna, won=True)
        for _ in range(5):
            dna_engine.record(dna, won=False)
        adj = dna_engine.confidence_adjustment(dna)
        assert adj["action"] == "block"
        assert adj["multiplier"] < 0.5


# ── Pattern-Tracking ─────────────────────────────────────────────────────


class TestPatternTracking:
    """Tests für Pattern-Recording und Statistiken."""

    def test_record_updates_stats(self):
        """record() aktualisiert Pattern-Statistiken korrekt."""
        dna_engine = TradeDNA()
        scan = {"atr_pct": 1.0, "news_score": 0.0, "ob_ratio": 0.5, "confidence": 0.5}
        dna = dna_engine.compute("BTC/USDT", scan, "bull")
        dna_engine.record(dna, won=True)
        dna_engine.record(dna, won=False)
        stats = dna_engine.stats()
        assert stats["total_trades"] == 2
        assert stats["total_patterns"] == 1

    def test_top_patterns_sorted(self):
        """top_patterns() sortiert nach Win-Rate absteigend."""
        dna_engine = TradeDNA(min_matches=2)
        scan1 = {"atr_pct": 0.3, "news_score": 0.0, "ob_ratio": 0.5, "confidence": 0.5}
        scan2 = {"atr_pct": 3.5, "news_score": 0.0, "ob_ratio": 0.5, "confidence": 0.5}
        dna1 = dna_engine.compute("BTC/USDT", scan1, "bull")
        dna2 = dna_engine.compute("BTC/USDT", scan2, "bull")
        # Pattern 1: 100% WR
        for _ in range(3):
            dna_engine.record(dna1, won=True)
        # Pattern 2: 33% WR
        dna_engine.record(dna2, won=True)
        dna_engine.record(dna2, won=False)
        dna_engine.record(dna2, won=False)
        top = dna_engine.top_patterns(2)
        assert len(top) == 2
        assert top[0]["win_rate"] >= top[1]["win_rate"]

    def test_find_similar_returns_matches(self):
        """find_similar() findet ähnliche historische Trades."""
        dna_engine = TradeDNA()
        scan = {"atr_pct": 1.5, "news_score": 0.1, "ob_ratio": 0.6, "confidence": 0.65}
        dna = dna_engine.compute("BTC/USDT", scan, "bull")
        dna_engine.record(dna, won=True)
        similar = dna_engine.find_similar(dna)
        assert len(similar) >= 1
        assert similar[0]["similarity"] == 100.0

    def test_load_from_trades(self):
        """load_from_trades() importiert historische Trades."""
        dna_engine = TradeDNA()
        trades = [
            {
                "symbol": "BTC/USDT",
                "pnl": 100,
                "regime": "bull",
                "confidence": 0.7,
                "news_score": 0.2,
                "onchain_score": 0.3,
            },
            {
                "symbol": "ETH/USDT",
                "pnl": -50,
                "regime": "bear",
                "confidence": 0.4,
                "news_score": -0.3,
                "onchain_score": -0.1,
            },
        ]
        count = dna_engine.load_from_trades(trades)
        assert count == 2
        assert dna_engine.stats()["total_trades"] == 2

    def test_to_dict_structure(self):
        """to_dict() gibt die erwartete Struktur zurück."""
        dna_engine = TradeDNA()
        result = dna_engine.to_dict()
        assert "enabled" in result
        assert "total_patterns" in result
        assert "total_trades" in result
        assert "avg_win_rate" in result
        assert "top_patterns" in result
