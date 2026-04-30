"""Trading Blueprint – alle Kern-Trading-Routen.

Enthält: State, Trades, Positionen, Bot-Steuerung, Backtest, Steuer,
User-Settings, Exchange-Verwaltung, Signale, Grid, Kühlzeiten.
"""

from __future__ import annotations

import re
import threading
import time
from datetime import datetime
from typing import TYPE_CHECKING

from flask import Blueprint, jsonify, request, session
from pydantic import BaseModel, ValidationError, field_validator

if TYPE_CHECKING:
    from routes.api.deps import AppDeps

# ── Constants ─────────────────────────────────────────────────────────────────

_SYMBOL_RE = re.compile(r"^[A-Z0-9]{1,15}/[A-Z0-9]{1,15}$")
MAX_GRID_LEVELS = 200
_MIN_CELL_USDT = 5.0


def _valid_symbol(sym: str) -> bool:
    return bool(_SYMBOL_RE.match(sym))


# ── Pydantic validation models ────────────────────────────────────────────────

_VALID_EXCHANGES: frozenset[str] = frozenset(
    {
        "cryptocom",
        "binance",
        "bybit",
        "okx",
        "kucoin",
        "kraken",
        "huobi",
        "coinbase",
        "bitget",
        "mexc",
        "gateio",
        "nonkyc",
    }
)


class ExchangeUpsertRequest(BaseModel):
    """Validated request body for POST /api/v1/user/exchanges."""

    exchange: str
    api_key: str = ""
    api_secret: str = ""
    passphrase: str = ""
    enabled: bool = False
    is_primary: bool = False

    @field_validator("exchange")
    @classmethod
    def validate_exchange(cls, v: str) -> str:
        v = v.strip().lower()
        if v not in _VALID_EXCHANGES:
            raise ValueError(f"Nicht unterstützte Exchange: '{v}'")
        return v

    @field_validator("api_key", "api_secret", "passphrase")
    @classmethod
    def strip_str(cls, v: str) -> str:
        return v.strip()


class TradingModeRequest(BaseModel):
    """Validated request body for POST /api/v1/trading/mode."""

    mode: str

    @field_validator("mode")
    @classmethod
    def validate_mode(cls, v: str) -> str:
        v = v.strip().lower()
        if v not in ("paper", "live"):
            raise ValueError("mode muss 'paper' oder 'live' sein")
        return v


