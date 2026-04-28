"""System Blueprint – Health, Metrics, Risk, Revenue, Cluster, Alerts.

Enthält: Health-Checks, Prometheus-Metriken, Monte-Carlo-Simulation,
Revenue-Tracking, Cluster-Steuerung, Alert-Eskalation, CVaR, Volatilität,
Trade-DNA, Smart-Exits, Performance-Attribution.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any

import numpy as np
from flask import Blueprint, Response, jsonify, request

log = logging.getLogger("trevlix.api.system")

if TYPE_CHECKING:
    from routes.api.deps import AppDeps


def _run_monte_carlo(deps: AppDeps, n_simulations: int = 10_000, n_days: int = 30) -> dict:
    """Monte-Carlo-Simulation des Portfolio-Werts über n_days Tage."""
    trades = deps.state.closed_trades
    if len(trades) < 5:
        return {"error": "Mindestens 5 abgeschlossene Trades erforderlich"}
    pnl_pcts = [
        t.get("pnl", 0) / max(t.get("invested", 1), 1)
        for t in trades
        if t.get("invested", 0) > 0
    ]
    if not pnl_pcts:
        return {"error": "Keine PnL-Daten vorhanden"}
    mu = float(np.mean(pnl_pcts))
    sigma = float(np.std(pnl_pcts))
    start_value = deps.state.portfolio_value()
    if trades:
        span_days = max(
            1,
            (
                datetime.now()
                - datetime.fromisoformat(str(trades[-1].get("opened", datetime.now().isoformat()))[:19])
            ).days,
        )
        trades_per_day = max(0.1, len(trades) / span_days)
    else:
        trades_per_day = 1.0
    results = []
    rng = np.random.default_rng(42)
    cfg = deps.config
    for _ in range(n_simulations):
        val = start_value
        for _day in range(n_days):
            n_trades_today = max(0, int(rng.poisson(trades_per_day)))
            for _ in range(n_trades_today):
                pnl_pct = rng.normal(mu, sigma)
                invested = val * cfg.get("risk_per_trade", 0.015)
                val = max(0, val + invested * pnl_pct)
        results.append(val)
    results_arr = np.array(results)
    p5, p25, p50, p75, p95 = np.percentile(results_arr, [5, 25, 50, 75, 95])
    var_95 = start_value - float(p5)
    var_pct = var_95 / start_value * 100 if start_value > 0 else 0
    return {
        "n_simulations": n_simulations,
        "n_days": n_days,
        "start_value": round(start_value, 2),
        "mu_per_trade": round(mu * 100, 3),
        "sigma_per_trade": round(sigma * 100, 3),
        "trades_per_day": round(trades_per_day, 2),
        "percentile_5": round(float(p5), 2),
        "percentile_25": round(float(p25), 2),
        "percentile_50": round(float(p50), 2),
        "percentile_75": round(float(p75), 2),
        "percentile_95": round(float(p95), 2),
        "var_95_usdt": round(var_95, 2),
        "var_95_pct": round(var_pct, 2),
        "prob_profit_pct": round(float(np.mean(results_arr > start_value) * 100), 1),
        "prob_ruin_pct": round(float(np.mean(results_arr < start_value * 0.5) * 100), 1),
        "expected_return": round((float(p50) - start_value) / start_value * 100, 2) if start_value > 0 else 0.0,
    }


def create_system_blueprint(deps: AppDeps) -> Blueprint:
    """Erstellt den System-Blueprint."""
    bp = Blueprint("api_system", __name__)

    st = deps.state
    auth = deps.api_auth_required
    admin = deps.admin_required
    body = deps.get_json_body
    si = deps.safe_int
    sf = deps.safe_float

    # ── Health ────────────────────────────────────────────────────────────────

    @bp.route("/api/v1/health/basic")
    def api_health_basic():
        return jsonify({"status": "ok", "running": st.running, "version": deps.bot_version})

    @bp.route("/api/v1/health/live")
    def api_health_live():
        # K8s-style liveness probe: the process is up and responding. We
        # intentionally do not touch dependencies here so a degraded DB does
        # not trigger a pod restart loop.
        return jsonify({"status": "alive", "version": deps.bot_version}), 200

    @bp.route("/api/v1/health/ready")
    def api_health_ready():
        # K8s-style readiness probe: runs the registered dependency checks
        # and returns 503 on aggregate UNHEALTHY so upstream load balancers
        # stop sending traffic.
        from services.health_check import get_registry

        report = get_registry().check()
        status = 503 if report.get("status") == "unhealthy" else 200
        return jsonify(report), status

    @bp.route("/api/v1/health/snapshot")
    @auth
    def api_health_snapshot():
        if deps.healer is None:
            return jsonify({})
        return jsonify(deps.healer.health_snapshot())

    @bp.route("/api/v1/health/incidents")
    @auth
    def api_health_incidents():
        if deps.healer is None:
            return jsonify({"incidents": []})
        snap = deps.healer.health_snapshot()
        return jsonify({"incidents": snap.get("incidents", [])})

    # ── Prometheus & Metrics ──────────────────────────────────────────────────

    @bp.route("/metrics")
    @auth
    def prometheus_metrics():
        if deps.build_prometheus_lines:
            lines = deps.build_prometheus_lines(bot_version=deps.bot_version, state=st, db=deps.db)
            return Response("\n".join(lines) + "\n", mimetype="text/plain; charset=utf-8")
        return Response("", mimetype="text/plain")

    @bp.route("/api/v1/metrics")
    @auth
    def api_metrics():
        return jsonify({
            "portfolio_value": st.portfolio_value(),
            "positions": len(st.positions),
            "short_positions": len(st.short_positions),
            "balance": st.balance,
            "running": st.running,
            "iteration": st.iteration,
        })

    # ── System Analytics ──────────────────────────────────────────────────────

    @bp.route("/api/v1/system-analytics")
    @auth
    def api_system_analytics():
        data: dict[str, Any] = {}
        # Revenue
        try:
            if deps.revenue:
                rev = deps.revenue.snapshot()
                data["revenue"] = {
                    "gross_pnl": round(rev.get("gross_pnl", 0), 2),
                    "net_pnl": round(rev.get("net_pnl", 0), 2),
                    "total_fees": round(rev.get("total_fees", 0), 2),
                    "total_trades": rev.get("total_trades", 0),
                    "roi_pct": f"{rev.get('roi_pct', 0):.2f}%",
                    "max_drawdown": f"{rev.get('max_drawdown_pct', 0):.1f}%",
                    "profit_factor": round(rev.get("profit_factor", 0), 2),
                    "win_rate": f"{rev.get('win_rate', 0):.1f}%",
                }
        except Exception:
            data["revenue"] = {}
        # Performance attribution
        try:
            if deps.perf_attribution:
                pa_stats = deps.perf_attribution.stats()
                data["attribution"] = {
                    "total_trades": pa_stats.get("total_trades", 0),
                    "profit_factor": round(pa_stats.get("profit_factor", 0), 2),
                    "expectancy": round(pa_stats.get("expectancy", 0), 2),
                    "sharpe": round(pa_stats.get("sharpe_ratio", 0), 2),
                }
        except Exception:
            data["attribution"] = {}
        # Adaptive weights
        try:
            if deps.adaptive_weights:
                aw = deps.adaptive_weights.to_dict()
                perf_list = aw.get("performance", [])
                top_strats = sorted(perf_list, key=lambda x: x.get("weight", 0), reverse=True)[:5]
                data["strategies"] = {
                    "total": aw.get("strategies_total", 0),
                    "adapted": aw.get("strategies_adapted", 0),
                    "total_votes": aw.get("total_votes", 0),
                    "top": [
                        {"name": s.get("strategy", "?"), "weight": round(s.get("weight", 0), 2),
                         "win_rate": f"{s.get('win_rate', 0):.0f}%", "trades": s.get("trades", 0)}
                        for s in top_strats
                    ],
                }
        except Exception:
            data["strategies"] = {}
        # Healing
        try:
            if deps.healer:
                data["healing"] = deps.healer.health_snapshot()
        except Exception:
            data["healing"] = {}
        return jsonify(data)

    # ── Risk ──────────────────────────────────────────────────────────────────

    @bp.route("/api/v1/risk/monte-carlo")
    @auth
    def api_monte_carlo():
        n_sim = min(si(request.args.get("n", 10000), 10000), 50000)
        n_days = min(si(request.args.get("days", 30), 30), 365)
        return jsonify(_run_monte_carlo(deps, n_sim, n_days))

    @bp.route("/api/v1/risk/cvar")
    @auth
    def api_cvar():
        if deps.adv_risk is None:
            return jsonify({"error": "Risiko-Modul nicht verfügbar"}), 503
        confidence = sf(request.args.get("conf", 0.95), 0.95)
        return jsonify(deps.adv_risk.compute_cvar(st.closed_trades, confidence))

    @bp.route("/api/v1/risk/volatility")
    @auth
    def api_volatility():
        if deps.adv_risk is None:
            return jsonify({"error": "Risiko-Modul nicht verfügbar"}), 503
        return jsonify(deps.adv_risk.volatility_forecast(si(request.args.get("h", 5), 5)))

    @bp.route("/api/v1/risk/regime")
    @auth
    def api_market_regime():
        if deps.adv_risk is None:
            return jsonify({"regime": "UNKNOWN"})
        prices = list(st.prices.values())
        if not prices:
            return jsonify({"regime": "UNKNOWN"})
        regime_result = deps.adv_risk.classify_regime(
            [e["value"] for e in list(st.portfolio_history)[-50:]] if st.portfolio_history else prices
        )
        return jsonify({
            "regime": regime_result,
            "vol_pct": round(deps.adv_risk._ewma_vol * 100, 3),
            "risk_level": deps.adv_risk.volatility_forecast(1)["risk_level"],
        })

    # ── Revenue ───────────────────────────────────────────────────────────────

    @bp.route("/api/v1/revenue/snapshot")
    @auth
    def api_revenue_snapshot():
        return jsonify(deps.revenue.snapshot() if deps.revenue else {})

    @bp.route("/api/v1/revenue/daily")
    @auth
    def api_revenue_daily():
        if deps.revenue is None:
            return jsonify({})
        date_str = request.args.get("date")
        dt = None
        if date_str:
            try:
                dt = datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                return jsonify({"error": "Invalid date format, use YYYY-MM-DD"}), 400
        return jsonify(deps.revenue.get_daily_summary(dt))

    @bp.route("/api/v1/revenue/weekly")
    @auth
    def api_revenue_weekly():
        return jsonify(deps.revenue.get_weekly_summary() if deps.revenue else {})

    @bp.route("/api/v1/revenue/monthly")
    @auth
    def api_revenue_monthly():
        return jsonify(deps.revenue.get_monthly_summary() if deps.revenue else {})

    @bp.route("/api/v1/revenue/strategies")
    @auth
    def api_revenue_strategies():
        return jsonify(deps.revenue.get_strategy_performance() if deps.revenue else {})

    @bp.route("/api/v1/revenue/losing")
    @auth
    def api_revenue_losing():
        losing = deps.revenue.detect_losing_strategies() if deps.revenue else []
        return jsonify({"losing_strategies": losing})

    # ── Cluster ───────────────────────────────────────────────────────────────

    @bp.route("/api/v1/cluster/snapshot")
    @auth
    def api_cluster_snapshot():
        return jsonify(deps.cluster_ctrl.snapshot() if deps.cluster_ctrl else {})

    @bp.route("/api/v1/cluster/nodes", methods=["GET"])
    @auth
    def api_cluster_nodes_list():
        if deps.cluster_ctrl is None:
            return jsonify({"nodes": []})
        nodes = deps.cluster_ctrl.get_nodes()
        return jsonify({"nodes": [n.to_dict() for n in nodes]})

    @bp.route("/api/v1/cluster/nodes", methods=["POST"])
    @auth
    @admin
    def api_cluster_nodes_add():
        data = body()
        name = data.get("name", "").strip()
        host = data.get("host", "").strip()
        port = si(data.get("port", 5000), 5000)
        api_token = data.get("api_token", "")
        if not name or not host:
            return jsonify({"error": "name and host are required"}), 400
        try:
            node = deps.cluster_ctrl.add_node(name, host, port, api_token)
            return jsonify({"ok": True, "node": node.to_dict()}), 201
        except ValueError as e:
            log.warning("cluster_add_node failed: %s", e)
            return jsonify({"error": "cluster_add_node_failed"}), 409

    @bp.route("/api/v1/cluster/nodes/<name>", methods=["DELETE"])
    @auth
    @admin
    def api_cluster_nodes_remove(name):
        try:
            deps.cluster_ctrl.remove_node(name)
            return jsonify({"ok": True})
        except KeyError:
            return jsonify({"error": f"Node '{name}' not found"}), 404

    @bp.route("/api/v1/cluster/nodes/<name>/start", methods=["POST"])
    @auth
    @admin
    def api_cluster_node_start(name):
        try:
            return jsonify({"ok": deps.cluster_ctrl.start_bot(name)})
        except KeyError:
            return jsonify({"error": f"Node '{name}' not found"}), 404

    @bp.route("/api/v1/cluster/nodes/<name>/stop", methods=["POST"])
    @auth
    @admin
    def api_cluster_node_stop(name):
        try:
            return jsonify({"ok": deps.cluster_ctrl.stop_bot(name)})
        except KeyError:
            return jsonify({"error": f"Node '{name}' not found"}), 404

    @bp.route("/api/v1/cluster/nodes/<name>/restart", methods=["POST"])
    @auth
    @admin
    def api_cluster_node_restart(name):
        try:
            return jsonify({"ok": deps.cluster_ctrl.restart_bot(name)})
        except KeyError:
            return jsonify({"error": f"Node '{name}' not found"}), 404

    @bp.route("/api/v1/cluster/nodes/<name>/deploy", methods=["POST"])
    @auth
    @admin
    def api_cluster_node_deploy(name):
        try:
            return jsonify({"ok": deps.cluster_ctrl.deploy_update(name)})
        except KeyError:
            return jsonify({"error": f"Node '{name}' not found"}), 404

    @bp.route("/api/v1/cluster/metrics")
    @auth
    def api_cluster_metrics():
        return jsonify(deps.cluster_ctrl.get_cluster_metrics() if deps.cluster_ctrl else {})

    # ── Alerts ────────────────────────────────────────────────────────────────

    @bp.route("/api/v1/alerts/active")
    @auth
    def api_alerts_active():
        alerts = deps.alert_escalation.get_active_alerts() if deps.alert_escalation else []
        return jsonify({"alerts": alerts})

    @bp.route("/api/v1/alerts/history")
    @auth
    def api_alerts_history():
        limit = si(request.args.get("limit", 50), 50)
        history = deps.alert_escalation.get_history(limit) if deps.alert_escalation else []
        return jsonify({"history": history})

    @bp.route("/api/v1/alerts/snapshot")
    @auth
    def api_alerts_snapshot():
        return jsonify(deps.alert_escalation.snapshot() if deps.alert_escalation else {})

    @bp.route("/api/v1/alerts/<alert_id>/acknowledge", methods=["POST"])
    @auth
    def api_alert_acknowledge(alert_id):
        if deps.alert_escalation and deps.alert_escalation.acknowledge(alert_id):
            return jsonify({"ok": True})
        return jsonify({"error": f"Alert '{alert_id}' not found"}), 404

    @bp.route("/api/v1/alerts/<alert_id>/resolve", methods=["POST"])
    @auth
    def api_alert_resolve(alert_id):
        if deps.alert_escalation and deps.alert_escalation.resolve(alert_id):
            return jsonify({"ok": True})
        return jsonify({"error": f"Alert '{alert_id}' not found"}), 404

    # ── Trading Algorithmen / DNA / Smart Exits ───────────────────────────────

    @bp.route("/api/v1/trading-algorithms")
    @auth
    def api_trading_algorithms():
        return jsonify(deps.trading_algos.to_dict() if deps.trading_algos else {})

    @bp.route("/api/v1/trade-dna")
    @auth
    def api_trade_dna():
        return jsonify(deps.trade_dna.to_dict() if deps.trade_dna else {})

    @bp.route("/api/v1/trade-dna/patterns")
    @auth
    def api_trade_dna_patterns():
        n = si(request.args.get("n", 10), 10)
        if deps.trade_dna is None:
            return jsonify({"top": [], "worst": []})
        return jsonify({"top": deps.trade_dna.top_patterns(n), "worst": deps.trade_dna.worst_patterns(n)})

    @bp.route("/api/v1/smart-exits")
    @auth
    def api_smart_exits():
        return jsonify(deps.smart_exits.to_dict() if deps.smart_exits else {})

    @bp.route("/api/v1/performance/attribution")
    @auth
    def api_performance_attribution():
        return jsonify(deps.perf_attribution.full_report() if deps.perf_attribution else {})

    @bp.route("/api/v1/performance/contributors")
    @auth
    def api_performance_contributors():
        n = si(request.args.get("n", 5), 5)
        return jsonify(deps.perf_attribution.top_contributors(n) if deps.perf_attribution else {})

    return bp
