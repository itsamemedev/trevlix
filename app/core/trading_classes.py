"""Trading helper classes extracted from server.py.

Includes: MultiTimeframeFilter, OrderbookImbalance, PriceAlertManager,
DailyReportScheduler, BackupScheduler, BotState, ArbitrageScanner, ShortEngine.

Module-level globals are injected at startup via init_trading_classes().
"""

from __future__ import annotations

import threading
import time
from collections import deque
from datetime import datetime, timedelta
from typing import Any

import numpy as np

from services.exchange_factory import create_ccxt_exchange

# ---------------------------------------------------------------------------
# Module-level references – populated by init_trading_classes()
# ---------------------------------------------------------------------------
CONFIG: dict = {}
log = None
db = None
state = None
discord = None
emit_event = None
ai_engine = None
dominance = None
arb_scanner = None
_SHUTDOWN_EVENT = None
risk = None
revenue_tracker = None
get_exchange_fee_rate = None
_reveal_and_decrypt = None

# BotState snapshot references
BOT_NAME: str = ""
BOT_VERSION: str = ""
BOT_FULL: str = ""
regime = None
fg_idx = None
anomaly = None
genetic = None
rl_agent = None
trade_dna = None
smart_exits = None
adaptive_weights = None
perf_attribution = None
trading_algos = None
_get_exchange_key_states = None
telegram = None


def init_trading_classes(
    *,
    config: dict,
    logger,
    db_ref,
    state_ref=None,
    discord_ref=None,
    emit_event_fn=None,
    ai_engine_ref=None,
    dominance_ref=None,
    arb_scanner_ref=None,
    shutdown_event=None,
    risk_ref=None,
    revenue_tracker_ref=None,
    get_exchange_fee_rate_fn=None,
    reveal_and_decrypt_fn=None,
    bot_name: str = "",
    bot_version: str = "",
    bot_full: str = "",
    regime_ref=None,
    fg_idx_ref=None,
    anomaly_ref=None,
    genetic_ref=None,
    rl_agent_ref=None,
    trade_dna_ref=None,
    smart_exits_ref=None,
    adaptive_weights_ref=None,
    perf_attribution_ref=None,
    trading_algos_ref=None,
    get_exchange_key_states_fn=None,
    telegram_ref=None,
) -> None:
    """Inject runtime dependencies into this module's globals."""
    global CONFIG, log, db, state, discord, emit_event, ai_engine
    global dominance, arb_scanner, _SHUTDOWN_EVENT, risk, revenue_tracker
    global get_exchange_fee_rate, _reveal_and_decrypt
    global BOT_NAME, BOT_VERSION, BOT_FULL, regime, fg_idx, anomaly
    global genetic, rl_agent, trade_dna, smart_exits, adaptive_weights
    global perf_attribution, trading_algos, _get_exchange_key_states, telegram
    CONFIG = config
    log = logger
    db = db_ref
    state = state_ref
    discord = discord_ref
    emit_event = emit_event_fn
    ai_engine = ai_engine_ref
    dominance = dominance_ref
    arb_scanner = arb_scanner_ref
    _SHUTDOWN_EVENT = shutdown_event
    risk = risk_ref
    revenue_tracker = revenue_tracker_ref
    get_exchange_fee_rate = get_exchange_fee_rate_fn
    _reveal_and_decrypt = reveal_and_decrypt_fn
    BOT_NAME = bot_name
    BOT_VERSION = bot_version
    BOT_FULL = bot_full
    regime = regime_ref
    fg_idx = fg_idx_ref
    anomaly = anomaly_ref
    genetic = genetic_ref
    rl_agent = rl_agent_ref
    trade_dna = trade_dna_ref
    smart_exits = smart_exits_ref
    adaptive_weights = adaptive_weights_ref
    perf_attribution = perf_attribution_ref
    trading_algos = trading_algos_ref
    _get_exchange_key_states = get_exchange_key_states_fn
    telegram = telegram_ref


