"""AI Blueprint – VIRGINIE, Knowledge-Base, MCP-Tools, KI-Status.

Alle Virginie-Hilfsfunktionen leben in diesem Modul (kein server.py-Zugriff).
"""

from __future__ import annotations

import threading
import uuid
from collections import deque
from datetime import datetime
from typing import TYPE_CHECKING, Any

from flask import Blueprint, jsonify, request

from app.core.time_compat import UTC

if TYPE_CHECKING:
    from routes.api.deps import AppDeps

# Modul-lokaler Chat-Speicher (pro User, max 100 Einträge)
_VIRGINIE_CHAT_MAX_MESSAGES = 100
_virginie_chat_by_user: dict[int, deque] = {}
_virginie_chat_lock = threading.Lock()


# ── Virginie-Helfer ───────────────────────────────────────────────────────────

def _chat_history_for_user(user_id: int) -> list[dict[str, Any]]:
    with _virginie_chat_lock:
        history = _virginie_chat_by_user.setdefault(
            int(user_id), deque(maxlen=_VIRGINIE_CHAT_MAX_MESSAGES)
        )
        return [dict(item) for item in history]


def _chat_append(user_id: int, role: str, content: str) -> dict[str, Any]:
    entry = {
        "id": uuid.uuid4().hex,
        "role": role,
        "content": str(content).strip(),
        "time": datetime.now(UTC).isoformat(),
    }
    with _virginie_chat_lock:
        history = _virginie_chat_by_user.setdefault(
            int(user_id), deque(maxlen=_VIRGINIE_CHAT_MAX_MESSAGES)
        )
        history.append(entry)
    return entry


def _runtime_status(deps: AppDeps) -> dict[str, Any]:
    ai = deps.ai_engine.to_dict() if deps.ai_engine else {}
    assistant_agents = ai.get("assistant_agents", {}) if isinstance(ai, dict) else {}
    assistant_review = ai.get("assistant_review", {}) if isinstance(ai, dict) else {}
    cfg = deps.config
    return {
        "enabled": bool(cfg.get("virginie_enabled", True)),
        "primary_control": bool(cfg.get("virginie_primary_control", True)),
        "autonomy_weight": float(cfg.get("virginie_autonomy_weight", 0.7) or 0.7),
        "min_score": float(cfg.get("virginie_min_score", 0.0) or 0.0),
        "max_risk_penalty": float(cfg.get("virginie_max_risk_penalty", 1000.0) or 1000.0),
        "assistant_name": ai.get("assistant_name", "VIRGINIE"),
        "assistant_version": ai.get("assistant_version", "0.0.0"),
        "assistant_agents": assistant_agents if isinstance(assistant_agents, dict) else {},
        "assistant_review": assistant_review if isinstance(assistant_review, dict) else {},
    }


def _runtime_advice(deps: AppDeps) -> dict[str, Any]:
    status = _runtime_status(deps)
    ai = deps.ai_engine.to_dict() if deps.ai_engine else {}
    wf = float(ai.get("wf_accuracy", 0) or 0)
    drift = float(ai.get("drift_score", 0) or 0)
    trained = bool(ai.get("is_trained", False))
    guardrail_min_score = float(status.get("min_score", 0) or 0)
    actions: list[dict[str, str]] = []
    if not status.get("enabled", True):
        actions.append({"priority": "high", "title": "VIRGINIE aktivieren",
                        "detail": "Setze virginie_enabled=true."})
    if not trained:
        actions.append({"priority": "high", "title": "Training starten",
                        "detail": "Modell noch nicht trainiert – starte Initial-Training."})
    if wf < 55:
        actions.append({"priority": "medium", "title": "Qualität stabilisieren",
                        "detail": "WF-Accuracy niedrig – Trainingsdaten erhöhen."})
    if drift >= 0.7:
        actions.append({"priority": "medium", "title": "Drift reduzieren",
                        "detail": "Erhöhtes Drift-Risiko – Setups neu kalibrieren."})
    if guardrail_min_score < 0.5:
        actions.append({"priority": "low", "title": "Min-Score anheben",
                        "detail": "Konservativeres Verhalten: virginie_min_score +0.05."})
    if not actions:
        actions.append({"priority": "low", "title": "System stabil",
                        "detail": "VIRGINIE läuft stabil – Fokus auf Monitoring."})
    return {
        "assistant": status.get("assistant_name", "VIRGINIE"),
        "version": status.get("assistant_version", "0.0.0"),
        "wf_accuracy": wf,
        "drift_score": drift,
        "actions": actions[:5],
    }


