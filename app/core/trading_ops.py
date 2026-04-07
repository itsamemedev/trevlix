"""Trading operations extracted from server.py.

Includes: create_exchange, preflight_exchange_markets, get_exchange_fee_rate,
fetch_markets, scan_symbol, open_position, close_position, _make_trade,
try_dca, manage_positions, get_heatmap_data, bot_loop, fetch_aggregated_balance,
safety_scan, and related helpers.

Module-level globals are injected at startup via init_trading_ops().
"""

from __future__ import annotations

import math
import os
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

import ccxt
import pandas as pd

from services.exchange_factory import (
    create_ccxt_exchange,
    get_fee_rate as _factory_get_fee_rate,
    safe_fetch_tickers as _factory_safe_fetch_tickers,
)
from services.strategies import STRATEGIES, compute_indicators
from services.utils import EXCHANGE_MAP
from app.core.request_helpers import normalize_exchange_name as _normalize_exchange_name, safe_int
from app.core.exchange_runtime import create_exchange_instance, preflight_exchange_markets
from app.core.market_cache import build_cache_paths, load_market_cache, save_market_cache
from app.core.bot_heartbeat import heartbeat_sleep

# ---------------------------------------------------------------------------
# Module-level references – populated by init_trading_ops()
# ---------------------------------------------------------------------------
CONFIG: dict = {}
log = None
db = None
state = None
discord = None
emit_event = None
regime = None
risk = None
anomaly = None
fg_idx = None
dominance = None
news_fetcher = None
onchain = None
ob = None
mtf = None
liq = None
ai_engine = None
rl_agent = None
trading_algos = None
trade_dna = None
smart_exits = None
adv_risk = None
funding_tracker = None
knowledge_base = None
grid_engine = None
price_alerts = None
telegram = None
revenue_tracker = None
perf_attribution = None
adaptive_weights = None
symbol_cooldown = None
healer = None
alert_escalation = None
cluster_ctrl = None
arb_scanner = None
short_engine = None
sentiment_f = None
_SHUTDOWN_EVENT = None
_ind_get = None
_ind_set = None
safe_fetch_tickers = _factory_safe_fetch_tickers
_MARKET_CACHE_MAX_AGE = 86400
_get_admin_exchange_by_name = None
_get_admin_primary_exchange = None
_is_single_exchange_mode = None
_reveal_and_decrypt = None
_pin_user_exchange = None

# Heatmap cache (module-level)
_heatmap_cache: list[dict] = []
_heatmap_ts: float = 0.0
_heatmap_lock = threading.Lock()



def normalize_exchange_name(raw):
    """Normalize exchange names with the shared EXCHANGE_MAP."""
    return _normalize_exchange_name(raw, EXCHANGE_MAP)


def init_trading_ops(
    *,
    config: dict,
    logger,
    db_ref,
    state_ref,
    discord_ref,
    emit_event_fn,
    regime_ref,
    risk_ref,
    anomaly_ref,
    fg_idx_ref,
    dominance_ref,
    news_fetcher_ref,
    onchain_ref,
    ob_ref,
    mtf_ref,
    liq_ref,
    ai_engine_ref,
    rl_agent_ref,
    trading_algos_ref,
    trade_dna_ref,
    smart_exits_ref,
    adv_risk_ref,
    funding_tracker_ref,
    knowledge_base_ref,
    grid_engine_ref,
    price_alerts_ref,
    telegram_ref,
    revenue_tracker_ref,
    perf_attribution_ref,
    adaptive_weights_ref,
    symbol_cooldown_ref,
    healer_ref,
    alert_escalation_ref,
    cluster_ctrl_ref,
    arb_scanner_ref,
    short_engine_ref,
    sentiment_f_ref,
    shutdown_event,
    ind_get_fn,
    ind_set_fn,
    get_admin_exchange_by_name_fn,
    get_admin_primary_exchange_fn,
    is_single_exchange_mode_fn,
    reveal_and_decrypt_fn,
    pin_user_exchange_fn,
    market_cache_max_age: int = 86400,
) -> None:
    """Inject runtime dependencies into this module's globals."""
    global CONFIG, log, db, state, discord, emit_event, regime, risk
    global anomaly, fg_idx, dominance, news_fetcher, onchain, ob, mtf, liq
    global ai_engine, rl_agent, trading_algos, trade_dna, smart_exits
    global adv_risk, funding_tracker, knowledge_base, grid_engine
    global price_alerts, telegram, revenue_tracker, perf_attribution
    global adaptive_weights, symbol_cooldown, healer, alert_escalation
    global cluster_ctrl, arb_scanner, short_engine, sentiment_f
    global _SHUTDOWN_EVENT, _ind_get, _ind_set, _MARKET_CACHE_MAX_AGE
    global _get_admin_exchange_by_name, _get_admin_primary_exchange
    global _is_single_exchange_mode, _reveal_and_decrypt, _pin_user_exchange
    CONFIG = config
    log = logger
    db = db_ref
    state = state_ref
    discord = discord_ref
    emit_event = emit_event_fn
    regime = regime_ref
    risk = risk_ref
    anomaly = anomaly_ref
    fg_idx = fg_idx_ref
    dominance = dominance_ref
    news_fetcher = news_fetcher_ref
    onchain = onchain_ref
    ob = ob_ref
    mtf = mtf_ref
    liq = liq_ref
    ai_engine = ai_engine_ref
    rl_agent = rl_agent_ref
    trading_algos = trading_algos_ref
    trade_dna = trade_dna_ref
    smart_exits = smart_exits_ref
    adv_risk = adv_risk_ref
    funding_tracker = funding_tracker_ref
    knowledge_base = knowledge_base_ref
    grid_engine = grid_engine_ref
    price_alerts = price_alerts_ref
    telegram = telegram_ref
    revenue_tracker = revenue_tracker_ref
    perf_attribution = perf_attribution_ref
    adaptive_weights = adaptive_weights_ref
    symbol_cooldown = symbol_cooldown_ref
    healer = healer_ref
    alert_escalation = alert_escalation_ref
    cluster_ctrl = cluster_ctrl_ref
    arb_scanner = arb_scanner_ref
    short_engine = short_engine_ref
    sentiment_f = sentiment_f_ref
    _SHUTDOWN_EVENT = shutdown_event
    _ind_get = ind_get_fn
    _ind_set = ind_set_fn
    _get_admin_exchange_by_name = get_admin_exchange_by_name_fn
    _get_admin_primary_exchange = get_admin_primary_exchange_fn
    _is_single_exchange_mode = is_single_exchange_mode_fn
    _reveal_and_decrypt = reveal_and_decrypt_fn
    _pin_user_exchange = pin_user_exchange_fn
    _MARKET_CACHE_MAX_AGE = market_cache_max_age


def create_exchange():
    """Erstellt die primäre Exchange-Instanz.

    Priorität der Quelle für Keys + Exchange-Name:
      1. Admin-Exchange aus DB (user_exchanges, is_primary + enabled)
      2. EXCHANGE aus .env (Single-Mode)
      3. Fallback: "cryptocom" als Default
    Im Paper-Trading-Modus werden keine Credentials verwendet (public-only).
    """
    return create_exchange_instance(
        config=CONFIG,
        normalize_exchange_name=normalize_exchange_name,
        get_admin_exchange_by_name=_get_admin_exchange_by_name,
        get_admin_primary_exchange=_get_admin_primary_exchange,
        is_single_exchange_mode=_is_single_exchange_mode,
        reveal_and_decrypt=_reveal_and_decrypt,
        safe_int=safe_int,
        create_ccxt_exchange=create_ccxt_exchange,
        log=log,
    )