class MultiTimeframeFilter:
    _MAX_CACHE = 500

    def __init__(self):
        self._cache: dict[str, dict] = {}
        self._lock = threading.Lock()

    def is_confirmed(self, ex, symbol, signal) -> tuple[bool, str]:
        if not CONFIG.get("mtf_enabled") or signal != 1:
            return True, "MTF deaktiv"
        with self._lock:
            c = self._cache.get(symbol)
            if c and (datetime.now() - c["ts"]).total_seconds() < 240:
                ok = c["trend"] >= 0
                return ok, f"{'✅' if ok else '❌'} 4h cached"
        try:
            ohlcv = ex.fetch_ohlcv(symbol, CONFIG["mtf_confirm_tf"], limit=60)
            if not ohlcv or len(ohlcv) < 30:
                return True, "MTF: wenig Daten"
            df = pd.DataFrame(ohlcv, columns=["ts", "o", "h", "l", "close", "v"])
            c2 = df["close"]
            e21 = float(c2.ewm(span=21, adjust=False).mean().iloc[-1])
            e50 = float(c2.ewm(span=50, adjust=False).mean().iloc[-1])
            price = float(c2.iloc[-1])
            d = c2.diff()
            g = d.clip(lower=0).ewm(span=14, adjust=False).mean()
            ls = (-d.clip(upper=0)).ewm(span=14, adjust=False).mean()
            rsi_raw = (100 - (100 / (1 + g / ls.replace(0, 1e-10)))).iloc[-1]
            rsi = float(rsi_raw) if not np.isnan(rsi_raw) else 50.0
            score = (1 if price > e21 else 0) + (1 if e21 > e50 else 0) + (1 if rsi > 45 else 0)
            trend = 1 if score >= 2 else (-1 if score == 0 else 0)
            with self._lock:
                self._cache[symbol] = {"trend": trend, "ts": datetime.now()}
                # Evict stale entries if cache grows too large
                if len(self._cache) > self._MAX_CACHE:
                    cutoff = datetime.now() - timedelta(minutes=10)
                    stale = [k for k, v in self._cache.items() if v["ts"] < cutoff]
                    for k in stale:
                        del self._cache[k]
                    # If still over limit after stale eviction, drop oldest entries
                    if len(self._cache) > self._MAX_CACHE:
                        by_age = sorted(self._cache, key=lambda k: self._cache[k]["ts"])
                        for k in by_age[: len(self._cache) - self._MAX_CACHE]:
                            del self._cache[k]
            ok = trend >= 0
            return ok, f"{'✅' if ok else '❌'} 4h RSI:{rsi:.0f}"
        except Exception as e:
            return True, f"MTF Err:{e}"


# ═══════════════════════════════════════════════════════════════════════════════
# ORDERBOOK IMBALANCE
# ═══════════════════════════════════════════════════════════════════════════════
class OrderbookImbalance:
    def get(self, ex, symbol) -> tuple[float, str]:
        try:
            ob = ex.fetch_order_book(symbol, limit=20)
            if not ob.get("bids") or not ob.get("asks"):
                return 0.5, "Leer"
            bid_vol = sum(b[1] * b[0] for b in ob["bids"][:10])
            ask_vol = sum(a[1] * a[0] for a in ob["asks"][:10])
            total = bid_vol + ask_vol
            if total == 0:
                return 0.5, "Leer"
            ratio = bid_vol / total
            desc = (
                "💪 Kaufdruck"
                if ratio > 0.65
                else "⬇️ Verkaufsdruck"
                if ratio < 0.35
                else "⚖️ Ausgeglichen"
            ) + f" {ratio:.0%}"
            return round(ratio, 3), desc
        except Exception as e:
            return 0.5, f"OB:{e}"


# ═══════════════════════════════════════════════════════════════════════════════
# STEUER (modularisiert → services/tax_report.py)
# ═══════════════════════════════════════════════════════════════════════════════

# MarketRegime importiert aus services.market_data


# RiskManager importiert aus services.risk


# LiquidityScorer importiert aus services.risk


# SentimentFetcher importiert aus services.market_data


