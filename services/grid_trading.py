"""TREVLIX – Grid Trading Engine.

Klassisches Grid-Trading:
- Definiert N Preisstufen zwischen lower_price und upper_price
- Kauft wenn Preis eine Stufe unterschreitet
- Verkauft wenn Preis eine Stufe überschreitet
- Funktioniert ohne KI-Signal, ideal für Seitwärtsmärkte
"""

import logging
import threading
from datetime import datetime
from typing import Any

log = logging.getLogger("trevlix.grid_trading")


class GridTradingEngine:
    """Grid-Trading-Engine für automatisierten Stufenhandel.

    Erstellt Kauf-/Verkaufsebenen in einem definierten Preisbereich
    und handelt automatisch bei Stufenwechseln.
    """

    def __init__(self) -> None:
        self.grids: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()

    def create_grid(
        self,
        symbol: str,
        lower: float,
        upper: float,
        levels: int = 10,
        invest_per_level: float = 100.0,
    ) -> dict[str, Any]:
        """Erstellt ein neues Grid für ein Symbol.

        Args:
            symbol: Trading-Pair (z.B. 'BTC/USDT').
            lower: Untere Preisgrenze.
            upper: Obere Preisgrenze.
            levels: Anzahl der Stufen.
            invest_per_level: Investment pro Stufe in USDT.

        Returns:
            Grid-Konfiguration oder Fehler-Dict.
        """
        if lower >= upper or levels < 2:
            return {"error": "Ungültige Parameter: lower < upper, levels >= 2"}
        step = (upper - lower) / levels
        grid_levels = [round(lower + i * step, 6) for i in range(levels + 1)]
        with self._lock:
            self.grids[symbol] = {
                "symbol": symbol,
                "lower": lower,
                "upper": upper,
                "levels": levels,
                "step": round(step, 6),
                "grid_levels": grid_levels,
                "invest_per_level": invest_per_level,
                "active": True,
                "filled_buys": {},
                "filled_sells": {},
                "total_pnl": 0.0,
                "total_trades": 0,
                "created": datetime.now().isoformat(),
            }
        log.info(f"[GRID] {symbol}: {levels} Stufen zwischen {lower}–{upper} · {step:.4f}/Stufe")
        return self.grids[symbol]

    def update(self, symbol: str, current_price: float, balance_ref: list[float]) -> list[dict[str, Any]]:
        """Prüft für ein Symbol ob Grid-Orders ausgelöst werden sollen.

        Args:
            symbol: Trading-Pair.
            current_price: Aktueller Marktpreis.
            balance_ref: Mutable Liste mit [balance] als Referenz.

        Returns:
            Liste ausgeführter Grid-Aktionen.
        """
        with self._lock:
            return self._update_locked(symbol, current_price, balance_ref)

    def _update_locked(self, symbol: str, current_price: float, balance_ref: list[float]) -> list[dict[str, Any]]:
        grid = self.grids.get(symbol)
        if not grid or not grid["active"]:
            return []
        if current_price <= 0:
            return []
        actions: list[dict[str, Any]] = []
        levels = grid["grid_levels"]
        invest = grid["invest_per_level"]

        for i, lvl in enumerate(levels[:-1]):
            buy_price = lvl
            sell_price = levels[i + 1]

            # BUY: Preis ist gerade unter buy_price gefallen
            if (
                current_price <= buy_price * 1.001
                and buy_price not in grid["filled_buys"]
                and balance_ref[0] >= invest
            ):
                qty = invest / current_price
                grid["filled_buys"][buy_price] = {"qty": qty, "price": current_price}
                balance_ref[0] -= invest
                grid["total_trades"] += 1
                actions.append(
                    {
                        "action": "BUY",
                        "symbol": symbol,
                        "price": current_price,
                        "qty": round(qty, 6),
                        "grid_level": i,
                        "invest": invest,
                    }
                )
                log.info(f"[GRID] BUY  {symbol} @ {current_price:.4f} (Stufe {i})")

            # SELL: Preis hat sell_price überschritten und wir haben eine Position
            if current_price >= sell_price * 0.999 and buy_price in grid["filled_buys"]:
                buy_info = grid["filled_buys"].pop(buy_price)
                pnl = (current_price - buy_info["price"]) * buy_info["qty"]
                balance_ref[0] += buy_info["qty"] * current_price
                grid["total_pnl"] = round(grid["total_pnl"] + pnl, 4)
                grid["total_trades"] += 1
                grid["filled_sells"][sell_price] = {"pnl": pnl}
                actions.append(
                    {
                        "action": "SELL",
                        "symbol": symbol,
                        "price": current_price,
                        "qty": round(buy_info["qty"], 6),
                        "pnl": round(pnl, 4),
                        "grid_level": i,
                    }
                )
                log.info(f"[GRID] SELL {symbol} @ {current_price:.4f} PnL={pnl:+.4f}")
        return actions

    def stop_grid(self, symbol: str) -> None:
        """Stoppt ein Grid (deaktiviert es)."""
        with self._lock:
            if symbol in self.grids:
                self.grids[symbol]["active"] = False

    def delete_grid(self, symbol: str) -> None:
        """Löscht ein Grid vollständig."""
        with self._lock:
            self.grids.pop(symbol, None)

    def status(self) -> list[dict[str, Any]]:
        """Gibt den Status aller Grids zurück (ohne volle Grid-Level-Listen)."""
        return [
            {
                **g,
                "open_buys": len(g["filled_buys"]),
                "grid_levels": None,
            }
            for g in self.grids.values()
        ]