def _preflight_exchange_markets(max_attempts: int = 4) -> tuple[list[str], str | None]:
    """Preflight für Exchange + Märkte mit Retry und persistentem Cache-Fallback.

    Returns:
        (markets, error_message). Bei Erfolg ist error_message None.
    """
    return preflight_exchange_markets(
        max_attempts=max_attempts,
        create_exchange=create_exchange,
        fetch_markets=fetch_markets,
        normalize_exchange_name=normalize_exchange_name,
        config=CONFIG,
        db=db,
        pin_user_exchange=_pin_user_exchange,
        log=log,
        load_market_cache=_load_market_cache,
    )


def get_exchange_fee_rate(exchange_id: str | None = None, symbol: str = "BTC/USDT") -> float:
    """Gibt die Taker-Fee für eine Exchange zurück (gecached)."""
    ex_id = exchange_id or CONFIG.get("exchange", "cryptocom")
    return _factory_get_fee_rate(ex_id, symbol, fallback=CONFIG.get("fee_rate", 0.001))


# safe_fetch_tickers ist ein Alias auf die Factory-Implementierung
safe_fetch_tickers = _factory_safe_fetch_tickers


# ═══════════════════════════════════════════════════════════════════════════════
# MARKT-SCANNER
# ═══════════════════════════════════════════════════════════════════════════════

# Persistenter Markt-Cache: überlebt Neustarts, damit der Bot auch bei
# temporären Exchange-Ausfällen mit der letzten bekannten Marktliste starten kann.
_MARKET_CACHE_MAX_AGE = 86400  # 24h – danach wird der Cache als veraltet betrachtet
_MARKET_CACHE_DIR, _MARKET_CACHE_FILE = build_cache_paths(
    os.path.dirname(os.path.abspath(__file__))
)


def _save_market_cache(markets: list[str]) -> None:
    """Speichert Marktliste auf Disk für Restart-Resilienz."""
    save_market_cache(
        markets=markets, cache_dir=_MARKET_CACHE_DIR, cache_file=_MARKET_CACHE_FILE, log=log
    )


def _load_market_cache(max_age: int = _MARKET_CACHE_MAX_AGE) -> list[str]:
    """Lädt gecachte Marktliste von Disk (falls vorhanden und nicht veraltet)."""
    return load_market_cache(cache_file=_MARKET_CACHE_FILE, max_age=max_age, log=log)


# Beim Start: persistenten Cache in state.markets laden, damit der Bot sofort
# eine Marktliste hat, auch wenn die Exchange beim ersten Preflight nicht antwortet.
_startup_cached_markets = _load_market_cache()
if _startup_cached_markets and not state.markets:
    with state._lock:
        state.markets = _startup_cached_markets
    log.info(
        "📦 %d Märkte aus persistentem Cache geladen (Startup-Seed).",
        len(_startup_cached_markets),
    )


def fetch_markets(ex) -> list[str]:
    try:
        markets = ex.load_markets()
        quote = CONFIG.get("quote_currency", "USDT")
        bl = set(CONFIG.get("blacklist", []))
        syms = [
            s
            for s, m in markets.items()
            if m.get("quote") == quote and m.get("active") and s not in bl and m.get("spot", True)
        ]
        if CONFIG.get("use_vol_filter"):
            try:
                tickers = safe_fetch_tickers(ex, syms[:150])
                min_vol = CONFIG.get("min_volume_usdt", 1_000_000)
                syms = [s for s in syms if (tickers.get(s, {}).get("quoteVolume") or 0) >= min_vol]
            except (ccxt.BaseError, OSError, TimeoutError) as vol_err:
                log.warning(
                    "Volumenfilter übersprungen (Marktdaten-Timeout/API-Fehler): %s",
                    vol_err,
                )
        trending = sentiment_f.get_trending()
        priority = [s for s in trending if s in syms]
        rest = [s for s in syms if s not in priority]
        result = (priority + rest)[:80]
        # Erfolgreiche Marktliste persistent cachen
        if result:
            _save_market_cache(result)
        return result
    except Exception as e:
        log.error(f"Märkte: {e}")
        # Fallback 1: In-Memory Cache
        with state._lock:
            cached = list(state.markets)
        if cached:
            log.warning("Nutze gecachte Märkte (%d), da Exchange-Daten fehlen.", len(cached))
            return cached
        # Fallback 2: Persistenter Disk-Cache
        disk_cached = _load_market_cache()
        if disk_cached:
            log.warning(
                "Nutze persistenten Markt-Cache (%d Märkte) – Exchange nicht erreichbar.",
                len(disk_cached),
            )
        return disk_cached


def scan_symbol(ex, symbol) -> dict | None:
    try:
        ohlcv = ex.fetch_ohlcv(
            symbol, CONFIG.get("timeframe", "1h"), limit=CONFIG.get("candle_limit", 250)
        )
        if not ohlcv or len(ohlcv) < 100:
            return None
        df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        df.set_index("timestamp", inplace=True)
        # Indikator-Cache: Nur neu berechnen wenn sich der letzte Timestamp geändert hat
        _last_ts = df.index[-1]
        df_cached = _ind_get(symbol, _last_ts)
        if df_cached is not None:
            df = df_cached
        else:
            df = compute_indicators(df)
            if df is None:
                return None
            _ind_set(symbol, _last_ts, df)
        if df is None or len(df) < 2:
            return None
        row = df.iloc[-1]
        prev = df.iloc[-2]
        price = float(row["close"])
        # [24+27] Multi-Regime classification
        ph = list(df["close"].values[-50:])
        adv_risk.classify_regime(ph) if ph else None
        risk.update_prices(symbol, price)
        with state._lock:
            state.prices[symbol] = price

        votes = {}
        for nm, fn in STRATEGIES:
            try:
                votes[nm] = fn(row, prev)
            except Exception:
                votes[nm] = 0

        # Adaptive Weights: dynamische Strategie-Gewichte anwenden
        if CONFIG.get("use_adaptive_weights"):
            regime_str = "bull" if regime and regime.is_bull else "bear"
            aw = adaptive_weights.get_weights(regime=regime_str)
            with ai_engine._lock:
                for nm in aw:
                    if nm in ai_engine.weights:
                        ai_engine.weights[nm] = aw[nm]

        signal, conf = ai_engine.weighted_vote(votes, CONFIG.get("min_vote_score", 0.3))
        ob_ratio, ob_desc = ob.get(ex, symbol)
        mtf_ok, mtf_desc = mtf.is_confirmed(ex, symbol, signal)
        sentiment = sentiment_f.get_score(symbol)
        news_score, news_hl, news_cnt = news_fetcher.get_score(symbol)
        onchain_score, onchain_detail = onchain.get_score(symbol)

        # Anomalie-Check (NaN-Werte filtern, da sie den IsolationForest vergiften)
        price_chg = float(row.get("returns", 0) * 100)
        _vol_r = float(row.get("vol_ratio", 1))
        _rsi_v = float(row.get("rsi", 50))
        _atr_v = float(row.get("atr_pct", 1))
        if not any(math.isnan(v) for v in (price_chg, _vol_r, _rsi_v, _atr_v)):
            anomaly.add_observation(price_chg, _vol_r, _rsi_v, _atr_v)

        return {
            "symbol": symbol,
            "price": price,
            "signal": signal,
            "confidence": conf,
            "votes": votes,
            "rsi": round(float(row.get("rsi", 50)), 1),
            "stoch_rsi": float(row.get("stoch_rsi", 50)),
            "bb_pct": float(row.get("bb_pct", 0.5)),
            "bb_width": float(row.get("bb_width", 0.05)),
            "macd_hist": float(row.get("macd_hist", 0)),
            "macd_hist_slope": float(row.get("macd_hist_slope", 0)),
            "vol_ratio": float(row.get("vol_ratio", 1)),
            "atr_pct": float(row.get("atr_pct", 1)),
            "atr14": float(row.get("atr14", 0)),
            "ema_alignment": float(row.get("ema_alignment", 0)),
            "price_vs_ema21": float(row.get("price_vs_ema21", 0)),
            "roc10": float(row.get("roc10", 0)),
            "ob_ratio": ob_ratio,
            "ob_desc": ob_desc,
            "mtf_ok": mtf_ok,
            "mtf_desc": mtf_desc,
            "sentiment": sentiment,
            "news_score": news_score,
            "news_headline": news_hl,
            "news_count": news_cnt,
            "onchain_score": onchain_score,
            "onchain_detail": onchain_detail,
            "ohlcv": [
                [int(r[0]), float(r[1]), float(r[2]), float(r[3]), float(r[4]), float(r[5])]
                for r in ohlcv[-100:]
                if len(r) >= 6
            ],
            "time": datetime.now().strftime("%H:%M:%S"),
        }
    # [Verbesserung #5] Differenzierte ccxt-Exceptions in scan_symbol
    except ccxt.RateLimitExceeded:
        log.warning(f"Rate-Limit beim Scan von {symbol} – überspringe")
        return None
    except ccxt.NetworkError as e:
        log.warning(f"Netzwerk-Timeout beim Scan von {symbol}: {e}")
        return None
    except ccxt.ExchangeError as e:
        log.warning(f"Exchange-Fehler beim Scan von {symbol}: {e}")
        return None
    except Exception as e:
        log.warning(f"Scan {symbol} fehlgeschlagen: {e}")
        return None