# ═══════════════════════════════════════════════════════════════════════════════
# PRICE ALERT MANAGER
# ═══════════════════════════════════════════════════════════════════════════════
class PriceAlertManager:
    def check(self, prices: dict[str, float]):
        alerts = db.get_active_alerts()
        for a in alerts:
            sym = a.get("symbol", "")
            if not sym:
                continue
            price = prices.get(sym)
            if price is None:
                continue
            raw_target = a.get("target_price")
            if raw_target is None:
                continue
            target = safe_float(raw_target, None)
            if target is None:
                continue
            direction = a.get("direction", "above")
            triggered = (direction == "above" and price >= target) or (
                direction == "below" and price <= target
            )
            if triggered:
                db.trigger_alert(a.get("id", 0))
                discord.price_alert(sym, price, target, direction)
                emit_event(
                    "price_alert",
                    {"symbol": sym, "price": price, "target": target, "direction": direction},
                )
                log.info(f"🔔 Alert: {sym} {direction} {target} (aktuell: {price})")


# ═══════════════════════════════════════════════════════════════════════════════
# DAILY REPORT SCHEDULER
# ═══════════════════════════════════════════════════════════════════════════════
class DailyReportScheduler:
    def run(self):
        while not _SHUTDOWN_EVENT.is_set():
            if _SHUTDOWN_EVENT.wait(60):
                return
            now = datetime.now()
            if now.hour == CONFIG.get("discord_report_hour", 20) and now.minute < 5:
                if not db.report_sent_today():
                    self._send_report()
            # Dominanz-Update stündlich
            if now.minute == 0:
                threading.Thread(target=dominance.update, daemon=True).start()

    def _send_report(self):
        try:
            today = datetime.now().strftime("%Y-%m-%d")
            trades_today = [
                t for t in state.closed_trades if str(t.get("closed", ""))[:10] == today
            ]
            daily_pnl = sum(t.get("pnl", 0) for t in trades_today)
            pv = state.portfolio_value()
            win_rate = (
                (sum(1 for t in trades_today if t.get("pnl", 0) > 0) / len(trades_today) * 100)
                if trades_today
                else 0
            )
            # Best/worst coin
            coin_pnl: dict[str, float] = {}
            for t in trades_today:
                coin_pnl[t.get("symbol", "?")] = coin_pnl.get(t.get("symbol", "?"), 0) + t.get(
                    "pnl", 0
                )
            best = max(coin_pnl, key=coin_pnl.get, default="—") if coin_pnl else "—"
            worst = min(coin_pnl, key=coin_pnl.get, default="—") if coin_pnl else "—"
            ai_acc = ai_engine.wf_accuracy * 100
            arb_count = getattr(arb_scanner, "found_today", 0)
            report = {
                "date": today,
                "summary": {
                    "daily_pnl": round(daily_pnl, 2),
                    "trades_today": len(trades_today),
                    "win_rate": round(win_rate, 1),
                    "portfolio_value": round(pv, 2),
                    "return_pct": round(state.return_pct(), 2),
                    "best_coin": best,
                    "worst_coin": worst,
                    "ai_acc": round(ai_acc, 1),
                    "arb_found": arb_count,
                },
            }
            discord.daily_report(report)
            db.save_daily_report(today, report)
            log.info(f"📊 Tages-Report gesendet: PnL={daily_pnl:+.2f}")
        except Exception as e:
            log.error(f"Report: {e}")


# ═══════════════════════════════════════════════════════════════════════════════
# BACKUP SCHEDULER
# ═══════════════════════════════════════════════════════════════════════════════
class BackupScheduler:
    def run(self):
        while not _SHUTDOWN_EVENT.is_set():
            if _SHUTDOWN_EVENT.wait(60):
                return
            now = datetime.now()
            if now.hour == 3 and now.minute < 5 and CONFIG.get("backup_enabled"):
                path = db.backup()
                if path:
                    discord.backup_done(path)


