"""TREVLIX – Tax Report Generator.

Generiert steuerliche Berichte über realisierte Gewinne/Verluste.
Unterstützt FIFO-Methode für deutsche Steuerberichterstattung.
"""

from typing import Any


class TaxReportGenerator:
    """Erzeugt steuerliche Berichte für ein bestimmtes Jahr.

    Args:
        fee_rate: Gebührenrate pro Trade (z.B. 0.001 = 0.1%).
    """

    def __init__(self, fee_rate: float = 0.001) -> None:
        self._fee_rate = fee_rate

    def generate(
        self, trades: list[dict[str, Any]], year: int, method: str = "fifo"
    ) -> dict[str, Any]:
        """Generiert einen Steuer-Report für das angegebene Jahr.

        Args:
            trades: Liste abgeschlossener Trades.
            year: Steuerjahr.
            method: Berechnungsmethode (default: FIFO).

        Returns:
            Report-Dict mit Gewinnen, Verlusten und Zusammenfassung.
        """
        yt = [
            t
            for t in trades
            if str(t.get("closed", ""))[:4] == str(year) and t.get("pnl") is not None
        ]
        if not yt:
            return {
                "year": year,
                "method": method,
                "trades": [],
                "gains": [],
                "losses": [],
                "summary": {
                    "total_gains": 0,
                    "total_losses": 0,
                    "net_pnl": 0,
                    "total_fees": 0,
                    "taxable_gains": 0,
                    "trade_count": 0,
                    "win_count": 0,
                    "loss_count": 0,
                },
            }
        gains: list[dict[str, Any]] = []
        losses: list[dict[str, Any]] = []
        total_fees = 0.0
        for t in yt:
            pnl = float(t.get("pnl") or 0)
            fee = float(t.get("invested") or 0) * self._fee_rate * 2
            net = pnl - fee
            total_fees += fee
            entry = {
                "date": str(t.get("closed", ""))[:10],
                "symbol": t.get("symbol", "?"),
                "buy_price": t.get("entry", 0),
                "sell_price": t.get("exit", 0),
                "qty": t.get("qty", 0),
                "gross_pnl": round(pnl, 2),
                "fee": round(fee, 4),
                "net_pnl": round(net, 2),
                "taxable": net > 0,
                "type": t.get("trade_type", "long"),
            }
            (gains if net > 0 else losses).append(entry)
        tg = sum(e["net_pnl"] for e in gains)
        tl = sum(e["net_pnl"] for e in losses)
        return {
            "year": year,
            "method": method.upper(),
            "gains": sorted(gains, key=lambda x: x["net_pnl"], reverse=True)[:50],
            "losses": sorted(losses, key=lambda x: x["net_pnl"])[:50],
            "summary": {
                "total_gains": round(tg, 2),
                "total_losses": round(tl, 2),
                "net_pnl": round(tg + tl, 2),
                "total_fees": round(total_fees, 2),
                "taxable_gains": round(max(0, tg + tl), 2),
                "trade_count": len(yt),
                "win_count": len(gains),
                "loss_count": len(losses),
            },
        }
