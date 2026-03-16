"""TREVLIX – Trade DNA Fingerprinting & Pattern Mining.

Jeder Trade bekommt einen einzigartigen "DNA-Fingerprint" basierend auf
den exakten Marktbedingungen zum Zeitpunkt der Trade-Eröffnung. Das System
lernt, welche DNA-Muster historisch profitabel waren und passt die
Konfidenz zukünftiger Trades mit ähnlichem Fingerprint an.

DNA-Dimensionen:
    1. Regime (bull/bear/range/crash)
    2. Volatilität (low/mid/high/extreme)
    3. Fear & Greed Bucket (extreme_fear/fear/neutral/greed/extreme_greed)
    4. News Sentiment (negative/neutral/positive)
    5. Orderbook Imbalance (sell/balanced/buy)
    6. Vote-Konsensus (weak/moderate/strong/unanimous)
    7. Tageszeit-Bucket (asia/europe/us/off_hours)

Verwendung:
    from services.trade_dna import TradeDNA

    dna = TradeDNA()
    fingerprint = dna.compute("BTC/USDT", scan_data, regime_str)
    boost = dna.confidence_adjustment(fingerprint)
    dna.record(fingerprint, won=True)
"""

import hashlib
import logging
import threading
from collections import defaultdict
from datetime import datetime
from typing import Any

import numpy as np

log = logging.getLogger("trevlix.trade_dna")

# ── DNA-Bucket-Definitionen ─────────────────────────────────────────────────

_VOL_BUCKETS = [
    (0.5, "low"),
    (1.5, "mid"),
    (3.0, "high"),
    (float("inf"), "extreme"),
]

_FG_BUCKETS = [
    (20, "extreme_fear"),
    (40, "fear"),
    (60, "neutral"),
    (80, "greed"),
    (101, "extreme_greed"),
]

_NEWS_BUCKETS = [
    (-0.2, "negative"),
    (0.2, "neutral"),
    (float("inf"), "positive"),
]

_OB_BUCKETS = [
    (0.40, "sell_pressure"),
    (0.55, "balanced"),
    (float("inf"), "buy_pressure"),
]

_VOTE_BUCKETS = [
    (0.40, "weak"),
    (0.55, "moderate"),
    (0.70, "strong"),
    (float("inf"), "unanimous"),
]

_HOUR_BUCKETS = [
    (8, "asia"),  # 00:00-07:59 UTC
    (16, "europe"),  # 08:00-15:59 UTC
    (22, "us"),  # 16:00-21:59 UTC
    (24, "off_hours"),  # 22:00-23:59 UTC
]


def _bucketize(value: float, buckets: list[tuple[float, str]]) -> str:
    """Ordnet einen Wert dem passenden Bucket zu.

    Args:
        value: Einzuordnender Wert.
        buckets: Liste von (Obergrenze, Label) Tupeln.

    Returns:
        Label des passenden Buckets.
    """
    for threshold, label in buckets:
        if value < threshold:
            return label
    return buckets[-1][1]


def _hour_bucket(hour: int) -> str:
    """Ordnet eine Stunde (0-23 UTC) einem Markt-Bucket zu.

    Args:
        hour: Stunde im UTC-Format.

    Returns:
        Markt-Bucket-Label.
    """
    return _bucketize(hour, _HOUR_BUCKETS)


