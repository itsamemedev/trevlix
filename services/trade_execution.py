"""Unified paper/live execution services with shared safety checks."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import math
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

    def _get_market(self, ex, symbol: str) -> tuple[dict[str, Any] | None, str]:
        try:
            market = ex.market(symbol)
            if not market:
                return None, "Symbol nicht gefunden"
            if not market.get("active", True):
                return None, "Symbol ist inaktiv"
            return market, "ok"
        except Exception:
            return None, "Symbol-Validierung fehlgeschlagen"

    def _validate_precision(self, market: dict[str, Any], qty: float) -> tuple[bool, str]:
        try:
            amount_precision = (market.get("precision") or {}).get("amount")
            if amount_precision is None:
                return True, "ok"
            step = 10 ** (-int(amount_precision))
            if abs((qty / step) - round(qty / step)) > 1e-6:
                return False, "Precision-Validierung fehlgeschlagen"
            return True, "ok"
        except Exception:
            return True, "ok"

    def _validate_market_limits(self, market: dict[str, Any], qty: float, notional: float | None = None) -> tuple[bool, str]:
        try:
            limits = market.get("limits") or {}
            amount_limits = limits.get("amount") or {}
            cost_limits = limits.get("cost") or {}
            min_amount = self._safe_float(amount_limits.get("min"), 0.0)
            min_cost = self._safe_float(cost_limits.get("min"), 0.0)
            if min_amount > 0.0 and qty < min_amount:
                return False, "Ordermenge unter Mindestgröße"
            if notional is not None and min_cost > 0.0 and notional < min_cost:
                return False, "Orderwert unter Mindestwert"
            return True, "ok"
        except Exception:
            return True, "ok"

    def _validate_live_quote_balance(self, ex, quote: str, required: float) -> tuple[bool, str]:
        try:
            bal = ex.fetch_balance() or {}
            free = self._safe_float(((bal.get(quote) or {}).get("free")), 0.0)
            if free < required:
                return False, "Live-Guthaben zu niedrig"
            return True, "ok"
        except Exception:
            return False, "Live-Balance-Abfrage fehlgeschlagen"

    def _validate_live_base_balance(self, ex, base: str, required_qty: float) -> tuple[bool, str]:
        try:
            bal = ex.fetch_balance() or {}
            free = self._safe_float(((bal.get(base) or {}).get("free")), 0.0)
            if free < required_qty:
                return False, "Live-Basisguthaben zu niedrig"
            return True, "ok"
        except Exception:
            return False, "Live-Balance-Abfrage fehlgeschlagen"

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

    @staticmethod
    def _valid_quantity(qty: float) -> bool:
        return math.isfinite(qty) and qty > 0.0

    def _parse_positive_float(self, value: Any) -> float | None:
        parsed = self._safe_float(value, float("nan"))
        if not math.isfinite(parsed) or parsed <= 0.0:
            return None
        return parsed

    def _sanitize_fee_rate(self) -> float | None:
        fee_rate = self._safe_float(self._get_fee_rate(), float("nan"))
        if not math.isfinite(fee_rate) or fee_rate < 0.0 or fee_rate >= 1.0:
            return None
        return fee_rate

    def execute_buy(self, ex, *, symbol: str, price: float, invest_usdt: float) -> ExecutionResult:
        mode = self._mode()
        safe_price = self._parse_positive_float(price)
        safe_invest = self._parse_positive_float(invest_usdt)
        safe_fee_rate = self._sanitize_fee_rate()
        if safe_price is None or safe_invest is None or safe_fee_rate is None:
            return ExecutionResult(False, mode, "Ungültige Orderparameter")
        qty = (safe_invest - (safe_invest * safe_fee_rate)) / safe_price
        if not self._valid_quantity(qty):
            return ExecutionResult(False, mode, "Ungültige Ordermenge")
        market, reason_symbol = self._get_market(ex, symbol)
        if market is None:
            return ExecutionResult(False, mode, reason_symbol)
        valid_precision, reason_precision = self._validate_precision(market, qty)
        if not valid_precision:
            return ExecutionResult(False, mode, reason_precision)
        valid_limits, reason_limits = self._validate_market_limits(market, qty, safe_invest)
        if not valid_limits:
            return ExecutionResult(False, mode, reason_limits)
        with self._state._lock:
            free_usdt = self._safe_float(self._state.balance, 0.0)
        allowed, reason = self._guard(symbol, safe_invest, free_usdt, safe_price, qty)
        if not allowed:
            return ExecutionResult(False, mode, reason)
        fee = safe_invest * safe_fee_rate
        if mode == "paper":
            with self._state._lock:
                if self._safe_float(self._state.balance, 0.0) < safe_invest:
                    return ExecutionResult(False, mode, "Unzureichendes Guthaben")
                self._state.balance -= safe_invest
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
        quote = str(market.get("quote") or "USDT").upper()
        quote_ok, quote_reason = self._validate_live_quote_balance(ex, quote, safe_invest)
        if not quote_ok:
            return ExecutionResult(False, mode, quote_reason)
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
        safe_qty = self._parse_positive_float(qty)
        safe_fee_rate = self._sanitize_fee_rate()
        if safe_qty is None:
            return ExecutionResult(False, mode, "Ungültige Ordermenge")
        if safe_fee_rate is None:
            return ExecutionResult(False, mode, "Ungültige Orderparameter")
        safe_invest = self._safe_float(invest_usdt, 0.0)
        fee = max(0.0, safe_invest) * safe_fee_rate
        market, reason_symbol = self._get_market(ex, symbol)
        if market is None:
            return ExecutionResult(False, mode, reason_symbol)
        valid_precision, reason_precision = self._validate_precision(market, safe_qty)
        if not valid_precision:
            return ExecutionResult(False, mode, reason_precision)
        valid_limits, reason_limits = self._validate_market_limits(market, safe_qty)
        if not valid_limits:
            return ExecutionResult(False, mode, reason_limits)
        if mode == "paper":
            if self._mode_manager is not None:
                self._mode_manager.mark_order(symbol)
            return ExecutionResult(True, mode, "filled", fee=fee, executed_at=datetime.now().isoformat())
        base = str(market.get("base") or str(symbol).split("/")[0]).upper()
        base_ok, base_reason = self._validate_live_base_balance(ex, base, safe_qty)
        if not base_ok:
            return ExecutionResult(False, mode, base_reason)
        try:
            order = ex.create_market_sell_order(symbol, safe_qty)
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
