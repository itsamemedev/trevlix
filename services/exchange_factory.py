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
from typing import Any

try:
    import ccxt

    CCXT_AVAILABLE = True
except ImportError:
    CCXT_AVAILABLE = False

from cachetools import TTLCache
from tenacity import (
    RetryError,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

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
    "bitget": 0.0010,  # 0.10% Standard
    "mexc": 0.0020,  # 0.20% Standard Spot (Maker gratis auf Promo)
    "gateio": 0.0020,  # 0.20% Standard
    "nonkyc": 0.0020,  # 0.20% Standard Taker (kein KYC, viele Altcoins)
}

# Exchanges die eine API-Passphrase zusätzlich zu Key/Secret benötigen
# Crypto.com benötigt KEINE Passphrase – nur OKX und KuCoin.
PASSPHRASE_REQUIRED: frozenset[str] = frozenset({"okx", "kucoin"})

# Exchanges, bei denen fetch_tickers(symbols) ineffizient oder nicht unterstützt ist.
# Für diese wird fetch_tickers() ohne Argumente aufgerufen und client-seitig gefiltert.
_SINGLE_TICKER_EXCHANGES: frozenset[str] = frozenset({"cryptocom"})

# Maximale Anzahl Symbole für Einzel-Ticker-Fallback
_MAX_SINGLE_TICKER_FETCH = 30

# Exchange-spezifische Timeout-Overrides (Millisekunden).
# Crypto.com ist historisch langsam und benötigt mehr Zeit für volle Ticker-Dumps.
_EXCHANGE_TIMEOUT_OVERRIDES: dict[str, int] = {
    "cryptocom": 20000,
    "bybit": 15000,
    "okx": 15000,
    "kucoin": 15000,
    "binance": 10000,
    "nonkyc": 20000,  # NonKYC ist tendenziell langsamer (kleinere Infrastruktur)
}
_DEFAULT_TIMEOUT_MS = 15000

# Retry-Konfiguration für transiente Netzwerkfehler
_TICKER_RETRY_ATTEMPTS = 3
_TICKER_RETRY_BACKOFF_S = 0.5

# Transient exceptions to retry on — extended with ccxt types after import guard
_TRANSIENT_EXC: tuple[type[Exception], ...] = (OSError, TimeoutError)
if CCXT_AVAILABLE:
    _TRANSIENT_EXC = (*_TRANSIENT_EXC, ccxt.RequestTimeout, ccxt.NetworkError)
try:
    import requests as _requests

    _TRANSIENT_EXC = (
        *_TRANSIENT_EXC,
        _requests.ConnectionError,
        _requests.Timeout,
    )
except ImportError:
    pass

# Fee-Cache: TTLCache auto-expires after 1 hour, no manual timestamp tracking needed
_FEE_CACHE_TTL = 3600  # 1 Stunde
_fee_cache: TTLCache[str, float] = TTLCache(maxsize=50, ttl=_FEE_CACHE_TTL)
_fee_cache_lock = threading.Lock()


# Exchanges, die nicht in ccxt enthalten sind und über einen lokalen Adapter
# bereitgestellt werden. Werden in get_exchange_class() / create_ccxt_exchange()
# als Sonderfall behandelt.
_LOCAL_ADAPTERS: frozenset[str] = frozenset({"nonkyc"})


