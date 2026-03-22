"""TREVLIX – Backtest Engine.

Simuliert Trading-Strategien auf historischen Kursdaten.
Berechnet Win-Rate, PnL, Drawdown und weitere Kennzahlen.
"""

import logging
import threading
from typing import Any, Callable

import pandas as pd

log = logging.getLogger("trevlix.backtest")


class BacktestEngine:
    """Backtesting-Engine für Trading-Strategien.

    Args:
        compute_indicators_fn: Funktion die technische Indikatoren berechnet.
        strategies: Liste von (name, strategy_fn) Tupeln.
        save_fn: Optionale Funktion zum Speichern der Ergebnisse.
    """

    def __init__(
        self,
        compute_indicators_fn: Callable[[pd.DataFrame], pd.DataFrame | None],
        strategies: list[tuple[str, Callable]],
        save_fn: Callable[[dict], None] | None = None,
    ) -> None:
        self._compute_indicators = compute_indicators_fn
        self._strategies = strategies
        self._save_fn = save_fn

    def run(
        self,
        ex: Any,
        symbol: str,
        tf: str,
        candles: int,
        sl_pct: float,
        tp_pct: float,
        vote_thr: float,
    ) -> dict[str, Any]:
        """Führt einen Backtest durch.

        Args:
            ex: Exchange-Objekt (CCXT-kompatibel).
            symbol: Trading-Pair (z.B. 'BTC/USDT').
            tf: Timeframe (z.B. '1h', '15m').
            candles: Anzahl historischer Kerzen.
            sl_pct: Stop-Loss in Prozent (z.B. 0.03 = 3%).
            tp_pct: Take-Profit in Prozent.
            vote_thr: Mindest-Vote-Score für Einstieg.

        Returns:
            Ergebnis-Dict mit Trades, Equity-Curve und Statistiken.
        """
        try:
            ohlcv = ex.fetch_ohlcv(symbol, tf, limit=candles)
            if not ohlcv or len(ohlcv) < 100:
                return {"error": "Zu wenig Daten"}
            df = pd.DataFrame(
                ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"]
            )
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
            df.set_index("timestamp", inplace=True)
            df = self._compute_indicators(df)
            if df is None or len(df) < 3:
                return {"error": "Nicht genug Daten für Backtest (min. 3 Kerzen)"}
            cap = 10000.0
            start = cap
            pos = None
            trades: list[dict[str, Any]] = []
            equity = [{"time": str(df.index[0])[:16], "value": cap}]
            for i in range(2, len(df)):
                row = df.iloc[i]
                prev = df.iloc[i - 1]
                price = float(row["close"])
                if price <= 0:
                    continue
                if pos and pos.get("entry") and pos["entry"] > 0:
                    pp = (price - pos["entry"]) / pos["entry"]
                    if pp <= -sl_pct:
                        pnl = pos["inv"] * pp
                        cap += pos["inv"] + pnl
                        trades.append(
                            {
                                "time": str(row.name)[:16],
                                "entry": round(pos["entry"], 4),
                                "exit": round(price, 4),
                                "pnl": round(pnl, 2),
                                "won": False,
                                "reason": "SL",
                            }
                        )
                        pos = None
                    elif pp >= tp_pct:
                        pnl = pos["inv"] * pp
                        cap += pos["inv"] + pnl
                        trades.append(
                            {
                                "time": str(row.name)[:16],
                                "entry": round(pos["entry"], 4),
                                "exit": round(price, 4),
                                "pnl": round(pnl, 2),
                                "won": True,
                                "reason": "TP",
                            }
                        )
                        pos = None
                if pos is None:
                    votes = {nm: fn(row, prev) for nm, fn in self._strategies}
                    conf = (
                        sum(1 for v in votes.values() if v == 1) / len(self._strategies)
                        if self._strategies
                        else 0.0
                    )
                    if conf >= vote_thr:
                        inv = cap * 0.2
                        cap -= inv
                        pos = {"entry": price, "inv": inv}
                # Equity inkl. offener Position
                equity_val = cap
                if pos is not None and pos.get("entry") and pos["entry"] > 0:
                    equity_val += pos["inv"] * (1 + (price - pos["entry"]) / pos["entry"])
                equity.append({"time": str(row.name)[:16], "value": round(equity_val, 2)})
            if not trades:
                return {
                    "error": "Keine Trades – Threshold zu hoch",
                    "symbol": symbol,
                    "timeframe": tf,
                }
            won = [t for t in trades if t["won"]]
            lost = [t for t in trades if not t["won"]]
            wr = len(won) / len(trades) * 100
            total_pnl = sum(t["pnl"] for t in trades)
            gp = sum(t["pnl"] for t in won)
            gl = abs(sum(t["pnl"] for t in lost))
            pf = gp / gl if gl > 0 else 99.0
            dd = 0.0
            peak = start
            for e in equity:
                if e["value"] > peak:
                    peak = e["value"]
                dd = max(dd, (peak - e["value"]) / peak * 100) if peak > 0 else 0.0
            result = {
                "symbol": symbol,
                "timeframe": tf,
                "candles": candles,
                "total_trades": len(trades),
                "win_rate": round(wr, 1),
                "total_pnl": round(total_pnl, 2),
                "profit_factor": round(pf, 2),
                "max_drawdown": round(dd, 2),
                "start_balance": start,
                "final_balance": round(equity[-1]["value"] if equity else cap, 2),
                "return_pct": round(
                    ((equity[-1]["value"] if equity else cap) - start) / start * 100, 2
                )
                if start > 0
                else 0.0,
                "equity_curve": equity[:: max(1, len(equity) // 100)],
                "trades": trades[-30:],
            }
            if self._save_fn:
                threading.Thread(target=lambda r=result: self._save_fn(r), daemon=True).start()
            return result
        except Exception as e:
            return {"error": str(e), "symbol": symbol}
