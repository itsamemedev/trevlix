"""
TREVLIX – Notifications Service
================================
Sendet Benachrichtigungen über Discord-Webhooks und Telegram.

Verwendung:
    from services.notifications import DiscordNotifier, TelegramNotifier

    discord = DiscordNotifier(config=CONFIG)
    discord.trade_buy(symbol, price, invest, ai_score, win_prob)

    telegram = TelegramNotifier(config=CONFIG)
    telegram.send("Bot gestartet")
"""

import logging
import os
from datetime import UTC, datetime

import httpx

log = logging.getLogger("trevlix.notifications")


class DiscordNotifier:
    """Sendet Benachrichtigungen über Discord-Webhooks.

    Requires config keys:
        discord_webhook (str): Full Discord webhook URL.
        discord_on_buy / discord_on_sell / discord_on_circuit /
        discord_on_error / discord_daily_report (bool): Feature toggles.
        exchange (str): Exchange name shown in footer.
        paper_trading (bool): Shown in trade notifications.
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

    def __init__(self, config: dict, bot_full: str = "TREVLIX"):
        """
        Args:
            config: Config dict with Discord/bot settings.
            bot_full: Bot-Name für Footer-Text.
        """
        self._config = config
        self._bot_full = bot_full

    def _cfg(self, key: str, default=None):
        return self._config.get(key, default)

    def send(
        self,
        title: str,
        desc: str,
        color_key: str = "info",
        fields: list | None = None,
    ) -> None:
        url = self._cfg("discord_webhook", "")
        if not url:
            return
        try:
            embed: dict = {
                "title": title,
                "description": desc,
                "color": self.COLORS.get(color_key, 3447003),
                "timestamp": datetime.now(UTC).isoformat(),
                "footer": {"text": f"{self._bot_full} · {self._cfg('exchange', '?').upper()}"},
            }
            if fields:
                embed["fields"] = [
                    {"name": f[0], "value": str(f[1]), "inline": f[2] if len(f) > 2 else True}
                    for f in fields
                ]
            httpx.post(url, json={"embeds": [embed]}, timeout=5)
        except Exception as e:
            log.debug(f"Discord send failed: {e}")

    def trade_buy(
        self,
        symbol: str,
        price: float,
        invest: float,
        ai_score: float,
        win_prob: float,
        news_score: float = 0,
    ) -> None:
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

    def trade_sell(
        self,
        symbol: str,
        price: float,
        pnl: float,
        pnl_pct: float,
        reason: str,
        partial: bool = False,
    ) -> None:
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

    def circuit_breaker(self, losses: int, pause_min: int) -> None:
        if not self._cfg("discord_on_circuit"):
            return
        self.send(
            "⚡ CIRCUIT BREAKER",
            f"```\n{losses} Verluste hintereinander!\nPause: {pause_min} Minuten\n```",
            "circuit",
        )

    def price_alert(self, symbol: str, price: float, target: float, direction: str) -> None:
        self.send(
            f"🔔 PREIS-ALERT: {symbol}",
            f"```\nAktuell: {price:.4f}\nZiel:    {target:.4f}\n"
            f"Richtung: {'↑' if direction == 'above' else '↓'}\n```",
            "alert",
        )

    def arb_found(self, symbol: str, buy_ex: str, sell_ex: str, spread: float) -> None:
        self.send(
            f"💹 ARBITRAGE: {symbol}",
            f"```\nKauf:    {buy_ex}\nVerkauf: {sell_ex}\nSpread:  {spread:.2f}%\n```",
            "arb",
        )

    def anomaly_detected(self, symbol: str, score: float) -> None:
        self.send(
            f"🚨 ANOMALIE: {symbol}",
            f"```\nAnomalie-Score: {score:.3f}\nBot pausiert!\n```",
            "anomaly",
        )

    def daily_report(self, report: dict) -> None:
        if not self._cfg("discord_daily_report"):
            return
        s = report.get("summary", {})
        self.send(
            f"📊 {self._bot_full.split()[0]} Tages-Report – {report.get('date', '')}",
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

    def error(self, msg: str) -> None:
        if not self._cfg("discord_on_error"):
            return
        self.send(
            f"🔴 {self._bot_full.split()[0]} FEHLER",
            f"```\n{msg[:500]}\n```",
            "error",
        )

    def backup_done(self, path: str) -> None:
        self.send("💾 Backup erstellt", f"```\n{os.path.basename(path)}\n```", "info")

    def short_open(self, symbol: str, price: float, invest: float) -> None:
        self.send(
            f"🔴 SHORT: {symbol}",
            f"```\nPreis:      {price:.4f} USDT\nInvestiert: {invest:.2f} USDT\n```",
            "sell_loss",
        )

    def genetic_result(self, gen: int, fitness: float, genome: dict) -> None:
        self.send(
            f"🧬 Genetik Gen.{gen}",
            f"```\nFitness: {fitness:.3f}\n"
            f"SL: {genome.get('sl', 0) * 100:.1f}% TP: {genome.get('tp', 0) * 100:.1f}%\n```",
            "info",
        )

    def dna_boost(
        self, symbol: str, action: str, win_rate: float, matches: int, multiplier: float
    ) -> None:
        """Benachrichtigung bei DNA-Pattern-Match (Boost oder Block).

        Args:
            symbol: Trading-Pair.
            action: 'boost' oder 'block'.
            win_rate: Historische Win-Rate des Musters.
            matches: Anzahl historischer Matches.
            multiplier: Konfidenz-Multiplikator.
        """
        emoji = "🧬✅" if action == "boost" else "🧬⛔"
        color = "buy" if action == "boost" else "sell_loss"
        self.send(
            f"{emoji} DNA-{action.upper()}: {symbol}",
            f"```\nWin-Rate:    {win_rate:.0f}%\n"
            f"Matches:     {matches}\n"
            f"Multiplikator: {multiplier:.2f}x\n```",
            color,
        )

    def smart_exit(self, symbol: str, sl: float, tp: float, regime: str, atr_pct: float) -> None:
        """Benachrichtigung über Smart Exit Level.

        Args:
            symbol: Trading-Pair.
            sl: Berechneter Stop-Loss.
            tp: Berechnetes Take-Profit.
            regime: Aktuelles Marktregime.
            atr_pct: ATR in Prozent.
        """
        self.send(
            f"📐 Smart Exit: {symbol}",
            f"```\nRegime:  {regime}\nATR:     {atr_pct:.2f}%\n"
            f"SL:      {sl:.4f}\nTP:      {tp:.4f}\n```",
            "info",
        )


class TelegramNotifier:
    """Sendet Benachrichtigungen über Telegram Bot API.

    Requires config keys:
        telegram_token (str): Bot token from @BotFather.
        telegram_chat_id (str): Target chat / channel ID.
        telegram_on_buy / telegram_on_sell / telegram_on_error (bool): Toggles.

    Falls back to TELEGRAM_TOKEN / TELEGRAM_CHAT_ID environment variables
    if the config keys are not present.
    """

    _API_BASE = "https://api.telegram.org/bot{token}/sendMessage"

    def __init__(self, config: dict, bot_full: str = "TREVLIX"):
        self._config = config
        self._bot_full = bot_full

    def _token(self) -> str:
        return self._config.get("telegram_token", "") or os.getenv("TELEGRAM_TOKEN", "")

    def _chat_id(self) -> str:
        return self._config.get("telegram_chat_id", "") or os.getenv("TELEGRAM_CHAT_ID", "")

    def send(self, text: str, parse_mode: str = "HTML") -> None:
        """Sends a plain text (or HTML-formatted) message to the configured chat."""
        token = self._token()
        chat_id = self._chat_id()
        if not token or not chat_id:
            return
        try:
            url = self._API_BASE.format(token=token)
            httpx.post(
                url,
                json={"chat_id": chat_id, "text": text, "parse_mode": parse_mode},
                timeout=5,
            )
        except Exception as e:
            log.debug(f"Telegram send failed: {e}")

    def trade_buy(
        self,
        symbol: str,
        price: float,
        invest: float,
        ai_score: float,
        win_prob: float,
    ) -> None:
        if not self._config.get("telegram_on_buy"):
            return
        mode = "📝 Paper" if self._config.get("paper_trading") else "💰 Live"
        self.send(
            f"🟢 <b>KAUF: {symbol}</b>\n"
            f"Preis: <code>{price:.4f}</code> USDT\n"
            f"Investiert: <code>{invest:.2f}</code> USDT\n"
            f"KI-Score: <code>{ai_score:.0f}%</code>  Win: <code>{win_prob:.0f}%</code>\n"
            f"Modus: {mode}"
        )

    def trade_sell(
        self,
        symbol: str,
        price: float,
        pnl: float,
        pnl_pct: float,
        reason: str,
    ) -> None:
        if not self._config.get("telegram_on_sell"):
            return
        icon = "✅" if pnl >= 0 else "❌"
        self.send(
            f"{icon} <b>VERKAUF: {symbol}</b>\n"
            f"Preis: <code>{price:.4f}</code> USDT\n"
            f"PnL: <code>{pnl:+.2f} ({pnl_pct:+.2f}%)</code>\n"
            f"Grund: {reason}"
        )

    def error(self, msg: str) -> None:
        if not self._config.get("telegram_on_error"):
            return
        short = msg[:400] if len(msg) > 400 else msg
        self.send(f"🔴 <b>{self._bot_full.split()[0]} FEHLER</b>\n<code>{short}</code>")

    def circuit_breaker(self, losses: int, pause_min: int) -> None:
        self.send(
            f"⚡ <b>CIRCUIT BREAKER</b>\n{losses} Verluste → Pause <code>{pause_min}</code> Minuten"
        )

    def price_alert(self, symbol: str, price: float, target: float, direction: str) -> None:
        arrow = "↑" if direction == "above" else "↓"
        self.send(
            f"🔔 <b>PREIS-ALERT: {symbol}</b>\n"
            f"Aktuell: <code>{price:.4f}</code>  Ziel: <code>{target:.4f}</code> {arrow}"
        )