def get_exchange_class(exchange_name: str) -> Any | None:
    """Gibt die CCXT-Klasse (oder lokalen Adapter) für eine Exchange zurück.

    Args:
        exchange_name: Name der Exchange (z.B. "binance", "okx", "nonkyc").

    Returns:
        CCXT-Klasse, lokaler Adapter, oder None falls nicht verfügbar.
    """
    if exchange_name in _LOCAL_ADAPTERS:
        if exchange_name == "nonkyc":
            from services.nonkyc_adapter import NonKYCExchange

            return NonKYCExchange
        return None
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
    is_local = exchange_name in _LOCAL_ADAPTERS
    if not CCXT_AVAILABLE and not is_local:
        log.error("CCXT nicht installiert")
        return None

    ex_cls = get_exchange_class(exchange_name)
    if ex_cls is None:
        log.error("Exchange '%s' nicht in CCXT verfügbar", exchange_name)
        return None

    params: dict[str, Any] = {
        "enableRateLimit": True,
        "timeout": _EXCHANGE_TIMEOUT_OVERRIDES.get(exchange_name, _DEFAULT_TIMEOUT_MS),
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
       und anschließend client-seitig filtern (z.B. Crypto.com).
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

    # Strategie 1: Für Exchanges in _SINGLE_TICKER_EXCHANGES direkt ohne Args + filtern.
    # Crypto.com unterstützt keine Batch-Ticker-Abfragen mit mehreren Symbolen.
    if ex_id in _SINGLE_TICKER_EXCHANGES:
        return _fetch_tickers_filtered(ex, sym_set, symbols)

    # Strategie 2: Batch-Aufruf mit Symbolen und Retry (bevorzugt)
    result = _with_retry(lambda: ex.fetch_tickers(symbols), ex_id, "fetch_tickers(symbols)")
    if result is not None:
        return result

    # Strategie 3: Ohne Argumente + filtern (Fallback für andere Exchanges)
    return _fetch_tickers_filtered(ex, sym_set, symbols)


def _with_retry(fn: Any, ex_id: str, op: str) -> Any:
    """Führt einen Exchange-Call mit exponentiellem Backoff via tenacity aus.

    Retries nur bei transienten Netzwerk-/Timeout-Fehlern. Gibt None zurück
    wenn alle Versuche scheitern oder ein nicht-transienter Fehler auftritt.
    """

    @retry(
        stop=stop_after_attempt(_TICKER_RETRY_ATTEMPTS),
        wait=wait_exponential(
            multiplier=_TICKER_RETRY_BACKOFF_S,
            min=_TICKER_RETRY_BACKOFF_S,
            max=30,
        ),
        retry=retry_if_exception_type(_TRANSIENT_EXC),
        reraise=True,
    )
    def _call() -> Any:
        return fn()

    try:
        return _call()
    except (RetryError, Exception) as exc:
        log.warning("%s endgültig fehlgeschlagen bei %s: %s", op, ex_id, exc)
        return None


def _fetch_tickers_filtered(ex: Any, sym_set: set[str], symbols: list[str]) -> dict[str, Any]:
    """Interner Helper: fetch_tickers() ohne Args, dann filtern; bei Fehler einzeln."""
    ex_id = getattr(ex, "id", "")
    all_tickers = _with_retry(ex.fetch_tickers, ex_id, "fetch_tickers()")
    if all_tickers:
        return {s: t for s, t in all_tickers.items() if s in sym_set}

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
    with _fee_cache_lock:
        cached = _fee_cache.get(exchange_id)
        if cached is not None:
            return cached  # TTLCache handles expiry automatically

    # Versuche CCXT-Fee-Abfrage (public endpoint, kein API-Key nötig)
    try:
        ex_cls = get_exchange_class(exchange_id)
        if ex_cls:
            ex = ex_cls({"enableRateLimit": True})
            fee_info = ex.fetch_trading_fee(symbol)
            default_rate = EXCHANGE_DEFAULT_FEES.get(exchange_id, fallback)
            rate = float(fee_info.get("taker", default_rate))
            with _fee_cache_lock:
                _fee_cache[exchange_id] = rate
            return rate
    except Exception as e:
        log.debug("Live-Fee-Abfrage für %s fehlgeschlagen: %s", exchange_id, e)

    rate = EXCHANGE_DEFAULT_FEES.get(exchange_id, fallback)
    with _fee_cache_lock:
        _fee_cache[exchange_id] = rate
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
            _fee_cache.clear()  # TTLCache.clear() is supported


def requires_passphrase(exchange_name: str) -> bool:
    """True, wenn die Exchange eine Passphrase zur Authentifizierung benötigt."""
    return exchange_name in PASSPHRASE_REQUIRED


def supported_exchanges() -> list[str]:
    """Gibt die Liste aller unterstützten Exchange-Namen zurück."""
    return sorted(EXCHANGE_MAP.keys())
