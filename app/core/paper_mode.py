"""Paper-trading enforcement helpers."""

from __future__ import annotations


def enforce_paper_trading(config: dict, log, source: str = "system") -> None:
    """Force paper-trading mode and log when live mode gets disabled."""
    if not config.get("paper_trading", True):
        log.warning("Paper-Trading erzwungen (%s): Live-Modus wurde deaktiviert.", source)
    config["paper_trading"] = True
