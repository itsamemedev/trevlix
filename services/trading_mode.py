"""Trading mode and execution safety guards shared by paper/live execution."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass


@dataclass
class GuardResult:
    allowed: bool
    reason: str


class TradingModeManager:
    def __init__(self, config: dict):
        self.config = config
        self._lock = threading.RLock()
        self.mode = "paper" if config.get("paper_trading", True) else "live"
        self.enabled = True
        self._last_order_by_symbol: dict[str, float] = {}

    def set_mode(self, mode: str) -> str:
        m = "live" if str(mode).lower() == "live" else "paper"
        with self._lock:
            self.mode = m
            self.config["paper_trading"] = m != "live"
        return self.mode

    def status(self) -> dict:
        with self._lock:
            return {
                "mode": self.mode,
                "paper_trading": self.mode != "live",
                "trading_enabled": self.enabled,
            }

    def set_enabled(self, enabled: bool) -> bool:
        with self._lock:
            self.enabled = bool(enabled)
            return self.enabled

    def can_place_order(
        self,
        *,
        symbol: str,
        invest_usdt: float,
        free_usdt: float,
        price: float,
        qty: float,
        precision: int | None = None,
    ) -> GuardResult:
        with self._lock:
            if not self.enabled:
                return GuardResult(False, "Trading ist gestoppt")
            max_trade = float(self.config.get("max_trade_usdt", 0) or 0)
            if max_trade > 0 and invest_usdt > max_trade:
                return GuardResult(False, f"Max-Trade-Limit: {invest_usdt:.2f}>{max_trade:.2f}")
            if free_usdt < invest_usdt:
                return GuardResult(False, "Unzureichendes Guthaben")
            if price <= 0 or qty <= 0:
                return GuardResult(False, "Ungültiger Preis/Menge")
            if precision is not None and precision >= 0:
                step = 10 ** (-precision)
                if abs((qty / step) - round(qty / step)) > 1e-6:
                    return GuardResult(False, "Precision-Validierung fehlgeschlagen")
            cooldown = int(self.config.get("order_cooldown_sec", 8) or 0)
            last = self._last_order_by_symbol.get(symbol, 0.0)
            now = time.time()
            if cooldown > 0 and now - last < cooldown:
                return GuardResult(False, f"Cooldown aktiv ({cooldown}s)")
            return GuardResult(True, "ok")

    def mark_order(self, symbol: str) -> None:
        with self._lock:
            self._last_order_by_symbol[symbol] = time.time()