class TradeDNA:
    """Trade DNA Fingerprinting & Pattern Mining Engine.

    Erzeugt für jeden Trade einen reproduzierbaren Fingerprint aus den
    Marktbedingungen und lernt, welche Fingerprint-Muster profitabel sind.

    Args:
        min_matches: Mindestanzahl historischer Matches für Konfidenz-Anpassung.
        boost_threshold: Win-Rate ab der ein Boost gewährt wird.
        block_threshold: Win-Rate unter der ein Trade blockiert wird.
        max_history: Maximale Anzahl gespeicherter DNA-Einträge.
    """

    def __init__(
        self,
        min_matches: int = 5,
        boost_threshold: float = 0.65,
        block_threshold: float = 0.35,
        max_history: int = 2000,
    ) -> None:
        self._min_matches = min_matches
        self._boost_threshold = boost_threshold
        self._block_threshold = block_threshold
        self._max_history = max_history
        self._lock = threading.Lock()
        # Fingerprint → [win_count, total_count]
        self._pattern_stats: dict[str, list[int]] = defaultdict(lambda: [0, 0])
        # Letzte N DNA-Einträge für Ähnlichkeitssuche
        self._history: list[dict[str, Any]] = []

    def compute(
        self,
        symbol: str,
        scan: dict[str, Any],
        regime: str,
        fg_value: int = 50,
    ) -> dict[str, Any]:
        """Berechnet den DNA-Fingerprint für einen Trade.

        Args:
            symbol: Trading-Pair (z.B. 'BTC/USDT').
            scan: Scan-Ergebnis-Dict mit Indikatoren.
            regime: Aktuelles Marktregime ('bull', 'bear', etc.).
            fg_value: Fear & Greed Index (0-100).

        Returns:
            DNA-Dict mit Fingerprint, Hash und allen Dimensionen.
        """
        atr_pct = scan.get("atr_pct", 1.0)
        news_score = scan.get("news_score", 0.0)
        ob_ratio = scan.get("ob_ratio", 0.5)
        confidence = scan.get("confidence", 0.5)
        hour = datetime.now().hour

        dimensions = {
            "regime": regime,
            "volatility": _bucketize(atr_pct, _VOL_BUCKETS),
            "fear_greed": _bucketize(fg_value, _FG_BUCKETS),
            "news": _bucketize(news_score, _NEWS_BUCKETS),
            "orderbook": _bucketize(ob_ratio, _OB_BUCKETS),
            "consensus": _bucketize(confidence, _VOTE_BUCKETS),
            "session": _hour_bucket(hour),
        }

        # Deterministischer Hash aus allen Dimensionen
        fingerprint_str = "|".join(f"{k}={v}" for k, v in sorted(dimensions.items()))
        fingerprint_hash = hashlib.sha256(fingerprint_str.encode()).hexdigest()[:16]

        return {
            "symbol": symbol,
            "hash": fingerprint_hash,
            "fingerprint": fingerprint_str,
            "dimensions": dimensions,
            "raw_values": {
                "atr_pct": round(atr_pct, 3),
                "fg_value": fg_value,
                "news_score": round(news_score, 3),
                "ob_ratio": round(ob_ratio, 3),
                "confidence": round(confidence, 3),
                "hour": hour,
            },
            "timestamp": datetime.now().isoformat(),
        }

    def confidence_adjustment(self, dna: dict[str, Any]) -> dict[str, Any]:
        """Berechnet die Konfidenz-Anpassung basierend auf historischen DNA-Matches.

        Args:
            dna: DNA-Dict aus ``compute()``.

        Returns:
            Dict mit ``multiplier`` (0.0-1.5), ``win_rate``, ``matches``,
            ``action`` ('boost'/'block'/'neutral') und ``reason``.
        """
        fp = dna["fingerprint"]
        with self._lock:
            stats = self._pattern_stats.get(fp)
            if not stats or stats[1] < self._min_matches:
                return {
                    "multiplier": 1.0,
                    "win_rate": None,
                    "matches": stats[1] if stats else 0,
                    "action": "neutral",
                    "reason": f"Zu wenig Daten ({stats[1] if stats else 0}/{self._min_matches})",
                }

            wr = stats[0] / stats[1]

        if wr >= self._boost_threshold:
            mult = min(1.0 + (wr - self._boost_threshold) * 2, 1.5)
            return {
                "multiplier": round(mult, 3),
                "win_rate": round(wr * 100, 1),
                "matches": stats[1],
                "action": "boost",
                "reason": f"DNA-Pattern WR {wr * 100:.0f}% ({stats[1]} Trades)",
            }
        elif wr <= self._block_threshold:
            mult = max(wr / self._block_threshold * 0.5, 0.0)
            return {
                "multiplier": round(mult, 3),
                "win_rate": round(wr * 100, 1),
                "matches": stats[1],
                "action": "block",
                "reason": f"DNA-Pattern WR nur {wr * 100:.0f}% ({stats[1]} Trades)",
            }

        return {
            "multiplier": 1.0,
            "win_rate": round(wr * 100, 1),
            "matches": stats[1],
            "action": "neutral",
            "reason": f"DNA-Pattern WR {wr * 100:.0f}% (normal)",
        }

    def record(self, dna: dict[str, Any], won: bool) -> None:
        """Zeichnet das Ergebnis eines Trades für den DNA-Fingerprint auf.

        Args:
            dna: DNA-Dict aus ``compute()``.
            won: True wenn der Trade profitabel war.
        """
        fp = dna["fingerprint"]
        with self._lock:
            stats = self._pattern_stats[fp]
            if won:
                stats[0] += 1
            stats[1] += 1

            entry = {
                **dna,
                "won": won,
                "recorded_at": datetime.now().isoformat(),
            }
            self._history.append(entry)
            if len(self._history) > self._max_history:
                self._history = self._history[-self._max_history :]

    def find_similar(self, dna: dict[str, Any], top_n: int = 5) -> list[dict[str, Any]]:
        """Findet die ähnlichsten historischen DNA-Fingerprints.

        Verwendet Dimension-Matching: Je mehr Dimensionen übereinstimmen,
        desto ähnlicher ist der Trade.

        Args:
            dna: DNA-Dict aus ``compute()``.
            top_n: Maximale Anzahl Ergebnisse.

        Returns:
            Liste der ähnlichsten historischen Trades mit Similarity-Score.
        """
        target_dims = dna["dimensions"]
        n_dims = len(target_dims)
        results: list[tuple[float, dict]] = []

        with self._lock:
            for entry in self._history:
                match_count = sum(
                    1 for k, v in target_dims.items() if entry.get("dimensions", {}).get(k) == v
                )
                similarity = match_count / n_dims
                if similarity >= 0.5:  # Min. 50% Übereinstimmung
                    results.append((similarity, entry))

        results.sort(key=lambda x: x[0], reverse=True)
        return [
            {
                "similarity": round(sim * 100, 0),
                "hash": e["hash"],
                "fingerprint": e["fingerprint"],
                "symbol": e.get("symbol", "?"),
                "won": e.get("won"),
                "timestamp": e.get("timestamp", ""),
            }
            for sim, e in results[:top_n]
        ]

    def top_patterns(self, n: int = 10) -> list[dict[str, Any]]:
        """Gibt die Top-N profitabelsten DNA-Muster zurück.

        Args:
            n: Anzahl Ergebnisse.

        Returns:
            Liste der profitabelsten Muster mit Win-Rate und Trade-Count.
        """
        with self._lock:
            patterns = [
                {
                    "fingerprint": fp,
                    "win_rate": round(stats[0] / stats[1] * 100, 1),
                    "wins": stats[0],
                    "total": stats[1],
                }
                for fp, stats in self._pattern_stats.items()
                if stats[1] >= self._min_matches
            ]
        patterns.sort(key=lambda x: x["win_rate"], reverse=True)
        return patterns[:n]

    def worst_patterns(self, n: int = 5) -> list[dict[str, Any]]:
        """Gibt die N schlechtesten DNA-Muster zurück.

        Args:
            n: Anzahl Ergebnisse.

        Returns:
            Liste der verlustreichsten Muster mit Win-Rate und Trade-Count.
        """
        with self._lock:
            patterns = [
                {
                    "fingerprint": fp,
                    "win_rate": round(stats[0] / stats[1] * 100, 1),
                    "wins": stats[0],
                    "total": stats[1],
                }
                for fp, stats in self._pattern_stats.items()
                if stats[1] >= self._min_matches
            ]
        patterns.sort(key=lambda x: x["win_rate"])
        return patterns[:n]

    def load_from_trades(self, closed_trades: list[dict[str, Any]]) -> int:
        """Lädt DNA-Pattern-Statistiken aus historischen Trades.

        Rekonstruiert Fingerprints aus gespeicherten Trade-Daten.
        Nützlich beim Bot-Neustart.

        Args:
            closed_trades: Liste abgeschlossener Trades aus state.closed_trades.

        Returns:
            Anzahl geladener Trades.
        """
        count = 0
        for trade in closed_trades:
            regime = trade.get("regime", "bull")
            confidence = trade.get("confidence", 0.5)
            news_score = trade.get("news_score", 0.0)
            won = trade.get("pnl", 0) > 0

            # Rekonstruiere vereinfachte Scan-Daten aus Trade-Metadaten
            scan_approx = {
                "atr_pct": 1.5,  # Default, da nicht in Trade gespeichert
                "news_score": news_score,
                "ob_ratio": 0.5,  # Default
                "confidence": confidence,
            }
            dna = self.compute(trade.get("symbol", "?"), scan_approx, regime, fg_value=50)
            self.record(dna, won)
            count += 1
        log.info(f"Trade-DNA: {count} historische Trades geladen")
        return count

    def stats(self) -> dict[str, Any]:
        """Gibt Gesamtstatistiken zurück.

        Returns:
            Dict mit total_patterns, total_trades, history_size und
            den Top-3 profitabelsten Mustern.
        """
        with self._lock:
            total_patterns = len(self._pattern_stats)
            total_trades = sum(s[1] for s in self._pattern_stats.values())
            avg_wr = (
                np.mean([s[0] / s[1] for s in self._pattern_stats.values() if s[1] > 0])
                if self._pattern_stats
                else 0.5
            )
        return {
            "total_patterns": total_patterns,
            "total_trades": total_trades,
            "history_size": len(self._history),
            "avg_win_rate": round(float(avg_wr) * 100, 1),
            "top_patterns": self.top_patterns(3),
            "worst_patterns": self.worst_patterns(3),
        }

    def to_dict(self) -> dict[str, Any]:
        """Serialisierung für Dashboard/API.

        Returns:
            Dict mit DNA-Engine-Status und Statistiken.
        """
        return {
            "enabled": True,
            "min_matches": self._min_matches,
            "boost_threshold": self._boost_threshold,
            "block_threshold": self._block_threshold,
            **self.stats(),
        }