# ═══════════════════════════════════════════════════════════════════════════════
# BOT STATE (Multi-User aware)
# ═══════════════════════════════════════════════════════════════════════════════
class BotState:
    def __init__(self, db_ref):
        self.db = db_ref
        self._lock = threading.RLock()  # [Verbesserung #4] Thread-Safety
        self.running = False
        self.paused = False
        self.balance = CONFIG.get("paper_balance", 10000)
        self.initial_balance = CONFIG.get("paper_balance", 10000)
        self.positions: dict[str, dict] = {}
        self.short_positions: dict[str, dict] = {}
        self.prices: dict[str, float] = {}
        self.closed_trades: list[dict] = []
        self.markets: list[str] = []
        # [Verbesserung #4] deque statt list – thread-safe + automatische Begrenzung
        self.portfolio_history: deque = deque(maxlen=500)
        self.signal_log: deque = deque(maxlen=50)
        self.activity_log: deque = deque(maxlen=50)
        self.arb_log: deque = deque(maxlen=20)
        self.iteration = 0
        self.last_scan = "—"
        self.next_scan = "—"
        self._start_time = time.time()  # für Uptime-Berechnung in /api/v1/status
        self._exchange_reset = False  # Signal: Exchange-Instanz neu erstellen
        self._load_trades()

    def _load_trades(self):
        try:
            t = self.db.load_trades(limit=500)
            if t:
                with self._lock:
                    self.closed_trades = t
                log.info(f"📂 {len(t)} Trades aus DB")
        except Exception as e:
            log.debug(f"Load trades: {e}")

    def portfolio_value(self):
        with self._lock:
            pos_copy = dict(self.positions)
            short_copy = dict(self.short_positions)
            prices_copy = dict(self.prices)
        longs = sum(
            p.get("qty", 0) * (prices_copy.get(s) or p.get("entry", 0))
            for s, p in pos_copy.items()
            if p.get("qty", 0) > 0
        )
        shorts = sum(safe_float(p.get("pnl_unrealized"), 0.0) for p in short_copy.values())
        return self.balance + longs + shorts

    def return_pct(self):
        pv = self.portfolio_value()
        if self.initial_balance <= 0:
            return 0.0
        return (pv - self.initial_balance) / self.initial_balance * 100

    def win_rate(self):
        with self._lock:
            trades_copy = list(self.closed_trades)
        if not trades_copy:
            return 0.0
        return sum(1 for t in trades_copy if t.get("pnl", 0) > 0) / len(trades_copy) * 100

    def total_pnl(self):
        with self._lock:
            trades_copy = list(self.closed_trades)
        return sum(t.get("pnl", 0) for t in trades_copy)

    def avg_win(self):
        with self._lock:
            trades_copy = list(self.closed_trades)
        w = [t.get("pnl", 0) for t in trades_copy if t.get("pnl", 0) > 0]
        return sum(w) / len(w) if w else 0

    def avg_loss(self):
        with self._lock:
            trades_copy = list(self.closed_trades)
        losses = [t.get("pnl", 0) for t in trades_copy if t.get("pnl", 0) < 0]
        return sum(losses) / len(losses) if losses else 0

    def profit_factor(self):
        with self._lock:
            trades_copy = list(self.closed_trades)
        g = sum(t.get("pnl", 0) for t in trades_copy if t.get("pnl", 0) > 0)
        total_loss = abs(sum(t.get("pnl", 0) for t in trades_copy if t.get("pnl", 0) < 0))
        return round(g / total_loss, 2) if total_loss > 0 else 0.0

    def add_activity(self, icon, title, detail, atype="info"):
        # [Verbesserung #4] deque.appendleft ist thread-safe, kein Truncating nötig
        self.activity_log.appendleft(
            {
                "icon": icon,
                "title": title,
                "detail": detail,
                "type": atype,
                "time": datetime.now().strftime("%H:%M:%S"),
            }
        )

    def add_signal(self, s):
        self.signal_log.appendleft(s)

    def snapshot(self) -> dict:
        pv = self.portfolio_value()
        risk.update_peak(pv)
        today = datetime.now().strftime("%Y-%m-%d")
        with self._lock:
            closed_copy = list(self.closed_trades)
            pos_copy = dict(self.positions)
            short_copy = dict(self.short_positions)
            prices_snap = dict(self.prices)
        trades_today = [t for t in closed_copy if str(t.get("closed", ""))[:10] == today]
        daily_pnl = sum(t.get("pnl", 0) for t in trades_today)

        open_pos = [
            {
                "symbol": sym,
                "entry": round(p.get("entry", 0), 4),
                "current": round(prices_snap.get(sym, p.get("entry", 0)), 4),
                "qty": round(p.get("qty", 0), 4),
                "pnl": round(
                    (prices_snap.get(sym, p.get("entry", 0)) - p.get("entry", 0)) * p.get("qty", 0),
                    2,
                ),
                "pnl_pct": round(
                    (prices_snap.get(sym, p.get("entry", 0)) - p.get("entry", 0))
                    / p.get("entry", 0)
                    * 100
                    if p.get("entry", 0) > 0
                    else 0.0,
                    2,
                ),
                "sl": round(p.get("sl", 0), 4),
                "tp": round(p.get("tp", 0), 4),
                "invested": round(p.get("invested", 0), 2),
                "confidence": round(p.get("confidence", 0), 3),
                "ai_score": round(p.get("ai_score", 0), 1),
                "win_prob": round(p.get("win_prob", 0), 1),
                "dca_level": p.get("dca_level", 0),
                "partial_sold": p.get("partial_sold", 0),
                "news_score": round(p.get("news_score", 0), 2),
                "onchain_score": round(p.get("onchain_score", 0), 2),
                "trade_type": "long",
                "dna_hash": p.get("dna_hash", ""),
                "dna_boost": p.get("dna_boost", 1.0),
                "exit_regime": p.get("exit_regime", ""),
            }
            for sym, p in pos_copy.items()
        ] + [
            {
                "symbol": sym,
                "entry": round(p.get("entry", 0), 4),
                "current": round(prices_snap.get(sym, p.get("entry", 0)), 4),
                "qty": round(p.get("qty", 0), 4),
                "pnl": round(
                    p.get("invested", 0)
                    * (
                        (p.get("entry", 0) - (prices_snap.get(sym) or p.get("entry", 0)))
                        / p.get("entry", 0)
                    )
                    * CONFIG.get("short_leverage", 2)
                    if p.get("entry", 0) > 0
                    else 0.0,
                    2,
                ),
                "pnl_pct": round(
                    (p.get("entry", 0) - (prices_snap.get(sym) or p.get("entry", 0)))
                    / p.get("entry", 0)
                    * 100
                    if p.get("entry", 0) > 0
                    else 0.0,
                    2,
                ),
                "sl": round(p.get("sl", 0), 4),
                "tp": round(p.get("tp", 0), 4),
                "invested": round(p.get("invested", 0), 2),
                "trade_type": "short",
            }
            for sym, p in short_copy.items()
        ]

        # Goal ETA
        goal = CONFIG.get("portfolio_goal", 0)
        goal_pct = min(100, round(pv / goal * 100, 1)) if goal > 0 else 0
        goal_eta = "—"
        if goal > 0 and len(closed_copy) > 5:
            recent_slice = closed_copy[:20]  # [:20] = newest 20 trades
            recent_g = sum(t.get("pnl", 0) for t in recent_slice)
            daily_est = recent_g / len(recent_slice) if recent_g > 0 and recent_slice else 0
            if daily_est > 0:
                remaining = goal - pv
                if remaining <= 0:
                    goal_eta = "✅ Ziel erreicht!"
                else:
                    days = int(remaining / daily_est)
                    goal_eta = (
                        f"~{(datetime.now() + timedelta(days=days)).strftime('%d.%m.%Y')} ({days}d)"
                    )

        returns = [
            t.get("pnl", 0) / t.get("invested", 1) for t in closed_copy if t.get("invested", 0) > 0
        ]

        return {
            "bot_name": BOT_NAME,
            "bot_version": BOT_VERSION,
            "bot_full": BOT_FULL,
            "running": self.running,
            "paused": self.paused,
            "portfolio_value": round(pv, 2),
            "balance": round(self.balance, 2),
            "initial_balance": self.initial_balance,
            "return_pct": round(self.return_pct(), 2),
            "total_pnl": round(self.total_pnl(), 2),
            "win_rate": round(self.win_rate(), 1),
            "total_trades": len(closed_copy),
            "open_trades": len(open_pos),
            "max_trades": CONFIG.get("max_open_trades", 10),
            "avg_win": round(self.avg_win(), 2),
            "avg_loss": round(self.avg_loss(), 2),
            "profit_factor": self.profit_factor(),
            "sharpe": round(risk.sharpe(returns), 2),
            "max_drawdown": round(risk.max_drawdown, 2),
            "daily_pnl": round(daily_pnl, 2),
            "trade_today": len(trades_today),
            "market_regime": "bullish" if regime.is_bull else "bearish",
            "btc_price": round(regime.btc_price, 2),
            "positions": open_pos,
            "closed_trades": [
                {
                    "symbol": t.get("symbol"),
                    "entry": t.get("entry"),
                    "exit": t.get("exit") or t.get("exit_price"),
                    "qty": t.get("qty"),
                    "pnl": round(t.get("pnl", 0), 2),
                    "pnl_pct": round(t.get("pnl_pct", 0), 2),
                    "reason": t.get("reason", ""),
                    "confidence": t.get("confidence", 0),
                    "ai_score": t.get("ai_score", 0),
                    "win_prob": t.get("win_prob", 0),
                    "invested": t.get("invested", 0),
                    "opened": t.get("opened", ""),
                    "closed": t.get("closed", ""),
                    "regime": t.get("regime", ""),
                    "trade_type": t.get("trade_type", "long"),
                    "dca_level": t.get("dca_level", 0),
                    "news_score": t.get("news_score", 0),
                }
                for t in closed_copy[:100]
            ],
            "portfolio_history": list(self.portfolio_history)[-200:],
            "signal_log": list(self.signal_log)[:30],
            "activity_log": list(self.activity_log)[:20],
            "arb_log": list(self.arb_log)[:10],
            "last_scan": self.last_scan,
            "next_scan": self.next_scan,
            "ai": ai_engine.to_dict(),
            "fear_greed": fg_idx.to_dict(),
            "circuit_breaker": risk.circuit_status(),
            "dominance": dominance.to_dict(),
            "anomaly": anomaly.to_dict(),
            "genetic": genetic.to_dict(),
            "rl": rl_agent.to_dict(),
            "exchange": CONFIG.get("exchange", "cryptocom"),
            "exchange_key_states": _get_exchange_key_states(),
            "paper_trading": CONFIG.get("paper_trading", True),
            "goal": {"target": goal, "current": pv, "pct": goal_pct, "eta": goal_eta},
            "price_alerts": db.get_all_alerts()[:20],
            "use_shorts": CONFIG.get("use_shorts", False),
            "use_arbitrage": CONFIG.get("use_arbitrage", True),
            "trade_dna": trade_dna.to_dict(),
            "smart_exits": smart_exits.to_dict(),
            "adaptive_weights": adaptive_weights.to_dict(),
            "performance_attribution": perf_attribution.to_dict(),
            "trading_algorithms": trading_algos.to_dict(),
            "markets": list(self.markets),
            "iteration": self.iteration,
            "prices": {s: round(p, 4) for s, p in prices_snap.items()},
        }


