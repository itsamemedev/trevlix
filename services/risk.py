"""TREVLIX – Risk Management Services.

Extrahiert aus server.py für bessere Modularisierung.
Enthält RiskManager, LiquidityScorer, SymbolCooldown,
FundingRateTracker und AdvancedRiskMetrics.

Verwendung:
    from services.risk import RiskManager, LiquidityScorer, SymbolCooldown
"""

import logging
import math
import threading
from datetime import datetime, timedelta

import httpx
import numpy as np

log = logging.getLogger("trevlix.risk")


class RiskManager:
    """Zentrales Risikomanagement mit Circuit Breaker und Korrelationsfilter."""

    def __init__(self, config: dict, discord=None):
        self.config = config
        self.discord = discord
        self._lock = threading.Lock()
        self.daily_start = config.get("paper_balance", 10000.0)
        self.daily_pnl = 0.0
        self.peak = config.get("paper_balance", 10000.0)
        self.max_drawdown = 0.0
        self.consecutive_losses = 0
        self.circuit_breaker_until = None
        self._price_history: dict[str, list[float]] = {}
        self._day = datetime.now().date()

    def reset_daily(self, balance: float) -> None:
        """Setzt die täglichen PnL-Werte zurück bei Tageswechsel.

        Args:
            balance: Aktueller Kontostand.
        """
        with self._lock:
            today = datetime.now().date()
            if today != self._day:
                self.daily_start = balance
                self.daily_pnl = 0.0
                self._day = today

    def update_peak(self, pv: float) -> None:
        """Aktualisiert den Portfolio-Höchststand und Drawdown.

        Args:
            pv: Aktueller Portfolio-Wert.
        """
        with self._lock:
            if pv > self.peak:
                self.peak = pv
            dd = (self.peak - pv) / self.peak * 100 if self.peak > 0 else 0
            if dd > self.max_drawdown:
                self.max_drawdown = dd

    def daily_loss_exceeded(self, balance) -> bool:
        with self._lock:
            self._reset_daily_unlocked(balance)
            return (
                (self.daily_start - balance) / self.daily_start
                > self.config.get("max_daily_loss_pct", 0.05)
                if self.daily_start > 0
                else False
            )

    def _reset_daily_unlocked(self, balance):
        """Internes Reset ohne Lock (muss unter self._lock aufgerufen werden)."""
        today = datetime.now().date()
        if today != self._day:
            self.daily_start = balance
            self.daily_pnl = 0.0
            self._day = today

    def circuit_breaker_active(self) -> bool:
        with self._lock:
            return self._circuit_breaker_active_unlocked()

    def drawdown_breaker_active(self, current_balance: float) -> bool:
        with self._lock:
            max_dd_pct = self.config.get("max_drawdown_pct", 0.10)
            if self.peak <= 0:
                return False
            current_dd = (self.peak - current_balance) / self.peak
            if current_dd > max_dd_pct:
                if not self.circuit_breaker_until:
                    mins = self.config.get("circuit_breaker_min", 30) * 2
                    self.circuit_breaker_until = datetime.now() + timedelta(minutes=mins)
                    log.warning(
                        f"Drawdown Circuit Breaker: {current_dd * 100:.1f}% > {max_dd_pct * 100:.0f}%"
                    )
                    if self.discord:
                        self.discord.circuit_breaker(0, mins)
                return True
            return False

    def record_result(self, won: bool):
        with self._lock:
            if won:
                self.consecutive_losses = 0
            else:
                self.consecutive_losses += 1
                if self.consecutive_losses >= self.config.get("circuit_breaker_losses", 3):
                    mins = self.config.get("circuit_breaker_min", 30)
                    self.circuit_breaker_until = datetime.now() + timedelta(minutes=mins)
                    if self.discord:
                        self.discord.circuit_breaker(self.consecutive_losses, mins)

    def is_correlated(self, symbol: str, open_syms: list[str]) -> bool:
        if not open_syms or self.config.get("max_corr", 0.75) >= 1.0:
            return False
        with self._lock:
            h1 = list(self._price_history.get(symbol, []))
            histories = {s: list(self._price_history.get(s, [])) for s in open_syms if s != symbol}
        if len(h1) < 20:
            return False
        for s, h2 in histories.items():
            if len(h2) < 20:
                continue
            n = min(len(h1), len(h2), 100)
            r1 = np.diff(h1[-n:])
            r2 = np.diff(h2[-n:])
            if len(r1) > 3 and len(r1) == len(r2):
                try:
                    corr = abs(float(np.corrcoef(r1, r2)[0, 1]))
                    if corr != corr:  # NaN check (identical price series)
                        continue
                    max_corr = self.config.get("max_corr", 0.75)
                    if corr > max_corr:
                        log.info(f"Korrelations-Block: {symbol}<->{s} corr={corr:.2f} > {max_corr}")
                        return True
                except (ValueError, TypeError, IndexError):
                    pass
        return False

    def update_prices(self, symbol: str, price: float) -> None:
        """Speichert den aktuellen Preis für Korrelationsberechnung.

        Args:
            symbol: Trading-Pair (z.B. 'BTC/USDT').
            price: Aktueller Preis.
        """
        with self._lock:
            h = self._price_history.setdefault(symbol, [])
            h.append(price)
            if len(h) > 100:
                self._price_history[symbol] = h[-100:]

    def circuit_status(self) -> dict:
        with self._lock:
            active = self._circuit_breaker_active_unlocked()
            remaining = 0
            if active and self.circuit_breaker_until:
                remaining = max(
                    0, int((self.circuit_breaker_until - datetime.now()).total_seconds() / 60)
                )
            return {
                "active": active,
                "losses": self.consecutive_losses,
                "limit": self.config.get("circuit_breaker_losses", 3),
                "remaining_min": remaining,
                "until": self.circuit_breaker_until.strftime("%H:%M")
                if self.circuit_breaker_until
                else None,
            }

    def _circuit_breaker_active_unlocked(self) -> bool:
        """Interner Check ohne Lock (muss unter self._lock aufgerufen werden)."""
        if self.circuit_breaker_until and datetime.now() < self.circuit_breaker_until:
            return True
        if self.circuit_breaker_until and datetime.now() >= self.circuit_breaker_until:
            self.circuit_breaker_until = None
            self.consecutive_losses = 0
        return False

    def sharpe(self, returns, rf=0.0) -> float:
        if len(returns) < 3:
            return 0.0
        r = np.array(returns, dtype=float)
        exc = r - rf
        std = np.nanstd(exc)
        return float(np.nanmean(exc) / std * np.sqrt(252)) if std > 0 else 0.0