def _edge_profile(deps: AppDeps) -> dict[str, Any]:
    status = _runtime_status(deps)
    advice = _runtime_advice(deps)
    snap = deps.state.snapshot() if deps.state else {}
    wf = float(advice.get("wf_accuracy", 0) or 0)
    drift = float(advice.get("drift_score", 0) or 0)
    autonomy = float(status.get("autonomy_weight", 0.7) or 0.7)
    open_trades = int(snap.get("open_trades", 0) or 0)
    risk_load = min(100.0, open_trades * 8.0)
    edge_score = max(0.0, min(100.0, (wf * 0.55) + ((1.0 - drift) * 35.0) + (autonomy * 10.0) - risk_load))
    tier = "S" if edge_score >= 85 else ("A" if edge_score >= 70 else ("B" if edge_score >= 55 else "C"))
    urgency = "high" if (drift >= 0.75 or edge_score < 45) else ("medium" if edge_score < 65 else "low")
    signature = uuid.uuid5(
        uuid.NAMESPACE_DNS,
        f"{status.get('assistant_version', '0')}-{snap.get('exchange', 'na')}-{tier}-{int(edge_score)}-{int(drift * 100)}",
    ).hex[:12]
    return {
        "edge_score": round(edge_score, 2),
        "tier": tier,
        "urgency": urgency,
        "running": bool(snap.get("running", False)),
        "exchange": snap.get("exchange", "unbekannt"),
        "open_trades": open_trades,
        "signature": signature,
    }


def _cpu_fast_reply(prompt: str) -> str | None:
    p = str(prompt or "").strip().lower()
    if not p:
        return None
    if any(k in p for k in ("risiko", "risk", "verlust", "drawdown")):
        return "CPU-Quickcheck: Risiko zuerst. Prüfe max_drawdown, daily_loss_limit und open_trades."
    if any(k in p for k in ("markt", "market", "regime", "trend")):
        return "CPU-Quickcheck: Regime + Volatilität zuerst prüfen. Nur bei bestätigtem Trend aggressiv handeln."
    if any(k in p for k in ("setup", "konfig", "config", "einstellung")):
        return "CPU-Quickcheck Setup: 1) virginie_primary_control aktiv, 2) ai_min_confidence validieren."
    if len(p.split()) <= 5:
        return "Beschreibe bitte kurz Symbol, Ziel und Risiko-Toleranz."
    return None


def _build_context(deps: AppDeps, user_id: int) -> str:
    ai = deps.ai_engine.to_dict() if deps.ai_engine else {}
    snap = deps.state.snapshot() if deps.state else {}
    recent = _chat_history_for_user(user_id)[-8:]
    recent_lines = "\n".join(
        f"[{e['role']}]: {e['content'][:200]}" for e in recent if e.get("role") != "system"
    )
    return (
        f"Exchange: {snap.get('exchange', '?')}, Paper: {snap.get('paper_trading', True)}, "
        f"Running: {snap.get('running', False)}, Open: {snap.get('open_trades', 0)}, "
        f"PnL: {snap.get('total_pnl', 0):.2f}, WR: {snap.get('win_rate', 0):.1f}%, "
        f"AI trained: {ai.get('is_trained', False)}, WF: {ai.get('wf_accuracy', 0):.1f}%\n"
        f"Recent chat:\n{recent_lines}"
    )


def _generate_reply(deps: AppDeps, user_id: int, user_prompt: str) -> str:
    cfg = deps.config
    if cfg.get("virginie_cpu_fast_chat", True):
        fast = _cpu_fast_reply(user_prompt)
        if fast:
            return fast
    if deps.knowledge and deps.knowledge.llm_enabled:
        try:
            ctx = _build_context(deps, user_id)
            answer = deps.knowledge.query_llm_with_tools(user_prompt, ctx)
            if answer:
                return str(answer)
        except Exception:
            pass
    return (
        "VIRGINIE analysiert: Das System läuft stabil. "
        "Für detailliertere Antworten setze LLM_ENDPOINT in der .env-Datei."
    )


