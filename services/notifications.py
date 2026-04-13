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
import threading
import time
from datetime import datetime

import httpx

from app.core.time_compat import UTC

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
        self._signal_lock = threading.Lock()
        self._signal_last_sent: dict[str, float] = {}

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
        if not url or not isinstance(url, str):
            return
        url = url.strip()
        if not url.startswith("https://"):
            log.warning("Discord webhook URL must start with https://")
            return
        title = str(title or "")[:256]
        desc = str(desc or "")[:4096]
        try:
            exchange_name = self._cfg("exchange", "?")
            exchange_str = str(exchange_name).upper() if exchange_name else "?"
            embed: dict = {
                "title": title,
                "description": desc,
                "color": self.COLORS.get(color_key, 3447003),
                "timestamp": datetime.now(UTC).isoformat(),
                "footer": {"text": f"{self._bot_full} · {exchange_str}"},
            }
            if fields:
                embed["fields"] = [
                    {"name": f[0], "value": str(f[1]), "inline": f[2] if len(f) > 2 else True}
                    for f in fields
                    if len(f) >= 2
                ]
            resp = httpx.post(url, json={"embeds": [embed]}, timeout=5)
            if resp.status_code >= 400:
                log.warning("Discord webhook HTTP %s: %s", resp.status_code, resp.text[:200])
        except Exception as e:
            log.warning("Discord send failed: %s", e)

    def trade_buy(
        self,
        symbol: str,
        price: float,
        invest: float,
        ai_score: float,
        win_prob: float,
        news_score: float = 0,
        confidence: float | None = None,
        rsi: float | None = None,
        regime: str | None = None,
        votes: dict | None = None,
    ) -> None:
        if not self._cfg("discord_on_buy"):
            return
        news_txt = f"{news_score:+.2f}" if news_score != 0 else "0.00"
        exchange_name = self._cfg("exchange", "?")
        exchange_str = str(exchange_name).upper() if exchange_name else "?"
        mode_txt = "📝 Paper Trading" if self._cfg("paper_trading") else "💰 Live Trading"
        vote_txt = "—"
        if votes and isinstance(votes, dict):
            buy_votes = int(votes.get("buy", 0))
            sell_votes = int(votes.get("sell", 0))
            hold_votes = int(votes.get("hold", 0))
            vote_txt = f"B:{buy_votes} / S:{sell_votes} / H:{hold_votes}"
        self.send(
            f"🟢 BUY EXECUTED · {symbol}",
            (
                "```yaml\n"
                f"pair: {symbol}\n"
                f"price: {price:.4f} USDT\n"
                f"invest: {invest:.2f} USDT\n"
                f"ai_score: {ai_score:.1f}%\n"
                f"win_prob: {win_prob:.1f}%\n"
                f"news_score: {news_txt}\n"
                "```"
            ),
            "buy",
            fields=[
                ("Exchange", exchange_str),
                ("Mode", mode_txt),
                ("Signal Confidence", f"{(confidence or 0) * 100:.1f}%" if confidence else "—"),
                ("RSI", f"{rsi:.1f}" if rsi is not None else "—"),
                ("Regime", regime or "—"),
                ("Votes", vote_txt, False),
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
        pref = "🔶 PARTIAL EXIT" if partial else ("✅ TAKE PROFIT" if won else "❌ STOP / LOSS")
        roi_icon = "📈" if pnl_pct >= 0 else "📉"
        self.send(
            f"{pref} · {symbol}",
            (
                "```yaml\n"
                f"pair: {symbol}\n"
                f"exit_price: {price:.4f} USDT\n"
                f"pnl_usdt: {pnl:+.2f}\n"
                f"pnl_pct: {pnl_pct:+.2f}%\n"
                f"reason: {reason}\n"
                "```"
            ),
            "sell_win" if won else "sell_loss",
            fields=[
                ("Result", "WIN ✅" if won else "LOSS ❌"),
                ("ROI", f"{roi_icon} {pnl_pct:+.2f}%"),
            ],
        )

    def signal_opportunity(
        self,
        symbol: str,
        side: str,
        confidence: float,
        price: float,
        *,
        ai_score: float | None = None,
        news_score: float | None = None,
        note: str = "",
    ) -> None:
        """Sendet Trade-Opportunity Hinweise (throttled pro Symbol/Richtung)."""
        if not self._cfg("discord_on_signals", True):
            return
        side_norm = str(side or "").lower()
        if side_norm not in {"buy", "sell"}:
            return
        cooldown = int(self._cfg("discord_signal_cooldown_sec", 900) or 900)
        key = f"{side_norm}:{symbol}"
        now_ts = time.time()
        with self._signal_lock:
            last = self._signal_last_sent.get(key, 0.0)
            if now_ts - last < cooldown:
                return
            self._signal_last_sent[key] = now_ts

        up = side_norm == "buy"
        icon = "🟢" if up else "🔻"
        color = "buy" if up else "sell_loss"
        signal_txt = "BUY setup" if up else "SELL setup"
        ai_txt = f"{ai_score:.1f}%" if ai_score is not None else "—"
        news_txt = f"{news_score:+.2f}" if news_score is not None else "—"
        self.send(
            f"{icon} Opportunity · {symbol}",
            (
                "```yaml\n"
                f"signal: {signal_txt}\n"
                f"confidence: {confidence * 100:.1f}%\n"
                f"price: {price:.4f} USDT\n"
                f"ai_score: {ai_txt}\n"
                f"news_score: {news_txt}\n"
                "```"
            ),
            color,
            fields=[("Note", note[:200] if note else "Potential setup detected", False)],
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

    def algo_buy_signal(
        self,
        symbol: str,
        price: float,
        confidence: float,
        reason: str,
        sub_scores: dict | None = None,
    ) -> None:
        """Sendet Kauf-Signal des selbstlernenden Algorithmus."""
        if not self._cfg("discord_on_algo_signals", True):
            return
        scores_txt = ""
        if sub_scores:
            scores_txt = " | ".join(f"{k}:{v:.0%}" for k, v in sub_scores.items())
        self.send(
            f"🧠 ALGO BUY SIGNAL · {symbol}",
            (
                "```yaml\n"
                f"pair: {symbol}\n"
                f"price: {price:.4f} USDT\n"
                f"algo_confidence: {confidence:.1%}\n"
                f"strategy: {reason}\n"
                f"sub_scores: {scores_txt}\n"
                "```"
            ),
            "buy",
            fields=[
                ("Typ", "Selbstlernend (KI)"),
                (
                    "Modus",
                    "📝 Paper" if self._cfg("paper_trading") else "💰 Live",
                ),
            ],
        )

    def algo_sell_signal(
        self,
        symbol: str,
        price: float,
        confidence: float,
        reason: str,
        pnl: float | None = None,
    ) -> None:
        """Sendet Verkauf-Signal des selbstlernenden Algorithmus."""
        if not self._cfg("discord_on_algo_signals", True):
            return
        pnl_txt = f"{pnl:+.2f} USDT" if pnl is not None else "—"
        self.send(
            f"🧠 ALGO SELL SIGNAL · {symbol}",
            (
                "```yaml\n"
                f"pair: {symbol}\n"
                f"price: {price:.4f} USDT\n"
                f"algo_confidence: {confidence:.1%}\n"
                f"strategy: {reason}\n"
                f"unrealized_pnl: {pnl_txt}\n"
                "```"
            ),
            "sell_win" if pnl and pnl > 0 else "sell_loss",
            fields=[
                ("Typ", "Selbstlernend (KI)"),
                ("Grund", reason[:100]),
            ],
        )

    def daily_report(self, report: dict) -> None:
        if not self._cfg("discord_daily_report"):
            return
        s = report.get("summary", {})
        self.send(
            f"📊 {(self._bot_full.split() or ['TREVLIX'])[0]} Tages-Report – {report.get('date', '')}",
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
            f"🔴 {(self._bot_full.split() or ['TREVLIX'])[0]} FEHLER",
            f"```\n{msg[:500]}\n```",
            "error",
        )

    def info(self, msg: str) -> None:
        self.send(
            f"ℹ️ {(self._bot_full.split() or ['TREVLIX'])[0]} INFO",
            f"```\n{str(msg)[:500]}\n```",
            "info",
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
        try:
            raw_sl = genome.get("sl")
            sl_val = float(raw_sl) if raw_sl is not None else 0.0
        except (ValueError, TypeError):
            sl_val = 0.0
        try:
            raw_tp = genome.get("tp")
            tp_val = float(raw_tp) if raw_tp is not None else 0.0
        except (ValueError, TypeError):
            tp_val = 0.0
        self.send(
            f"🧬 Genetik Gen.{gen}",
            f"```\nFitness: {fitness:.3f}\nSL: {sl_val * 100:.1f}% TP: {tp_val * 100:.1f}%\n```",
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

    @property
    def enabled(self) -> bool:
        """True, wenn Token und Chat-ID konfiguriert sind."""
        return bool(self._token() and self._chat_id())

    def test(self) -> bool:
        """Sendet eine Test-Nachricht. Gibt True bei Erfolg zurück."""
        token = self._token()
        chat_id = self._chat_id()
        if not token or not chat_id:
            return False
        try:
            url = self._API_BASE.format(token=token)
            resp = httpx.post(
                url,
                json={
                    "chat_id": chat_id,
                    "text": f"🤖 <b>{(self._bot_full.split() or ['TREVLIX'])[0]}</b> — Verbindung erfolgreich!",
                    "parse_mode": "HTML",
                },
                timeout=5,
            )
            return resp.status_code == 200
        except Exception as e:
            log.warning("Telegram test failed: %s", e)
            return False

    def send(self, text: str, parse_mode: str = "HTML") -> None:
        """Sends a plain text (or HTML-formatted) message to the configured chat."""
        token = self._token()
        chat_id = self._chat_id()
        if not token or not chat_id:
            return
        text = str(text or "")[:4096]
        if not text.strip():
            return
        try:
            url = self._API_BASE.format(token=token)
            resp = httpx.post(
                url,
                json={"chat_id": chat_id, "text": text, "parse_mode": parse_mode},
                timeout=5,
            )
            if resp.status_code >= 400:
                log.warning("Telegram HTTP %s: %s", resp.status_code, resp.text[:200])
        except Exception as e:
            log.warning("Telegram send failed: %s", e)

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
        self.send(
            f"🔴 <b>{(self._bot_full.split() or ['TREVLIX'])[0]} FEHLER</b>\n<code>{short}</code>"
        )

    def info(self, msg: str) -> None:
        short = str(msg)[:400]
        self.send(
            f"ℹ️ <b>{(self._bot_full.split() or ['TREVLIX'])[0]} INFO</b>\n<code>{short}</code>"
        )

    def circuit_breaker(self, losses: int, pause_min: int) -> None:
        self.send(
            f"⚡ <b>CIRCUIT BREAKER</b>\n{losses} Verluste → Pause <code>{pause_min}</code> Minuten"
        )

    def algo_buy_signal(
        self,
        symbol: str,
        price: float,
        confidence: float,
        reason: str,
    ) -> None:
        """Sendet Algo-Kaufsignal per Telegram."""
        if not self._config.get("telegram_on_algo_signals", True):
            return
        self.send(
            f"🧠 <b>ALGO KAUF-SIGNAL: {symbol}</b>\n"
            f"Preis: <code>{price:.4f}</code> USDT\n"
            f"Konfidenz: <code>{confidence:.1%}</code>\n"
            f"Strategie: {reason}"
        )

    def algo_sell_signal(
        self,
        symbol: str,
        price: float,
        confidence: float,
        reason: str,
        pnl: float | None = None,
    ) -> None:
        """Sendet Algo-Verkaufssignal per Telegram."""
        if not self._config.get("telegram_on_algo_signals", True):
            return
        pnl_txt = f"\nPnL: <code>{pnl:+.2f}</code> USDT" if pnl is not None else ""
        self.send(
            f"🧠 <b>ALGO VERKAUF-SIGNAL: {symbol}</b>\n"
            f"Preis: <code>{price:.4f}</code> USDT\n"
            f"Konfidenz: <code>{confidence:.1%}</code>\n"
            f"Grund: {reason}{pnl_txt}"
        )

    def price_alert(self, symbol: str, price: float, target: float, direction: str) -> None:
        arrow = "↑" if direction == "above" else "↓"
        self.send(
            f"🔔 <b>PREIS-ALERT: {symbol}</b>\n"
            f"Aktuell: <code>{price:.4f}</code>  Ziel: <code>{target:.4f}</code> {arrow}"
        )