# ═══════════════════════════════════════════════════════════════════════════════
# TRADE EXECUTION mit DCA + Partial TP
# ═══════════════════════════════════════════════════════════════════════════════
def open_position(ex, scan: dict):
    symbol = scan["symbol"]
    price = scan["price"]
    if not price or price <= 0:
        log.warning(f"open_position: Ungültiger Preis {price} für {symbol}")
        return
    if len(state.positions) >= CONFIG.get("max_open_trades", 5):
        return
    if symbol in state.positions:
        return
    if symbol in state.short_positions:
        return
    if symbol_cooldown.is_blocked(symbol):
        log.debug(f"[COOLDOWN] {symbol} blockiert")
        return
    if not regime.is_bull and CONFIG["use_market_regime"]:
        return
    if risk.daily_loss_exceeded(state.balance):
        return
    if risk.circuit_breaker_active():
        return
    # News-Sentiment-Filter (Verbesserung 9)
    news_score = scan.get("news_score", 0.0)
    min_score = CONFIG.get("news_sentiment_min", -0.2)
    if news_score < min_score:
        log.debug(f"[NEWS-FILTER] {symbol} blockiert: news_score={news_score:.2f} < {min_score}")
        return
    if CONFIG.get("news_require_positive") and news_score < 0:
        log.debug(f"[NEWS-FILTER] {symbol} blockiert: positiver Score erforderlich")
        return
    if anomaly.is_anomaly:
        log.info(f"🚨 {symbol} blockiert – Anomalie")
        return
    if not fg_idx.is_ok_to_buy():
        log.info(f"😱 {symbol} F&G:{fg_idx.value}")
        return

    # Dominanz
    dom_ok, dom_reason = dominance.is_ok_to_buy(symbol)
    if not dom_ok:
        log.info(f"🌐 {symbol}: {dom_reason}")
        return

    if risk.is_correlated(symbol, list(state.positions.keys())):
        return
    if not scan.get("mtf_ok", True) and CONFIG.get("mtf_enabled"):
        return
    if scan.get("ob_ratio", 0.5) < CONFIG.get("ob_imbalance_min", 0.45):
        return
    ok, spread, _ = liq.check(ex, symbol)
    if not ok:
        return

    features = ai_engine.extract_features(
        scan["votes"],
        scan,
        regime.is_bull,
        fg_idx.value,
        state.closed_trades,
        ob_imbalance=scan.get("ob_ratio", 0.5),
        mtf_bullish=int(scan.get("mtf_ok", True)),
        sentiment=scan.get("sentiment", 0.5),
        news_score=news_score,
        onchain_score=scan.get("onchain_score", 0),
        dominance_ok=int(dom_ok),
    )

    # RL-Agent konsultieren
    if CONFIG.get("rl_enabled") and rl_agent.is_trained:
        rl_action = rl_agent.act(
            scan.get("rsi", 50),
            1 if regime.is_bull else -1,
            fg_idx.value,
            news_score,
            scan.get("ob_ratio", 0.5),
        )
        if rl_action == 0:
            log.info(f"🤖 {symbol} RL: Hold")
            return

    allowed, ai_score, ai_reason = ai_engine.should_buy(features, scan["confidence"])
    win_prob = ai_engine.win_probability(features) * 100
    if not allowed:
        return

    # ── Selbstlernender Kauf-Algorithmus ─────────────────────────────────
    algo_buy, algo_conf, algo_reason = trading_algos.evaluate_buy(scan)
    if not algo_buy:
        log.debug(f"[BUY-ALGO] {symbol} blockiert: {algo_reason}")
        return
    # Algo-Kaufsignal per Discord/Telegram senden
    discord.algo_buy_signal(symbol, price, algo_conf, algo_reason)
    telegram.algo_buy_signal(symbol, price, algo_conf, algo_reason)

    # ── Trade DNA Fingerprinting ─────────────────────────────────────────
    dna_result = None
    dna_adjustment = None
    if CONFIG.get("use_trade_dna"):
        regime_str = "bull" if regime.is_bull else "bear"
        local_regime = (
            smart_exits.classify_regime_from_scan(scan) if smart_exits.enabled else regime_str
        )
        dna_result = trade_dna.compute(symbol, scan, local_regime, fg_idx.value)
        dna_adjustment = trade_dna.confidence_adjustment(dna_result)
        if dna_adjustment["action"] == "block" and dna_adjustment["matches"] >= CONFIG.get(
            "dna_min_matches", 5
        ):
            log.info(f"🧬 {symbol} DNA-Block: {dna_adjustment['reason']}")
            state.add_activity("🧬", f"DNA-Block: {symbol}", dna_adjustment["reason"], "warning")
            return

    fg_boost = fg_idx.buy_boost()
    # DNA-Boost in Position-Sizing einbeziehen
    dna_mult = dna_adjustment.get("multiplier", 1.0) if dna_adjustment else 1.0
    invest = (
        ai_engine.kelly_size(win_prob / 100, state.balance, scan.get("atr14", 0), fg_boost)
        if CONFIG["ai_use_kelly"]
        else state.balance * CONFIG.get("risk_per_trade", 0.015) * fg_boost
    )
    invest *= dna_mult
    invest = min(invest, state.balance * CONFIG["max_position_pct"])
    if invest < 5:
        return

    fee = invest * get_exchange_fee_rate()  # [#29] Exchange-spezifische Fee
    if price <= 0:
        log.warning(f"open_position {symbol}: Preis ist 0, überspringe")
        return
    qty = (invest - fee) / price
    if qty <= 0:
        log.warning(f"open_position {symbol}: qty <= 0 (invest={invest:.2f}, fee={fee:.2f})")
        return

    # ── Smart Exits: Dynamische SL/TP ────────────────────────────────────
    if smart_exits.enabled:
        local_regime = smart_exits.classify_regime_from_scan(scan)
        sl, tp = smart_exits.compute(price, scan, local_regime)
    else:
        sl = price * (1 - CONFIG.get("stop_loss_pct", 0.025))
        tp = price * (1 + CONFIG.get("take_profit_pct", 0.06))

    if CONFIG.get("paper_trading", True):
        with state._lock:
            # Re-clamp invest under lock to prevent stale-balance race condition
            invest = min(invest, state.balance * CONFIG["max_position_pct"])
            if invest > state.balance or invest < 5:
                log.warning(f"Invest {invest:.2f} > Balance {state.balance:.2f}, skipping {symbol}")
                return
            # Recalculate fee and qty after re-clamp to keep them consistent
            fee = invest * get_exchange_fee_rate()
            qty = (invest - fee) / price
            if qty <= 0:
                return
            state.balance -= invest
    else:
        try:
            ex.create_market_buy_order(symbol, qty)
        except Exception as e:
            log.error(f"Order {symbol}: {e}")
            discord.error(str(e))
            return

    ai_engine.on_buy(symbol, features, scan["votes"], scan)
    pos_data = {
        "entry": price,
        "qty": qty,
        "invested": invest - fee,
        "sl": sl,
        "tp": tp,
        "highest": price,
        "opened": datetime.now().isoformat(),
        "confidence": scan["confidence"],
        "ai_score": round(ai_score * 100, 1),
        "win_prob": round(win_prob, 1),
        "regime": "bull" if regime.is_bull else "bear",
        "dca_level": 0,
        "partial_sold": 0,
        "news_score": round(news_score, 3),
        "onchain_score": round(scan.get("onchain_score", 0), 3),
        # Indikatoren für Sell-Algorithmus
        "rsi": scan.get("rsi", 50),
        "stoch_rsi": scan.get("stoch_rsi", 50),
        "bb_pct": scan.get("bb_pct", 0.5),
        "vol_ratio": scan.get("vol_ratio", 1.0),
        "ema_alignment": scan.get("ema_alignment", 0),
        "macd_hist_slope": scan.get("macd_hist_slope", 0),
        "roc10": scan.get("roc10", 0),
        "atr_pct": scan.get("atr_pct", 1.0),
        "price_vs_ema21": scan.get("price_vs_ema21", 0),
        "algo_buy_conf": round(algo_conf, 3),
        "algo_buy_reason": algo_reason,
    }
    # Trade DNA: Fingerprint in Position speichern
    if dna_result:
        pos_data["dna_hash"] = dna_result["hash"]
        pos_data["dna_fingerprint"] = dna_result["fingerprint"]
        pos_data["dna_boost"] = round(dna_mult, 3)
    # Smart Exits: Regime in Position speichern
    if smart_exits.enabled:
        pos_data["exit_regime"] = smart_exits.classify_regime_from_scan(scan)
    with state._lock:
        state.positions[symbol] = pos_data
    dna_info = f" | DNA:{dna_mult:.2f}x" if dna_result and dna_mult != 1.0 else ""
    smart_info = f" | SL:{sl:.4f} TP:{tp:.4f}" if smart_exits.enabled else ""
    log.info(
        f"🟢 KAUF {symbol} @ {price:.4f} | {invest:.2f} USDT | KI:{ai_score * 100:.0f}%"
        f" | News:{news_score:+.2f}{dna_info}{smart_info}"
    )
    state.add_activity(
        "🟢",
        f"Kauf: {symbol}",
        f"@ {price:.4f} | {invest:.2f} USDT | KI:{ai_score * 100:.0f}%",
        "success",
    )
    discord.trade_buy(
        symbol,
        price,
        invest,
        ai_score * 100,
        win_prob,
        news_score,
        confidence=scan.get("confidence"),
        rsi=scan.get("rsi"),
        regime=pos_data.get("regime"),
        votes=scan.get("votes"),
    )
    # DNA + Smart Exit Discord-Notifications
    if dna_adjustment and dna_adjustment["action"] in ("boost", "block"):
        discord.dna_boost(
            symbol,
            dna_adjustment["action"],
            dna_adjustment.get("win_rate", 0),
            dna_adjustment.get("matches", 0),
            dna_adjustment.get("multiplier", 1.0),
        )
    if smart_exits.enabled:
        discord.smart_exit(
            symbol, sl, tp, pos_data.get("exit_regime", "bull"), scan.get("atr_pct", 0)
        )
    emit_event(
        "trade",
        {
            "type": "buy",
            "symbol": symbol,
            "price": price,
            "invest": round(invest, 2),
            "ai_score": round(ai_score * 100, 1),
        },
    )