class LiquidityScorer:
    """Prüft Liquidität via Orderbook Spread."""

    def __init__(self, config: dict):
        self.config = config

    def check(self, ex, symbol) -> tuple[bool, float, str]:
        try:
            ob = ex.fetch_order_book(symbol, limit=5)
            if not ob["bids"] or not ob["asks"]:
                return False, 0.0, "Kein Orderbook"
            bid = ob["bids"][0][0]
            ask = ob["asks"][0][0]
            mid = (bid + ask) / 2
            if mid <= 0:
                return False, 0.0, "Ungültige Preise (mid=0)"
            spread = (ask - bid) / mid * 100
            max_spread = self.config.get("max_spread_pct", 0.5)
            if spread > max_spread:
                return (
                    False,
                    round(spread, 3),
                    f"Spread {spread:.3f}%>{max_spread}%",
                )
            return True, round(spread, 3), "OK"
        except Exception as e:
            return True, 0.0, f"LQ:{e}"


class SymbolCooldown:
    """Verhindert Re-Entry in dasselbe Symbol direkt nach einem Verlust-Trade."""

    def __init__(self, config: dict):
        self.config = config
        self._cooldowns: dict[str, datetime] = {}
        self._lock = threading.Lock()

    def set_cooldown(self, symbol: str, minutes: int | None = None):
        mins = minutes or self.config.get("cooldown_minutes", 60)
        until = datetime.now() + timedelta(minutes=mins)
        with self._lock:
            self._cooldowns[symbol] = until
        log.debug(f"[COOLDOWN] {symbol} gesperrt bis {until.strftime('%H:%M')}")

    def is_blocked(self, symbol: str) -> bool:
        with self._lock:
            until = self._cooldowns.get(symbol)
            if until and datetime.now() < until:
                return True
            if until:
                del self._cooldowns[symbol]
            return False

    def status(self) -> dict:
        now = datetime.now()
        with self._lock:
            return {
                sym: {
                    "until": until.strftime("%H:%M:%S"),
                    "remaining_min": round((until - now).total_seconds() / 60, 1),
                }
                for sym, until in self._cooldowns.items()
                if until > now
            }


