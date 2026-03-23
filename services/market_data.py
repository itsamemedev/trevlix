"""TREVLIX – Marktdaten-Services.

Enthält FearGreedIndex, MarketRegime, DominanceFilter,
SentimentFetcher und OnChainFetcher.

Verwendung:
    from services.market_data import FearGreedIndex, MarketRegime, DominanceFilter
"""

import logging
import threading
import time
from datetime import datetime

import numpy as np
import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

log = logging.getLogger("trevlix.market_data")


class _TTLCache:
    """Einfacher Thread-sicherer TTL-Cache für API-Responses.

    Args:
        ttl: Time-to-live in Sekunden.
    """

    def __init__(self, ttl: int = 300) -> None:
        self._ttl = ttl
        self._data: dict[str, tuple[float, object]] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> object | None:
        """Gibt den gecachten Wert zurück oder None bei Ablauf/Miss."""
        with self._lock:
            entry = self._data.get(key)
            if entry and time.monotonic() - entry[0] < self._ttl:
                return entry[1]
            return None

    def set(self, key: str, value: object) -> None:
        """Speichert einen Wert mit aktuellem Timestamp."""
        with self._lock:
            self._data[key] = (time.monotonic(), value)

    def clear(self) -> None:
        """Leert den gesamten Cache."""
        with self._lock:
            self._data.clear()


# ── Shared CoinGecko ID map (previously duplicated in two classes) ────────────
COINGECKO_ID_MAP: dict[str, str] = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "BNB": "binancecoin",
    "SOL": "solana",
    "XRP": "ripple",
    "ADA": "cardano",
    "AVAX": "avalanche-2",
    "DOT": "polkadot",
    "LINK": "chainlink",
    "MATIC": "matic-network",
    "LTC": "litecoin",
    "UNI": "uniswap",
    "ATOM": "cosmos",
    "DOGE": "dogecoin",
    "SHIB": "shiba-inu",
    "OP": "optimism",
    "ARB": "arbitrum",
    "SUI": "sui",
    "TRX": "tron",
    "TON": "the-open-network",
}


