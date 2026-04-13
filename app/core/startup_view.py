"""Startup banner rendering helper."""

from __future__ import annotations


def render_startup_banner(*, bot_version: str, config: dict) -> str:
    """Render the startup ASCII banner."""
    return f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║ ████████╗██████╗ ███████╗██╗   ██╗██╗     ██╗██╗  ██╗                    ║
║ ╚══██╔══╝██╔══██╗██╔════╝██║   ██║██║     ██║╚██╗██╔╝                    ║
║    ██║   ██████╔╝█████╗  ██║   ██║██║     ██║ ╚███╔╝                     ║
║    ██║   ██╔══██╗██╔══╝  ╚██╗ ██╔╝██║     ██║ ██╔██╗                     ║
║    ██║   ██║  ██║███████╗ ╚████╔╝ ███████╗██║██╔╝ ██╗                    ║
║    ╚═╝   ╚═╝  ╚═╝╚══════╝  ╚═══╝  ╚══════╝╚═╝╚═╝  ╚═╝                    ║
║                                                                              ║
║  Algorithmic Crypto Trading  ·  v{bot_version}  ·  trevlix.dev                ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  MySQL:   {config["mysql_host"]}/{config["mysql_db"]:<44}║
║  Exchange:{config["exchange"]:<51}║
║  Modus:   {"📝 Paper Trading" if config["paper_trading"] else "💰 Live Trading":<50}║
║  Kapital: {config["paper_balance"]:<50}║
╚══════════════════════════════════════════════════════════════════════════════╝
    """