class FundingRateTracker:
    """Ruft Perpetual Funding Rates von Bybit ab und filtert teure Shorts."""

    def __init__(self, config: dict):
        self.config = config
        self._rates: dict[str, float] = {}
        self._last_update: datetime | None = None
        self._lock = threading.Lock()

    def update(self, ex=None):
        with self._lock:
            if self._last_update and (datetime.now() - self._last_update).total_seconds() < 900:
                return
        try:
            url = "https://api.bybit.com/v5/market/tickers?category=linear"
            resp = httpx.get(url, timeout=8)
            resp.raise_for_status()
            data = resp.json().get("result", {}).get("list", [])
            with self._lock:
                for item in data:
                    sym = item.get("symbol", "")
                    fr = item.get("fundingRate", "0")
                    if sym.endswith("USDT"):
                        base = sym.replace("USDT", "") + "/USDT"
                        try:
                            self._rates[base] = float(fr)
                        except (ValueError, TypeError):
                            log.debug("Ungültige Funding-Rate für %s: %s", base, fr)
            self._last_update = datetime.now()
            log.debug(f"[FUNDING] {len(self._rates)} Rates geladen")
        except Exception as e:
            log.debug(f"[FUNDING] Update: {e}")

    def get_rate(self, symbol: str) -> float | None:
        with self._lock:
            return self._rates.get(symbol)

    def is_short_too_expensive(self, symbol: str) -> bool:
        if not self.config.get("funding_rate_filter"):
            return False
        rate = self.get_rate(symbol)
        if rate is None:
            return False
        max_rate = self.config.get("funding_rate_max", 0.001)
        return rate > max_rate

    def top_rates(self, n: int = 10) -> list:
        with self._lock:
            sorted_rates = sorted(self._rates.items(), key=lambda x: abs(x[1]), reverse=True)[:n]
        return [
            {"symbol": s, "rate": round(r * 100, 4), "rate_8h_pct": round(r * 100, 4)}
            for s, r in sorted_rates
        ]

    def status(self) -> dict:
        return {
            "count": len(self._rates),
            "last_update": self._last_update.isoformat() if self._last_update else None,
            "filter_enabled": self.config.get("funding_rate_filter"),
            "max_rate": self.config.get("funding_rate_max"),
        }


