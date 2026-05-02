"""VIRGINIE chat helpers extracted from server.py.

Eight related helpers that build the dashboard-side conversation with
the VIRGINIE assistant: per-user history buffer, runtime status / advice
/ edge-profile readouts, a CPU-only fast-reply fallback, prompt-context
construction, and the slash-command dispatcher.

Per-user history is stored in this module's private state. All other
state (CONFIG, state, ai_engine, knowledge_base, log) is passed in as
keyword arguments so the module is import-safe and unit-testable.
"""

from __future__ import annotations

import threading
import uuid
from collections import deque
from datetime import datetime
from typing import Any

from app.core.time_compat import UTC

# ---------------------------------------------------------------------------
# Per-user chat history – module-private state
# ---------------------------------------------------------------------------

VIRGINIE_CHAT_MAX_MESSAGES = 80

_chat_lock = threading.Lock()
_chat_by_user: dict[int, deque[dict[str, Any]]] = {}


def chat_history_for_user(user_id: int) -> list[dict[str, Any]]:
    """Return a copy of the per-user chat history (oldest first)."""
    with _chat_lock:
        history = _chat_by_user.setdefault(int(user_id), deque(maxlen=VIRGINIE_CHAT_MAX_MESSAGES))
        return [dict(item) for item in history]


def chat_append(user_id: int, role: str, content: str) -> dict[str, Any]:
    """Append one message to the user's history and return the entry."""
    entry = {
        "id": uuid.uuid4().hex,
        "role": role,
        "content": str(content).strip(),
        "time": datetime.now(UTC).isoformat(),
    }
    with _chat_lock:
        history = _chat_by_user.setdefault(int(user_id), deque(maxlen=VIRGINIE_CHAT_MAX_MESSAGES))
        history.append(entry)
    return entry


def clear_chat_history(user_id: int) -> None:
    """Reset a user's chat history to an empty deque."""
    with _chat_lock:
        _chat_by_user[int(user_id)] = deque(maxlen=VIRGINIE_CHAT_MAX_MESSAGES)


# ---------------------------------------------------------------------------
# Runtime status / advice / edge-profile
# ---------------------------------------------------------------------------


def runtime_status(*, config: dict[str, Any], ai_engine: Any) -> dict[str, Any]:
    """Compact VIRGINIE state for the API/chat surface."""
    ai = ai_engine.to_dict() if ai_engine else {}
    assistant_agents = ai.get("assistant_agents", {}) if isinstance(ai, dict) else {}
    assistant_review = ai.get("assistant_review", {}) if isinstance(ai, dict) else {}
    return {
        "enabled": bool(config.get("virginie_enabled", True)),
        "primary_control": bool(config.get("virginie_primary_control", True)),
        "autonomy_weight": float(config.get("virginie_autonomy_weight", 0.7) or 0.7),
        "min_score": float(config.get("virginie_min_score", 0.0) or 0.0),
        "max_risk_penalty": float(config.get("virginie_max_risk_penalty", 1000.0) or 1000.0),
        "assistant_name": ai.get("assistant_name", "VIRGINIE"),
        "assistant_version": ai.get("assistant_version", "0.0.0"),
        "assistant_agents": assistant_agents if isinstance(assistant_agents, dict) else {},
        "assistant_review": assistant_review if isinstance(assistant_review, dict) else {},
    }


def runtime_advice(*, config: dict[str, Any], ai_engine: Any) -> dict[str, Any]:
    """Derive concrete next-step actions from the runtime status."""
    status = runtime_status(config=config, ai_engine=ai_engine)
    ai = ai_engine.to_dict() if ai_engine else {}
    wf = float(ai.get("wf_accuracy", 0) or 0)
    drift = float(ai.get("drift_score", 0) or 0)
    trained = bool(ai.get("is_trained", False))
    guardrail_min_score = float(status.get("min_score", 0) or 0)
    actions: list[dict[str, str]] = []
    if not status.get("enabled", True):
        actions.append(
            {
                "priority": "high",
                "title": "VIRGINIE aktivieren",
                "detail": (
                    "Setze virginie_enabled=true, damit Guardrails und Agenten-Workflow aktiv sind."
                ),
            }
        )
    if not trained:
        actions.append(
            {
                "priority": "high",
                "title": "Training starten",
                "detail": (
                    "Das Modell ist noch nicht trainiert. Starte ein "
                    "Initial-Training im Admin-Bereich."
                ),
            }
        )
    if wf < 55:
        actions.append(
            {
                "priority": "medium",
                "title": "Qualität stabilisieren",
                "detail": (
                    "WF-Accuracy ist niedrig. Prüfe Feature-Importance und erhöhe Trainingsdaten."
                ),
            }
        )
    if drift >= 0.7:
        actions.append(
            {
                "priority": "medium",
                "title": "Drift reduzieren",
                "detail": (
                    "Erhöhtes Drift-Risiko erkannt. Setups neu kalibrieren und Risk-Limits prüfen."
                ),
            }
        )
    if guardrail_min_score < 0.5:
        actions.append(
            {
                "priority": "low",
                "title": "Min-Score anheben",
                "detail": (
                    "Für konservativeres Verhalten virginie_min_score leicht erhöhen (z.B. +0.05)."
                ),
            }
        )
    if not actions:
        actions.append(
            {
                "priority": "low",
                "title": "System stabil",
                "detail": "VIRGINIE läuft stabil. Fokus auf Monitoring und regelmäßiges Review.",
            }
        )
    return {
        "assistant": status.get("assistant_name", "VIRGINIE"),
        "version": status.get("assistant_version", "0.0.0"),
        "wf_accuracy": wf,
        "drift_score": drift,
        "actions": actions[:5],
    }


