"""TREVLIX – Market Link Builder.

Erzeugt Deep-Links zur Trading-Page eines Pairs auf der jeweiligen Exchange,
damit User aus Benachrichtigungen heraus mit einem Klick reagieren können.

Verwendung:
    from services.market_links import build_market_url

    url = build_market_url("cryptocom", "BTC/USDT")
    # → "https://crypto.com/exchange/trade/spot/BTC_USDT"
"""

from __future__ import annotations

_TEMPLATES: dict[str, str] = {
    "cryptocom": "https://crypto.com/exchange/trade/spot/{base}_{quote}",
    "binance": "https://www.binance.com/en/trade/{base}_{quote}",
    "bybit": "https://www.bybit.com/trade/spot/{base}/{quote}",
    "okx": "https://www.okx.com/trade-spot/{base_lower}-{quote_lower}",
    "kucoin": "https://www.kucoin.com/trade/{base}-{quote}",
    "kraken": "https://pro.kraken.com/app/trade/{base_lower}-{quote_lower}",
    "coinbase": "https://www.coinbase.com/advanced-trade/spot/{base}-{quote}",
    "bitget": "https://www.bitget.com/spot/{base}{quote}",
    "mexc": "https://www.mexc.com/exchange/{base}_{quote}",
    "gateio": "https://www.gate.io/trade/{base}_{quote}",
    "huobi": "https://www.htx.com/trade/{base_lower}_{quote_lower}",
    "nonkyc": "https://nonkyc.io/market/{base}_{quote}",
}


def build_market_url(exchange: str | None, symbol: str | None) -> str:
    """Liefert eine Deep-Link-URL zur Trading-Seite des Pairs.

    Args:
        exchange: Exchange-Name (z.B. ``"cryptocom"``).
        symbol: Trading-Pair im CCXT-Format ``"BASE/QUOTE"`` (z.B. ``"BTC/USDT"``).

    Returns:
        Vollständige HTTPS-URL, oder leerer String falls Exchange/Symbol unbekannt.
    """
    if not exchange or not symbol or "/" not in symbol:
        return ""
    template = _TEMPLATES.get(str(exchange).lower())
    if not template:
        return ""
    base, _, quote = symbol.partition("/")
    base = base.upper()
    quote = quote.upper()
    if not base or not quote:
        return ""
    return template.format(
        base=base,
        quote=quote,
        base_lower=base.lower(),
        quote_lower=quote.lower(),
    )
