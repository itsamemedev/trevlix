"""Unified paper/live execution services with shared safety checks."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass
class ExecutionResult:
    ok: bool
    mode: str
    reason: str
    fee: float = 0.0
    order_id: str = ""
    executed_at: str = ""
    meta: dict[str, Any] | None = None


class TradeExecutionService:
    """Shared trade execution helpers for both paper and live mode."""

    def __init__(self, *, config: dict, state, get_fee_rate, mode_manager=None):
        self._config = config
        self._state = state
        self._get_fee_rate = get_fee_rate
        self._mode_manager = mode_manager

    def _mode(self) -> str:
        return "live" if not self._config.get("paper_trading", True) else "paper"

    @staticmethod
    def _safe_float(v: Any, default: float = 0.0) -> float:
        try:
            return float(v)
        except Exception:
            return default

    def _validate_symbol(self, ex, symbol: str) -> tuple[bool, str]:
        try:
            market = ex.market(symbol)
            if not market or not market.get("active", True):
                return False, "Symbol ist inaktiv"
            return True, "ok"
        except Exception:
            return False, "Symbol-Validierung fehlgeschlagen"

    def _validate_precision(self, ex, symbol: str, qty: float) -> tuple[bool, str]:
        try:
            market = ex.market(symbol)
            amount_precision = (market.get("precision") or {}).get("amount")
            if amount_precision is None:
                return True, "ok"
            step = 10 ** (-int(amount_precision))
            if abs((qty / step) - round(qty / step)) > 1e-6:
                return False, "Precision-Validierung fehlgeschlagen"
            return True, "ok"
        except Exception:
            return True, "ok"

    def _guard(self, symbol: str, invest_usdt: float, free_usdt: float, price: float, qty: float):
        if self._mode_manager is None:
            return True, "ok"
        guard = self._mode_manager.can_place_order(
            symbol=symbol,
            invest_usdt=invest_usdt,
            free_usdt=free_usdt,
            price=price,
            qty=qty,
        )
        return bool(guard.allowed), guard.reason

    def execute_buy(self, ex, *, symbol: str, price: float, invest_usdt: float) -> ExecutionResult:
        qty = max(0.0, (invest_usdt - (invest_usdt * self._get_fee_rate())) / max(price, 1e-12))
        mode = self._mode()
        valid_symbol, reason_symbol = self._validate_symbol(ex, symbol)
        if not valid_symbol:
            return ExecutionResult(False, mode, reason_symbol)
        valid_precision, reason_precision = self._validate_precision(ex, symbol, qty)
        if not valid_precision:
            return ExecutionResult(False, mode, reason_precision)
        with self._state._lock:
            free_usdt = self._safe_float(self._state.balance, 0.0)
        allowed, reason = self._guard(symbol, invest_usdt, free_usdt, price, qty)
        if not allowed:
            return ExecutionResult(False, mode, reason)
        fee = invest_usdt * self._get_fee_rate()
        if mode == "paper":
            with self._state._lock:
                if self._safe_float(self._state.balance, 0.0) < invest_usdt:
                    return ExecutionResult(False, mode, "Unzureichendes Guthaben")
                self._state.balance -= invest_usdt
            if self._mode_manager is not None:
                self._mode_manager.mark_order(symbol)
            return ExecutionResult(
                True,
                mode,
                "filled",
                fee=fee,
                executed_at=datetime.now().isoformat(),
                meta={"qty": qty},
            )
        try:
            bal = ex.fetch_balance()
            free = self._safe_float((bal.get("USDT") or {}).get("free"), 0.0)
            if free and free < invest_usdt:
                return ExecutionResult(False, mode, "Live-Guthaben zu niedrig")
        except Exception:
            pass
        try:
            order = ex.create_market_buy_order(symbol, qty)
            if self._mode_manager is not None:
                self._mode_manager.mark_order(symbol)
            return ExecutionResult(
                True,
                mode,
                "filled",
                fee=fee,
                order_id=str((order or {}).get("id", "")),
                executed_at=datetime.now().isoformat(),
                meta={"qty": qty, "order": order},
            )
        except Exception as exc:
            return ExecutionResult(False, mode, f"live_buy_failed:{exc}")

    def execute_sell(self, ex, *, symbol: str, qty: float, invest_usdt: float) -> ExecutionResult:
        mode = self._mode()
        fee = invest_usdt * self._get_fee_rate()
        valid_symbol, reason_symbol = self._validate_symbol(ex, symbol)
        if not valid_symbol:
            return ExecutionResult(False, mode, reason_symbol)
        valid_precision, reason_precision = self._validate_precision(ex, symbol, qty)
        if not valid_precision:
            return ExecutionResult(False, mode, reason_precision)
        if mode == "paper":
            if self._mode_manager is not None:
                self._mode_manager.mark_order(symbol)
            return ExecutionResult(True, mode, "filled", fee=fee, executed_at=datetime.now().isoformat())
        try:
            order = ex.create_market_sell_order(symbol, qty)
            if self._mode_manager is not None:
                self._mode_manager.mark_order(symbol)
            return ExecutionResult(
                True,
                mode,
                "filled",
                fee=fee,
                order_id=str((order or {}).get("id", "")),
                executed_at=datetime.now().isoformat(),
                meta={"order": order},
            )
        except Exception as exc:
            return ExecutionResult(False, mode, f"live_sell_failed:{exc}")

