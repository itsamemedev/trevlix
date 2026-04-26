"""TREVLIX – NonKYC.io Exchange-Adapter (CCXT-kompatibel).

NonKYC.io ist eine No-KYC-Spot-Exchange mit großem Altcoin-Angebot, die NICHT
nativ in der ccxt-Library unterstützt wird. Dieses Modul stellt eine schmale,
ccxt-kompatible Adapter-Klasse bereit, die intern gegen die REST-API
``https://api.nonkyc.io/api/v2`` spricht und Antworten in das von TREVLIX
erwartete ccxt-Format normalisiert.

Implementierte Methoden (Subset des ccxt-Interface, das TREVLIX tatsächlich
verwendet):

- ``load_markets()`` / ``fetch_markets()`` / ``market(symbol)``
- ``fetch_tickers(symbols=None)`` / ``fetch_ticker(symbol)``
- ``fetch_ohlcv(symbol, timeframe, limit)`` – aus Trade-Historie aggregiert,
  da NonKYC keine native Candle-Endpoints anbietet
- ``fetch_balance()``
- ``create_order(symbol, type, side, amount, price=None)``
- ``create_market_buy_order(symbol, amount)``
- ``create_market_sell_order(symbol, amount)``
- ``fetch_open_orders(symbol=None)``
- ``cancel_order(order_id, symbol=None)``

Authentifizierung: HTTP-Basic-Auth (``Authorization: Basic <base64(key:secret)>``).

Siehe auch: ``services/exchange_factory.py`` – ``create_ccxt_exchange()`` erkennt
den Namen ``nonkyc`` und liefert eine ``NonKYCExchange``-Instanz statt einer
ccxt-Klasse.
"""

from __future__ import annotations

import base64
import logging
import time
from typing import Any
from urllib.parse import quote

import requests

log = logging.getLogger("trevlix.nonkyc_adapter")

NONKYC_API_BASE = "https://api.nonkyc.io/api/v2"
DEFAULT_TIMEOUT_S = 15
# Trade-history aggregation cap pro fetch_ohlcv-Aufruf, um Rate-Limits zu schonen.
_OHLCV_TRADE_LIMIT = 500
_TIMEFRAME_TO_SECONDS: dict[str, int] = {
    "1m": 60,
    "3m": 180,
    "5m": 300,
    "15m": 900,
    "30m": 1800,
    "1h": 3600,
    "2h": 7200,
    "4h": 14400,
    "6h": 21600,
    "8h": 28800,
    "12h": 43200,
    "1d": 86400,
    "3d": 259200,
    "1w": 604800,
}


class NonKYCError(Exception):
    """Wirft die NonKYC-Adapter-Schicht bei API-Fehlern."""