def edge_profile(*, config: dict[str, Any], ai_engine: Any, state: Any) -> dict[str, Any]:
    """Compact VIRGINIE edge-score for trading/forecast workflows."""
    status = runtime_status(config=config, ai_engine=ai_engine)
    advice = runtime_advice(config=config, ai_engine=ai_engine)
    snap = state.snapshot() if state else {}
    wf = float(advice.get("wf_accuracy", 0) or 0)
    drift = float(advice.get("drift_score", 0) or 0)
    autonomy = float(status.get("autonomy_weight", 0.7) or 0.7)
    running = bool(snap.get("running", False))
    open_trades = int(snap.get("open_trades", 0) or 0)
    risk_load = min(100.0, open_trades * 8.0)
    edge_score = max(
        0.0, min(100.0, (wf * 0.55) + ((1.0 - drift) * 35.0) + (autonomy * 10.0) - risk_load)
    )
    tier = (
        "S"
        if edge_score >= 85
        else ("A" if edge_score >= 70 else ("B" if edge_score >= 55 else "C"))
    )
    urgency = (
        "high" if (drift >= 0.75 or edge_score < 45) else ("medium" if edge_score < 65 else "low")
    )
    signature = uuid.uuid5(
        uuid.NAMESPACE_DNS,
        f"{status.get('assistant_version', '0')}-{snap.get('exchange', 'na')}-"
        f"{tier}-{int(edge_score)}-{int(drift * 100)}",
    ).hex[:12]
    return {
        "edge_score": round(edge_score, 2),
        "tier": tier,
        "urgency": urgency,
        "running": running,
        "exchange": snap.get("exchange", "unbekannt"),
        "open_trades": open_trades,
        "signature": signature,
    }


# ---------------------------------------------------------------------------
# CPU fast-reply + LLM context + slash-command dispatcher
# ---------------------------------------------------------------------------


def cpu_fast_reply(prompt: str) -> str | None:
    """Ultraschnelle CPU-basierte VIRGINIE-Antwort ohne externen LLM-Call."""
    p = str(prompt or "").strip().lower()
    if not p:
        return None
    if any(k in p for k in ("risiko", "risk", "verlust", "drawdown")):
        return (
            "CPU-Quickcheck: Risiko zuerst. Prüfe max_drawdown, daily_loss_limit und open_trades. "
            "Wenn Drawdown steigt, Trade-Frequenz reduzieren und Stops enger setzen."
        )
    if any(k in p for k in ("markt", "market", "regime", "trend")):
        return (
            "CPU-Quickcheck: Regime + Volatilität zuerst prüfen. "
            "Nur bei bestätigtem Trend aggressiv handeln, sonst Positionsgröße drosseln."
        )
    if any(k in p for k in ("setup", "konfig", "config", "einstellung")):
        return (
            "CPU-Quickcheck Setup: 1) virginie_primary_control aktiv, 2) ai_min_confidence "
            "validieren, 3) stop_loss/take_profit auf aktuelle Volatilität abstimmen."
        )
    if len(p.split()) <= 5:
        return (
            "Beschreibe bitte kurz Symbol, Ziel und Risiko-Toleranz, dann gebe ich dir "
            "einen konkreten Plan."
        )
    return None