def close_position(ex, symbol, reason, partial_ratio=1.0):
    partial_ratio = max(0.01, min(partial_ratio, 1.0))
    is_partial = partial_ratio < 1.0
    with state._lock:
        pos = state.positions.get(symbol)
        if not pos:
            return
        price = state.prices.get(symbol, pos.get("entry", 0))
        if not is_partial:
            # Eagerly pop to prevent concurrent double-close from bot_loop + WebSocket
            state.positions.pop(symbol, None)

    close_qty = pos.get("qty", 0) * partial_ratio
    close_invest = pos.get("invested", 0) * partial_ratio
    entry = pos.get("entry") or price
    if entry <= 0:
        entry = price
    if price <= 0 or entry <= 0:
        log.warning(f"close_position {symbol}: ungültiger Preis {price} / Entry {entry}")
        return
    pnl_pct = (price - entry) / entry * 100
    fee = close_invest * get_exchange_fee_rate()  # [#29] Exchange-spezifische Fee
    pnl = close_invest * (pnl_pct / 100) - fee

    if CONFIG.get("paper_trading", True):
        with state._lock:
            state.balance += close_invest + pnl
    else:
        try:
            ex.create_market_sell_order(symbol, close_qty)
        except Exception as e:
            log.error(f"Sell {symbol}: {e}")
            return

    if is_partial:
        # Teilverkauf → Position aktualisieren
        with state._lock:
            pos["qty"] = max(0, pos["qty"] - close_qty)
            pos["invested"] = max(0, pos["invested"] - close_invest)
            pos["partial_sold"] = min(1.0, pos.get("partial_sold", 0) + partial_ratio)
        log.info(f"🔶 PARTIAL {symbol} {partial_ratio * 100:.0f}% @ {price:.4f} | PnL: {pnl:+.2f}")
        state.add_activity(
            "🔶",
            f"Partial TP: {symbol}",
            f"{partial_ratio * 100:.0f}% @ {price:.4f} | {pnl:+.2f}",
            "success" if pnl > 0 else "warning",
        )
        discord.trade_sell(symbol, price, pnl, pnl_pct, reason, partial=True)
        trade = {
            **_make_trade(
                symbol, pos, price, close_qty, close_invest, pnl, pnl_pct, reason + "(partial)"
            ),
            "partial_sold": 1,
        }
    else:
        regime_str = pos.get("regime", "bull")
        ai_engine.on_sell(symbol, pnl, regime_str)
        risk.record_result(pnl > 0)
        # Trade DNA: Ergebnis aufzeichnen
        if CONFIG.get("use_trade_dna") and pos.get("dna_fingerprint"):
            dna_entry = {
                "hash": pos.get("dna_hash", ""),
                "fingerprint": pos.get("dna_fingerprint", {}),
                "dimensions": {},  # Nicht gespeichert, aber Fingerprint reicht
                "symbol": symbol,
                "timestamp": pos.get("opened", ""),
            }
            trade_dna.record(dna_entry, won=pnl > 0)
        trade = _make_trade(
            symbol,
            pos,
            price,
            close_qty,
            close_invest,
            pnl,
            pnl_pct,
            reason,
            dca_level=pos.get("dca_level", 0),
        )
        with state._lock:
            state.closed_trades.insert(0, trade)
            # positions already popped in initial lock to prevent double-close
        icon = "✅" if pnl > 0 else "❌"
        state.add_activity(
            icon,
            f"Verkauf: {symbol}",
            f"PnL:{pnl:+.2f} ({pnl_pct:+.2f}%) | {reason}",
            "success" if pnl > 0 else "error",
        )
        discord.trade_sell(symbol, price, pnl, pnl_pct, reason)
        log.info(f"{icon} VKAUF {symbol} @ {price:.4f} | {pnl:+.2f} ({pnl_pct:+.2f}%) | {reason}")

    db.save_trade(trade)
    # Trading-Algorithmen: Ergebnis für Selbstlernen aufzeichnen
    try:
        scan_at_entry = {
            k: pos.get(k)
            for k in (
                "rsi",
                "stoch_rsi",
                "bb_pct",
                "vol_ratio",
                "ema_alignment",
                "macd_hist_slope",
                "roc10",
                "atr_pct",
                "price_vs_ema21",
            )
            if pos.get(k) is not None
        }
        trading_algos.record_buy_result(scan_at_entry, pnl)
        trading_algos.record_sell_result(scan_at_entry, pos, pnl, reason)
    except Exception:
        pass  # Feedback ist optional
    # Performance Attribution: Trade aufzeichnen
    try:
        perf_attribution.record_trade(
            symbol=symbol,
            pnl=pnl,
            strategy=reason,
            regime=pos.get("regime", "unknown"),
            fg_value=pos.get("fg_value", 50),
            hour=pos.get("entry_hour"),
        )
    except Exception:
        pass
    # Adaptive Weights: Strategie-Ergebnis aufzeichnen
    try:
        adaptive_weights.record_vote(
            strategy=reason,
            won=pnl > 0,
            regime=pos.get("regime", "unknown"),
        )
    except Exception:
        pass
    # KI-Gemeinschaftswissen: Erkenntnisse aus Trade speichern
    try:
        knowledge_base.learn_from_trade(trade)
    except Exception:
        pass  # Knowledge-Update ist optional
    # Autonome LLM-Analyse: Trade per LLM analysieren (async, non-blocking)
    try:
        knowledge_base.analyze_trade_async(
            trade,
            features={
                "rsi": pos.get("rsi", "?"),
                "news_score": pos.get("news_score", 0),
                "regime": pos.get("regime", "unknown"),
                "ai_score": pos.get("ai_score", 0),
                "win_prob": pos.get("win_prob", 0),
            },
        )
    except Exception:
        pass  # LLM-Analyse ist optional
    # Revenue Tracking: Record trade with fees/slippage for real PnL
    try:
        revenue_tracker.record_trade(
            {
                "symbol": symbol,
                "side": "sell",
                "amount": close_qty,
                "price": price,
                "fee": fee,
                "strategy": reason,
                "pnl": pnl,
                "timestamp": datetime.now(),
            }
        )
    except Exception:
        pass  # Revenue tracking is optional
    emit_event(
        "trade",
        {
            "type": "sell",
            "symbol": symbol,
            "price": price,
            "pnl": round(pnl, 2),
            "pnl_pct": round(pnl_pct, 2),
            "reason": reason,
        },
    )


