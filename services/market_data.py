"""TREVLIX – Marktdaten-Services.

Extrahiert aus server.py für bessere Modularisierung.
Enthält FearGreedIndex, MarketRegime, DominanceFilter,
SentimentFetcher und OnChainFetcher.

Verwendung:
    from services.market_data import FearGreedIndex, MarketRegime, DominanceFilter
"""

import logging
import threading
from datetime import datetime

import numpy as np
import pandas as pd
import requests

log = logging.getLogger("trevlix.market_data")


class FearGreedIndex:
    """Fear & Greed Index von alternative.me."""

    def __init__(self, config: dict):
        self.config = config
        self.value = 50
        self.label = "Neutral"
        self.last_update = None

    def update(self):
        if not self.config.get("use_fear_greed"):
            return
        try:
            r = requests.get("https://api.alternative.me/fng/?limit=1", timeout=8)
            d = r.json()["data"][0]
            self.value = int(d["value"])
            self.label = d["value_classification"]
            self.last_update = datetime.now().strftime("%H:%M")
        except Exception as e:
            log.debug(f"FG: {e}")

    def is_ok_to_buy(self) -> bool:
        return self.value <= self.config["fg_buy_max"] if self.config.get("use_fear_greed") else True

    def buy_boost(self) -> float:
        return 1.3 if self.value < self.config["fg_sell_min"] else 1.0

    def to_dict(self) -> dict:
        return {
            "value": self.value,
            "label": self.label,
            "last_update": self.last_update,
            "ok_to_buy": self.is_ok_to_buy(),
        }


class MarketRegime:
    """Bull/Bear-Erkennung anhand von BTC EMA-Kreuzungen."""

    def __init__(self, config: dict):
        self.config = config
        self.is_bull = True
        self.btc_price = 0.0
        self.last_update = None

    def update(self, ex):
        try:
            ohlcv = ex.fetch_ohlcv("BTC/USDT", self.config["btc_regime_tf"], limit=200)
            df = pd.DataFrame(ohlcv, columns=["ts", "o", "h", "l", "close", "v"])
            c = df["close"]
            e50 = c.ewm(span=50, adjust=False).mean().iloc[-1]
            e200 = c.ewm(span=200, adjust=False).mean().iloc[-1] if len(c) >= 200 else e50
            cur = float(c.iloc[-1])
            self.btc_price = cur
            self.is_bull = cur > e50 and e50 > e200 * 0.98
            self.last_update = datetime.now().strftime("%H:%M:%S")
        except Exception as e:
            log.debug(f"Regime:{e}")


class DominanceFilter:
    """BTC/USDT-Dominanz-Filter für Altcoin-Käufe."""

    def __init__(self, config: dict):
        self.config = config
        self.btc_dom = 50.0
        self.usdt_dom = 6.0
        self.last_update = None
        self._lock = threading.Lock()

    def update(self):
        if not self.config.get("use_dominance"):
            return
        try:
            r = requests.get("https://api.coingecko.com/api/v3/global", timeout=8)
            data = r.json().get("data", {})
            mcp = data.get("market_cap_percentage", {})
            with self._lock:
                self.btc_dom = float(mcp.get("btc", 50))
                self.usdt_dom = float(mcp.get("usdt", 6))
                self.last_update = datetime.now().strftime("%H:%M")
            log.info(f"Dominanz: BTC={self.btc_dom:.1f}% USDT={self.usdt_dom:.1f}%")
        except Exception as e:
            log.debug(f"Dominanz: {e}")

    def is_ok_to_buy(self, symbol: str) -> tuple[bool, str]:
        if not self.config.get("use_dominance"):
            return True, "Dominanz-Filter deaktiv"
        with self._lock:
            if self.usdt_dom > self.config["usdt_dom_max"]:
                return (
                    False,
                    f"USDT-Dominanz {self.usdt_dom:.1f}% > {self.config['usdt_dom_max']}% → Markt flüchtet",
                )
            if symbol not in ("BTC/USDT", "ETH/USDT") and self.btc_dom > self.config["btc_dom_min"]:
                return False, f"BTC-Dominanz {self.btc_dom:.1f}% → Altcoin-Käufe blockiert"
            return True, f"BTC:{self.btc_dom:.0f}% USDT:{self.usdt_dom:.0f}%"

    def to_dict(self) -> dict:
        with self._lock:
            return {
                "btc_dom": round(self.btc_dom, 1),
                "usdt_dom": round(self.usdt_dom, 1),
                "last_update": self.last_update,
                "ok_btc": self.btc_dom <= self.config["btc_dom_min"],
                "ok_usdt": self.usdt_dom <= self.config["usdt_dom_max"],
            }


