"""TREVLIX – Performance Attribution Engine.

Analysiert WOHER Gewinne und Verluste kommen. Zerlegt die Trading-Performance
in einzelne Faktoren: Strategie, Marktregime, Tageszeit, Symbol und
Fear & Greed Bucket.

Einzigartig: Kein anderer Open-Source-Trading-Bot bietet eine vollständige
Performance-Attribution wie sie bei Hedge Funds üblich ist.

Verwendung:
    from services.performance_attribution import PerformanceAttribution

    pa = PerformanceAttribution()
    pa.record_trade(trade_data)
    report = pa.full_report()
"""

import logging
import math
import threading
from collections import defaultdict
from datetime import datetime
from typing import Any

import numpy as np

log = logging.getLogger("trevlix.performance_attribution")

# ── Tageszeit-Buckets (UTC) ──────────────────────────────────────────────────
_SESSION_MAP = {
    range(0, 8): "asia",
    range(8, 16): "europe",
    range(16, 22): "us",
    range(22, 24): "off_hours",
}


def _hour_to_session(hour: int) -> str:
    """Ordnet eine UTC-Stunde einem Handelssession-Bucket zu."""
    for hours, label in _SESSION_MAP.items():
        if hour in hours:
            return label
    return "off_hours"


def _fg_bucket(value: int) -> str:
    """Ordnet den Fear & Greed Index einem Bucket zu."""
    value = max(0, min(value, 100))
    if value < 20:
        return "extreme_fear"
    elif value < 40:
        return "fear"
    elif value < 60:
        return "neutral"
    elif value < 80:
        return "greed"
    return "extreme_greed"


class _FactorStats:
    """Aggregierte Statistiken für einen einzelnen Faktor-Wert."""

    __slots__ = ("total_pnl", "wins", "losses", "total_trades", "pnl_list")

    def __init__(self) -> None:
        self.total_pnl: float = 0.0
        self.wins: int = 0
        self.losses: int = 0
        self.total_trades: int = 0
        self.pnl_list: list[float] = []

    def record(self, pnl: float) -> None:
        """Zeichnet einen Trade auf."""
        self.total_pnl += pnl
        self.total_trades += 1
        self.pnl_list.append(pnl)
        if pnl >= 0:
            self.wins += 1
        else:
            self.losses += 1

    def to_dict(self) -> dict[str, Any]:
        """Serialisiert die Statistiken."""
        wr = (self.wins / self.total_trades * 100) if self.total_trades > 0 else 0
        avg_pnl = (self.total_pnl / self.total_trades) if self.total_trades > 0 else 0
        pnl_arr = np.array(self.pnl_list) if self.pnl_list else np.array([0.0])
        return {
            "total_pnl": round(self.total_pnl, 2),
            "trades": self.total_trades,
            "wins": self.wins,
            "losses": self.losses,
            "win_rate": round(wr, 1),
            "avg_pnl": round(avg_pnl, 2),
            "best_trade": round(float(pnl_arr.max()), 2),
            "worst_trade": round(float(pnl_arr.min()), 2),
            "std_pnl": round(float(np.std(pnl_arr)), 2) if len(pnl_arr) > 1 else 0,
        }