def _make_trade(symbol, pos, price, qty, invest, pnl, pnl_pct, reason, dca_level=0, partial_sold=0):
    trade = {
        "symbol": symbol,
        "entry": round(pos.get("entry", 0), 4),
        "exit": round(price, 4),
        "qty": round(qty, 6),
        "pnl": round(pnl, 2),
        "pnl_pct": round(pnl_pct, 2),
        "reason": reason,
        "confidence": round(pos.get("confidence", 0), 3),
        "ai_score": round(pos.get("ai_score", 0), 1),
        "win_prob": round(pos.get("win_prob", 0), 1),
        "invested": round(invest, 2),
        "opened": pos.get("opened", ""),
        "closed": datetime.now().isoformat(),
        "exchange": CONFIG.get("exchange", "cryptocom"),
        "regime": pos.get("regime", "bull"),
        "trade_type": "long",
        "partial_sold": partial_sold,
        "dca_level": dca_level,
        "news_score": round(pos.get("news_score", 0), 3),
        "onchain_score": round(pos.get("onchain_score", 0), 3),
    }
    # Trade DNA Fingerprint anhängen (für historische Analyse)
    if pos.get("dna_hash"):
        trade["dna_hash"] = pos.get("dna_hash", "")
        trade["dna_boost"] = pos.get("dna_boost", 1.0)
    # Smart Exit Regime anhängen
    if pos.get("exit_regime"):
        trade["exit_regime"] = pos["exit_regime"]
    return trade


def try_dca(ex, symbol):
    """Dollar-Cost-Averaging: bei Kursrückgang nachkaufen."""
    if not CONFIG.get("use_dca"):
        return
    with state._lock:
        pos_ref = state.positions.get(symbol)
        if not pos_ref:
            return
        pos = dict(pos_ref)  # snapshot to prevent reading stale data outside lock
        price = state.prices.get(symbol, pos.get("entry", 0))
    dca_level = pos.get("dca_level", 0)
    if dca_level >= CONFIG.get("dca_max_levels", 3):
        return
    if pos.get("entry", 0) <= 0 or price <= 0:
        return
    entry_price = pos.get("entry", 0)
    drop = (entry_price - price) / entry_price if entry_price > 0 else 0.0
    threshold = CONFIG.get("dca_drop_pct", 0.05) * (dca_level + 1)
    if drop < threshold:
        return
    # Nachkauf
    dca_invest = pos.get("invested", 0) * CONFIG.get("dca_size_mult", 1.0)
    with state._lock:
        dca_invest = min(dca_invest, state.balance * 0.15)
    if dca_invest < 5:
        return
    if price <= 0:
        return
    fee = dca_invest * get_exchange_fee_rate()  # [#29] Exchange-spezifische Fee
    add_qty = (dca_invest - fee) / price
    # Neuer Durchschnittspreis
    total_qty = pos.get("qty", 0) + add_qty
    if total_qty <= 0:
        return
    total_cost = pos.get("invested", 0) + dca_invest - fee
    new_entry = total_cost / total_qty
    if CONFIG.get("paper_trading", True):
        with state._lock:
            if dca_invest > state.balance:
                log.warning(f"DCA {symbol}: invest {dca_invest:.2f} > balance {state.balance:.2f}")
                return
            state.balance -= dca_invest
    else:
        try:
            ex.create_market_buy_order(symbol, add_qty)
        except Exception as e:
            log.error(f"DCA {symbol}: {e}")
            return
    with state._lock:
        # Re-fetch live reference; position may have been closed concurrently
        live_pos = state.positions.get(symbol)
        if not live_pos:
            # Position closed while we were calculating – refund balance
            if CONFIG.get("paper_trading", True):
                state.balance += dca_invest
            return
        live_pos["qty"] = total_qty
        live_pos["invested"] = total_cost
        live_pos["entry"] = new_entry
        live_pos["dca_level"] = dca_level + 1
        live_pos["sl"] = new_entry * (1 - CONFIG.get("stop_loss_pct", 0.025))
        live_pos["tp"] = new_entry * (1 + CONFIG.get("take_profit_pct", 0.06))
    log.info(
        f"📉 DCA Lvl{dca_level + 1} {symbol}: +{add_qty:.4f} @ {price:.4f} | ⌀:{new_entry:.4f}"
    )
    state.add_activity(
        "📉",
        f"DCA Level {dca_level + 1}: {symbol}",
        f"Ø-Preis:{new_entry:.4f} | +{dca_invest:.0f} USDT",
        "info",
    )