def build_chat_context(user_id: int, *, ai_engine: Any, state: Any) -> str:
    """Build the prompt-context string handed to the LLM."""
    ai = ai_engine.to_dict() if ai_engine else {}
    snap = state.snapshot() if state else {}
    ass = ai.get("assistant_agents", {}) if isinstance(ai, dict) else {}
    recent = chat_history_for_user(user_id)[-8:]
    recent_lines = []
    for item in recent:
        role = "User" if str(item.get("role", "")) == "user" else "VIRGINIE"
        msg = str(item.get("content", "")).strip().replace("\n", " ")
        if msg:
            recent_lines.append(f"- {role}: {msg[:160]}")
    recent_block = "\n".join(recent_lines) if recent_lines else "- (keine Historie)"
    return (
        "Du bist VIRGINIE, die Trading-Assistentin im TREVLIX Admin-Dashboard.\n"
        "Antwortstil: kurz, konkret, handlungsorientiert, sicherheitsbewusst.\n"
        "Keine Garantien, stattdessen klare nächste Schritte vorschlagen.\n"
        f"Aktuelle Bot-Lage: running={bool(snap.get('running', False))}, "
        f"paper_trading={bool(snap.get('paper_trading', True))}, "
        f"exchange={snap.get('exchange', 'unbekannt')}, "
        f"portfolio={snap.get('portfolio_value', 0)}.\n"
        f"VIRGINIE-Agenten: count={ass.get('registered_agents', 0)}, "
        f"coverage={ass.get('coverage_pct', 0)}%, "
        f"last_agent={ass.get('last_agent', '—')}.\n"
        "Letzte Unterhaltung (gekürzt):\n"
        f"{recent_block}"
    )


def generate_chat_reply(
    user_id: int,
    user_prompt: str,
    *,
    config: dict[str, Any],
    ai_engine: Any,
    state: Any,
    knowledge_base: Any,
    log: Any,
) -> str:
    """Slash-command dispatcher + CPU fast-reply + LLM fallback."""
    prompt = str(user_prompt or "").strip()
    if not prompt:
        return "Bitte sende eine konkrete Frage, damit ich dir gezielt helfen kann."
    status = runtime_status(config=config, ai_engine=ai_engine)
    if not status.get("enabled", True):
        return "VIRGINIE ist aktuell deaktiviert. Aktiviere 'virginie_enabled' in den Settings."
    cmd = prompt.lower()
    if cmd in {"/help", "help"}:
        return (
            "VIRGINIE Kommandos: /status (Live-Status), /review (letztes Self-Review), "
            "/plan (Aktionsplan), /edge (Edge-Profil), /help (diese Hilfe). "
            "Du kannst auch normale Fragen zu Risiko, Setup und Strategie stellen."
        )
    if cmd in {"/status", "status"}:
        agents = status.get("assistant_agents", {})
        return (
            f"Status: {'Primary' if status.get('primary_control') else 'Hybrid'} | "
            f"w={status.get('autonomy_weight', 0):.2f} | "
            f"Agents={agents.get('registered_agents', 0)} | "
            f"Coverage={agents.get('coverage_pct', 0)}% | "
            f"Last={agents.get('last_agent', '—')}"
        )
    if cmd in {"/review", "review"}:
        review = status.get("assistant_review", {})
        summary = str(review.get("summary", "")).strip() if isinstance(review, dict) else ""
        return (
            summary
            or "Noch kein Self-Review vorhanden. Nach weiteren Entscheidungen erneut prüfen."
        )
    if cmd in {"/plan", "plan", "/diagnose", "diagnose"}:
        advice = runtime_advice(config=config, ai_engine=ai_engine)
        action_lines = [
            f"{i + 1}. [{a.get('priority', 'low')}] {a.get('title', 'Schritt')} – "
            f"{a.get('detail', '')}"
            for i, a in enumerate(advice.get("actions", []))
        ]
        return "VIRGINIE Aktionsplan:\n" + (
            "\n".join(action_lines) if action_lines else "Keine Aktionen."
        )
    if cmd in {"/edge", "edge"}:
        edge = edge_profile(config=config, ai_engine=ai_engine, state=state)
        return (
            f"VIRGINIE Edge: {edge.get('edge_score', 0)} / 100 | Tier {edge.get('tier')} | "
            f"Urgency {edge.get('urgency')} | Exchange {edge.get('exchange')} | "
            f"Sig {edge.get('signature')}"
        )
    if bool(config.get("virginie_cpu_fast_chat", True)):
        fast_reply = cpu_fast_reply(prompt)
        if fast_reply:
            return fast_reply
    context = build_chat_context(user_id, ai_engine=ai_engine, state=state)
    try:
        reply = knowledge_base.query_llm_with_tools(prompt, context)
        if reply:
            return str(reply).strip()[:4000]
    except Exception as exc:  # noqa: BLE001 – LLM fallback must not raise
        log.debug("VIRGINIE chat LLM fallback: %s", exc)
    return (
        "Ich konnte die LLM-Antwort gerade nicht abrufen. "
        "Bitte prüfe die LLM-Konfiguration unter Wissen/LLM-Status und versuche es erneut."
    )
