"""Unified paper/live execution services with shared safety checks."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from services.exchange_factory import safe_fetch_balance

log = logging.getLogger(__name__)


def _sanitize_exchange_error(exc: Exception) -> str:
    """Map a raw ccxt/exchange exception to a short, user-facing reason.

    The full exception text is logged separately; it may contain headers,
    IPs or fragments of API keys, so we never surface it verbatim. The
    returned phrase tells the user *what* went wrong so they can act (top up,
    wait out a rate-limit, fix keys) instead of seeing an opaque token.
    """
    raw = str(exc).lower()
    if any(t in raw for t in ("insufficient", "balance", "not enough", "no_balance")):
        return "Guthaben auf der Exchange zu niedrig"
    if any(t in raw for t in ("timeout", "timed out")):
        return "Exchange-Antwort dauerte zu lange"
    if any(t in raw for t in ("invalid", "signature", "auth", "permission", "forbidden")):
        return "Authentifizierung fehlgeschlagen – API-Keys prüfen"
    if "rate" in raw and "limit" in raw:
        return "Rate-Limit erreicht – kurz warten"
    if any(t in raw for t in ("network", "connection")):
        return "Netzwerk-Fehler – Exchange nicht erreichbar"
    if any(t in raw for t in ("min", "minimum", "too small", "dust")):
        return "Order unter Mindestgröße der Exchange"
    return "Exchange hat die Order abgelehnt"


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
        # Per-exchange mode: the BotState facade resolves to the account being
        # processed in the current (bot-loop) thread, so paper/live is decided
        # per exchange rather than by one global flag. Falls back to the global
        # config flag for direct/test callers without a multi-account state.
        st = self._state
        if st is not None:
            getter = getattr(st, "current_mode", None)
            if callable(getter):
                try:
                    return getter()
                except Exception:
                    pass
        return "live" if not self._config.get("paper_trading", True) else "paper"

    @staticmethod
    def _safe_float(v: Any, default: float = 0.0) -> float:
        try:
            return float(v)
        except (ValueError, TypeError):
            return default

    @staticmethod
    def _lookup_market(ex, symbol: str):
        """Resolve a market, loading markets once if the instance hasn't yet.

        A freshly-created or reconnected exchange instance frequently has no
        markets loaded: OHLCV is served from the shared ``market_cache`` so
        ``scan_symbol`` never triggers ccxt's implicit ``load_markets``, and a
        reconnected primary keeps the existing ``state.markets`` symbol list
        without reloading. ``ex.market(symbol)`` then raises a ``KeyError`` for
        every symbol, which (because validation runs before the paper/live
        branch) blocks ALL trades — paper and live alike. Loading markets on the
        first miss makes validation fail only for genuinely unknown symbols or
        an unreachable exchange.
        """
        try:
            return ex.market(symbol)
        except Exception:
            loader = getattr(ex, "load_markets", None)
            if not callable(loader):
                raise
            loader()  # may raise if the exchange is unreachable — caller handles it
            return ex.market(symbol)

    def _validate_symbol(self, ex, symbol: str) -> tuple[bool, str]:
        try:
            market = self._lookup_market(ex, symbol)
            if not market or not market.get("active", True):
                return False, "Symbol ist inaktiv"
            return True, "ok"
        except Exception:
            return False, "Symbol-Validierung fehlgeschlagen"

    def _round_amount(self, ex, symbol: str, qty: float) -> float:
        """Return ``qty`` rounded to the exchange's amount precision.

        Prefers ccxt's own ``amount_to_precision`` (it correctly handles every
        precision mode); falls back to interpreting ``precision['amount']`` as
        either a tick size (value < 1 → ``TICK_SIZE`` mode) or a decimal-place
        count (value >= 1 → ``DECIMAL_PLACES`` mode) for mocks/exchanges that do
        not expose the helper.
        """
        formatter = getattr(ex, "amount_to_precision", None)
        if callable(formatter):
            try:
                return self._safe_float(formatter(symbol, qty), qty)
            except Exception:
                pass
        market = self._lookup_market(ex, symbol)
        amount_precision = (market.get("precision") or {}).get("amount")
        if amount_precision is None:
            return qty
        ap = self._safe_float(amount_precision, 0.0)
        if ap <= 0:
            return qty
        if ap < 1:
            # TICK_SIZE mode: ``amount_precision`` IS the lot step (e.g. 0.0001).
            return round(qty / ap) * ap
        # DECIMAL_PLACES mode: ``amount_precision`` is the number of decimals.
        return round(qty, int(ap))

    def _validate_precision(self, ex, symbol: str, qty: float) -> tuple[bool, str, float]:
        """Round ``qty`` to the exchange's amount precision; reject only if the
        result falls below the minimum lot (rounds to <= 0).

        The previous implementation computed ``10 ** -int(precision_amount)`` and
        then required ``qty`` to be an *exact* multiple of that step. That was
        wrong on two counts for every supported exchange:

        * ccxt reports amount precision in ``TICK_SIZE`` mode
          (``precisionMode == 4``) for crypto.com/binance/bybit/okx/kucoin, so
          ``precision['amount']`` is the lot *step itself* (e.g. ``0.0001``) — a
          value < 1. ``int(0.0001)`` truncates to ``0``, yielding ``step = 1`` and
          rejecting every fractional quantity (BTC, ETH, …). This blocked the
          live order in BOTH directions, but the failure was loudest on the sell
          path, so positions could no longer be closed.
        * Even with the correct step, a freshly computed ``qty`` is virtually
          never an exact multiple of it, so the order should be rounded to a
          valid amount rather than rejected.

        Returns ``(ok, reason, adjusted_qty)`` so callers can send the rounded
        quantity to the exchange.
        """
        try:
            adjusted = self._round_amount(ex, symbol, qty)
            if adjusted is None or adjusted <= 0:
                return False, "Menge unter Mindeststückelung", qty
            return True, "ok", adjusted
        except Exception:
            return True, "ok", qty

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
        valid_precision, reason_precision, qty = self._validate_precision(ex, symbol, qty)
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
        if not getattr(ex, "apiKey", None) and not getattr(ex, "secret", None):
            return ExecutionResult(
                False,
                mode,
                "Kein API-Key konfiguriert – Trade nicht möglich. "
                "Keys unter 'Exchanges' im Dashboard eintragen.",
            )
        try:
            bal = safe_fetch_balance(ex)
            free = self._safe_float((bal.get("USDT") or {}).get("free"), 0.0)
            if free and free < invest_usdt:
                return ExecutionResult(False, mode, "Live-Guthaben zu niedrig")
        except Exception as e:
            log.warning("Live-Balance-Prüfung fehlgeschlagen: %s – blockiere Order", e)
            return ExecutionResult(False, mode, "balance_check_failed")
        # Mark the cooldown BEFORE sending the order: if the exchange call raises
        # (e.g. network timeout) we do not know whether it was accepted, and we
        # must not retry immediately — the symbol cooldown prevents a duplicate.
        self._safe_mark_order(symbol)
        try:
            order = ex.create_market_buy_order(symbol, qty)
        except Exception as exc:
            reason = _sanitize_exchange_error(exc)
            log.error(
                "Live-Order fehlgeschlagen für %s qty=%.8f: %s (Cooldown aktiviert)",
                symbol,
                qty,
                exc,
            )
            return ExecutionResult(False, mode, f"live_buy_failed: {reason}")
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

    def _clamp_to_free_base(self, ex, symbol: str, qty: float) -> float:
        """Cap ``qty`` to the free base-asset balance held on the exchange.

        Returns the (possibly reduced) quantity rounded down to the lot step.
        Only shrinks the order — if the wallet reports *at least* ``qty`` free
        (or the balance can't be read / doesn't list the asset) the requested
        ``qty`` is returned unchanged, so this never blocks a legitimate sell.
        """
        base = symbol.split("/")[0].upper() if "/" in symbol else ""
        if not base:
            return qty
        try:
            bal = safe_fetch_balance(ex) or {}
        except Exception as exc:
            # Don't block the sell on a flaky balance read — let the exchange
            # be the final arbiter (it will reject if truly out of funds).
            log.warning("Live-Sell: Balance-Prüfung für %s fehlgeschlagen: %s", symbol, exc)
            return qty
        entry = bal.get(base)
        if not isinstance(entry, dict) or entry.get("free") is None:
            return qty
        free_base = self._safe_float(entry.get("free"), 0.0)
        if free_base <= 0 or free_base >= qty:
            return qty
        adjusted = self._round_amount(ex, symbol, free_base)
        # ``_round_amount`` may round to nearest on mock exchanges; never let the
        # clamp grow the order beyond what is actually free.
        adjusted = min(self._safe_float(adjusted, free_base), free_base)
        log.info(
            "Live-Sell %s: Menge %.8f auf freies Guthaben %.8f angepasst",
            symbol,
            qty,
            adjusted,
        )
        return adjusted

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
        valid_precision, reason_precision, qty = self._validate_precision(ex, symbol, qty)
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
        if not getattr(ex, "apiKey", None) and not getattr(ex, "secret", None):
            return ExecutionResult(
                False,
                mode,
                "Kein API-Key konfiguriert – Trade nicht möglich. "
                "Keys unter 'Exchanges' im Dashboard eintragen.",
            )
        # Clamp the sell quantity to the base asset actually held on the
        # exchange. The buy fee is charged in the base asset (e.g. crypto.com
        # deducts the taker fee from the received BTC), so the position's
        # recorded qty is marginally larger than the free wallet balance.
        # Selling the full recorded qty then trips an "INSUFFICIENT_BALANCE"
        # rejection — the single most common cause of live_sell_failed. We
        # round the available balance down to the exchange's lot step so the
        # close can still go through.
        qty = self._clamp_to_free_base(ex, symbol, qty)
        if qty <= 0:
            return ExecutionResult(
                False, mode, "live_sell_failed: kein verkaufbares Guthaben auf der Exchange"
            )
        # Mark cooldown BEFORE sending the order (see execute_buy for rationale).
        self._safe_mark_order(symbol)
        try:
            order = ex.create_market_sell_order(symbol, qty)
        except Exception as exc:
            reason = _sanitize_exchange_error(exc)
            log.error(
                "Live-Sell fehlgeschlagen für %s qty=%.8f: %s (Cooldown aktiviert)",
                symbol,
                qty,
                exc,
            )
            return ExecutionResult(False, mode, f"live_sell_failed: {reason}")
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