def manage_positions(ex):
    with state._lock:
        position_keys = list(state.positions.keys())
    for symbol in position_keys:
        with state._lock:
            pos = state.positions.get(symbol)
        if not pos:
            continue
        try:
            ticker = ex.fetch_ticker(symbol)
            last_price = ticker.get("last")
            if last_price is None:
                continue
            price = float(last_price)
            with state._lock:
                state.prices[symbol] = price
            adv_risk.update_volatility(price)  # [25] EWMA vol update
        except (ccxt.BaseError, OSError, TimeoutError) as ticker_err:
            log.debug(f"Ticker {symbol}: {ticker_err}")
            price = state.prices.get(symbol)
            if price is None:
                continue

        # Re-check: Position könnte zwischen fetch_ticker und jetzt geschlossen worden sein
        with state._lock:
            pos = state.positions.get(symbol)
        if not pos:
            continue

        # Break-Even Stop: SL auf Einstiegspreis (+Puffer) setzen sobald +X% Gewinn
        pos_entry = pos.get("entry") or price
        if pos_entry and pos_entry > 0:
            with state._lock:
                if (
                    CONFIG.get("break_even_enabled")
                    and not pos.get("break_even_set")
                    and (price - pos_entry) / pos_entry >= CONFIG.get("break_even_trigger", 0.015)
                ):
                    be_sl = pos_entry * (1 + CONFIG.get("break_even_buffer", 0.001))
                    if be_sl > pos.get("sl", 0):
                        pos["sl"] = be_sl
                        pos["break_even_set"] = True
                        log.info(
                            f"🔒 Break-Even {symbol}: SL → {be_sl:.4f} "
                            f"(+{CONFIG.get('break_even_buffer', 0.001) * 100:.1f}%)"
                        )

        # Smart Exits: Dynamische SL/TP-Anpassung basierend auf aktueller Volatilität
        if smart_exits.enabled:
            atr_val = pos.get("_last_atr", 0)
            if atr_val <= 0 and pos_entry:
                atr_val = abs(price - pos_entry) * 0.5
            exit_regime = pos.get("exit_regime", "bull" if regime.is_bull else "bear")
            new_smart_sl, new_smart_tp = smart_exits.adapt(symbol, pos, price, atr_val, exit_regime)
            with state._lock:
                if new_smart_sl and new_smart_sl > pos.get("sl", 0):
                    pos["sl"] = new_smart_sl
                if new_smart_tp and new_smart_tp > pos.get("tp", 0):
                    pos["tp"] = new_smart_tp

        # Trailing Stop
        with state._lock:
            if CONFIG.get("trailing_stop") and price > pos.get("highest", price):
                pos["highest"] = price
                new_sl = price * (1 - CONFIG.get("trailing_pct", 0.03))
                if new_sl > pos.get("sl", 0):
                    pos["sl"] = new_sl

        # Partial Take-Profit – pro Level separat prüfen, nicht nur Level 0
        # Jedes Level hat einen eigenen Index. "partial_tp_done" speichert,
        # wie viele Level bereits ausgeführt wurden (0 = noch keins).
        if CONFIG.get("use_partial_tp"):
            levels = CONFIG.get("partial_tp_levels", [])
            levels_done = pos.get("partial_tp_done", 0)
            if levels_done < len(levels):
                level = levels[levels_done]
                pct = level.get("pct", 0)
                sell_ratio = min(
                    level.get("sell_ratio", 0.25), 0.99
                )  # Clamp: nie Full-Close via Partial TP
                if pos_entry and pct > 0 and (price - pos_entry) / pos_entry >= pct:
                    close_position(
                        ex,
                        symbol,
                        f"Partial-TP {pct * 100:.0f}%",
                        partial_ratio=sell_ratio,
                    )
                    # Re-fetch pos – close_position may have removed it
                    with state._lock:
                        pos = state.positions.get(symbol)
                        if not pos:
                            continue
                        pos["partial_tp_done"] = levels_done + 1

        # SL / TP – re-check pos in case partial TP removed it
        with state._lock:
            pos = state.positions.get(symbol)
        if not pos:
            continue
        if price <= pos.get("sl", 0):
            close_position(ex, symbol, "Stop-Loss 🛑")
        elif price >= pos.get("tp", float("inf")):
            close_position(ex, symbol, "Take-Profit 🎯")
        else:
            # ── Selbstlernender Verkauf-Algorithmus ──────────────────────
            scan_for_sell = {
                "price": price,
                "rsi": pos.get("rsi", 50),
                "stoch_rsi": pos.get("stoch_rsi", 50),
                "bb_pct": pos.get("bb_pct", 0.5),
                "vol_ratio": pos.get("vol_ratio", 1.0),
                "ema_alignment": pos.get("ema_alignment", 0),
                "macd_hist_slope": pos.get("macd_hist_slope", 0),
                "roc10": pos.get("roc10", 0),
                "atr_pct": pos.get("atr_pct", 1.0),
                "price_vs_ema21": pos.get("price_vs_ema21", 0),
            }
            algo_sell, algo_conf, algo_reason = trading_algos.evaluate_sell(scan_for_sell, pos)
            if algo_sell:
                # Unrealisierten PnL berechnen für Notification
                _entry = pos.get("entry", 0)
                _unrealized = (price - _entry) * pos.get("qty", 0) if _entry > 0 else None
                discord.algo_sell_signal(symbol, price, algo_conf, algo_reason, pnl=_unrealized)
                telegram.algo_sell_signal(symbol, price, algo_conf, algo_reason, pnl=_unrealized)
                close_position(ex, symbol, f"SellAlgo:{algo_reason}")
            else:
                # DCA prüfen
                try_dca(ex, symbol)


# ═══════════════════════════════════════════════════════════════════════════════
# HEATMAP
# ═══════════════════════════════════════════════════════════════════════════════
_heatmap_cache: list[dict] = []
_heatmap_ts: datetime | None = None
_heatmap_lock = threading.Lock()


def get_heatmap_data(ex) -> list[dict]:
    global _heatmap_cache, _heatmap_ts
    with _heatmap_lock:
        if _heatmap_ts and (datetime.now() - _heatmap_ts).total_seconds() < 90:
            return list(_heatmap_cache)
    try:
        syms = state.markets[:60] if state.markets else []
        # On-demand: Märkte laden falls Bot noch nicht läuft oder Liste leer
        if not syms:
            try:
                fresh = fetch_markets(ex)
                if fresh:
                    with state._lock:
                        state.markets = fresh
                    syms = fresh[:60]
            except Exception as load_err:
                log.debug("Heatmap on-demand market load: %s", load_err)
        if not syms:
            return []
        tickers = safe_fetch_tickers(ex, syms)
        result = []
        for sym, t in tickers.items():
            ns, _, _ = news_fetcher.get_score(sym)
            change = safe_float(t.get("percentage"), 0.0)
            vol = safe_float(t.get("quoteVolume"), 0.0)
            last = safe_float(t.get("last"), 0.0)
            if vol < 0:
                vol = 0.0
            result.append(
                {
                    "symbol": sym,
                    "change": round(change, 2),
                    "volume": round(vol / 1e6, 1),
                    "price": round(last, 4),
                    "in_pos": sym in state.positions,
                    "news_score": round(ns, 2),
                }
            )
        result.sort(key=lambda x: x["change"], reverse=True)
        with _heatmap_lock:
            _heatmap_cache = result
            _heatmap_ts = datetime.now()
        return result
    except Exception as e:
        log.debug(f"Heatmap: {e}")
        return []