# ═══════════════════════════════════════════════════════════════════════════════
# ARBITRAGE SCANNER
# ═══════════════════════════════════════════════════════════════════════════════
class ArbitrageScanner:
    def __init__(self):
        self._exchanges: dict[str, Any] = {}
        self._lock = threading.Lock()
        self.found_today = 0
        self.last_scan = None

    def _get_ex(self, name: str):
        with self._lock:
            if name not in self._exchanges:
                keys = CONFIG.get("arb_api_keys", {}).get(name, {})
                inst = create_ccxt_exchange(
                    name,
                    api_key=keys.get("key", ""),
                    api_secret=keys.get("secret", ""),
                    passphrase=keys.get("passphrase", ""),
                    default_type="spot",
                )
                if inst is None:
                    return None
                self._exchanges[name] = inst
            return self._exchanges.get(name)

    def scan(self, symbols: list[str]) -> list[dict]:
        if not CONFIG.get("use_arbitrage"):
            return []
        exchanges = CONFIG.get("arb_exchanges", ["binance", "bybit"])
        if len(exchanges) < 2:
            return []
        opportunities = []
        try:
            # Hole Preise von allen Exchanges
            prices_by_ex: dict[str, dict[str, float]] = {}
            for ex_name in exchanges:
                ex = self._get_ex(ex_name)
                if not ex:
                    continue
                try:
                    tickers = safe_fetch_tickers(ex, symbols[:30])
                    prices_by_ex[ex_name] = {
                        s: float(t.get("last") or 0) for s, t in tickers.items() if t.get("last")
                    }
                except Exception as exc:
                    log.debug(f"ARB ticker fetch {ex_name}: {exc}")

            ex_names = list(prices_by_ex.keys())
            for sym in symbols[:30]:
                sym_prices = {
                    n: prices_by_ex[n][sym] for n in ex_names if sym in prices_by_ex.get(n, {})
                }
                if len(sym_prices) < 2:
                    continue
                buy_ex = min(sym_prices, key=lambda k: sym_prices.get(k, 0))
                sell_ex = max(sym_prices, key=lambda k: sym_prices.get(k, 0))
                p_buy = sym_prices[buy_ex]
                p_sell = sym_prices[sell_ex]
                if p_buy <= 0:
                    continue
                spread = (p_sell - p_buy) / p_buy * 100
                # Fees abziehen (≈0.04% * 4 = 0.16%)
                net_spread = spread - 0.16
                if net_spread >= CONFIG.get("arb_min_spread_pct", 0.3):
                    opp = {
                        "symbol": sym,
                        "exchange_buy": buy_ex,
                        "price_buy": round(p_buy, 6),
                        "exchange_sell": sell_ex,
                        "price_sell": round(p_sell, 6),
                        "spread_pct": round(net_spread, 3),
                        "executed": 0,
                        "profit": 0,
                    }
                    opportunities.append(opp)
                    db.save_arb(opp)
                    self.found_today += 1
                    discord.arb_found(sym, buy_ex, sell_ex, net_spread)
                    state.arb_log.appendleft(
                        {
                            "time": datetime.now().strftime("%H:%M"),
                            "symbol": sym,
                            "buy": buy_ex,
                            "sell": sell_ex,
                            "spread": round(net_spread, 3),
                        }
                    )
                    log.info(f"💹 ARB: {sym} {buy_ex}→{sell_ex} Spread:{net_spread:.2f}%")
        except Exception as e:
            log.debug(f"ARB scan: {e}")
        self.last_scan = datetime.now().strftime("%H:%M:%S")
        return opportunities