class PerformanceAttribution:
    """Performance Attribution Engine – zerlegt Trading-Ergebnisse in Faktoren.

    Analysiert die Herkunft von Gewinnen und Verlusten über 5 Dimensionen:
    1. **Strategie** – Welche der 9 Voting-Strategien performte wie?
    2. **Marktregime** – Bull/Bear/Range/Crash Profitabilität
    3. **Tageszeit** – Asia/Europe/US/Off-Hours Performance
    4. **Symbol** – Welche Coins brachten Gewinn/Verlust?
    5. **Fear & Greed** – Performance je Sentiment-Bucket

    Args:
        max_trades: Maximale Anzahl gespeicherter Trades für Detailanalyse.
    """

    def __init__(self, max_trades: int = 5000) -> None:
        self._max_trades = max_trades
        self._lock = threading.Lock()
        self._trades: list[dict[str, Any]] = []

        # Faktor-Dimensionen: {dimension_name: {factor_value: _FactorStats}}
        self._by_strategy: dict[str, _FactorStats] = defaultdict(_FactorStats)
        self._by_regime: dict[str, _FactorStats] = defaultdict(_FactorStats)
        self._by_session: dict[str, _FactorStats] = defaultdict(_FactorStats)
        self._by_symbol: dict[str, _FactorStats] = defaultdict(_FactorStats)
        self._by_fg: dict[str, _FactorStats] = defaultdict(_FactorStats)

        # Kreuz-Dimensionen: regime×strategy
        self._by_regime_strategy: dict[str, _FactorStats] = defaultdict(_FactorStats)

    def record_trade(
        self,
        symbol: str,
        pnl: float,
        strategy: str = "unknown",
        regime: str = "unknown",
        fg_value: int = 50,
        hour: int | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        """Zeichnet einen abgeschlossenen Trade für die Attribution auf.

        Args:
            symbol: Trading-Pair (z.B. 'BTC/USDT').
            pnl: Gewinn/Verlust in USDT.
            strategy: Dominierende Strategie des Signals.
            regime: Marktregime zum Zeitpunkt des Trades.
            fg_value: Fear & Greed Index (0-100).
            hour: UTC-Stunde des Trade-Einstiegs (None = jetzt).
            extra: Zusätzliche Metadaten.
        """
        if hour is None:
            hour = datetime.now().hour
        session = _hour_to_session(hour)
        fg = _fg_bucket(fg_value)

        with self._lock:
            self._by_strategy[strategy].record(pnl)
            self._by_regime[regime].record(pnl)
            self._by_session[session].record(pnl)
            self._by_symbol[symbol].record(pnl)
            self._by_fg[fg].record(pnl)
            self._by_regime_strategy[f"{regime}:{strategy}"].record(pnl)

            entry = {
                "symbol": symbol,
                "pnl": pnl,
                "strategy": strategy,
                "regime": regime,
                "fg_value": fg_value,
                "fg_bucket": fg,
                "session": session,
                "hour": hour,
                "timestamp": datetime.now().isoformat(),
                **(extra or {}),
            }
            self._trades.append(entry)
            if len(self._trades) > self._max_trades:
                self._trades = self._trades[-self._max_trades :]

    def attribution_by(self, dimension: str) -> dict[str, dict[str, Any]]:
        """Gibt die Attribution für eine Dimension zurück.

        Args:
            dimension: Eine von 'strategy', 'regime', 'session', 'symbol', 'fg'.

        Returns:
            Dict mit {factor_value: Statistiken}.
        """
        dim_map = {
            "strategy": self._by_strategy,
            "regime": self._by_regime,
            "session": self._by_session,
            "symbol": self._by_symbol,
            "fg": self._by_fg,
        }
        store = dim_map.get(dimension)
        if store is None:
            return {}
        with self._lock:
            return {k: v.to_dict() for k, v in store.items()}

    def top_contributors(self, n: int = 5) -> dict[str, list[dict[str, Any]]]:
        """Identifiziert die profitabelsten und verlustreichsten Faktoren.

        Args:
            n: Anzahl Top/Bottom-Einträge pro Dimension.

        Returns:
            Dict mit 'best' und 'worst' Listen pro Dimension.
        """
        result: dict[str, list[dict[str, Any]]] = {"best": [], "worst": []}

        with self._lock:
            all_factors: list[tuple[str, str, _FactorStats]] = []
            for dim_name, store in [
                ("strategy", self._by_strategy),
                ("regime", self._by_regime),
                ("session", self._by_session),
                ("symbol", self._by_symbol),
                ("fg", self._by_fg),
            ]:
                for factor_val, stats in store.items():
                    if stats.total_trades >= 3:
                        all_factors.append((dim_name, factor_val, stats))

            sorted_by_pnl = sorted(all_factors, key=lambda x: x[2].total_pnl, reverse=True)

        for dim_name, factor_val, stats in sorted_by_pnl[:n]:
            result["best"].append(
                {
                    "dimension": dim_name,
                    "value": factor_val,
                    **stats.to_dict(),
                }
            )

        for dim_name, factor_val, stats in sorted_by_pnl[-n:]:
            if stats.total_pnl < 0:
                result["worst"].append(
                    {
                        "dimension": dim_name,
                        "value": factor_val,
                        **stats.to_dict(),
                    }
                )

        return result

    def regime_strategy_matrix(self) -> dict[str, dict[str, Any]]:
        """Gibt die Kreuz-Attribution Regime×Strategy zurück.

        Zeigt welche Strategien in welchem Regime am besten performen.

        Returns:
            Dict mit {regime:strategy: Statistiken}.
        """
        with self._lock:
            return {k: v.to_dict() for k, v in self._by_regime_strategy.items()}

    def profit_factor(self) -> float:
        """Berechnet den globalen Profit Factor (Gewinn/Verlust-Verhältnis).

        Returns:
            Profit Factor (>1 = profitabel). 0 wenn keine Verluste.
        """
        with self._lock:
            gross_profit = sum(s.total_pnl for s in self._by_symbol.values() if s.total_pnl > 0)
            gross_loss = abs(sum(s.total_pnl for s in self._by_symbol.values() if s.total_pnl < 0))
        if gross_loss > 0:
            return round(gross_profit / gross_loss, 2)
        return round(gross_profit, 2) if gross_profit > 0 else 0.0

    def expectancy(self) -> float:
        """Berechnet die mathematische Erwartung pro Trade.

        Returns:
            Erwarteter PnL pro Trade in USDT.
        """
        with self._lock:
            total_trades = sum(s.total_trades for s in self._by_symbol.values())
            total_pnl = sum(s.total_pnl for s in self._by_symbol.values())
        return round(total_pnl / total_trades, 2) if total_trades > 0 else 0.0

    def sharpe_ratio(self, risk_free: float = 0.0) -> float:
        """Berechnet die annualisierte Sharpe Ratio.

        Args:
            risk_free: Risikofreier Zinssatz (Default: 0).

        Returns:
            Sharpe Ratio (annualisiert auf 252 Handelstage).
        """
        with self._lock:
            all_pnl = []
            for s in self._by_symbol.values():
                all_pnl.extend(s.pnl_list)

        if len(all_pnl) < 3:
            return 0.0
        arr = np.array(all_pnl)
        excess = arr - risk_free
        std = float(np.std(excess))
        if std == 0:
            return 0.0
        return round(float(np.mean(excess) / std * math.sqrt(252)), 2)

    def full_report(self) -> dict[str, Any]:
        """Erstellt einen vollständigen Performance-Attribution-Report.

        Returns:
            Umfassender Report mit allen Dimensionen, Top-Contributors,
            und globalen Metriken.
        """
        with self._lock:
            total_trades = sum(s.total_trades for s in self._by_symbol.values())
            total_pnl = sum(s.total_pnl for s in self._by_symbol.values())
            total_wins = sum(s.wins for s in self._by_symbol.values())

        return {
            "summary": {
                "total_trades": total_trades,
                "total_pnl": round(total_pnl, 2),
                "win_rate": round(total_wins / total_trades * 100, 1) if total_trades > 0 else 0,
                "profit_factor": self.profit_factor(),
                "expectancy": self.expectancy(),
                "sharpe_ratio": self.sharpe_ratio(),
            },
            "by_strategy": self.attribution_by("strategy"),
            "by_regime": self.attribution_by("regime"),
            "by_session": self.attribution_by("session"),
            "by_symbol": self.attribution_by("symbol"),
            "by_fear_greed": self.attribution_by("fg"),
            "regime_strategy_matrix": self.regime_strategy_matrix(),
            "top_contributors": self.top_contributors(),
        }

    def load_from_trades(self, closed_trades: list[dict[str, Any]]) -> int:
        """Lädt historische Trades für die Attribution.

        Args:
            closed_trades: Liste abgeschlossener Trades aus state.closed_trades.

        Returns:
            Anzahl geladener Trades.
        """
        count = 0
        for trade in closed_trades:
            self.record_trade(
                symbol=trade.get("symbol", "UNKNOWN"),
                pnl=trade.get("pnl", 0.0),
                strategy=trade.get("reason", "unknown"),
                regime=trade.get("regime", "unknown"),
                fg_value=trade.get("fg_value", 50),
                hour=trade.get("entry_hour"),
            )
            count += 1
        log.info(f"Performance Attribution: {count} historische Trades geladen")
        return count

    def stats(self) -> dict[str, Any]:
        """Kurzstatistiken für Dashboard-Übersicht."""
        with self._lock:
            total = sum(s.total_trades for s in self._by_symbol.values())
            pnl = sum(s.total_pnl for s in self._by_symbol.values())
            n_strategies = len(self._by_strategy)
            n_symbols = len(self._by_symbol)

        return {
            "total_trades": total,
            "total_pnl": round(pnl, 2),
            "tracked_strategies": n_strategies,
            "tracked_symbols": n_symbols,
            "profit_factor": self.profit_factor(),
            "expectancy": self.expectancy(),
        }

    def to_dict(self) -> dict[str, Any]:
        """Serialisierung für Dashboard/API."""
        return {
            "enabled": True,
            **self.stats(),
        }
