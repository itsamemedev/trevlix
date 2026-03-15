"""TREVLIX – Utility-Funktionen & gemeinsame Konstanten.

Verwendung:
    from services.utils import SecretStr, validate_config, BOT_NAME, BOT_VERSION
"""

import re

BOT_NAME = "TREVLIX"
BOT_VERSION = "1.2.0"
BOT_FULL = f"{BOT_NAME} v{BOT_VERSION} · Algorithmic Crypto Trading Bot"

# Exchange-Name → ccxt-Klassen-Name
EXCHANGE_MAP = {
    "cryptocom": "cryptocom",
    "binance": "binance",
    "bybit": "bybit",
    "okx": "okx",
    "kucoin": "kucoin",
    "kraken": "kraken",
    "huobi": "huobi",
    "coinbase": "coinbaseadvanced",  # CCXT-Klassenname für Coinbase Advanced Trade
}

# Valid CCXT-style timeframe strings
_VALID_TIMEFRAMES = frozenset(
    ["1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "8h", "12h", "1d", "3d", "1w"]
)

# Symbol format: BASE/QUOTE, e.g. BTC/USDT
_SYMBOL_RE = re.compile(r"^[A-Z0-9]{2,10}/[A-Z]{2,6}$")


class SecretStr(str):
    """String-Subklasse, die in __repr__ und __str__ maskiert wird."""

    def __repr__(self) -> str:
        return "SecretStr('***')"

    def __str__(self) -> str:
        return "***"

    def reveal(self) -> str:
        """Gibt den echten Wert zurück – explizit aufrufen."""
        return str.__str__(self)


def make_secret(val: str) -> SecretStr:
    """Erstellt ein SecretStr-Objekt aus einem normalen String."""
    return SecretStr(val)


def validate_symbol(symbol: str) -> bool:
    """Returns True if ``symbol`` looks like a valid trading pair (e.g. 'BTC/USDT')."""
    return bool(_SYMBOL_RE.match(symbol))


def validate_config(cfg: dict) -> list[str]:
    """Validiert CONFIG-Werte und gibt eine Liste von Fehlermeldungen zurück.

    Args:
        cfg: Konfigurations-Dictionary mit den zu prüfenden Werten.

    Returns:
        Liste mit Fehlermeldungen. Leere Liste = alles OK.
    """
    errors: list[str] = []

    sl = cfg.get("stop_loss_pct", 0.025)
    tp = cfg.get("take_profit_pct", 0.06)

    if not (0 < sl < 1):
        errors.append("stop_loss_pct muss zwischen 0 und 1 liegen")
    if not (0 < tp < 1):
        errors.append("take_profit_pct muss zwischen 0 und 1 liegen")
    if tp <= sl:
        errors.append("take_profit_pct muss größer als stop_loss_pct sein")

    scan = cfg.get("scan_interval", 60)
    if scan < 10:
        errors.append("scan_interval muss mindestens 10 Sekunden betragen")
    if scan > 3600:
        errors.append("scan_interval sollte 3600 Sekunden nicht überschreiten")

    if cfg.get("max_open_trades", 5) < 1:
        errors.append("max_open_trades muss mindestens 1 sein")

    risk = cfg.get("risk_per_trade", 0.015)
    if not (0 < risk <= 0.5):
        errors.append("risk_per_trade muss zwischen 0 und 0.5 liegen")

    ex = cfg.get("exchange", "")
    if ex not in EXCHANGE_MAP:
        errors.append(f"exchange '{ex}' ist ungültig – erlaubt: {list(EXCHANGE_MAP.keys())}")

    tf = cfg.get("timeframe", "")
    if tf and tf not in _VALID_TIMEFRAMES:
        errors.append(f"timeframe '{tf}' ist ungültig – erlaubt: {sorted(_VALID_TIMEFRAMES)}")

    max_dd = cfg.get("max_drawdown_pct", 0.10)
    if not (0 < max_dd < 1):
        errors.append("max_drawdown_pct muss zwischen 0 und 1 liegen")

    daily_loss = cfg.get("max_daily_loss_pct", 0.05)
    if not (0 < daily_loss < 1):
        errors.append("max_daily_loss_pct muss zwischen 0 und 1 liegen")

    # Symbol list validation
    symbol_list = cfg.get("symbol_list", [])
    if symbol_list:
        invalid = [s for s in symbol_list if not validate_symbol(s)]
        if invalid:
            errors.append(f"Ungültige Symbole in symbol_list: {invalid}")

    if cfg.get("use_shorts") and not (cfg.get("short_api_key") and cfg.get("short_secret")):
        errors.append("use_shorts=True erfordert short_api_key und short_secret")

    return errors