# ═══════════════════════════════════════════════════════════════════════════════
# SHORT ENGINE
# ═══════════════════════════════════════════════════════════════════════════════
class ShortEngine:
    def __init__(self):
        self._ex = None
        self._ex_lock = threading.Lock()

    def _get_ex(self):
        # Paper-Trading: keine Exchange-Instanz nötig, Shorts sind rein virtuell.
        if CONFIG.get("paper_trading", True):
            return None
        with self._ex_lock:
            if self._ex:
                return self._ex
            name = CONFIG.get("short_exchange", "bybit")
            api_key = _reveal_and_decrypt(CONFIG.get("short_api_key", ""))
            api_secret = _reveal_and_decrypt(CONFIG.get("short_secret", ""))
            passphrase = _reveal_and_decrypt(CONFIG.get("short_passphrase", ""))
            self._ex = create_ccxt_exchange(
                name,
                api_key=api_key,
                api_secret=api_secret,
                passphrase=passphrase,
                default_type="swap",
            )
            return self._ex

    def open_short(self, symbol: str, invest: float, price: float) -> bool:
        if not CONFIG.get("use_shorts"):
            return False
        if not price or price <= 0:
            return False
        if symbol in state.positions:
            return False
        if invest <= 0 or invest > state.balance:
            return False
        sl = price * (1 + CONFIG.get("stop_loss_pct", 0.03))
        tp = price * (1 - CONFIG.get("take_profit_pct", 0.05))
        try:
            ex = self._get_ex()
            qty = invest / price
            if not CONFIG.get("paper_trading", True) and ex:
                ex.set_leverage(CONFIG.get("short_leverage", 2), symbol)
                ex.create_market_sell_order(symbol, qty)
            with state._lock:
                # Re-check under lock to prevent race with concurrent open/close
                if symbol in state.positions or symbol in state.short_positions:
                    return False
                if CONFIG.get("paper_trading", True):
                    if invest > state.balance:
                        return False
                    state.balance -= invest
                state.short_positions[symbol] = {
                    "entry": price,
                    "qty": qty,
                    "invested": invest,
                    "sl": sl,
                    "tp": tp,
                    "opened": datetime.now().isoformat(),
                    "pnl_unrealized": 0.0,
                }
            discord.short_open(symbol, price, invest)
            state.add_activity(
                "🔴", f"Short: {symbol}", f"@ {price:.4f} | {invest:.2f} USDT", "warning"
            )
            log.info(f"🔴 SHORT {symbol} @ {price:.4f}")
            return True
        except Exception as e:
            log.error(f"Short open: {e}")
            return False

    def close_short(self, symbol: str, reason: str):
        with state._lock:
            pos = state.short_positions.pop(symbol, None)
            price = state.prices.get(symbol, pos.get("entry", 0)) if pos else 0
        if not pos:
            return
        short_entry = pos.get("entry") or price
        pnl_pct = (short_entry - price) / short_entry * 100 if short_entry > 0 else 0.0
        leverage = CONFIG.get("short_leverage", 2)
        fee = (
            pos.get("invested", 0) * get_exchange_fee_rate(CONFIG.get("short_exchange")) * leverage
        )  # [#29]
        pnl = pos.get("invested", 0) * (pnl_pct / 100) * leverage - fee
        if CONFIG.get("paper_trading", True):
            with state._lock:
                state.balance += pos.get("invested", 0) + pnl
        else:
            try:
                ex = self._get_ex()
                if ex:
                    ex.create_market_buy_order(symbol, pos.get("qty", 0))
            except Exception as e:
                log.error(f"Short close: {e}")
        trade = {
            "symbol": symbol,
            "entry": round(pos.get("entry", 0), 4),
            "exit": round(price, 4),
            "qty": round(pos.get("qty", 0), 6),
            "pnl": round(pnl, 2),
            "pnl_pct": round(pnl_pct, 2),
            "reason": reason,
            "confidence": 0,
            "ai_score": 0,
            "win_prob": 0,
            "invested": round(pos.get("invested", 0), 2),
            "opened": pos.get("opened", ""),
            "closed": datetime.now().isoformat(),
            "exchange": CONFIG.get("short_exchange", "bybit"),
            "regime": "bear",
            "trade_type": "short",
        }
        with state._lock:
            state.closed_trades.insert(0, trade)
        db.save_trade(trade)
        won = pnl >= 0
        risk.record_result(won)
        icon = "✅" if won else "❌"
        state.add_activity(
            icon,
            f"Short Close: {symbol}",
            f"PnL:{pnl:+.2f} ({pnl_pct:+.2f}%) | {reason}",
            "success" if won else "error",
        )
        discord.trade_sell(symbol, price, pnl, pnl_pct, f"SHORT-{reason}")
        log.info(f"{icon} SHORT CLOSE {symbol} @ {price:.4f} | {pnl:+.2f} USDT")
        # Revenue Tracking: Record short trade
        try:
            revenue_tracker.record_trade(
                {
                    "symbol": symbol,
                    "side": "sell",
                    "amount": pos.get("qty", 0),
                    "price": price,
                    "fee": fee,
                    "strategy": f"SHORT-{reason}",
                    "pnl": pnl,
                    "timestamp": datetime.now(),
                }
            )
        except Exception:
            pass

    def update_shorts(self):
        for sym in list(state.short_positions.keys()):
            with state._lock:
                pos = state.short_positions.get(sym)
                price = state.prices.get(sym, pos.get("entry", 0)) if pos else 0
            if not pos:
                continue
            s_entry = pos.get("entry") or price
            if s_entry <= 0:
                continue
            pnl_pct = (s_entry - price) / s_entry * 100
            leverage = CONFIG.get("short_leverage", 2)
            with state._lock:
                invested = pos.get("invested", 0)
                est_fee = invested * get_exchange_fee_rate(CONFIG.get("short_exchange")) * leverage
                pos["pnl_unrealized"] = invested * (pnl_pct / 100) * leverage - est_fee
            sl = pos.get("sl", float("inf"))
            tp = pos.get("tp", 0)
            if price >= sl:
                self.close_short(sym, "SL 🛑")
            elif price <= tp:
                self.close_short(sym, "TP 🎯")
