"""Tests für DiscordNotifier-Verbesserungen."""

from __future__ import annotations

from services.notifications import DiscordNotifier


class _Resp:
    def __init__(self, status_code: int = 204, text: str = ""):
        self.status_code = status_code
        self.text = text


def test_signal_opportunity_respects_cooldown(monkeypatch):
    sent_payloads: list[dict] = []

    def _fake_post(_url, json, timeout):
        sent_payloads.append(json)
        return _Resp()

    monkeypatch.setattr("services.notifications.httpx.post", _fake_post)
    notifier = DiscordNotifier(
        {
            "discord_webhook": "https://discord.example/hook",
            "discord_on_signals": True,
            "discord_signal_cooldown_sec": 600,
        }
    )

    notifier.signal_opportunity("BTC/USDT", "buy", 0.81, 65000.0, ai_score=77.2, news_score=0.2)
    notifier.signal_opportunity("BTC/USDT", "buy", 0.85, 65100.0, ai_score=80.1, news_score=0.3)

    assert len(sent_payloads) == 1
    embed = sent_payloads[0]["embeds"][0]
    assert "Opportunity" in embed["title"]
    assert "confidence" in embed["description"]


def test_trade_buy_contains_extended_fields(monkeypatch):
    sent_payloads: list[dict] = []

    def _fake_post(_url, json, timeout):
        sent_payloads.append(json)
        return _Resp()

    monkeypatch.setattr("services.notifications.httpx.post", _fake_post)
    notifier = DiscordNotifier(
        {
            "discord_webhook": "https://discord.example/hook",
            "discord_on_buy": True,
            "paper_trading": True,
            "exchange": "binance",
        }
    )

    notifier.trade_buy(
        "ETH/USDT",
        3200.0,
        125.0,
        84.2,
        71.3,
        news_score=0.33,
        confidence=0.79,
        rsi=42.5,
        regime="bull",
        votes={"buy": 6, "sell": 1, "hold": 2},
    )

    assert len(sent_payloads) == 1
    fields = sent_payloads[0]["embeds"][0]["fields"]
    names = {f["name"] for f in fields}
    assert "Signal Confidence" in names
    assert "Votes" in names
