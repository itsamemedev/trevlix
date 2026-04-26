"""Unified paper/live execution services with shared safety checks."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any

log = logging.getLogger(__name__)


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
        mode = self._mode()
        # Explicit price validation avoids the silent "1e-12" fallback which would
        # produce an absurdly large qty if price were ever 0/negative.
        if price is None or price <= 0:
            return ExecutionResult(False, mode, "Ungültiger Preis (<=0)")
        if invest_usdt is None or invest_usdt <= 0:
            return ExecutionResult(False, mode, "Ungültiges Investment (<=0)")
        qty = max(0.0, (invest_usdt - (invest_usdt * self._get_fee_rate())) / price)
        if qty <= 0:
            return ExecutionResult(False, mode, "Berechnete Menge <= 0")
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
            slippage_bps = self._safe_float(self._config.get("paper_slippage_bps"), 5.0)
            slippage_factor = slippage_bps / 10_000.0
            effective_price = price * (1.0 + slippage_factor)
            actual_qty = max(0.0, (invest_usdt - fee) / effective_price)
            with self._state._lock:
                if self._safe_float(self._state.balance, 0.0) < invest_usdt:
                    return ExecutionResult(False, mode, "Unzureichendes Guthaben")
                self._state.balance -= invest_usdt
            self._safe_mark_order(symbol)
            return ExecutionResult(
                True,
                mode,
                "filled",
                fee=fee,
                executed_at=datetime.now().isoformat(),
                meta={
                    "qty": actual_qty,
                    "actual_price": effective_price,
                    "slippage_bps": slippage_bps,
                },
            )
        try:
            bal = ex.fetch_balance()
            free = self._safe_float((bal.get("USDT") or {}).get("free"), 0.0)
            if free and free < invest_usdt:
                return ExecutionResult(False, mode, "Live-Guthaben zu niedrig")
        except Exception as e:
            log.warning("Live-Balance-Prüfung fehlgeschlagen: %s – blockiere Order", e)
            return ExecutionResult(False, mode, f"Balance-Check fehlgeschlagen: {e}")
        # Mark the cooldown BEFORE sending the order: if the exchange call raises
        # (e.g. network timeout) we do not know whether it was accepted, and we
        # must not retry immediately — the symbol cooldown prevents a duplicate.
        self._safe_mark_order(symbol)
        try:
            order = ex.create_market_buy_order(symbol, qty)
        except Exception as exc:
            log.error(
                "Live-Order fehlgeschlagen für %s qty=%.8f: %s (Cooldown aktiviert)",
                symbol,
                qty,
                exc,
            )
            return ExecutionResult(False, mode, f"live_buy_failed:{exc}")
        actual_qty = self._safe_float((order or {}).get("filled"), qty)
        actual_price = self._safe_float((order or {}).get("average"), price)
        if price > 0 and actual_price > 0:
            slippage_pct = (actual_price - price) / price * 100.0
            if abs(slippage_pct) > 0.1:
                log.warning(
                    "Buy slippage %.3f%% for %s (req=%.4f actual=%.4f)",
                    slippage_pct,
                    symbol,
                    price,
                    actual_price,
                )
        return ExecutionResult(
            True,
            mode,
            "filled",
            fee=fee,
            order_id=str((order or {}).get("id", "")),
            executed_at=datetime.now().isoformat(),
            meta={"qty": actual_qty, "actual_price": actual_price, "order": order},
        )

    def _safe_mark_order(self, symbol: str) -> None:
        """Mark order for cooldown tracking. Never raises."""
        if self._mode_manager is None:
            return
        try:
            self._mode_manager.mark_order(symbol)
        except Exception as exc:  # pragma: no cover - defensive
            log.warning("mark_order failed for %s: %s", symbol, exc)

    def execute_sell(
        self, ex, *, symbol: str, qty: float, invest_usdt: float, price: float = 0.0
    ) -> ExecutionResult:
        mode = self._mode()
        if qty is None or qty <= 0:
            return ExecutionResult(False, mode, "Ungültige Menge (<=0)")
        fee = invest_usdt * self._get_fee_rate()
        valid_symbol, reason_symbol = self._validate_symbol(ex, symbol)
        if not valid_symbol:
            return ExecutionResult(False, mode, reason_symbol)
        valid_precision, reason_precision = self._validate_precision(ex, symbol, qty)
        if not valid_precision:
            return ExecutionResult(False, mode, reason_precision)
        if mode == "paper":
            slippage_bps = self._safe_float(self._config.get("paper_slippage_bps"), 5.0)
            slippage_factor = slippage_bps / 10_000.0
            effective_proceeds = invest_usdt * (1.0 - slippage_factor)
            self._safe_mark_order(symbol)
            return ExecutionResult(
                True,
                mode,
                "filled",
                fee=fee,
                executed_at=datetime.now().isoformat(),
                meta={"effective_proceeds": effective_proceeds, "slippage_bps": slippage_bps},
            )
        # Mark cooldown BEFORE sending the order (see execute_buy for rationale).
        self._safe_mark_order(symbol)
        try:
            order = ex.create_market_sell_order(symbol, qty)
        except Exception as exc:
            log.error(
                "Live-Sell fehlgeschlagen für %s qty=%.8f: %s (Cooldown aktiviert)",
                symbol,
                qty,
                exc,
            )
            return ExecutionResult(False, mode, f"live_sell_failed:{exc}")
        actual_qty = self._safe_float((order or {}).get("filled"), qty)
        actual_price = self._safe_float((order or {}).get("average"), price)
        if price > 0 and actual_price > 0:
            slippage_pct = (price - actual_price) / price * 100.0
            if abs(slippage_pct) > 0.1:
                log.warning(
                    "Sell slippage %.3f%% for %s (req=%.4f actual=%.4f)",
                    slippage_pct,
                    symbol,
                    price,
                    actual_price,
                )
        return ExecutionResult(
            True,
            mode,
            "filled",
            fee=fee,
            order_id=str((order or {}).get("id", "")),
            executed_at=datetime.now().isoformat(),
            meta={"actual_qty": actual_qty, "actual_price": actual_price, "order": order},
        )