# ═══════════════════════════════════════════════════════════════════════════════
# HAUPT BOT LOOP
# ═══════════════════════════════════════════════════════════════════════════════
def _heartbeat_sleep(seconds: float) -> None:
    """Sleep in short chunks while emitting loop heartbeats."""
    heartbeat_sleep(seconds=seconds, state=state, healer=healer)


def bot_loop():
    ex = None
    last_error_emit_ts = 0.0
    while state.running:
        if state.paused:
            _heartbeat_sleep(5)
            continue
        # Auto-Healing: Signal that bot loop is alive
        try:
            healer.heartbeat()
        except Exception:
            pass
        # Exchange-Wechsel erkannt → alte Instanz verwerfen
        if state._exchange_reset:
            log.info("🔄 Exchange-Wechsel erkannt – erstelle neue Verbindung")
            ex = None
            state._exchange_reset = False

        try:
            if ex is None:
                try:
                    ex = create_exchange()
                except Exception as exc_err:
                    log.error(f"Exchange-Verbindung fehlgeschlagen: {exc_err}")
                    now_ts = time.time()
                    if now_ts - last_error_emit_ts > 15:
                        emit_event(
                            "status",
                            {
                                "msg": f"⚠️ Exchange-Verbindung fehlgeschlagen: {str(exc_err)[:140]}",
                                "key": "ws_exchange_connect_failed",
                                "type": "warning",
                            },
                        )
                        state.add_activity(
                            "⚠️",
                            "Exchange-Verbindung fehlgeschlagen",
                            str(exc_err)[:120],
                            "warning",
                        )
                        last_error_emit_ts = now_ts
                    _heartbeat_sleep(30)
                    continue
            with state._lock:
                state.iteration += 1
                state.last_scan = datetime.now().strftime("%H:%M:%S")
                state.next_scan = (
                    datetime.now() + timedelta(seconds=CONFIG.get("scan_interval", 60))
                ).strftime("%H:%M:%S")

            risk.reset_daily(state.balance)
            regime.update(ex)

            # DB-Pool Health Check (alle 10 Iterationen)
            if state.iteration % 10 == 0:
                try:
                    db._check_pool_health()
                except Exception:
                    pass

            # Periodische Updates
            if state.iteration % 30 == 1:
                threading.Thread(target=fg_idx.update, daemon=True).start()
            if state.iteration % 60 == 1:
                threading.Thread(target=dominance.update, daemon=True).start()
                threading.Thread(
                    target=lambda ex=ex: funding_tracker.update(ex), daemon=True
                ).start()
                # Autonome LLM-Analyse: Periodische Marktanalyse
                try:
                    knowledge_base.generate_market_context_async(
                        regime_is_bull=regime.is_bull,
                        fg_value=fg_idx.value,
                        open_positions=len(state.positions),
                        iteration=state.iteration,
                    )
                except Exception:
                    pass  # LLM-Analyse ist optional

            # Positionen verwalten (Long + Short)
            manage_positions(ex)
            short_engine.update_shorts()
            # Grid Trading: update active grids with current prices
            if grid_engine.grids:
                bal_ref = [state.balance]
                for sym, grid in list(grid_engine.grids.items()):
                    if not grid.get("active", False):
                        continue
                    price = state.prices.get(sym)
                    if price is not None:
                        acts = grid_engine.update(sym, price, bal_ref)
                        for act in acts:
                            emit_event(
                                "trade", {**act, "type": act["action"].lower(), "source": "grid"}
                            )
                with state._lock:
                    state.balance = bal_ref[0]
            price_alerts.check(state.prices)

            # Anomalie global prüfen
            if anomaly.is_anomaly:
                emit_event("update", state.snapshot())
                _heartbeat_sleep(CONFIG.get("scan_interval", 60))
                continue

            # Märkte laden
            if state.iteration % 10 == 1 or not state.markets:
                new_markets = fetch_markets(ex)
                if new_markets:
                    with state._lock:
                        state.markets = new_markets
                else:
                    now_ts = time.time()
                    if now_ts - last_error_emit_ts > 15:
                        if state.markets:
                            emit_event(
                                "status",
                                {
                                    "msg": "⚠️ Keine frischen Märkte geladen – nutze letzte Marktliste",
                                    "key": "ws_no_markets_loaded",
                                    "type": "warning",
                                },
                            )
                            state.add_activity(
                                "⚠️",
                                "Keine frischen Märkte geladen",
                                "Fallback auf gecachte Marktliste aktiv",
                                "warning",
                            )
                        else:
                            # Letzter Fallback: persistenten Disk-Cache prüfen
                            disk_fb = _load_market_cache()
                            if disk_fb:
                                with state._lock:
                                    state.markets = disk_fb
                                emit_event(
                                    "status",
                                    {
                                        "msg": (
                                            "⚠️ Exchange nicht erreichbar – "
                                            f"nutze persistenten Cache ({len(disk_fb)} Märkte)"
                                        ),
                                        "key": "ws_markets_disk_cache",
                                        "type": "warning",
                                    },
                                )
                                state.add_activity(
                                    "⚠️",
                                    "Persistenter Markt-Cache geladen",
                                    f"{len(disk_fb)} Märkte aus Disk-Cache",
                                    "warning",
                                )
                            else:
                                emit_event(
                                    "status",
                                    {
                                        "msg": "❌ Keine Märkte verfügbar – Exchange nicht erreichbar",
                                        "key": "ws_no_markets_available",
                                        "type": "error",
                                    },
                                )
                                state.add_activity(
                                    "❌",
                                    "Keine Märkte verfügbar",
                                    "Exchange nicht erreichbar – kein Cache vorhanden",
                                    "error",
                                )
                        last_error_emit_ts = now_ts

            # Arbitrage
            if state.iteration % 5 == 1 and CONFIG.get("use_arbitrage"):
                threading.Thread(
                    target=lambda m=state.markets[:30]: arb_scanner.scan(m), daemon=True
                ).start()

            # Portfolio History
            pv = state.portfolio_value()
            with state._lock:
                state.portfolio_history.append(
                    {"time": datetime.now().strftime("%H:%M"), "value": round(pv, 2)}
                )

            # Short-Signale – parallelisiert mit ThreadPoolExecutor
            if not regime.is_bull and CONFIG.get("use_shorts"):
                short_candidates = [
                    sym
                    for sym in state.markets[:20]
                    if sym not in state.short_positions
                    and sym not in state.positions
                    and not funding_tracker.is_short_too_expensive(sym)
                ]
                if short_candidates:
                    with ThreadPoolExecutor(max_workers=CONFIG.get("max_workers", 4)) as short_pool:
                        short_futures = {
                            short_pool.submit(scan_symbol, ex, sym): sym for sym in short_candidates
                        }
                        for fut in as_completed(short_futures):
                            try:
                                scan = fut.result()
                                if (
                                    scan
                                    and scan["signal"] == -1
                                    and scan.get("confidence", 0)
                                    >= CONFIG.get("min_vote_score", 0.3)
                                ):
                                    discord.signal_opportunity(
                                        scan["symbol"],
                                        "sell",
                                        float(scan.get("confidence", 0.0)),
                                        float(scan.get("price", 0.0)),
                                        news_score=float(scan.get("news_score", 0.0)),
                                        note="Short-Kandidat erkannt (Signal -1)",
                                    )
                                    invest = state.balance * CONFIG.get("risk_per_trade", 0.015)
                                    short_engine.open_short(scan["symbol"], invest, scan["price"])
                            except Exception as se:
                                log.debug(f"Short-Scan: {se}")

            # Long-Signale
            if (
                len(state.positions) < CONFIG.get("max_open_trades", 5)
                and not risk.daily_loss_exceeded(state.balance)
                and not risk.circuit_breaker_active()
            ):
                with ThreadPoolExecutor(max_workers=CONFIG.get("max_workers", 4)) as pool:
                    futures = {
                        pool.submit(scan_symbol, ex, s): s
                        for s in state.markets
                        if s not in state.positions
                    }
                    for fut in as_completed(futures):
                        try:
                            res = fut.result()
                        except Exception as scan_err:
                            log.debug(f"Scan-Future: {scan_err}")
                            continue
                        if res and res["signal"] == 1:
                            discord.signal_opportunity(
                                res["symbol"],
                                "buy",
                                float(res.get("confidence", 0.0)),
                                float(res.get("price", 0.0)),
                                news_score=float(res.get("news_score", 0.0)),
                                note=res.get("mtf_desc", "") or "Long-Kandidat erkannt (Signal +1)",
                            )
                            # Re-check max_open_trades to prevent exceeding limit
                            if len(state.positions) >= CONFIG.get("max_open_trades", 5):
                                continue
                            state.add_signal(
                                {
                                    "symbol": res["symbol"],
                                    "signal": "KAUF",
                                    "confidence": res["confidence"],
                                    "rsi": res["rsi"],
                                    "price": res["price"],
                                    "time": res["time"],
                                    "votes": res["votes"],
                                    "mtf_desc": res.get("mtf_desc", ""),
                                    "news_score": res.get("news_score", 0),
                                    "news_headline": res.get("news_headline", ""),
                                    "onchain_detail": res.get("onchain_detail", ""),
                                }
                            )
                            open_position(ex, res)

            emit_event("update", state.snapshot())

            # Autonomous agent updates (every 10 iterations)
            if state.iteration % 10 == 0:
                try:
                    emit_event("healing_update", healer.health_snapshot())
                except Exception:
                    pass
                try:
                    emit_event("revenue_update", revenue_tracker.snapshot())
                except Exception:
                    pass
                try:
                    emit_event("cluster_update", cluster_ctrl.snapshot())
                except Exception:
                    pass
                # Auto-resolve stale alerts
                try:
                    alert_escalation.auto_resolve_stale()
                except Exception:
                    pass

        # [Verbesserung #5] Differenzierte ccxt-Fehlerbehandlung
        except ccxt.RateLimitExceeded as e:
            log.warning(f"Rate-Limit: {e} – warte 60s")
            _heartbeat_sleep(60)
        except ccxt.ExchangeNotAvailable as e:
            log.warning(f"Exchange nicht verfügbar: {e} – warte 120s, Circuit Breaker")
            ex = None
            risk.record_result(False)  # Zählt als Verlust für Circuit Breaker
            _heartbeat_sleep(120)
        except ccxt.NetworkError as e:
            log.warning(f"Netzwerkfehler: {e} – reconnect in 15s")
            ex = None
            _heartbeat_sleep(15)
        except ccxt.ExchangeError as e:
            log.error(f"Exchange-Fehler: {e}")
            discord.error(f"Exchange-Fehler:\n{str(e)[:200]}")
            emit_event(
                "status",
                {
                    "msg": f"❌ Exchange-Fehler: {str(e)[:140]}",
                    "key": "ws_exchange_error",
                    "type": "error",
                },
            )
            _heartbeat_sleep(30)
        except Exception as e:
            log.error(f"Bot-Loop: {e}", exc_info=True)
            discord.error(f"Loop:\n{traceback.format_exc()[:300]}")
            emit_event(
                "status",
                {
                    "msg": f"❌ Bot-Loop Fehler: {str(e)[:140]}",
                    "key": "ws_bot_loop_error",
                    "type": "error",
                },
            )
            _heartbeat_sleep(10)
        _heartbeat_sleep(CONFIG.get("scan_interval", 60))


