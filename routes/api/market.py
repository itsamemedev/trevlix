"""Market Blueprint – Exchange-Daten, Balance, Fees, News, Gas.

Enthält: Exchanges-Snapshot, Aggregiertes Balance, Fees, Arbitrage,
Marktdaten (Dominanz, Anomalie, Genetik, RL), News, On-Chain, Gas,
OHLCV, Portfolio-Optimierung, Backtest-Vergleich, Copy-Trading.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import TYPE_CHECKING, Any

import requests
from flask import Blueprint, Response, jsonify, request, send_file, session

from app.core.time_compat import UTC

if TYPE_CHECKING:
    from routes.api.deps import AppDeps


def create_market_blueprint(deps: AppDeps) -> Blueprint:
    """Erstellt den Market-Blueprint."""
    bp = Blueprint("api_market", __name__)

    cfg = deps.config
    st = deps.state
    db = deps.db
    log = deps.log
    auth = deps.api_auth_required
    body = deps.get_json_body
    si = deps.safe_int

    # ── Balance ───────────────────────────────────────────────────────────────

    @bp.route("/api/v1/balance/all")
    @auth
    def api_balance_all():
        try:
            return jsonify(deps.fetch_aggregated_balance())
        except Exception as e:
            log.error("API error: %s", e)
            return jsonify({"error": "Internal server error"}), 500

    # ── Fees ─────────────────────────────────────────────────────────────────

    @bp.route("/api/v1/fees")
    @auth
    def api_fees():
        try:
            from services.exchange_factory import _fee_cache, _fee_cache_lock
            current_ex = cfg.get("exchange", "cryptocom")
            fees = {}
            with _fee_cache_lock:
                for ex_id in deps.exchange_default_fees:
                    fees[ex_id] = {
                        "default": deps.exchange_default_fees[ex_id],
                        "cached": _fee_cache.get(ex_id, {}).get("rate"),
                        "cached_at": _fee_cache.get(ex_id, {}).get("ts"),
                    }
            return jsonify({
                "current_exchange": current_ex,
                "current_fee_rate": deps.get_exchange_fee_rate(),
                "exchanges": fees,
            })
        except Exception as e:
            log.error("API error: %s", e)
            return jsonify({"error": "Internal server error"}), 500

    # ── Arbitrage ─────────────────────────────────────────────────────────────

    @bp.route("/api/v1/arb")
    @auth
    def api_arb():
        try:
            with db._get_conn() as conn:
                with conn.cursor() as c:
                    c.execute("SELECT * FROM arb_opportunities ORDER BY found_at DESC LIMIT 20")
                    rows = c.fetchall()
            result = []
            for r in rows:
                d = dict(r)
                if hasattr(d.get("found_at"), "isoformat"):
                    d["found_at"] = d["found_at"].isoformat()
                result.append(d)
            return jsonify(result)
        except Exception as e:
            log.error("API error: %s", e)
            return jsonify({"error": "Internal server error"}), 500

    # ── Marktdaten ────────────────────────────────────────────────────────────

    @bp.route("/api/v1/dominance")
    @auth
    def api_dominance():
        if deps.dominance is None:
            return jsonify({})
        return jsonify(deps.dominance.status() if hasattr(deps.dominance, "status") else {})

    @bp.route("/api/v1/anomaly")
    @auth
    def api_anomaly():
        if deps.anomaly is None:
            return jsonify({})
        return jsonify(deps.anomaly.to_dict() if hasattr(deps.anomaly, "to_dict") else {})

    @bp.route("/api/v1/genetic")
    @auth
    def api_genetic():
        if deps.genetic is None:
            return jsonify({})
        return jsonify(deps.genetic.to_dict() if hasattr(deps.genetic, "to_dict") else {})

    @bp.route("/api/v1/rl")
    @auth
    def api_rl():
        if deps.rl_agent is None:
            return jsonify({})
        return jsonify(deps.rl_agent.to_dict() if hasattr(deps.rl_agent, "to_dict") else {})

    @bp.route("/api/v1/news/<path:symbol>")
    @auth
    def api_news(symbol):
        if deps.news_fetcher is None:
            return jsonify({"score": 0, "articles": []})
        sym = symbol.upper().replace("-", "/")
        try:
            return jsonify(deps.news_fetcher.get_news_sentiment(sym))
        except Exception as e:
            log.error("API error: %s", e)
            return jsonify({"error": "Internal server error"}), 500

    @bp.route("/api/v1/onchain/<path:symbol>")
    @auth
    def api_onchain(symbol):
        if deps.onchain is None:
            return jsonify({})
        sym = symbol.upper().replace("-", "/")
        try:
            return jsonify(deps.onchain.get_metrics(sym))
        except Exception as e:
            log.error("API error: %s", e)
            return jsonify({"error": "Internal server error"}), 500

    # ── Gas ───────────────────────────────────────────────────────────────────

    @bp.route("/api/v1/gas")
    def api_gas():
        try:
            r = requests.get(
                "https://api.etherscan.io/api?module=gastracker&action=gasoracle", timeout=5
            )
            if r.status_code == 200:
                data = r.json().get("result", {})
                return jsonify({
                    "low": data.get("SafeGasPrice", "0"),
                    "medium": data.get("ProposeGasPrice", "0"),
                    "high": data.get("FastGasPrice", "0"),
                    "source": "etherscan",
                })
            return jsonify({"low": "0", "medium": "0", "high": "0", "source": "unavailable"})
        except Exception:
            return jsonify({"low": "0", "medium": "0", "high": "0", "source": "error"})

    # ── Multi-Exchange Snapshot ───────────────────────────────────────────────

    @bp.route("/api/v1/exchanges")
    @auth
    def api_exchanges():
        try:
            uid = getattr(request, "user_id", None) or session.get("user_id")
            if not uid:
                return jsonify({"exchanges": {}, "combined_pv": 0, "combined_pnl": 0, "total_pv": 0, "total_pnl": 0})
            runtime = st.snapshot() if st else {}
            active_exchange = str(runtime.get("exchange") or cfg.get("exchange", "")).lower()
            runtime_positions = list(runtime.get("positions") or [])
            runtime_markets = list(runtime.get("markets") or [])
            pos_by_exchange: dict[str, list] = {}
            for pos in runtime_positions:
                ex_name = str(pos.get("exchange") or active_exchange or "").lower()
                if ex_name:
                    pos_by_exchange.setdefault(ex_name, []).append(pos)
            user_exchanges = db.get_user_exchanges(uid)
            now_iso = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")
            ex_map: dict[str, Any] = {}
            for ex in user_exchanges:
                ex_name = str(ex.get("exchange", "")).lower()
                if not ex_name:
                    continue
                is_active = ex_name == active_exchange
                ex_map[ex_name] = {
                    "enabled": bool(ex.get("enabled")),
                    "running": bool(runtime.get("running", False)) if is_active else False,
                    "portfolio_value": float(runtime.get("portfolio_value", 0) or 0) if is_active else 0.0,
                    "return_pct": float(runtime.get("return_pct", 0) or 0) if is_active else 0.0,
                    "trade_count": int(runtime.get("total_trades", 0) or 0) if is_active else 0,
                    "open_trades": len(pos_by_exchange.get(ex_name, [])),
                    "win_rate": float(runtime.get("win_rate", 0) or 0) if is_active else 0.0,
                    "total_pnl": float(runtime.get("total_pnl", 0) or 0) if is_active else 0.0,
                    "markets_count": len(runtime_markets) if is_active else 0,
                    "last_scan": str(runtime.get("last_scan") or now_iso),
                    "positions": pos_by_exchange.get(ex_name, []),
                    "error": "" if ex.get("enabled") else "Nicht aktiviert",
                }
            combined_pv = sum(v["portfolio_value"] for v in ex_map.values())
            combined_pnl = sum(v["total_pnl"] for v in ex_map.values())
            return jsonify({
                "exchanges": ex_map,
                "combined_pv": combined_pv,
                "combined_pnl": combined_pnl,
                "total_pv": combined_pv,
                "total_pnl": combined_pnl,
            })
        except Exception as e:
            log.error("api_exchanges: %s", e)
            return jsonify({"error": "Internal server error"}), 500

    @bp.route("/api/v1/exchanges/combined/trades")
    @auth
    def api_exchanges_combined_trades():
        try:
            limit = min(si(request.args.get("limit", 200), 200), 1000)
            trades = db.load_trades(limit=limit, user_id=request.user_id)
            return jsonify({"trades": trades, "count": len(trades)})
        except Exception as e:
            log.error("API error: %s", e)
            return jsonify({"error": "Internal server error"}), 500

    # ── OHLCV ─────────────────────────────────────────────────────────────────

    @bp.route("/api/ohlcv/<path:symbol>")
    def api_ohlcv(symbol):
        sym = symbol.replace("-", "/")
        tf = request.args.get("tf", "1h")
        if tf not in {"1m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "12h", "1d"}:
            tf = "1h"
        limit = min(si(request.args.get("limit", 200), 200), 500)
        try:
            ex = deps.create_exchange()
            ohlcv = ex.fetch_ohlcv(sym, tf, limit=limit)
            trades = [t for t in st.closed_trades if t.get("symbol") == sym][:20]
            return jsonify({"ohlcv": ohlcv, "trades": trades})
        except Exception as e:
            log.error("API error: %s", e)
            return jsonify({"error": "Internal server error"})

    # ── Heatmap (Legacy) ──────────────────────────────────────────────────────

    @bp.route("/api/heatmap")
    def api_heatmap_legacy():
        try:
            ex = deps.create_exchange()
            return jsonify(deps.get_heatmap_data(ex))
        except Exception as e:
            log.error("API error: %s", e)
            return jsonify({"error": "Internal server error"})

    # ── Portfolio Optimierung ─────────────────────────────────────────────────

    @bp.route("/api/v1/portfolio/optimize", methods=["POST"])
    @auth
    def api_portfolio_optimize():
        try:
            data = body()
            symbols = data.get("symbols", [])
            if not symbols or len(symbols) < 2:
                return jsonify({"error": "Mindestens 2 Symbole erforderlich"}), 400
            ex = deps.create_exchange()
            returns_data = {}
            for sym in symbols[:10]:
                try:
                    ohlcv = ex.fetch_ohlcv(sym, "1d", limit=90)
                    if len(ohlcv) > 10:
                        closes = [c[4] for c in ohlcv]
                        returns_data[sym] = [
                            (closes[i] - closes[i - 1]) / closes[i - 1]
                            for i in range(1, len(closes))
                        ]
                except Exception:
                    pass
            if len(returns_data) < 2:
                return jsonify({"error": "Nicht genügend Daten"}), 400
            import numpy as np
            ret_matrix = np.array(list(returns_data.values()))
            np.cov(ret_matrix)  # covariance computed but equal-weight used
            mu = np.mean(ret_matrix, axis=1)
            n = len(mu)
            weights = np.ones(n) / n
            return jsonify({
                "symbols": list(returns_data.keys()),
                "equal_weights": weights.tolist(),
                "expected_returns": mu.tolist(),
                "note": "Gleichgewichtete Allokation (Markowitz erfordert mehr Daten)",
            })
        except Exception as e:
            log.error("Portfolio-Optimierung: %s", e)
            return jsonify({"error": str(e)}), 500

    # ── Backtest Vergleich ────────────────────────────────────────────────────

    @bp.route("/api/v1/backtest/compare", methods=["POST"])
    @auth
    def api_backtest_compare():
        data = body()
        symbols = data.get("symbols", ["BTC/USDT"])
        tf = data.get("timeframe", "1h")
        candles = si(data.get("candles", 500), 500)
        if deps.backtest is None:
            return jsonify({"error": "Backtest nicht verfügbar"}), 503
        try:
            ex = deps.create_exchange()
            results = {}
            for sym in symbols[:5]:
                try:
                    results[sym] = deps.backtest.run(
                        ex, sym, tf, candles,
                        deps.config.get("stop_loss_pct", 0.025),
                        deps.config.get("take_profit_pct", 0.060),
                        deps.config.get("min_vote_score", 0.3),
                    )
                except Exception as exc:
                    results[sym] = {"error": str(exc)}
            return jsonify(results)
        except Exception as e:
            log.error("API error: %s", e)
            return jsonify({"error": "Internal server error"}), 500

    # ── Copy Trading ──────────────────────────────────────────────────────────

    @bp.route("/api/v1/copy-trading/register", methods=["POST"])
    @auth
    def api_copy_trading_register():
        return jsonify({"ok": False, "msg": "Copy-Trading in Entwicklung"})

    @bp.route("/api/v1/copy-trading/followers")
    @auth
    def api_copy_trading_followers():
        return jsonify({"followers": []})

    @bp.route("/api/v1/copy-trading/test", methods=["POST"])
    @auth
    def api_copy_trading_test():
        return jsonify({"ok": False, "msg": "Copy-Trading in Entwicklung"})

    # ── Export ────────────────────────────────────────────────────────────────

    @bp.route("/api/export/csv")
    def api_export_csv():
        return Response(
            db.export_csv(),
            mimetype="text/csv",
            headers={"Content-Disposition": "attachment;filename=trevlix_trades.csv"},
        )

    @bp.route("/api/export/json")
    def api_export_json():
        trades = db.load_trades(limit=10000)
        if deps.trades_to_json:
            content = deps.trades_to_json(trades)
        else:
            content = json.dumps(trades)
        return Response(
            content,
            mimetype="application/json",
            headers={"Content-Disposition": "attachment;filename=trevlix_trades.json"},
        )

    @bp.route("/api/backup/download")
    def api_backup_download():
        path = db.backup()
        if path:
            return send_file(path, as_attachment=True)
        return jsonify({"error": "Backup fehlgeschlagen"}), 500

    return bp