def create_trading_blueprint(deps: AppDeps) -> Blueprint:
    """Erstellt den Trading-Blueprint mit allen Routen."""
    bp = Blueprint("api_trading", __name__)

    cfg = deps.config
    st = deps.state
    db = deps.db
    log = deps.log
    auth = deps.api_auth_required
    admin = deps.admin_required
    body = deps.get_json_body
    si = deps.safe_int
    sf = deps.safe_float
    sb = deps.safe_bool
    norm_ex = deps.normalize_exchange_name
    audit = deps.audit_fn

    # ── State ─────────────────────────────────────────────────────────────────

    @bp.route("/api/v1/state")
    @auth
    def api_state():
        snap = st.snapshot()
        snap["user_role"] = session.get("user_role", "user")
        if deps.get_llm_header_status_fn:
            snap["llm"] = deps.get_llm_header_status_fn()
        return jsonify(snap)

    @bp.route("/api/v1/trades")
    @auth
    def api_trades():
        limit = min(si(request.args.get("limit", 100), 100), 1000)
        symbol = request.args.get("symbol")
        year = request.args.get("year")
        return jsonify(
            db.load_trades(limit=limit, symbol=symbol, year=year, user_id=request.user_id)
        )

    @bp.route("/api/v1/heatmap")
    @auth
    def api_heatmap_v1():
        try:
            ex = deps.create_exchange()
            return jsonify(deps.get_heatmap_data(ex))
        except Exception as e:
            log.error("API error: %s", e)
            return jsonify({"error": "Internal server error"}), 500

    @bp.route("/api/v1/backtest", methods=["POST"])
    @auth
    def api_backtest():
        data = body()
        try:
            ex = deps.create_exchange()
            result = deps.backtest.run(
                ex,
                data.get("symbol", "BTC/USDT"),
                data.get("timeframe", "1h"),
                min(si(data.get("candles", 500), 500), 5000),
                sf(data.get("sl", cfg.get("stop_loss_pct", 0.025)), cfg.get("stop_loss_pct", 0.025)),
                sf(data.get("tp", cfg.get("take_profit_pct", 0.060)), cfg.get("take_profit_pct", 0.060)),
                sf(
                    data.get("vote", cfg.get("min_vote_score", 0.3)), cfg.get("min_vote_score", 0.3)
                ),
            )
            return jsonify(result)
        except Exception as e:
            log.error("API error: %s", e)
            return jsonify({"error": "Internal server error"}), 500

    @bp.route("/api/v1/tax")
    @auth
    def api_tax_v1():
        year = si(request.args.get("year", datetime.now().year), datetime.now().year)
        method = request.args.get("method", "fifo")
        trades = db.load_trades(limit=10000, year=year, user_id=request.user_id)
        return jsonify(deps.tax_report.generate(trades, year, method))

    @bp.route("/api/v1/token", methods=["POST"])
    @auth
    def api_create_token():
        label = body().get("label", "api")
        token = db.create_api_token(request.user_id, label)
        return jsonify({"token": token, "expires_hours": cfg["jwt_expiry_hours"]})

    @bp.route("/api/v1/token/<int:token_id>", methods=["DELETE"])
    @auth
    def api_revoke_token(token_id):
        try:
            with db._get_conn() as conn:
                with conn.cursor() as c:
                    c.execute(
                        "UPDATE api_tokens SET active=0 WHERE id=%s AND user_id=%s",
                        (token_id, request.user_id),
                    )
            if audit:
                audit("token_revoked", f"token_id={token_id}", request.user_id)
            return jsonify({"success": True})
        except Exception as e:
            log.error("API error: %s", e)
            return jsonify({"error": "Internal server error"}), 500

    # ── User Settings ─────────────────────────────────────────────────────────

    @bp.route("/api/v1/user/settings")
    @auth
    def api_user_settings_get():
        settings = db.get_user_settings(request.user_id)
        settings["paper_trading"] = cfg.get("paper_trading", True)
        settings["trade_mode"] = "paper" if cfg.get("paper_trading", True) else "live"
        return jsonify(settings)

    # ── Onboarding / Setup-State (per User, geräteübergreifend) ───────────────

    @bp.route("/api/v1/user/setup-state")
    @auth
    def api_user_setup_state_get():
        """Liefert Onboarding-Flags pro User.

        Wird beim Dashboard-Load aufgerufen, um zu entscheiden ob der
        Wizard angezeigt werden muss. Antwortet auch dann definiert,
        wenn der User noch keine Settings hat.
        """
        settings = db.get_user_settings(request.user_id) or {}
        return jsonify(
            {
                "wizard_completed": bool(settings.get("wizard_completed", False)),
                "wizard_completed_at": settings.get("wizard_completed_at") or None,
                "has_configured_exchange": any(
                    bool(ex.get("has_key")) for ex in (db.get_user_exchanges(request.user_id) or [])
                ),
            }
        )

    @bp.route("/api/v1/user/setup-state", methods=["POST"])
    @auth
    def api_user_setup_state_update():
        """Persistiert Onboarding-Flags pro User (aktuell nur wizard_completed).

        Server-seitige Speicherung, damit das Setup nur einmal pro Account
        durchlaufen werden muss – auch wenn der User auf einem neuen Gerät
        einloggt (vorher in localStorage gespeichert → pro Browser).
        """
        from datetime import datetime as _dt

        data = body() or {}
        completed = sb(data.get("wizard_completed", False), False)
        current = db.get_user_settings(request.user_id) or {}
        current["wizard_completed"] = bool(completed)
        if completed:
            current["wizard_completed_at"] = _dt.now().isoformat()
        ok = db.update_user_settings(request.user_id, current)
        if audit:
            audit(
                "setup_state_updated",
                f"wizard_completed={completed}",
                request.user_id,
            )
        return jsonify({"ok": ok, "wizard_completed": bool(completed)})

    @bp.route("/api/v1/user/settings", methods=["POST"])
    @auth
    def api_user_settings_update():
        data = body()
        _ALLOWED = {
            "paper_trading",
            "paper_balance",
            "risk_per_trade",
            "stop_loss_pct",
            "take_profit_pct",
            "max_open_trades",
            "scan_interval",
            "timeframe",
            "use_dca",
            "dca_drop_pct",
            "dca_max_levels",
            "use_partial_tp",
            "trailing_stop",
            "trailing_pct",
            "break_even_enabled",
            "break_even_trigger",
            "break_even_buffer",
            "use_fear_greed",
            "use_sentiment",
            "use_news",
            "use_anomaly",
            "use_market_regime",
            "ai_enabled",
            "ai_min_confidence",
            "virginie_enabled",
            "virginie_primary_control",
            "virginie_autonomy_weight",
            "virginie_min_score",
            "virginie_max_risk_penalty",
            "virginie_cpu_fast_chat",
            "discord_webhook",
            "discord_on_buy",
            "discord_on_sell",
            "telegram_token",
            "telegram_chat_id",
            "portfolio_goal",
            "language",
            "max_daily_loss_pct",
        }
        filtered = {k: v for k, v in data.items() if k in _ALLOWED}
        current = db.get_user_settings(request.user_id)
        current.update(filtered)
        if "paper_trading" in filtered:
            mode = "paper" if sb(filtered.get("paper_trading", True), True) else "live"
            if deps.trade_mode:
                deps.trade_mode.set_mode(mode)
            cfg["paper_trading"] = mode == "paper"
        current["paper_trading"] = cfg.get("paper_trading", True)
        ok = db.update_user_settings(request.user_id, current)
        return jsonify({"ok": ok, "updated": list(filtered.keys())})

    # ── Trading Control ───────────────────────────────────────────────────────

    @bp.route("/api/v1/trading/mode", methods=["GET", "POST"])
    @auth
    def api_trading_mode():
        if request.method == "GET":
            return jsonify(deps.trade_mode.status())
        uid = getattr(request, "user_id", None)
        user = db.get_user_by_id(uid) if uid else None
        if not user or user.get("role") != "admin":
            return jsonify({"error": "Nur Admin darf den Trading-Modus wechseln"}), 403
        try:
            req = TradingModeRequest.model_validate(body())
        except ValidationError as ve:
            return jsonify({"error": ve.errors()[0]["msg"]}), 400
        new_mode = deps.trade_mode.set_mode(req.mode)
        cfg["paper_trading"] = new_mode != "live"
        st.add_activity("🧭", "Trading-Modus", new_mode.upper(), "info")
        if deps.discord:
            deps.discord.info(f"Trading-Modus gewechselt: {new_mode.upper()}")
        if deps.telegram:
            deps.telegram.info(f"Trading-Modus gewechselt: {new_mode.upper()}")
        return jsonify(deps.trade_mode.status())

    @bp.route("/api/v1/trading/control", methods=["POST"])
    @auth
    def api_trading_control():
        data = body()
        action = str(data.get("action", "start")).lower()
        if action == "start":
            if deps.trade_mode:
                deps.trade_mode.set_enabled(True)
            bot_loop_fn = deps.bot_loop_fn or (
                deps.trading_ops_mod.bot_loop if deps.trading_ops_mod else None
            )
            with st._lock:
                st.running = True
                st.paused = False
                if bot_loop_fn and not any(
                    t.name == "BotLoop" and t.is_alive() for t in threading.enumerate()
                ):
                    threading.Thread(target=bot_loop_fn, daemon=True, name="BotLoop").start()
            return jsonify({"ok": True, "running": True})
        if action == "stop":
            if deps.trade_mode:
                deps.trade_mode.set_enabled(False)
            with st._lock:
                st.running = False
                st.paused = False
            return jsonify({"ok": True, "running": False})
        return jsonify({"error": "action must be start|stop"}), 400

    @bp.route("/api/v1/trading/close-position", methods=["POST"])
    @auth
    def api_trading_close_position():
        data = body()
        sym = str(data.get("symbol", "")).strip().upper()
        if not sym:
            return jsonify({"error": "symbol required"}), 400
        if not _valid_symbol(sym):
            return jsonify({"error": "invalid_symbol"}), 400
        with st._lock:
            in_long = sym in st.positions
            in_short = sym in st.short_positions
        if not in_long and not in_short:
            return jsonify({"error": f"position not open: {sym}"}), 404
        try:
            if in_long:
                ex = deps.create_exchange()
                deps.close_position(ex, sym, "Manuell geschlossen 🖐")
                return jsonify({"ok": True, "symbol": sym, "side": "long"})
            deps.short_engine.close_short(sym, "Manuell 🖐")
            return jsonify({"ok": True, "symbol": sym, "side": "short"})
        except Exception as e:
            log.warning("api_trading_close_position failed: %s", e)
            return jsonify({"error": "close_position_failed"}), 500

    @bp.route("/api/v1/trading/buy", methods=["POST"])
    @auth
    def api_trading_manual_buy():
        """Manueller Kauf eines beliebigen Symbols (Altcoin oder Stablecoin)."""
        data = body()
        sym = str(data.get("symbol", "")).strip().upper()
        invest = sf(data.get("invest_usdt", 0.0), 0.0)
        if not sym:
            return jsonify({"error": "symbol required"}), 400
        if not _valid_symbol(sym):
            return jsonify({"error": "invalid_symbol"}), 400
        if invest <= 0:
            return jsonify({"error": "invest_usdt must be > 0"}), 400
        try:
            ex = deps.create_exchange()
            ticker = ex.fetch_ticker(sym)
            price = float(ticker.get("last") or ticker.get("ask") or 0)
            if price <= 0:
                return jsonify({"error": "Preis konnte nicht ermittelt werden"}), 502
            trade_exec = deps.trading_ops_mod.trade_execution if deps.trading_ops_mod else None
            if trade_exec is None:
                return jsonify({"error": "TradeExecutionService nicht verfügbar"}), 503
            result = trade_exec.execute_buy(ex, symbol=sym, price=price, invest_usdt=invest)
            if result.ok:
                with st._lock:
                    if sym not in st.positions:
                        st.positions[sym] = {
                            "symbol": sym,
                            "entry": price,
                            "qty": result.meta.get("qty", 0) if result.meta else 0,
                            "invested": invest,
                            "sl": price * (1 - cfg.get("stop_loss_pct", 0.025)),
                            "tp": price * (1 + cfg.get("take_profit_pct", 0.060)),
                            "highest": price,
                            "manual": True,
                            "trade_mode": "paper" if cfg.get("paper_trading", True) else "live",
                            "opened": datetime.now().isoformat(),
                            "opened_ts": time.time(),
                            "observed_ticks": 0,
                            "peak_price": price,
                            "trough_price": price,
                        }
                log.info("Manueller Kauf: %s @ %.4f invest=%.2f", sym, price, invest)
                return jsonify({"ok": True, "symbol": sym, "price": price, "mode": result.mode})
            return jsonify({"ok": False, "error": result.reason}), 400
        except Exception as e:
            log.warning("api_trading_manual_buy: %s", e)
            return jsonify({"error": "manual_buy_failed"}), 500

    @bp.route("/api/v1/trading/sell", methods=["POST"])
    @auth
    def api_trading_manual_sell():
        """Manueller Verkauf einer offenen Position (Altcoin oder Stablecoin)."""
        data = body()
        sym = str(data.get("symbol", "")).strip().upper()
        if not sym:
            return jsonify({"error": "symbol required"}), 400
        if not _valid_symbol(sym):
            return jsonify({"error": "invalid_symbol"}), 400
        with st._lock:
            pos = st.positions.get(sym)
        if not pos:
            return jsonify({"error": f"Keine offene Position für {sym}"}), 404
        try:
            ex = deps.create_exchange()
            deps.close_position(ex, sym, "Manuell verkauft")
            log.info("Manueller Verkauf: %s", sym)
            return jsonify({"ok": True, "symbol": sym})
        except Exception as e:
            log.warning("api_trading_manual_sell: %s", e)
            return jsonify({"error": "manual_sell_failed"}), 500

    # ── Offene & Geschlossene Positionen ─────────────────────────────────────

    @bp.route("/api/v1/trading/open-positions")
    @auth
    def api_open_positions():
        try:
            in_memory = st.snapshot().get("positions", [])
            if in_memory:
                return jsonify({"positions": in_memory})
            mode = request.args.get("mode")
            db_positions = (
                db.load_open_positions(user_id=request.user_id, trade_mode=mode)
                if hasattr(db, "load_open_positions")
                else []
            )
            return jsonify({"positions": db_positions})
        except Exception as e:
            log.warning("api_open_positions: %s", e)
            return jsonify({"positions": [], "error": "temporarily_unavailable"}), 503

    @bp.route("/api/v1/trading/closed-trades")
    @auth
    def api_closed_trades():
        try:
            limit = min(si(request.args.get("limit", 150), 150), 500)
            mode = request.args.get("mode")
            rows = db.load_trades(limit=limit, user_id=request.user_id)
            if mode in {"paper", "live"}:
                rows = [r for r in rows if str(r.get("trade_mode", "paper")) == mode]
            return jsonify({"trades": rows})
        except Exception as e:
            log.warning("api_closed_trades: %s", e)
            return jsonify({"trades": [], "error": "temporarily_unavailable"}), 503

    @bp.route("/api/v1/trading/order-history")
    @auth
    def api_order_history():
        try:
            limit = min(si(request.args.get("limit", 150), 150), 500)
            mode = request.args.get("mode")
            return jsonify(
                {"orders": db.load_orders(limit=limit, user_id=request.user_id, trade_mode=mode)}
            )
        except Exception as e:
            log.warning("api_order_history: %s", e)
            return jsonify({"orders": [], "error": "temporarily_unavailable"}), 503

    @bp.route("/api/v1/trading/signal-history")
    @auth
    def api_signal_history():
        try:
            return jsonify({"signals": list(st.signal_log)[:200]})
        except Exception as e:
            log.warning("api_signal_history: %s", e)
            return jsonify({"signals": [], "error": "temporarily_unavailable"}), 503

    @bp.route("/api/v1/trading/decision-history")
    @auth
    def api_decision_history():
        try:
            limit = min(si(request.args.get("limit", 150), 150), 500)
            mode = request.args.get("mode")
            return jsonify(
                {
                    "decisions": db.load_trade_decisions(
                        limit=limit, user_id=request.user_id, trade_mode=mode
                    )
                }
            )
        except Exception as e:
            log.warning("api_decision_history: %s", e)
            return jsonify({"decisions": [], "error": "temporarily_unavailable"}), 503

    @bp.route("/api/v1/trading/performance")
    @auth
    def api_trading_performance():
        try:
            return jsonify(db.performance_breakdown(user_id=request.user_id))
        except Exception as e:
            log.warning("api_trading_performance: %s", e)
            return jsonify(
                {
                    "by_mode": [],
                    "by_exchange": [],
                    "by_strategy": [],
                    "error": "temporarily_unavailable",
                }
            ), 503

    # ── User Exchange Management ──────────────────────────────────────────────

    @bp.route("/api/v1/user/exchanges")
    @auth
    def api_user_exchanges_list():
        return jsonify(db.get_user_exchanges(request.user_id))

    @bp.route("/api/v1/user/exchanges", methods=["POST"])
    @auth
    def api_user_exchanges_upsert():
        try:
            req = ExchangeUpsertRequest.model_validate(body())
        except ValidationError as ve:
            return jsonify({"error": ve.errors()[0]["msg"]}), 400
        requires_keys = not bool(cfg.get("paper_trading", True))
        if requires_keys and (not req.api_key or not req.api_secret):
            return jsonify({"error": "api_key und api_secret sind Pflichtfelder"}), 400
        ok = db.upsert_user_exchange(
            request.user_id,
            req.exchange,
            req.api_key,
            req.api_secret,
            req.enabled,
            req.is_primary,
            passphrase=req.passphrase,
        )
        if audit:
            audit(
                "exchange_upsert",
                f"Exchange: {req.exchange}, enabled: {req.enabled}",
                request.user_id,
            )
        auto_started = False
        if ok and req.enabled and deps.maybe_auto_start_bot_fn:
            auto_started = deps.maybe_auto_start_bot_fn()
        return jsonify({"ok": ok, "bot_auto_started": auto_started})

    @bp.route("/api/v1/user/exchanges/<int:exchange_id>/toggle", methods=["POST"])
    @auth
    def api_user_exchange_toggle(exchange_id):
        enabled = sb(body().get("enabled", False), False)
        ok = db.toggle_user_exchange(request.user_id, exchange_id, enabled)
        auto_started = False
        if ok and enabled and deps.maybe_auto_start_bot_fn:
            auto_started = deps.maybe_auto_start_bot_fn()
        # Balance-Cache invalidieren, damit UI frische Daten liefert.
        try:
            from routes.api.market import invalidate_balance_cache

            invalidate_balance_cache(request.user_id)
        except Exception:  # pragma: no cover – Cache-Invalidierung ist best-effort
            pass
        return jsonify({"ok": ok, "bot_auto_started": auto_started})

    @bp.route("/api/v1/user/exchanges/<int:exchange_id>", methods=["DELETE"])
    @auth
    def api_user_exchange_delete(exchange_id):
        ok = db.delete_user_exchange(request.user_id, exchange_id)
        try:
            from routes.api.market import invalidate_balance_cache

            invalidate_balance_cache(request.user_id)
        except Exception:  # pragma: no cover
            pass
        return jsonify({"ok": ok})

    def _resolve_exchange_id(user_id: int, name: str) -> int | None:
        """Findet die user_exchanges.id anhand des Exchange-Namens."""
        for row in db.get_user_exchanges(user_id) or []:
            if str(row.get("exchange", "")).lower() == name:
                try:
                    return int(row.get("id") or 0) or None
                except (TypeError, ValueError):
                    return None
        return None

    @bp.route("/api/v1/user/exchanges/<exchange>/toggle", methods=["POST"])
    @auth
    def api_user_exchange_toggle_by_name(exchange):
        """Enable/disable eine Exchange per Name (für die Dashboard-UI)."""
        name = (norm_ex(exchange) if norm_ex else str(exchange).strip().lower()) or ""
        if name not in _VALID_EXCHANGES:
            return jsonify({"error": "Ungültige Exchange"}), 400
        ex_id = _resolve_exchange_id(request.user_id, name)
        if ex_id is None:
            return jsonify({"error": "Exchange nicht konfiguriert"}), 404
        enabled = sb(body().get("enabled", False), False)
        ok = db.toggle_user_exchange(request.user_id, ex_id, enabled)
        auto_started = False
        if ok and enabled and deps.maybe_auto_start_bot_fn:
            auto_started = deps.maybe_auto_start_bot_fn()
        if audit:
            audit(
                "exchange_toggle",
                f"Exchange: {name}, enabled: {enabled}",
                request.user_id,
            )
        try:
            from routes.api.market import invalidate_balance_cache

            invalidate_balance_cache(request.user_id, name)
        except Exception:  # pragma: no cover
            pass
        return jsonify({"ok": ok, "enabled": enabled, "bot_auto_started": auto_started})

    @bp.route("/api/v1/user/exchanges/<exchange>/primary", methods=["POST"])
    @auth
    def api_user_exchange_set_primary(exchange):
        """Setzt eine Exchange als primary – diese wird vom Bot als Main-Exchange genutzt."""
        name = (norm_ex(exchange) if norm_ex else str(exchange).strip().lower()) or ""
        if name not in _VALID_EXCHANGES:
            return jsonify({"error": "Ungültige Exchange"}), 400
        ok = db.set_primary_exchange(request.user_id, name, enable=True)
        if not ok:
            return jsonify({"error": "Exchange nicht konfiguriert"}), 404
        if audit:
            audit("exchange_set_primary", f"Exchange: {name}", request.user_id)
        # Primary-Wechsel kann neue Bot-Runtime erfordern → CONFIG updaten
        try:
            if deps.pin_user_exchange:
                deps.pin_user_exchange(request.user_id, name)
        except Exception as exc:  # pragma: no cover
            log.debug("pin_user_exchange nach primary-Wechsel: %s", exc)
        try:
            from routes.api.market import invalidate_balance_cache

            invalidate_balance_cache(request.user_id)
        except Exception:  # pragma: no cover
            pass
        return jsonify({"ok": True, "primary": name})

    @bp.route("/api/v1/user/exchanges/<exchange>", methods=["DELETE"])
    @auth
    def api_user_exchange_delete_by_name(exchange):
        """Entfernt eine Exchange-Konfiguration per Name."""
        name = (norm_ex(exchange) if norm_ex else str(exchange).strip().lower()) or ""
        if name not in _VALID_EXCHANGES:
            return jsonify({"error": "Ungültige Exchange"}), 400
        ex_id = _resolve_exchange_id(request.user_id, name)
        if ex_id is None:
            return jsonify({"error": "Exchange nicht konfiguriert"}), 404
        ok = db.delete_user_exchange(request.user_id, ex_id)
        if audit:
            audit("exchange_delete", f"Exchange: {name}", request.user_id)
        try:
            from routes.api.market import invalidate_balance_cache

            invalidate_balance_cache(request.user_id, name)
        except Exception:  # pragma: no cover
            pass
        return jsonify({"ok": ok})

    @bp.route("/api/v1/user/exchanges/<exchange>/balance")
    @auth
    def api_user_exchange_balance(exchange):
        """Liefert eine frisch aktualisierte Balance für eine einzelne Exchange."""
        name = (norm_ex(exchange) if norm_ex else str(exchange).strip().lower()) or ""
        if name not in _VALID_EXCHANGES:
            return jsonify({"error": "Ungültige Exchange"}), 400
        enabled_rows = {
            str(r.get("exchange", "")).lower(): r
            for r in db.get_enabled_exchanges(request.user_id) or []
        }
        ex_row = enabled_rows.get(name)
        if not ex_row:
            return jsonify({"error": "Exchange nicht aktiviert"}), 404
        from routes.api.market import _get_balance_snapshot

        force = str(request.args.get("refresh", "1")).lower() in ("1", "true", "yes")
        paper = bool(cfg.get("paper_trading", True))
        quote = str(cfg.get("quote_currency", "USDT")).upper()
        snap = _get_balance_snapshot(
            request.user_id, ex_row, quote, paper, log, force_refresh=force
        )
        snap["exchange"] = name
        return jsonify(snap)

    @bp.route("/api/v1/user/exchanges/<exchange>/test", methods=["POST"])
    @auth
    def api_user_exchange_test(exchange):
        """Testet die Konnektivität einer Exchange unabhängig vom laufenden Bot."""
        import time as _time

        name = (norm_ex(exchange) if norm_ex else str(exchange).strip().lower()) or ""
        if name not in _VALID_EXCHANGES:
            return jsonify({"ok": False, "error": "Ungültige Exchange"}), 400
        enabled_rows = {
            str(r.get("exchange", "")).lower(): r
            for r in db.get_enabled_exchanges(request.user_id) or []
        }
        ex_row = enabled_rows.get(name)
        if not ex_row:
            return jsonify(
                {"ok": False, "error": "Exchange nicht konfiguriert oder deaktiviert"}
            ), 404
        from services.exchange_factory import create_ccxt_exchange

        paper = bool(cfg.get("paper_trading", True))
        api_key = ex_row.get("api_key", "") if not paper else ""
        api_secret = ex_row.get("api_secret", "") if not paper else ""
        passphrase = ex_row.get("passphrase", "") if not paper else ""
        t0 = _time.monotonic()
        try:
            inst = create_ccxt_exchange(
                name, api_key=api_key, api_secret=api_secret, passphrase=passphrase
            )
            if inst is None:
                return jsonify(
                    {
                        "ok": False,
                        "exchange": name,
                        "error": "Exchange konnte nicht erstellt werden",
                    }
                )
            markets = inst.fetch_markets()
            latency_ms = round((_time.monotonic() - t0) * 1000)
            return jsonify(
                {
                    "ok": True,
                    "exchange": name,
                    "markets": len(markets),
                    "latency_ms": latency_ms,
                    "paper": paper,
                }
            )
        except Exception as exc:
            latency_ms = round((_time.monotonic() - t0) * 1000)
            return jsonify(
                {
                    "ok": False,
                    "exchange": name,
                    "error": str(exc)[:200],
                    "latency_ms": latency_ms,
                }
            )

    @bp.route("/api/v1/user/api-keys", methods=["POST"])
    @auth
    def api_user_update_keys():
        data = body()
        exchange = (
            norm_ex(data.get("exchange", cfg.get("exchange", "")))
            if norm_ex
            else str(data.get("exchange", ""))
        )
        api_key = str(data.get("api_key", "")).strip()
        api_secret = str(data.get("api_secret", "")).strip()
        if not exchange:
            return jsonify({"error": "Ungültige oder nicht unterstützte Exchange"}), 400
        if not api_key or not api_secret:
            return jsonify({"error": "api_key und api_secret sind Pflichtfelder"}), 400
        ok = db.update_user_api_keys(request.user_id, exchange, api_key, api_secret)
        if audit:
            audit("api_keys_update", f"Exchange: {exchange}", request.user_id)
        return jsonify({"ok": ok})

    # ── Signal & Portfolio ────────────────────────────────────────────────────

    @bp.route("/api/v1/signal", methods=["POST"])
    @auth
    def api_signal():
        """TradingView Webhook → sofortiger Scan."""
        data = body()
        sym = data.get("symbol", "")
        action = data.get("action", "buy").lower()
        if not sym or not st.running:
            return jsonify({"ok": False, "msg": "Bot nicht aktiv"}), 400

        def _async():
            try:
                ex = deps.create_exchange()
                scan = deps.scan_symbol(ex, sym)
                if scan and action == "buy" and scan.get("signal") == 1:
                    deps.open_position(ex, scan)
            except Exception as exc:
                log.warning("Signal-Handler: %s", exc)

        threading.Thread(target=_async, daemon=True).start()
        return jsonify({"ok": True, "symbol": sym, "action": action})

    @bp.route("/api/v1/portfolio")
    @auth
    def api_portfolio():
        snap = st.snapshot()
        return jsonify(
            {
                "portfolio_value": snap.get("portfolio_value", 0),
                "balance": snap.get("balance", 0),
                "return_pct": snap.get("return_pct", 0),
                "total_pnl": snap.get("total_pnl", 0),
                "win_rate": snap.get("win_rate", 0),
                "total_trades": snap.get("total_trades", 0),
                "open_trades": snap.get("open_trades", 0),
            }
        )

    # ── Kühlzeiten ────────────────────────────────────────────────────────────

    @bp.route("/api/v1/cooldowns")
    @auth
    def api_cooldowns():
        return jsonify({"cooldowns": deps.symbol_cooldown.status() if deps.symbol_cooldown else {}})

    @bp.route("/api/v1/cooldowns/<symbol>", methods=["DELETE"])
    @auth
    @admin
    def api_cooldown_clear(symbol):
        if deps.symbol_cooldown:
            with deps.symbol_cooldown._lock:
                deps.symbol_cooldown._cooldowns.pop(symbol, None)
        return jsonify({"cleared": symbol})

    # ── Positionen / Stop-Loss Patch ─────────────────────────────────────────

    @bp.route("/api/v1/positions/<path:symbol>/sl", methods=["PATCH"])
    @auth
    def api_position_sl_update(symbol):
        sym = symbol.replace("-", "/").upper()
        data = body()
        new_sl = sf(data.get("sl"), 0.0)
        if not new_sl or new_sl <= 0:
            return jsonify({"error": "sl must be > 0"}), 400
        with st._lock:
            pos = st.positions.get(sym)
        if not pos:
            return jsonify({"error": f"No open position: {sym}"}), 404
        with st._lock:
            st.positions[sym]["sl"] = new_sl
        return jsonify({"ok": True, "symbol": sym, "sl": new_sl})

    # ── Grid Trading ──────────────────────────────────────────────────────────

    @bp.route("/api/v1/grid", methods=["GET"])
    @auth
    def api_grid_list():
        if deps.grid_engine is None:
            return jsonify([])
        return jsonify(deps.grid_engine.list_grids())

    @bp.route("/api/v1/grid", methods=["POST"])
    @auth
    @admin
    def api_grid_create():
        data = body()
        symbol = str(data.get("symbol", "")).upper()
        lower = sf(data.get("lower", 0), 0)
        upper = sf(data.get("upper", 0), 0)
        levels = si(data.get("levels", 10), 10)
        invest = sf(data.get("invest_usdt", 100), 100)
        if not symbol or lower <= 0 or upper <= lower or levels < 2:
            return jsonify({"error": "Ungültige Grid-Parameter"}), 400
        if not _valid_symbol(symbol):
            return jsonify({"error": "invalid_symbol"}), 400
        if levels > MAX_GRID_LEVELS:
            return jsonify({"error": f"levels must be <= {MAX_GRID_LEVELS}"}), 400
        if invest > 0 and invest / levels < _MIN_CELL_USDT:
            return jsonify(
                {"error": f"invest / levels must be >= {_MIN_CELL_USDT} USDT per cell"}
            ), 400
        if deps.grid_engine is None:
            return jsonify({"error": "Grid-Engine nicht verfügbar"}), 503
        try:
            ex = deps.create_exchange()
            grid = deps.grid_engine.create_grid(ex, symbol, lower, upper, levels, invest)
            return jsonify({"ok": True, "grid": grid})
        except Exception as e:
            log.error("API error: %s", e)
            return jsonify({"error": "grid_create_failed"}), 500

    @bp.route("/api/v1/grid/<symbol>", methods=["DELETE"])
    @auth
    @admin
    def api_grid_delete(symbol):
        sym = symbol.replace("-", "/").upper()
        if deps.grid_engine is None:
            return jsonify({"error": "Grid-Engine nicht verfügbar"}), 503
        ok = deps.grid_engine.delete_grid(sym)
        return jsonify({"ok": ok})

    return bp