def fetch_aggregated_balance() -> dict:
    """[#32] Aggregiert Balance über alle konfigurierten Exchanges.

    Verbindet sich mit der Haupt-Exchange sowie allen in ``arb_exchanges``
    konfigurierten Exchanges und summiert USDT-Guthaben und Coin-Bestände.

    Returns:
        Dict mit ``total_usdt``, ``by_exchange`` und ``errors``.
    """
    result: dict = {"total_usdt": 0.0, "by_exchange": {}, "errors": []}
    if CONFIG["paper_trading"]:
        result["total_usdt"] = state.balance
        result["by_exchange"]["paper"] = {"USDT": state.balance}
        return result

    exchanges_to_check = {CONFIG.get("exchange", "cryptocom"): create_exchange()}
    for ex_id in CONFIG.get("arb_exchanges", []):
        try:
            keys = CONFIG.get("arb_api_keys", {}).get(ex_id, {})
            ex_cls = getattr(ccxt, EXCHANGE_MAP.get(ex_id, ex_id), None)
            if ex_cls is None:
                result["errors"].append(f"{ex_id}: Exchange class not found")
                continue
            exchanges_to_check[ex_id] = ex_cls(
                {
                    "apiKey": keys.get("apiKey", ""),
                    "secret": keys.get("secret", ""),
                    "enableRateLimit": True,
                }
            )
        except Exception as e:
            result["errors"].append(f"{ex_id}: {e}")

    for ex_id, ex in exchanges_to_check.items():
        try:
            bal = ex.fetch_balance()
            totals = {}
            for k, v in bal.get("total", {}).items():
                fv = safe_float(v, 0.0)
                if fv > 0:
                    totals[k] = fv
            result["by_exchange"][ex_id] = totals
            # USDT direkt + Schätzung via last price für andere Coins
            usdt = totals.get(CONFIG.get("quote_currency", "USDT"), 0.0)
            result["total_usdt"] += usdt
        except Exception as e:
            result["errors"].append(f"{ex_id}: {e}")

    return result


def safety_scan():
    """Prüft beim Start ob unbekannte Positionen auf Exchange sind."""
    if CONFIG["paper_trading"]:
        return
    try:
        ex = create_exchange()
        bal = ex.fetch_balance()
        suspicious = []
        for coin, details in bal.get("total", {}).items():
            if coin == CONFIG["quote_currency"] or float(details or 0) <= 0.001:
                continue
            sym = f"{coin}/{CONFIG['quote_currency']}"
            if sym not in state.positions:
                suspicious.append(f"{coin}: {float(details or 0):.4f}")
        if suspicious:
            msg = "⚠️ Unbekannte Positionen:\n" + "\n".join(suspicious)
            discord.error(msg)
            log.warning(msg)
    except Exception as e:
        log.debug(f"Safety-Scan: {e}")
