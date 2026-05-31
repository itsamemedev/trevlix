"""TREVLIX – Tax Report Generator.

Generiert steuerliche Berichte über realisierte Gewinne/Verluste.

Jeder Eingabe-Trade ist bereits ein abgeschlossener Round-Trip (Entry → Exit
mit realisiertem ``pnl``), daher findet hier kein FIFO-Lot-Matching über
Teilfills statt – das wird beim Schließen der Position erledigt. Was dieser
Report zusätzlich anwendet, ist die deutsche **Spekulationsfrist nach § 23 EStG**:
private Veräußerungsgeschäfte mit einer Haltedauer > 1 Jahr sind steuerfrei.
"""

from datetime import datetime
from typing import Any

# § 23 EStG: Haltedauer > 1 Jahr (für Krypto als "anderes Wirtschaftsgut")
# macht den Veräußerungsgewinn steuerfrei.
_TAX_FREE_HOLDING_DAYS = 365


def _parse_dt(value: Any) -> datetime | None:
    """Parse an ISO-ish timestamp/date string into a datetime, or None."""
    if not value:
        return None
    s = str(value).strip().replace("T", " ")
    # Try full datetime first, then date-only.
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(s[: len(fmt) + 2].strip(), fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        return None


def _holding_days(opened: Any, closed: Any) -> int | None:
    """Whole days a position was held, or None if dates can't be parsed."""
    o = _parse_dt(opened)
    c = _parse_dt(closed)
    if o is None or c is None:
        return None
    delta = (c - o).days
    return delta if delta >= 0 else None


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
            Report-Dict mit Gewinnen, Verlusten und Zusammenfassung. Gewinne aus
            Positionen mit Haltedauer > 1 Jahr (§ 23 EStG) werden separat als
            steuerfrei ausgewiesen und nicht in ``taxable_gains`` eingerechnet.
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
                "tax_free": [],
                "summary": {
                    "total_gains": 0,
                    "total_losses": 0,
                    "net_pnl": 0,
                    "total_fees": 0,
                    "taxable_gains": 0,
                    "tax_free_gains": 0,
                    "trade_count": 0,
                    "win_count": 0,
                    "loss_count": 0,
                    "tax_free_count": 0,
                },
            }
        gains: list[dict[str, Any]] = []
        losses: list[dict[str, Any]] = []
        tax_free: list[dict[str, Any]] = []
        total_fees = 0.0
        for t in yt:
            pnl = float(t.get("pnl") or 0)
            fee = float(t.get("invested") or 0) * self._fee_rate * 2
            net = pnl - fee
            total_fees += fee

            held = _holding_days(t.get("opened"), t.get("closed"))
            # § 23 EStG: a *gain* on an asset held > 1 year is tax-free. Losses
            # from such long-held positions are likewise not deductible, but we
            # only special-case the gain side (it's what affects the tax base).
            long_held = held is not None and held > _TAX_FREE_HOLDING_DAYS
            is_tax_free_gain = long_held and net > 0

            entry = {
                "date": str(t.get("closed", ""))[:10],
                "symbol": t.get("symbol", "?"),
                "buy_price": t.get("entry", 0),
                "sell_price": t.get("exit", 0),
                "qty": t.get("qty", 0),
                "gross_pnl": round(pnl, 2),
                "fee": round(fee, 4),
                "net_pnl": round(net, 2),
                "holding_days": held,
                "taxable": net > 0 and not is_tax_free_gain,
                "tax_free": is_tax_free_gain,
                "type": t.get("trade_type", "long"),
            }
            if is_tax_free_gain:
                tax_free.append(entry)
            elif net > 0:
                gains.append(entry)
            else:
                losses.append(entry)

        tg = sum(e["net_pnl"] for e in gains)
        tl = sum(e["net_pnl"] for e in losses)
        tf = sum(e["net_pnl"] for e in tax_free)
        return {
            "year": year,
            "method": method.upper(),
            "gains": sorted(gains, key=lambda x: x["net_pnl"], reverse=True)[:50],
            "losses": sorted(losses, key=lambda x: x["net_pnl"])[:50],
            "tax_free": sorted(tax_free, key=lambda x: x["net_pnl"], reverse=True)[:50],
            "summary": {
                "total_gains": round(tg, 2),
                "total_losses": round(tl, 2),
                "net_pnl": round(tg + tl, 2),
                "total_fees": round(total_fees, 2),
                # Taxable gains exclude § 23-exempt long-held gains.
                "taxable_gains": round(max(0, tg + tl), 2),
                "tax_free_gains": round(tf, 2),
                "trade_count": len(yt),
                "win_count": len(gains),
                "loss_count": len(losses),
                "tax_free_count": len(tax_free),
            },
        }