class SentimentFetcher:
    """CoinGecko Community-Sentiment als Trading-Signal."""

    COIN_MAP = {
        "BTC": "bitcoin", "ETH": "ethereum", "BNB": "binancecoin",
        "SOL": "solana", "XRP": "ripple", "ADA": "cardano",
        "AVAX": "avalanche-2", "DOT": "polkadot", "LINK": "chainlink",
        "MATIC": "matic-network", "LTC": "litecoin", "UNI": "uniswap",
        "ATOM": "cosmos", "DOGE": "dogecoin", "SHIB": "shiba-inu",
        "OP": "optimism", "ARB": "arbitrum", "SUI": "sui",
        "TRX": "tron", "TON": "the-open-network",
    }

    def __init__(self, config: dict, db):
        self.config = config
        self.db = db

    def get_score(self, symbol: str) -> float:
        cached = self.db.get_sentiment(symbol)
        if cached is not None:
            return cached
        if not self.config.get("use_sentiment"):
            return 0.5
        coin = symbol.replace("/USDT", "").upper()
        cg_id = self.COIN_MAP.get(coin, "")
        if not cg_id:
            return 0.5
        try:
            r = requests.get(
                f"https://api.coingecko.com/api/v3/coins/{cg_id}"
                "?localization=false&tickers=false&market_data=false&community_data=true",
                timeout=8,
            )
            cd = r.json().get("community_data", {})
            sentiment_up = cd.get("sentiment_votes_up_percentage", 50) or 50
            score = float(np.clip(sentiment_up / 100, 0, 1))
            self.db.save_sentiment(symbol, score, "coingecko")
            return score
        except Exception:
            return 0.5

    def get_trending(self) -> list[str]:
        try:
            r = requests.get("https://api.coingecko.com/api/v3/search/trending", timeout=8)
            coins = r.json().get("coins", [])
            return [f"{c['item']['symbol'].upper()}/USDT" for c in coins[:7]]
        except Exception:
            return []


class OnChainFetcher:
    """On-Chain-Daten: Whale-Transfers, Exchange-Flows via CoinGecko."""

    def __init__(self, db):
        self.db = db

    def get_score(self, symbol: str) -> tuple[float, str]:
        cached = self.db.get_onchain(symbol)
        if cached:
            return float(cached["net_score"]), cached["detail"]

        coin = symbol.replace("/USDT", "").lower()
        whale_score = 0.0
        flow_score = 0.0
        detail = "—"

        cg_map = {
            "btc": "bitcoin", "eth": "ethereum", "bnb": "binancecoin",
            "sol": "solana", "xrp": "ripple", "ada": "cardano",
            "dot": "polkadot", "avax": "avalanche-2", "link": "chainlink",
            "matic": "matic-network", "ltc": "litecoin", "uni": "uniswap",
            "atom": "cosmos", "doge": "dogecoin", "shib": "shiba-inu",
            "op": "optimism", "arb": "arbitrum", "sui": "sui",
        }
        try:
            cg_id = cg_map.get(coin, "")
            if cg_id:
                r = requests.get(
                    f"https://api.coingecko.com/api/v3/coins/{cg_id}?localization=false"
                    "&tickers=false&market_data=true&community_data=true&developer_data=true",
                    timeout=8,
                )
                data = r.json()
                md = data.get("market_data", {})
                price_chg = float(md.get("price_change_percentage_24h", 0) or 0)
                vol_ratio = 0.0
                vol_chg = 0.0
                if md.get("total_volume", {}).get("usd") and md.get("market_cap", {}).get("usd"):
                    vol_ratio = md["total_volume"]["usd"] / max(md["market_cap"]["usd"], 1)
                    vol_chg = (vol_ratio - 0.05) * 10
                if price_chg > 2 and vol_chg > 0.5:
                    whale_score = 0.6
                elif price_chg < -2 and vol_chg > 0.5:
                    whale_score = -0.6
                elif price_chg > 1:
                    whale_score = 0.3
                elif price_chg < -1:
                    whale_score = -0.3
                dev = data.get("developer_data", {})
                commits = dev.get("commit_count_4_weeks") or 0
                if commits > 20:
                    flow_score = 0.2
                elif commits > 5:
                    flow_score = 0.1
                detail = f"24h:{price_chg:+.1f}% Vol:{vol_ratio * 100:.1f}% Commits:{commits}"
        except Exception as e:
            log.debug(f"OnChain {symbol}: {e}")

        net = float(np.clip((whale_score + flow_score) / 2, -1, 1))
        self.db.save_onchain(symbol, whale_score, flow_score, detail)
        return net, detail