class AdvancedRiskMetrics:
    """CVaR, EWMA-Volatilität und erweiterte Risikometriken."""

    def __init__(self):
        self._lock = threading.Lock()
        self._vol_history: list[float] = []
        self._ewma_vol: float = 0.02
        self._lambda: float = 0.94

    def compute_cvar(self, closed_trades: list, confidence: float = 0.95) -> dict:
        if len(closed_trades) < 10:
            return {"var": 0, "cvar": 0, "es": 0, "n": 0}
        pnl_arr = np.array([t.get("pnl", 0) for t in closed_trades])
        var_threshold = np.percentile(pnl_arr, (1 - confidence) * 100)
        tail_losses = pnl_arr[pnl_arr <= var_threshold]
        cvar = float(np.mean(tail_losses)) if len(tail_losses) > 0 else float(var_threshold)
        return {
            "var": round(float(var_threshold), 2),
            "cvar": round(cvar, 2),
            "es": round(abs(cvar), 2),
            "n_tail": len(tail_losses),
            "confidence": confidence,
            "worst_loss": round(float(pnl_arr.min()), 2),
            "avg_loss": round(float(pnl_arr[pnl_arr < 0].mean()) if any(pnl_arr < 0) else 0, 2),
        }

    def update_volatility(self, price: float) -> float:
        with self._lock:
            self._vol_history.append(price)
            if len(self._vol_history) > 200:
                self._vol_history = self._vol_history[-200:]
            if len(self._vol_history) < 5:
                return self._ewma_vol
            prices = np.array(self._vol_history[-30:])
            returns = np.diff(np.log(prices + 1e-9))
            if len(returns) > 0:
                r2 = float(returns[-1] ** 2)
                variance = self._lambda * self._ewma_vol**2 + (1 - self._lambda) * r2
                self._ewma_vol = math.sqrt(max(0.0, variance))
            return self._ewma_vol

    def volatility_forecast(self, horizon: int = 5) -> dict:
        """Prognostiziert Volatilität über n Perioden (EWMA mean-reversion)."""
        lt_avg = 0.02  # Langzeit-Volatilität Annahme
        forecasts = []
        with self._lock:
            vol = self._ewma_vol
            current_vol = self._ewma_vol
        for _h in range(1, horizon + 1):
            # Mean-Reversion: Vol zieht zurück zum LT-Durchschnitt
            vol = vol + 0.1 * (lt_avg - vol)
            forecasts.append(round(vol * 100, 3))
        return {
            "current_vol_pct": round(current_vol * 100, 3),
            "forecast_horizon": horizon,
            "forecasts_pct": forecasts,
            "risk_level": "HOCH"
            if current_vol > 0.04
            else "MITTEL"
            if current_vol > 0.02
            else "NIEDRIG",
        }

    def classify_regime(self, prices: list, volumes: list = None) -> str:
        """Klassifiziert Marktregime in 4 Zustände:
        - TREND_UP:   Starker Aufwärtstrend
        - TREND_DOWN: Starker Abwärtstrend
        - RANGE:      Seitwärtsbewegung
        - CRASH:      Schneller Absturz (>5% in kurzer Zeit)
        - UNKNOWN:    Zu wenig Daten (<20 Preispunkte)
        """
        if len(prices) < 20:
            return "UNKNOWN"
        pa = np.array(prices[-50:])
        sma_short = float(np.mean(pa[-10:]))
        sma_long = float(np.mean(pa[-30:]) if len(pa) >= 30 else np.mean(pa))
        trend_pct = (sma_short - sma_long) / (sma_long + 1e-9)
        vol = float(np.std(pa[-20:]) / (np.mean(pa[-20:]) + 1e-9))
        recent_peak = float(np.max(pa[-10:]))
        current = float(pa[-1])
        drawdown = (recent_peak - current) / (recent_peak + 1e-9)
        if drawdown > 0.05:
            return "CRASH"
        elif trend_pct > 0.02 and vol < 0.04:
            return "TREND_UP"
        elif trend_pct < -0.02 and vol < 0.04:
            return "TREND_DOWN"
        else:
            return "RANGE"

    def conformal_predict(
        self, model, X_cal: np.ndarray, y_cal: np.ndarray, X_test: np.ndarray, alpha: float = 0.1
    ) -> dict:
        """Conformal Prediction: Liefert garantierte Vorhersage-Intervalle."""
        if model is None or len(X_cal) < 10 or len(X_test) == 0:
            return {"lower": 0.3, "upper": 0.7, "coverage": 0.9, "method": "fallback"}
        try:
            proba_out = model.predict_proba(X_cal)
            if proba_out.shape[1] < 2:
                return {"lower": 0.3, "upper": 0.7, "coverage": 0.9, "method": "fallback"}
            probs = proba_out[:, 1]
            scores = np.abs(probs - y_cal)
            q_level = math.ceil((len(scores) + 1) * (1 - alpha)) / len(scores)
            q_level = min(q_level, 1.0)
            q_hat = float(np.quantile(scores, q_level))
            test_prob = float(model.predict_proba(X_test)[:, 1][0])
            lower = max(0.0, test_prob - q_hat)
            upper = min(1.0, test_prob + q_hat)
            return {
                "prediction": round(test_prob, 3),
                "lower": round(lower, 3),
                "upper": round(upper, 3),
                "width": round(upper - lower, 3),
                "q_hat": round(q_hat, 3),
                "coverage": round(1 - alpha, 2),
            }
        except Exception as e:
            log.debug(f"[CONFORMAL] {e}")
            return {"lower": 0.3, "upper": 0.7, "coverage": 0.9, "method": "error"}
