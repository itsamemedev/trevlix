"""REST API docs payload builder."""

from __future__ import annotations


def build_api_docs_payload(*, bot_full: str, bot_version: str) -> dict:
    """Build API docs payload for /api/v1/docs."""
    return {
        "name": bot_full,
        "version": bot_version,
        "website": "https://trevlix.dev",
        "endpoints": {
            "GET /api/v1/status": "Healthcheck (öffentlich, kein Auth)",
            "GET /api/v1/update/status": "Healthcheck alias (Docker HEALTHCHECK)",
            "GET /api/v1/state": "Bot-Status (Auth: Bearer Token)",
            "GET /api/v1/trades": "Trade-Liste (?limit=&symbol=&year=)",
            "GET /api/v1/portfolio": "Portfolio-Snapshot",
            "GET /api/v1/heatmap": "Markt-Heatmap",
            "POST /api/v1/backtest": "Backtest {symbol,timeframe,candles,sl,tp,vote}",
            "GET /api/v1/tax": "Steuer-Report (?year=&method=)",
            "POST /api/v1/signal": "TradingView Webhook {symbol,action}",
            "GET /api/v1/ai": "KI-Status",
            "GET /api/v1/dominance": "BTC/USDT Dominanz",
            "GET /api/v1/anomaly": "Anomalie-Detektor Status",
            "GET /api/v1/genetic": "Genetischer Optimizer",
            "GET /api/v1/rl": "Reinforcement Learning Agent",
            "GET /api/v1/news/{sym}": "News-Sentiment für Symbol",
            "GET /api/v1/onchain/{sym}": "On-Chain Score für Symbol",
            "GET /api/v1/arb": "Arbitrage-Chancen",
            "POST /api/v1/token": "API-Token erstellen",
            "GET /api/v1/admin/users": "Alle User (Admin)",
            "POST /api/v1/admin/users": "User anlegen (Admin)",
        },
    }