def _make_session(retries: int = 2, backoff: float = 0.3) -> requests.Session:
    """Creates a requests.Session with retry logic and a shared User-Agent."""
    session = requests.Session()
    retry = Retry(
        total=retries,
        backoff_factor=backoff,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update({"User-Agent": "TREVLIX/1.4 market-data-client"})
    return session


# Module-level session (thread-safe for reads, one session per process)
_session = _make_session()


class FearGreedIndex:
    """Fear & Greed Index von alternative.me mit TTL-Cache."""

    _URL = "https://api.alternative.me/fng/?limit=1"
    _cache = _TTLCache(ttl=300)  # 5 Minuten Cache

    def __init__(self, config: dict):
        self.config = config
        self.value = 50
        self.label = "Neutral"
        self.last_update: str | None = None

    def update(self) -> None:
        """Aktualisiert den Fear & Greed Index (mit 5-Min-Cache)."""
        if not self.config.get("use_fear_greed"):
            return
        cached = self._cache.get("fng")
        if cached is not None:
            self.value, self.label = cached
            log.debug("FearGreed: Cache-Hit")
            return
        try:
            r = _session.get(self._URL, timeout=8)
            r.raise_for_status()
            data_list = r.json().get("data", [])
            if not data_list:
                log.debug("FearGreed: leere API-Antwort")
                return
            d = data_list[0]
            try:
                raw_value = int(d.get("value", 50))
            except (ValueError, TypeError):
                log.debug("FearGreed: ungültiger Wert '%s'", d.get("value"))
                return
            self.value = max(0, min(100, raw_value))  # Clamp to [0, 100]
            self.label = d.get("value_classification", "Neutral")
            self.last_update = datetime.now().strftime("%H:%M")
            self._cache.set("fng", (self.value, self.label))
        except requests.HTTPError as e:
            log.debug(f"FearGreed HTTP error: {e}")
        except Exception as e:
            log.debug(f"FearGreed: {e}")

    def is_ok_to_buy(self) -> bool:
        if not self.config.get("use_fear_greed"):
            return True
        return self.value <= self.config.get("fg_buy_max", 80)

    def buy_boost(self) -> float:
        if not self.config.get("use_fear_greed"):
            return 1.0
        return 1.3 if self.value < self.config.get("fg_sell_min", 25) else 1.0

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
        self.last_update: str | None = None

    def update(self, ex) -> None:
        try:
            ohlcv = ex.fetch_ohlcv("BTC/USDT", self.config.get("btc_regime_tf", "4h"), limit=200)
            df = pd.DataFrame(ohlcv, columns=["ts", "o", "h", "l", "close", "v"])
            c = df["close"]
            if len(c) == 0:
                return
            e50 = c.ewm(span=50, adjust=False).mean().iloc[-1]
            e200 = c.ewm(span=200, adjust=False).mean().iloc[-1] if len(c) >= 200 else e50
            cur = float(c.iloc[-1])
            self.btc_price = cur
            self.is_bull = cur > e50 and e50 > e200 * 0.98
            self.last_update = datetime.now().strftime("%H:%M:%S")
        except Exception as e:
            log.debug(f"MarketRegime update: {e}")


class DominanceFilter:
    """BTC/USDT-Dominanz-Filter für Altcoin-Käufe mit TTL-Cache."""

    _URL = "https://api.coingecko.com/api/v3/global"
    _cache = _TTLCache(ttl=300)  # 5 Minuten Cache

    def __init__(self, config: dict):
        self.config = config
        self.btc_dom = 50.0
        self.usdt_dom = 6.0
        self.last_update: str | None = None
        self._lock = threading.Lock()

    def update(self) -> None:
        """Aktualisiert BTC/USDT-Dominanz (mit 5-Min-Cache)."""
        if not self.config.get("use_dominance"):
            return
        cached = self._cache.get("dominance")
        if cached is not None:
            with self._lock:
                self.btc_dom, self.usdt_dom = cached
            log.debug("Dominanz: Cache-Hit")
            return
        try:
            r = _session.get(self._URL, timeout=8)
            r.raise_for_status()
            data = r.json().get("data", {})
            mcp = data.get("market_cap_percentage", {})
            with self._lock:
                try:
                    self.btc_dom = max(0.0, min(100.0, float(mcp.get("btc", 50))))
                except (ValueError, TypeError):
                    self.btc_dom = 50.0
                try:
                    self.usdt_dom = max(0.0, min(100.0, float(mcp.get("usdt", 6))))
                except (ValueError, TypeError):
                    self.usdt_dom = 6.0
                self.last_update = datetime.now().strftime("%H:%M")
            self._cache.set("dominance", (self.btc_dom, self.usdt_dom))
            log.info(f"Dominanz: BTC={self.btc_dom:.1f}% USDT={self.usdt_dom:.1f}%")
        except requests.HTTPError as e:
            log.debug(f"Dominanz HTTP error: {e}")
        except Exception as e:
            log.debug(f"Dominanz: {e}")

    def is_ok_to_buy(self, symbol: str) -> tuple[bool, str]:
        if not self.config.get("use_dominance"):
            return True, "Dominanz-Filter deaktiv"
        with self._lock:
            usdt_max = self.config.get("usdt_dom_max", 12.0)
            btc_max = self.config.get("btc_dom_max", 40.0)
            if self.usdt_dom > usdt_max:
                return (
                    False,
                    f"USDT-Dominanz {self.usdt_dom:.1f}% > {usdt_max}% → Markt flüchtet",
                )
            if symbol not in ("BTC/USDT", "ETH/USDT") and self.btc_dom > btc_max:
                return False, f"BTC-Dominanz {self.btc_dom:.1f}% → Altcoin-Käufe blockiert"
            return True, f"BTC:{self.btc_dom:.0f}% USDT:{self.usdt_dom:.0f}%"

    def to_dict(self) -> dict:
        with self._lock:
            return {
                "btc_dom": round(self.btc_dom, 1),
                "usdt_dom": round(self.usdt_dom, 1),
                "last_update": self.last_update,
                "ok_btc": self.btc_dom <= self.config.get("btc_dom_max", 40.0),
                "ok_usdt": self.usdt_dom <= self.config.get("usdt_dom_max", 12.0),
            }


class SentimentFetcher:
    """CoinGecko Community-Sentiment als Trading-Signal."""

    # Uses the module-level COINGECKO_ID_MAP — no duplicate definition needed.

    def __init__(self, config: dict, db):
        self.config = config
        self.db = db

    def get_score(self, symbol: str) -> float:
        if not self.config.get("use_sentiment"):
            return 0.5
        cached = self.db.get_sentiment(symbol)
        if cached is not None:
            return cached
        coin = symbol.replace("/USDT", "").upper()
        cg_id = COINGECKO_ID_MAP.get(coin, "")
        if not cg_id:
            return 0.5
        try:
            url = (
                f"https://api.coingecko.com/api/v3/coins/{cg_id}"
                "?localization=false&tickers=false&market_data=false&community_data=true"
            )
            r = _session.get(url, timeout=8)
            r.raise_for_status()
            cd = r.json().get("community_data", {})
            raw = cd.get("sentiment_votes_up_percentage")
            sentiment_up = float(raw) if isinstance(raw, (int, float)) else 50.0
            score = float(np.clip(sentiment_up / 100, 0, 1))
            self.db.save_sentiment(symbol, score, "coingecko")
            return score
        except requests.HTTPError as e:
            log.debug(f"Sentiment HTTP error for {symbol}: {e}")
            return 0.5
        except Exception as e:
            log.debug(f"Sentiment {symbol}: {e}")
            return 0.5

    def get_trending(self) -> list[str]:
        try:
            r = _session.get("https://api.coingecko.com/api/v3/search/trending", timeout=8)
            r.raise_for_status()
            coins = r.json().get("coins", [])
            return [
                f"{c.get('item', {}).get('symbol', '').upper()}/USDT"
                for c in coins[:7]
                if c.get("item", {}).get("symbol")
            ]
        except Exception as e:
            log.debug(f"Trending: {e}")
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

        # Uses the module-level COINGECKO_ID_MAP (lowercased keys)
        cg_id = COINGECKO_ID_MAP.get(coin.upper(), "")
        if not cg_id:
            net = float(np.clip((whale_score + flow_score) / 2, -1, 1))
            return net, detail

        try:
            url = (
                f"https://api.coingecko.com/api/v3/coins/{cg_id}"
                "?localization=false&tickers=false"
                "&market_data=true&community_data=true&developer_data=true"
            )
            r = _session.get(url, timeout=8)
            r.raise_for_status()
            data = r.json()
            md = data.get("market_data", {})
            price_chg = float(md.get("price_change_percentage_24h", 0) or 0)

            vol_chg = 0.0
            raw_vol = md.get("total_volume")
            total_vol = (
                float(raw_vol.get("usd", 0) or 0)
                if isinstance(raw_vol, dict)
                else float(raw_vol or 0)
            )
            raw_cap = md.get("market_cap")
            market_cap = (
                float(raw_cap.get("usd", 0) or 0)
                if isinstance(raw_cap, dict)
                else float(raw_cap or 0)
            )
            if total_vol and market_cap:
                vol_ratio = total_vol / max(market_cap, 1)
                vol_chg = (vol_ratio - 0.05) * 10
            else:
                vol_ratio = 0.0

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
        except requests.HTTPError as e:
            log.debug(f"OnChain HTTP error {symbol}: {e}")
        except Exception as e:
            log.debug(f"OnChain {symbol}: {e}")

        net = float(np.clip((whale_score + flow_score) / 2, -1, 1))
        self.db.save_onchain(symbol, whale_score, flow_score, detail)
        return net, detail