class NonKYCExchange:
    """ccxt-kompatibler Adapter für NonKYC.io.

    Die Klasse implementiert nur das Subset des ccxt-Interface, das von
    TREVLIX' Trading-Loop genutzt wird (siehe Modul-Docstring). Methoden, die
    NonKYC nicht anbietet (z.B. ``create_market_buy_order_with_cost``), werden
    bewusst nicht emuliert – das vermeidet schweigende Fehlfunktionen.
    """

    id: str = "nonkyc"
    name: str = "NonKYC"
    has: dict[str, bool] = {
        "fetchTicker": True,
        "fetchTickers": True,
        "fetchBalance": True,
        "fetchOHLCV": "emulated",
        "fetchOpenOrders": True,
        "createOrder": True,
        "cancelOrder": True,
    }
    timeframes: dict[str, str] = {tf: tf for tf in _TIMEFRAME_TO_SECONDS}

    def __init__(self, params: dict[str, Any] | None = None) -> None:
        params = params or {}
        self.apiKey: str = str(params.get("apiKey", "") or "")
        self.secret: str = str(params.get("secret", "") or "")
        self.password: str = str(params.get("password", "") or "")  # nicht genutzt
        self.timeout: int = int(params.get("timeout", DEFAULT_TIMEOUT_S * 1000)) // 1000
        self.options: dict[str, Any] = dict(params.get("options") or {})
        self.options.setdefault("defaultType", "spot")
        self.enableRateLimit: bool = bool(params.get("enableRateLimit", True))
        self.markets: dict[str, dict[str, Any]] = {}
        self._session = requests.Session()
        self._session.headers.update(
            {"Accept": "application/json", "User-Agent": "trevlix/nonkyc-adapter"}
        )

    # ─────────────────────────────────────────────────────────────────
    # HTTP / Auth helpers
    # ─────────────────────────────────────────────────────────────────
    def _auth_header(self) -> dict[str, str]:
        if not self.apiKey or not self.secret:
            return {}
        token = base64.b64encode(f"{self.apiKey}:{self.secret}".encode()).decode()
        return {"Authorization": f"Basic {token}"}

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
        private: bool = False,
    ) -> Any:
        url = f"{NONKYC_API_BASE}{path}"
        headers: dict[str, str] = {}
        if private:
            headers.update(self._auth_header())
            if "Authorization" not in headers:
                raise NonKYCError("API-Key/Secret fehlt für privaten Endpoint")
        try:
            resp = self._session.request(
                method,
                url,
                params=params,
                json=json_body,
                headers=headers,
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            log.warning("NonKYC-Netzwerkfehler %s %s: %s", method, path, exc)
            raise NonKYCError(f"NonKYC-Netzwerkfehler ({method} {path}): {exc}") from exc
        if resp.status_code >= 400:
            log.error(
                "NonKYC-API-Fehler %s %s → %s: %s",
                method,
                path,
                resp.status_code,
                resp.text[:300],
            )
            raise NonKYCError(
                f"NonKYC-API-Fehler {resp.status_code} bei {method} {path}: {resp.text[:300]}"
            )
        try:
            return resp.json()
        except ValueError as exc:
            log.error("NonKYC ungültiges JSON von %s: %s", path, exc)
            raise NonKYCError(f"NonKYC: ungültiges JSON von {path}: {exc}") from exc

    # ─────────────────────────────────────────────────────────────────
    # Markets
    # ─────────────────────────────────────────────────────────────────
    def fetch_markets(self) -> list[dict[str, Any]]:
        raw = self._request("GET", "/market") or []
        out: list[dict[str, Any]] = []
        for m in raw:
            symbol = _extract_symbol(m)
            if not symbol:
                continue
            base, _, quote_ccy = symbol.partition("/")
            out.append(
                {
                    "id": m.get("id") or m.get("symbol") or symbol,
                    "symbol": symbol,
                    "base": base,
                    "quote": quote_ccy,
                    "active": bool(m.get("isActive", True)),
                    "spot": True,
                    "type": "spot",
                    "precision": {
                        "amount": m.get("primaryDecimals"),
                        "price": m.get("secondaryDecimals"),
                    },
                    "limits": {
                        "amount": {"min": _to_float(m.get("minimumQuantity"))},
                        "cost": {"min": _to_float(m.get("minimumValue"))},
                    },
                    "info": m,
                }
            )
        return out

    def load_markets(self, reload: bool = False) -> dict[str, dict[str, Any]]:
        if self.markets and not reload:
            return self.markets
        self.markets = {m["symbol"]: m for m in self.fetch_markets()}
        return self.markets

    def market(self, symbol: str) -> dict[str, Any]:
        if not self.markets:
            self.load_markets()
        m = self.markets.get(symbol)
        if not m:
            raise NonKYCError(f"NonKYC: Markt '{symbol}' unbekannt")
        return m

    def _market_id(self, symbol: str) -> str:
        # NonKYC akzeptiert das Symbol direkt (z.B. "BTC/USDT") für die
        # meisten Endpoints; Markt-ID ist nur als Fallback nötig.
        try:
            return self.market(symbol).get("info", {}).get("symbol", symbol) or symbol
        except NonKYCError:
            return symbol

    # ─────────────────────────────────────────────────────────────────
    # Ticker / Orderbook / OHLCV
    # ─────────────────────────────────────────────────────────────────
    def fetch_ticker(self, symbol: str) -> dict[str, Any]:
        raw = self._request("GET", f"/market/{quote(self._market_id(symbol), safe='')}")
        return _normalize_ticker(symbol, raw)

    def fetch_tickers(self, symbols: list[str] | None = None) -> dict[str, dict[str, Any]]:
        raw = self._request("GET", "/market") or []
        out: dict[str, dict[str, Any]] = {}
        wanted = set(symbols) if symbols is not None else None
        for m in raw:
            sym = _extract_symbol(m)
            if not sym:
                continue
            if wanted is not None and sym not in wanted:
                continue
            out[sym] = _normalize_ticker(sym, m)
        return out

    def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str = "1m",
        since: int | None = None,
        limit: int = 100,
    ) -> list[list[float]]:
        """Aggregiert OHLCV-Candles aus der Trade-Historie.

        NonKYC bietet keinen nativen Candle-Endpoint, daher werden die letzten
        Trades geholt und in Buckets passender Timeframe-Länge gegruppiert.
        Für hochfrequente Strategien (1m) auf illiquiden Pairs kann die
        Auflösung lückenhaft sein – das ist eine bekannte Einschränkung.
        """
        seconds = _TIMEFRAME_TO_SECONDS.get(timeframe)
        if not seconds:
            raise NonKYCError(f"Unbekannter Timeframe: {timeframe}")
        market_symbol = quote(self._market_id(symbol), safe="")
        trades = (
            self._request(
                "GET",
                f"/trades/{market_symbol}",
                params={"limit": _OHLCV_TRADE_LIMIT},
            )
            or []
        )
        return _aggregate_trades_to_ohlcv(trades, seconds, limit)

    # ─────────────────────────────────────────────────────────────────
    # Account / Orders
    # ─────────────────────────────────────────────────────────────────
    def fetch_balance(self) -> dict[str, Any]:
        raw = self._request("GET", "/balances", private=True) or []
        if isinstance(raw, dict):
            raw = raw.get("balances", []) or []
        free: dict[str, float] = {}
        used: dict[str, float] = {}
        total: dict[str, float] = {}
        for entry in raw:
            asset = (
                entry.get("asset") or entry.get("ticker") or entry.get("currency") or ""
            ).upper()
            if not asset:
                continue
            available = _to_float(entry.get("available") or entry.get("free") or 0.0)
            held = _to_float(entry.get("held") or entry.get("used") or entry.get("locked") or 0.0)
            free[asset] = available
            used[asset] = held
            total[asset] = available + held
        result: dict[str, Any] = {"free": free, "used": used, "total": total, "info": raw}
        for asset in total:
            result[asset] = {
                "free": free.get(asset, 0.0),
                "used": used.get(asset, 0.0),
                "total": total.get(asset, 0.0),
            }
        return result

    def create_order(
        self,
        symbol: str,
        type: str,  # noqa: A002 - ccxt-Signatur
        side: str,
        amount: float,
        price: float | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if side not in ("buy", "sell"):
            raise NonKYCError(f"Ungültige order-side: {side}")
        order_type = (type or "").lower()
        if order_type not in ("market", "limit"):
            raise NonKYCError(f"Ungültiger order-type: {type}")
        if order_type == "limit" and price is None:
            raise NonKYCError("Limit-Order erfordert price")
        body: dict[str, Any] = {
            "symbol": self._market_id(symbol),
            "side": side,
            "type": order_type,
            "quantity": str(amount),
        }
        if price is not None:
            body["price"] = str(price)
        if params:
            body.update(params)
        raw = self._request("POST", "/order", json_body=body, private=True)
        return _normalize_order(symbol, raw)

    def create_market_buy_order(
        self, symbol: str, amount: float, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        return self.create_order(symbol, "market", "buy", amount, params=params)

    def create_market_sell_order(
        self, symbol: str, amount: float, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        return self.create_order(symbol, "market", "sell", amount, params=params)

    def fetch_open_orders(
        self,
        symbol: str | None = None,
        since: int | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {}
        if symbol:
            params["symbol"] = self._market_id(symbol)
        if limit:
            params["limit"] = limit
        raw = self._request("GET", "/orders/open", params=params, private=True) or []
        return [_normalize_order(symbol or o.get("symbol", ""), o) for o in raw]

    def cancel_order(
        self, order_id: str, symbol: str | None = None, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        raw = self._request("DELETE", f"/order/{quote(str(order_id), safe='')}", private=True)
        return _normalize_order(symbol or "", raw)


# ───────────────────────────────────────────────────────────────────────
# Normalisierungs-Helper (modul-privat)
# ───────────────────────────────────────────────────────────────────────


def _extract_symbol(market: dict[str, Any]) -> str:
    """Extrahiert das CCXT-Symbol (BASE/QUOTE) aus einem NonKYC-Markt-Dict.

    Gibt einen leeren String zurück, wenn weder ein Symbol noch ein
    base/quote-Paar abgeleitet werden kann.
    """
    base = (
        market.get("primaryAsset") or market.get("base") or market.get("baseAsset") or ""
    ).upper()
    quote_ccy = (
        market.get("secondaryAsset") or market.get("quote") or market.get("quoteAsset") or ""
    ).upper()
    sym = market.get("symbol") or ""
    if "/" in sym:
        return sym
    if base and quote_ccy:
        return f"{base}/{quote_ccy}"
    return ""


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _to_int_ms(value: Any) -> int | None:
    if value is None:
        return None
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    # Heuristik: Werte < 1e12 sind Sekunden, sonst Millisekunden
    return int(v * 1000) if v < 1_000_000_000_000 else int(v)


def _normalize_ticker(symbol: str, raw: dict[str, Any]) -> dict[str, Any]:
    last = _to_float(raw.get("lastPrice") or raw.get("last") or raw.get("price"))
    bid = _to_float(raw.get("bestBid") or raw.get("bid"))
    ask = _to_float(raw.get("bestAsk") or raw.get("ask"))
    high = _to_float(raw.get("highPrice") or raw.get("high"))
    low = _to_float(raw.get("lowPrice") or raw.get("low"))
    base_vol = _to_float(raw.get("primaryVolume") or raw.get("baseVolume") or raw.get("volume"))
    quote_vol = _to_float(raw.get("secondaryVolume") or raw.get("quoteVolume"))
    ts = _to_int_ms(raw.get("timestamp")) or int(time.time() * 1000)
    return {
        "symbol": symbol,
        "timestamp": ts,
        "datetime": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts / 1000)),
        "high": high or None,
        "low": low or None,
        "bid": bid or None,
        "ask": ask or None,
        "last": last or None,
        "close": last or None,
        "baseVolume": base_vol or None,
        "quoteVolume": quote_vol or None,
        "info": raw,
    }


def _normalize_order(symbol: str, raw: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {"info": raw}
    status = (raw.get("status") or "").lower()
    status_map = {
        "new": "open",
        "open": "open",
        "partiallyfilled": "open",
        "partially_filled": "open",
        "filled": "closed",
        "closed": "closed",
        "cancelled": "canceled",
        "canceled": "canceled",
    }
    amount = _to_float(raw.get("quantity") or raw.get("amount"))
    filled = _to_float(raw.get("executedQuantity") or raw.get("filled"))
    return {
        "id": str(raw.get("id") or raw.get("orderId") or raw.get("orderid") or ""),
        "symbol": symbol or raw.get("symbol", ""),
        "type": (raw.get("type") or "").lower() or None,
        "side": (raw.get("side") or "").lower() or None,
        "price": _to_float(raw.get("price")) or None,
        "amount": amount or None,
        "filled": filled,
        "remaining": max(amount - filled, 0.0) if amount else None,
        "status": status_map.get(status, status or "open"),
        "timestamp": _to_int_ms(raw.get("createdAt") or raw.get("timestamp")),
        "info": raw,
    }


def _aggregate_trades_to_ohlcv(
    trades: list[dict[str, Any]], seconds: int, limit: int
) -> list[list[float]]:
    """Gruppiert Trades in OHLCV-Buckets der Länge ``seconds``.

    Trades werden chronologisch aufsteigend sortiert, bevor sie aggregiert
    werden – so ist garantiert, dass open der erste und close der letzte
    Trade jedes Buckets ist, unabhängig von der API-Reihenfolge.
    """
    if not trades:
        return []
    bucket_ms = seconds * 1000
    parsed: list[tuple[int, float, float]] = []
    for tr in trades:
        ts = _to_int_ms(tr.get("timestamp") or tr.get("createdAt"))
        price = _to_float(tr.get("price"))
        qty = _to_float(tr.get("quantity") or tr.get("amount"))
        if ts is None or price <= 0:
            continue
        parsed.append((ts, price, qty))
    parsed.sort(key=lambda t: t[0])

    buckets: dict[int, list[float]] = {}
    for ts, price, qty in parsed:
        bucket = (ts // bucket_ms) * bucket_ms
        b = buckets.get(bucket)
        if b is None:
            buckets[bucket] = [float(bucket), price, price, price, price, qty]
        else:
            b[2] = max(b[2], price)  # high
            b[3] = min(b[3], price)  # low
            b[4] = price  # close (letzter Trade nach sortierung)
            b[5] += qty
    ordered = [buckets[k] for k in sorted(buckets)]
    return ordered[-limit:] if limit else ordered
