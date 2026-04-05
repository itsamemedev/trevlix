"""TREVLIX – Exchange Factory Service.

Zentralisierte Erstellung von CCXT Exchange-Instanzen.
Behandelt Exchange-spezifische Eigenheiten einheitlich:

- Passphrase-Support für OKX, KuCoin, Crypto.com
- Robuste Ticker-Abfragen mit automatischem Fallback
- Standard-Fees pro Exchange
- Fee-Abfrage mit Caching

Verwendung:
    from services.exchange_factory import create_ccxt_exchange, safe_fetch_tickers

    ex = create_ccxt_exchange("okx", api_key, api_secret, passphrase="...")
    tickers = safe_fetch_tickers(ex, ["BTC/USDT", "ETH/USDT"])
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any

try:
    import ccxt

    CCXT_AVAILABLE = True
except ImportError:
    CCXT_AVAILABLE = False

from services.utils import EXCHANGE_MAP

log = logging.getLogger("trevlix.exchange_factory")

# ═══════════════════════════════════════════════════════════════════════════════
# STANDARD-FEES PRO EXCHANGE (Taker, Spot)
# ═══════════════════════════════════════════════════════════════════════════════
EXCHANGE_DEFAULT_FEES: dict[str, float] = {
    "binance": 0.0010,  # 0.10% Standard (0.075% mit BNB)
    "bybit": 0.0010,  # 0.10% Standard (0.06% Maker)
    "okx": 0.0008,  # 0.08% Standard (0.06% Maker)
    "kucoin": 0.0010,  # 0.10% Standard
    "cryptocom": 0.0004,  # 0.04% Standard
    "kraken": 0.0016,  # 0.16% Standard
    "huobi": 0.0020,  # 0.20% Standard
    "coinbase": 0.0060,  # 0.60% Standard (Advanced Trade niedriger)
}

# Exchanges die eine API-Passphrase zusätzlich zu Key/Secret benötigen
PASSPHRASE_REQUIRED: frozenset[str] = frozenset({"okx", "kucoin", "cryptocom"})

# Exchanges, bei denen fetch_tickers(symbols) ineffizient oder nicht unterstützt ist.
# Für diese wird fetch_tickers() ohne Argumente aufgerufen und client-seitig gefiltert.
_SINGLE_TICKER_EXCHANGES: frozenset[str] = frozenset({"cryptocom"})

# Maximale Anzahl Symbole für Einzel-Ticker-Fallback
_MAX_SINGLE_TICKER_FETCH = 30

# Cache für CCXT-Fee-Abfragen: {exchange_id: {"rate": 0.001, "ts": ...}}
_fee_cache: dict[str, dict] = {}
_fee_cache_lock = threading.Lock()
_FEE_CACHE_TTL = 3600  # 1 Stunde


def get_exchange_class(exchange_name: str) -> Any | None:
    """Gibt die CCXT-Klasse für eine Exchange zurück.

    Args:
        exchange_name: Name der Exchange (z.B. "binance", "okx").

    Returns:
        CCXT-Klasse oder None, falls nicht verfügbar.
    """
    if not CCXT_AVAILABLE:
        return None
    cls_name = EXCHANGE_MAP.get(exchange_name, exchange_name)
    return getattr(ccxt, cls_name, None)


def create_ccxt_exchange(
    exchange_name: str,
    api_key: str = "",
    api_secret: str = "",
    passphrase: str = "",
    default_type: str = "spot",
    extra_options: dict | None = None,
) -> Any | None:
    """Erstellt eine CCXT Exchange-Instanz mit korrekten Optionen.

    Zentrale Factory-Funktion für alle Exchange-Instanzen in TREVLIX.
    Behandelt Passphrase-Anforderungen für OKX, KuCoin und Crypto.com korrekt.

    Args:
        exchange_name: Name der Exchange (z.B. "binance", "okx").
        api_key: API-Key (plain text, bereits entschlüsselt).
        api_secret: API-Secret (plain text, bereits entschlüsselt).
        passphrase: Optionale Passphrase (erforderlich für OKX, KuCoin).
        default_type: "spot" (default), "swap", "future", "margin".
        extra_options: Zusätzliche CCXT-Options (werden mit defaults gemerged).

    Returns:
        CCXT Exchange-Instanz oder None bei Fehler.
    """
    if not CCXT_AVAILABLE:
        log.error("CCXT nicht installiert")
        return None

    ex_cls = get_exchange_class(exchange_name)
    if ex_cls is None:
        log.error("Exchange '%s' nicht in CCXT verfügbar", exchange_name)
        return None

    params: dict[str, Any] = {
        "enableRateLimit": True,
        "options": {"defaultType": default_type},
    }
    if api_key:
        params["apiKey"] = api_key
    if api_secret:
        params["secret"] = api_secret
    # CCXT verwendet "password" für OKX/KuCoin/Cryptocom Passphrase
    if passphrase:
        params["password"] = passphrase

    if extra_options:
        # Optionen zusammenführen (extra_options überschreiben defaults)
        if "options" in extra_options:
            params["options"].update(extra_options.pop("options"))
        params.update(extra_options)

    try:
        return ex_cls(params)
    except Exception as e:
        log.error("Exchange erstellen fehlgeschlagen (%s): %s", exchange_name, e)
        return None


def safe_fetch_tickers(ex: Any, symbols: list[str]) -> dict[str, Any]:
    """Holt Ticker-Daten exchange-kompatibel mit robustem Fallback.

    Strategie:
    1. Für Exchanges in _SINGLE_TICKER_EXCHANGES: fetch_tickers() ohne Args
       und anschließend client-seitig filtern.
    2. Für alle anderen: fetch_tickers(symbols) versuchen.
    3. Bei Fehler: fetch_tickers() ohne Args + filtern.
    4. Bei weiterem Fehler: fetch_ticker() einzeln (limitiert).

    Args:
        ex: CCXT Exchange-Instanz.
        symbols: Liste der gewünschten Symbole.

    Returns:
        Dict mit Ticker-Daten {symbol: ticker_dict}.
    """
    if not symbols:
        return {}
    ex_id = getattr(ex, "id", "")
    sym_set = set(symbols)

    # Strategie 1: Bekannt-problematische Exchanges direkt mit Filter-Fallback
    if ex_id in _SINGLE_TICKER_EXCHANGES:
        return _fetch_tickers_filtered(ex, sym_set, symbols)

    # Strategie 2: Batch-Aufruf mit Symbolen (bevorzugt)
    try:
        return ex.fetch_tickers(symbols)
    except Exception as e:
        log.debug("fetch_tickers(symbols) fehlgeschlagen bei %s: %s", ex_id, e)

    # Strategie 3: Ohne Argumente + filtern
    return _fetch_tickers_filtered(ex, sym_set, symbols)


def _fetch_tickers_filtered(ex: Any, sym_set: set[str], symbols: list[str]) -> dict[str, Any]:
    """Interner Helper: fetch_tickers() ohne Args, dann filtern; bei Fehler einzeln."""
    try:
        all_tickers = ex.fetch_tickers()
        return {s: t for s, t in all_tickers.items() if s in sym_set}
    except Exception as e:
        log.debug("fetch_tickers() ohne Args fehlgeschlagen: %s", e)

    # Letzter Fallback: einzeln abrufen (limitiert, um Rate-Limits zu schonen)
    result: dict[str, Any] = {}
    for sym in symbols[:_MAX_SINGLE_TICKER_FETCH]:
        try:
            t = ex.fetch_ticker(sym)
            if t:
                result[sym] = t
        except Exception:
            pass
    return result


def get_fee_rate(
    exchange_id: str,
    symbol: str = "BTC/USDT",
    fallback: float = 0.001,
) -> float:
    """Gibt die Taker-Fee für eine Exchange zurück (mit Cache).

    Versucht zuerst, die Fee live via CCXT abzurufen (gecached für 1 Stunde).
    Fällt auf Exchange-spezifische Defaults zurück, dann auf ``fallback``.

    Args:
        exchange_id: Exchange-Name (z.B. "binance").
        symbol: Trading-Pair für Fee-Abfrage.
        fallback: Default-Fee-Rate falls Exchange unbekannt.

    Returns:
        Fee-Rate als Dezimalzahl (z.B. 0.001 = 0.1%).
    """
    now = time.time()
    with _fee_cache_lock:
        cached = _fee_cache.get(exchange_id)
        if cached and now - cached.get("ts", 0) < _FEE_CACHE_TTL:
            return cached["rate"]

    # Versuche CCXT-Fee-Abfrage (public endpoint, kein API-Key nötig)
    try:
        ex_cls = get_exchange_class(exchange_id)
        if ex_cls:
            ex = ex_cls({"enableRateLimit": True})
            fee_info = ex.fetch_trading_fee(symbol)
            default_rate = EXCHANGE_DEFAULT_FEES.get(exchange_id, fallback)
            rate = float(fee_info.get("taker", default_rate))
            with _fee_cache_lock:
                _fee_cache[exchange_id] = {"rate": rate, "ts": now}
            return rate
    except Exception as e:
        log.debug("Live-Fee-Abfrage für %s fehlgeschlagen: %s", exchange_id, e)

    rate = EXCHANGE_DEFAULT_FEES.get(exchange_id, fallback)
    with _fee_cache_lock:
        _fee_cache[exchange_id] = {"rate": rate, "ts": now}
    return rate


def invalidate_fee_cache(exchange_id: str | None = None) -> None:
    """Invalidiert den Fee-Cache.

    Args:
        exchange_id: Optional spezifische Exchange. None = alle.
    """
    with _fee_cache_lock:
        if exchange_id:
            _fee_cache.pop(exchange_id, None)
        else:
            _fee_cache.clear()


def requires_passphrase(exchange_name: str) -> bool:
    """True, wenn die Exchange eine Passphrase zur Authentifizierung benötigt."""
    return exchange_name in PASSPHRASE_REQUIRED


def supported_exchanges() -> list[str]:
    """Gibt die Liste aller unterstützten Exchange-Namen zurück."""
    return sorted(EXCHANGE_MAP.keys())
