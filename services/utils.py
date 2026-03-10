"""TREVLIX – Utility-Funktionen & gemeinsame Konstanten.

Extrahiert aus server.py für bessere Modularisierung.

Verwendung:
    from services.utils import SecretStr, validate_config, BOT_NAME, BOT_VERSION
"""

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


def validate_config(cfg: dict) -> list[str]:
    """Validiert CONFIG-Werte und gibt eine Liste von Fehlermeldungen zurück.

    Args:
        cfg: Konfigurations-Dictionary mit den zu prüfenden Werten.

    Returns:
        Liste mit Fehlermeldungen. Leere Liste = alles OK.
    """
    errors: list[str] = []

    if not (0 < cfg.get("stop_loss_pct", 0.025) < 1):
        errors.append("stop_loss_pct muss zwischen 0 und 1 liegen")
    if not (0 < cfg.get("take_profit_pct", 0.06) < 1):
        errors.append("take_profit_pct muss zwischen 0 und 1 liegen")
    if cfg.get("take_profit_pct", 0.06) <= cfg.get("stop_loss_pct", 0.025):
        errors.append("take_profit_pct muss größer als stop_loss_pct sein")
    if cfg.get("scan_interval", 60) < 10:
        errors.append("scan_interval muss mindestens 10 Sekunden betragen")
    if cfg.get("max_open_trades", 5) < 1:
        errors.append("max_open_trades muss mindestens 1 sein")
    if not (0 < cfg.get("risk_per_trade", 0.015) <= 0.5):
        errors.append("risk_per_trade muss zwischen 0 und 0.5 liegen")

    ex = cfg.get("exchange", "")
    if ex not in EXCHANGE_MAP:
        errors.append(f"exchange '{ex}' ist ungültig – erlaubt: {list(EXCHANGE_MAP.keys())}")

    if cfg.get("use_shorts") and not (cfg.get("short_api_key") and cfg.get("short_secret")):
        errors.append("use_shorts=True erfordert short_api_key und short_secret")

    return errors
