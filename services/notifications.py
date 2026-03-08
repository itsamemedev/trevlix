"""
TREVLIX – Notifications Service
================================
[Verbesserung #6] Ausgelagerter Benachrichtigungs-Dienst.

Enthält DiscordNotifier als standalone-Modul, das ohne direkte
Abhängigkeit auf server.py verwendet werden kann.

Verwendung in server.py (nach vollständiger Migration):
    from services.notifications import DiscordNotifier
    discord = DiscordNotifier(config=CONFIG)
"""

import logging
import os
from datetime import datetime

import httpx

log = logging.getLogger("NEXUS.notifications")


class DiscordNotifier:
    """
    Sendet Benachrichtigungen über Discord-Webhooks.

    Kann standalone (mit config-Parameter) oder als Legacy-Wrapper
    (mit globalem CONFIG-Zugriff via server.py) verwendet werden.
    """

    COLORS = {
        "buy": 3066993,
        "sell_win": 3066993,
        "sell_loss": 15158332,
        "error": 15158332,
        "circuit": 16776960,
        "info": 3447003,
        "report": 9442302,
        "alert": 16776960,
        "arb": 16744272,
        "anomaly": 16711680,
    }

    def __init__(self, config: dict | None = None, bot_full: str = "TREVLIX"):
        """
        Args:
            config: Optionaler Config-Dict. Wenn None, wird der globale CONFIG
                    aus server.py verwendet (Backward-Compatibility).
            bot_full: Bot-Name für Footer-Text.
        """
        self._config = config
        self._bot_full = bot_full

    def _cfg(self, key: str, default=None):
        """Liest einen Config-Wert – aus übergebenem oder globalem CONFIG."""
        if self._config is not None:
            return self._config.get(key, default)
        # Lazy-Import für Backward-Compatibility
        try:
            import server
            return server.CONFIG.get(key, default)
        except Exception:
            return default

    def send(self, title: str, desc: str, color_key: str = "info", fields: list | None = None):
        url = self._cfg("discord_webhook", "")
        if not url:
            return
        try:
            embed = {
                "title": title,
                "description": desc,
                "color": self.COLORS.get(color_key, 3447003),
                "timestamp": datetime.utcnow().isoformat(),
                "footer": {"text": f"{self._bot_full} · {self._cfg('exchange', '?').upper()}"},
            }
            if fields:
                embed["fields"] = [
                    {"name": f[0], "value": str(f[1]), "inline": f[2] if len(f) > 2 else True}
                    for f in fields
                ]
            httpx.post(url, json={"embeds": [embed]}, timeout=5)
        except Exception as e:
            log.debug(f"Discord: {e}")

    def trade_buy(self, symbol, price, invest, ai_score, win_prob, news_score=0):
        if not self._cfg("discord_on_buy"):
            return
        news_txt = f"📰 {news_score:+.2f}" if news_score != 0 else "—"
        self.send(
            f"🟢 KAUF: {symbol}",
            f"```\nPreis:      {price:.4f} USDT\nInvestiert: {invest:.2f} USDT\n"
            f"KI-Score:   {ai_score:.0f}%\nWin-Chance: {win_prob:.0f}%\n"
            f"News:       {news_txt}\n```",
            "buy",
            fields=[
                ("Exchange", self._cfg("exchange", "?").upper()),
                ("Modus", "📝 Paper" if self._cfg("paper_trading") else "💰 Live"),
            ],
        )

    def trade_sell(self, symbol, price, pnl, pnl_pct, reason, partial=False):
        if not self._cfg("discord_on_sell"):
            return
        won = pnl >= 0
        pref = "🔶 PARTIAL" if partial else ("✅ GEWINN" if won else "❌ VERLUST")
        self.send(
            f"{pref}: {symbol}",
            f"```\nPreis:  {price:.4f} USDT\nPnL:    {pnl:+.2f} ({pnl_pct:+.2f}%)\n"
            f"Grund:  {reason}\n```",
            "sell_win" if won else "sell_loss",
        )

    def circuit_breaker(self, losses, pause_min):
        if not self._cfg("discord_on_circuit"):
            return
        self.send(
            "⚡ CIRCUIT BREAKER",
            f"```\n{losses} Verluste hintereinander!\nPause: {pause_min} Minuten\n```",
            "circuit",
        )

    def price_alert(self, symbol, price, target, direction):
        self.send(
            f"🔔 PREIS-ALERT: {symbol}",
            f"```\nAktuell: {price:.4f}\nZiel:    {target:.4f}\n"
            f"Richtung: {'↑' if direction == 'above' else '↓'}\n```",
            "alert",
        )

    def arb_found(self, symbol, buy_ex, sell_ex, spread):
        self.send(
            f"💹 ARBITRAGE: {symbol}",
            f"```\nKauf:    {buy_ex}\nVerkauf: {sell_ex}\nSpread:  {spread:.2f}%\n```",
            "arb",
        )

    def anomaly_detected(self, symbol, score):
        self.send(
            f"🚨 ANOMALIE: {symbol}",
            f"```\nAnomalie-Score: {score:.3f}\nBot pausiert!\n```",
            "anomaly",
        )

    def daily_report(self, report: dict):
        if not self._cfg("discord_daily_report"):
            return
        s = report.get("summary", {})
        self.send(
            f"📊 NEXUS Tages-Report – {report.get('date', '')}",
            f"```\nPnL heute:  {s.get('daily_pnl', 0):+.2f} USDT\n"
            f"Trades:     {s.get('trades_today', 0)}\n"
            f"Win-Rate:   {s.get('win_rate', 0):.1f}%\n"
            f"Portfolio:  {s.get('portfolio_value', 0):.2f} USDT\n"
            f"Rendite:    {s.get('return_pct', 0):+.2f}%\n"
            f"Arbitrage:  {s.get('arb_found', 0)} Chancen\n```",
            "report",
            fields=[
                ("Bester Coin", s.get("best_coin", "—")),
                ("Schlechtester", s.get("worst_coin", "—")),
                ("KI-Genauigkeit", f"{s.get('ai_acc', 0):.1f}%"),
            ],
        )

    def error(self, msg: str):
        if not self._cfg("discord_on_error"):
            return
        self.send("🔴 NEXUS FEHLER", f"```\n{msg[:500]}\n```", "error")

    def backup_done(self, path: str):
        self.send("💾 Backup erstellt", f"```\n{os.path.basename(path)}\n```", "info")

    def short_open(self, symbol, price, invest):
        self.send(
            f"🔴 SHORT: {symbol}",
            f"```\nPreis:      {price:.4f} USDT\nInvestiert: {invest:.2f} USDT\n```",
            "sell_loss",
        )

    def genetic_result(self, gen: int, fitness: float, genome: dict):
        self.send(
            f"🧬 Genetik Gen.{gen}",
            f"```\nFitness: {fitness:.3f}\n"
            f"SL: {genome.get('sl', 0) * 100:.1f}% TP: {genome.get('tp', 0) * 100:.1f}%\n```",
            "info",
        )