# ── Blueprint-Fabrik ──────────────────────────────────────────────────────────

def create_ai_blueprint(deps: AppDeps) -> Blueprint:
    """Erstellt den AI/Virginie/Knowledge/MCP Blueprint."""
    bp = Blueprint("api_ai", __name__)

    auth = deps.api_auth_required
    si = deps.safe_int
    body = deps.get_json_body

    # ── VIRGINIE Chat ─────────────────────────────────────────────────────────

    @bp.route("/api/v1/virginie/chat")
    @auth
    def api_virginie_chat_history():
        user_id = int(getattr(request, "user_id", 0) or 0)
        return jsonify({
            "messages": _chat_history_for_user(user_id),
            "max_messages": _VIRGINIE_CHAT_MAX_MESSAGES,
        })

    @bp.route("/api/v1/virginie/chat", methods=["POST"])
    @auth
    def api_virginie_chat_post():
        user_id = int(getattr(request, "user_id", 0) or 0)
        payload = body()
        message = str(payload.get("message", "")).strip()
        if not message:
            return jsonify({"error": "message ist Pflichtfeld"}), 400
        if len(message) > 2000:
            return jsonify({"error": "message ist zu lang (max. 2000 Zeichen)"}), 400
        user_entry = _chat_append(user_id, "user", message)
        assistant_reply = _generate_reply(deps, user_id, message)
        assistant_entry = _chat_append(user_id, "assistant", assistant_reply)
        return jsonify({"ok": True, "user": user_entry, "assistant": assistant_entry})

    @bp.route("/api/v1/virginie/chat/clear", methods=["POST"])
    @auth
    def api_virginie_chat_clear():
        user_id = int(getattr(request, "user_id", 0) or 0)
        with _virginie_chat_lock:
            _virginie_chat_by_user[int(user_id)] = deque(maxlen=_VIRGINIE_CHAT_MAX_MESSAGES)
        return jsonify({"ok": True})

    @bp.route("/api/v1/virginie/status")
    @auth
    def api_virginie_status():
        return jsonify(_runtime_status(deps))

    @bp.route("/api/v1/virginie/advice")
    @auth
    def api_virginie_advice():
        return jsonify(_runtime_advice(deps))

    @bp.route("/api/v1/virginie/edge-profile")
    @auth
    def api_virginie_edge_profile():
        return jsonify(_edge_profile(deps))

    @bp.route("/api/v1/virginie/forecast-feed")
    @auth
    def api_virginie_forecast_feed():
        limit = si(request.args.get("limit", 30), 30)
        feed = deps.get_virginie_forecast_feed(limit) if deps.get_virginie_forecast_feed else []
        stats = deps.get_virginie_forecast_stats() if deps.get_virginie_forecast_stats else {}
        return jsonify({"items": feed, "stats": stats})

    @bp.route("/api/v1/virginie/forecast-quality")
    @auth
    def api_virginie_forecast_quality():
        quality = deps.get_virginie_forecast_quality() if deps.get_virginie_forecast_quality else {}
        return jsonify(quality)

    # ── Knowledge Base ────────────────────────────────────────────────────────

    @bp.route("/api/v1/knowledge/summary")
    @auth
    def api_knowledge_summary():
        if deps.knowledge is None:
            return jsonify({})
        return jsonify(deps.knowledge.get_market_summary())

    @bp.route("/api/v1/knowledge/<category>")
    @auth
    def api_knowledge_category(category):
        if deps.knowledge is None:
            return jsonify([])
        from services.knowledge import KnowledgeBase
        if category not in KnowledgeBase.CATEGORIES:
            return jsonify({"error": f"Unbekannte Kategorie: {category}"}), 400
        limit = min(si(request.args.get("limit", 50), 50), 200)
        return jsonify(deps.knowledge.get_category(category, limit))

    @bp.route("/api/v1/knowledge/query", methods=["POST"])
    @auth
    def api_knowledge_query():
        if deps.knowledge is None:
            return jsonify({"error": "Knowledge-Base nicht verfügbar"}), 503
        data = body()
        prompt = data.get("prompt", "")
        if not prompt:
            return jsonify({"error": "prompt ist Pflichtfeld"}), 400
        summary = deps.knowledge.get_market_summary()
        import json as _json
        context = (
            f"Du bist ein Krypto-Trading-Analyst. Aktuelles Wissen:\n"
            f"Top Symbole: {_json.dumps(summary.get('top_symbols', [])[:5])}\n"
        )
        answer = deps.knowledge.query_llm_with_tools(prompt, context)
        if answer is None:
            return jsonify({"error": "LLM nicht verfügbar. Setze LLM_ENDPOINT in .env"}), 503
        return jsonify({"answer": answer})

    @bp.route("/api/v1/knowledge/llm-status")
    @auth
    def api_knowledge_llm_status():
        if deps.knowledge is None:
            return jsonify({"llm_enabled": False})
        kb = deps.knowledge
        return jsonify({
            "llm_enabled": kb.llm_enabled,
            "llm_endpoint": bool(kb._llm_endpoint),
            "cached_market_analysis": kb.cached_market_analysis or None,
            "trade_patterns": len(kb.get_category("trade_pattern", limit=100)),
            "model_analyses": len(kb.get_category("model_config", limit=100)),
            "risk_patterns": len(kb.get_category("risk_pattern", limit=100)),
            "multi_llm_providers": (kb._multi_llm.status() if kb._multi_llm else []),
        })

    # ── MCP Tools ─────────────────────────────────────────────────────────────

    @bp.route("/api/v1/mcp/tools")
    @auth
    def api_mcp_tools():
        if deps.mcp_tools is None:
            return jsonify({"tools": [], "count": 0})
        tools = deps.mcp_tools.get_tools_schema()
        return jsonify({"tools": tools, "count": len(tools)})

    @bp.route("/api/v1/mcp/execute", methods=["POST"])
    @auth
    def api_mcp_execute():
        if deps.mcp_tools is None:
            return jsonify({"error": "MCP nicht verfügbar"}), 503
        data = body()
        tool_name = data.get("tool", "")
        arguments = data.get("arguments", {})
        if not tool_name:
            return jsonify({"error": "tool ist Pflichtfeld"}), 400
        return jsonify(deps.mcp_tools.execute(tool_name, arguments))

    # ── AI Engine ─────────────────────────────────────────────────────────────

    @bp.route("/api/v1/ai")
    @auth
    def api_ai():
        if deps.ai_engine is None:
            return jsonify({})
        return jsonify(deps.ai_engine.to_dict())

    @bp.route("/api/v1/ai/shared/status")
    @auth
    def api_ai_shared_status():
        if deps.ai_engine is None:
            return jsonify({"enabled": False})
        ai = deps.ai_engine.to_dict()
        return jsonify({
            "shared_enabled": bool(ai.get("shared_enabled", False)),
            "is_trained": bool(ai.get("is_trained", False)),
            "wf_accuracy": float(ai.get("wf_accuracy", 0) or 0),
            "drift_score": float(ai.get("drift_score", 0) or 0),
            "samples": int(ai.get("samples", 0) or 0),
        })

    @bp.route("/api/v1/ai/shared/force-sync", methods=["POST"])
    @auth
    def api_ai_shared_force_sync():
        if deps.ai_engine is None:
            return jsonify({"ok": False, "error": "AI nicht verfügbar"}), 503
        try:
            if hasattr(deps.ai_engine, "force_sync"):
                deps.ai_engine.force_sync()
            return jsonify({"ok": True})
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)}), 500

    @bp.route("/api/v1/ai/shared/train", methods=["POST"])
    @auth
    def api_ai_shared_train():
        if deps.ai_engine is None:
            return jsonify({"ok": False, "error": "AI nicht verfügbar"}), 503
        def _train():
            try:
                if hasattr(deps.ai_engine, "train"):
                    deps.ai_engine.train()
            except Exception:
                pass
        threading.Thread(target=_train, daemon=True).start()
        return jsonify({"ok": True, "msg": "Training gestartet"})

    @bp.route("/api/v1/ai/feature-importance")
    @auth
    def api_ai_feature_importance():
        if deps.ai_engine is None:
            return jsonify({"features": []})
        ai = deps.ai_engine.to_dict()
        return jsonify({"features": ai.get("feature_importance", [])})

    return bp
