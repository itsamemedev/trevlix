"""System analytics builders extracted from server.py.

Three pure-ish builder functions that produce dashboards/payloads from
the long-lived runtime objects (CONFIG, db, ai_engine, ...). Pure-ish
because they catch broad exceptions and degrade gracefully – no caller
should crash because, say, ``revenue_tracker.snapshot()`` raised.

Module is import-safe: all dependencies are passed as keyword arguments
at call time, no module-level state is touched.
"""

from __future__ import annotations

import platform
import shutil
import time
import urllib.request
from datetime import datetime
from typing import Any

# ---------------------------------------------------------------------------
# LLM provider helpers
# ---------------------------------------------------------------------------

_LLM_PROVIDER_HOSTS: tuple[tuple[str, str], ...] = (
    ("openai.com", "OpenAI"),
    ("anthropic.com", "Anthropic"),
    ("groq.com", "Groq"),
    ("cerebras.ai", "Cerebras"),
    ("openrouter.ai", "OpenRouter"),
    ("huggingface.co", "HuggingFace"),
    ("together.xyz", "Together"),
    ("mistral.ai", "Mistral"),
    ("localhost", "Local"),
    ("127.0.0.1", "Local"),
    ("0.0.0.0", "Local"),
)


def derive_llm_provider_name(endpoint: str) -> str:
    """Map an LLM endpoint URL to a human-readable provider label.

    Falls back to ``"Custom"`` for unknown hosts and ``"—"`` for empty
    input. Pure function – no I/O, safe to call anywhere.
    """
    if not endpoint:
        return "—"
    ep = endpoint.lower()
    for needle, label in _LLM_PROVIDER_HOSTS:
        if needle in ep:
            return label
    return "Custom"


def build_llm_header_status(
    *,
    config: dict[str, Any],
    knowledge_base: Any,
    log: Any,
) -> dict[str, Any]:
    """Cheap LLM status payload for the dashboard header chip.

    No network calls – this is the lightweight version of the system
    analytics builder. Multi-provider state is read from
    ``knowledge_base._multi_llm.status()`` if available.
    """
    llm_endpoint = config.get("llm_endpoint", "") or getattr(knowledge_base, "_llm_endpoint", "")
    llm_model = config.get("llm_model", "—") or getattr(knowledge_base, "_llm_model", "—")
    out: dict[str, Any] = {
        "endpoint": llm_endpoint or "—",
        "model": llm_model,
        "provider": "—",
        "status": "⚪ Nicht konfiguriert",
    }
    if llm_endpoint:
        out["provider"] = derive_llm_provider_name(llm_endpoint)
        out["status"] = "✅ Konfiguriert"
    try:
        multi_llm = getattr(knowledge_base, "_multi_llm", None)
        if multi_llm:
            provider_stats = multi_llm.status()
            if provider_stats:
                active_ok = [p for p in provider_stats if p.get("available")]
                if not llm_endpoint:
                    out["endpoint"] = "multi-provider"
                if out["model"] in ("", "—"):
                    out["model"] = ", ".join(p.get("name", "?") for p in provider_stats[:3])
                primary = (active_ok or provider_stats)[0]
                out["provider"] = str(primary.get("name", "—")).title()
                out["status"] = (
                    f"✅ {len(active_ok)}/{len(provider_stats)} Provider online"
                    if active_ok
                    else "❌ Alle Provider offline"
                )
    except Exception as e:  # noqa: BLE001 – status helpers must not raise
        log.debug("LLM header status failed: %s", e)
    return out


# ---------------------------------------------------------------------------
# System analytics
# ---------------------------------------------------------------------------


def _section_system() -> dict[str, Any]:
    """OS / CPU / memory / disk / uptime block."""
    out: dict[str, Any] = {}
    try:
        import psutil

        mem = psutil.virtual_memory()
        cpu_pct = psutil.cpu_percent(interval=0.1)
        boot = datetime.fromtimestamp(psutil.boot_time())
        uptime_delta = datetime.now() - boot
        uptime_str = f"{uptime_delta.days}d {uptime_delta.seconds // 3600}h"
        out = {
            "python": platform.python_version(),
            "platform": f"{platform.system()} {platform.release()}",
            "cpu": f"{cpu_pct}%",
            "memory": f"{mem.used // (1024**2)}/{mem.total // (1024**2)} MB ({mem.percent}%)",
            "disk": "—",
            "uptime": uptime_str,
        }
    except ImportError:
        out = {
            "python": platform.python_version(),
            "platform": f"{platform.system()} {platform.release()}",
            "cpu": "—",
            "memory": "—",
            "disk": "—",
            "uptime": "—",
        }
    try:
        disk = shutil.disk_usage("/")
        out["disk"] = (
            f"{disk.used // (1024**3)}/{disk.total // (1024**3)} GB "
            f"({100 * disk.used // disk.total}%)"
        )
    except Exception:
        pass
    return out


def _section_api(*, config: dict[str, Any], state: Any, create_exchange) -> dict[str, Any]:
    """Exchange-API connectivity block."""
    exchange_name = config.get("exchange", "unknown")
    discord_configured = bool(config.get("discord_webhook"))
    telegram_configured = bool(config.get("telegram_token"))
    api_latency = "—"
    api_connected = "⏸️"
    try:
        ex = create_exchange()
        start_t = time.time()
        ex.fetch_time()
        api_latency = f"{int((time.time() - start_t) * 1000)} ms"
        api_connected = "✅"
    except Exception:
        if getattr(state, "running", False):
            api_connected = "⚠️"
        api_latency = "timeout"
    return {
        "exchange": exchange_name.upper(),
        "connected": api_connected,
        "latency": api_latency,
        "calls_24h": str(getattr(state, "api_calls_24h", "—")),
        "discord": "✅" if discord_configured else "❌",
        "telegram": "✅" if telegram_configured else "❌",
    }


def _section_llm(*, config: dict[str, Any], knowledge_base: Any, log: Any) -> dict[str, Any]:
    """LLM endpoint + provider + connectivity block (with network probe)."""
    llm_endpoint = config.get("llm_endpoint", "") or getattr(knowledge_base, "_llm_endpoint", "")
    llm_model = config.get("llm_model", "—") or getattr(knowledge_base, "_llm_model", "—")
    out: dict[str, Any] = {
        "endpoint": llm_endpoint or "—",
        "model": llm_model,
        "provider": "—",
        "status": "⚪ Nicht konfiguriert",
        "latency": "—",
        "queries_24h": "—",
        "tokens_24h": "—",
    }
    if llm_endpoint:
        out["provider"] = derive_llm_provider_name(llm_endpoint)
        out["status"] = "✅ Konfiguriert"

    try:
        multi_llm = getattr(knowledge_base, "_multi_llm", None)
        if multi_llm:
            provider_stats = multi_llm.status()
            if provider_stats:
                total_reqs = sum(int(p.get("requests", 0) or 0) for p in provider_stats)
                total_tokens = sum(int(p.get("tokens", 0) or 0) for p in provider_stats)
                active_ok = [p for p in provider_stats if p.get("available")]
                if not llm_endpoint:
                    out["endpoint"] = "multi-provider"
                if out["model"] in ("", "—"):
                    out["model"] = ", ".join(p.get("name", "?") for p in provider_stats[:3])
                primary = (active_ok or provider_stats)[0] if provider_stats else None
                if primary:
                    out["provider"] = str(primary.get("name", "—")).title()
                out["status"] = (
                    f"✅ {len(active_ok)}/{len(provider_stats)} Provider online"
                    if active_ok
                    else "❌ Alle Provider offline"
                )
                out["queries_24h"] = str(total_reqs)
                out["tokens_24h"] = str(total_tokens)
    except Exception as e:  # noqa: BLE001 – status block must not raise
        log.debug("Multi-LLM status query failed: %s", e)

    if llm_endpoint:
        try:
            # Compatible with OpenAI-/vLLM (/models) and Ollama (/api/tags)
            candidates = [
                llm_endpoint.rstrip("/") + "/models",
                llm_endpoint.rstrip("/") + "/api/tags",
            ]
            last_exc: Exception | None = None
            for url in candidates:
                try:
                    start_t = time.time()
                    req = urllib.request.Request(url, method="GET")
                    req.add_header("Connection", "close")
                    with urllib.request.urlopen(req, timeout=5):
                        latency_ms = int((time.time() - start_t) * 1000)
                        out["status"] = "✅ Online"
                        out["latency"] = f"{latency_ms} ms"
                        last_exc = None
                        break
                except Exception as exc:  # noqa: BLE001 – continue probing
                    last_exc = exc
            if last_exc is not None:
                out["status"] = "❌ Offline"
        except Exception:
            out["status"] = "❌ Offline"
    return out


def _section_db(*, db: Any) -> dict[str, Any]:
    """Database pool + size block."""
    out: dict[str, Any] = {
        "pool_size": "—",
        "active_conn": "—",
        "utilization": "—",
        "tables": "—",
        "size": "—",
    }
    try:
        pool_info = db.pool_stats() if hasattr(db, "pool_stats") else {}
        out["pool_size"] = pool_info.get("pool_size", "—")
        out["active_conn"] = pool_info.get("in_use", "—")
        util = pool_info.get("utilization_pct")
        out["utilization"] = f"{util}%" if util is not None else "—"
    except Exception:
        pass
    try:
        with db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema=DATABASE()"
                )
                row = cur.fetchone()
                out["tables"] = row[0] if row else "—"
                cur.execute(
                    "SELECT ROUND(SUM(data_length+index_length)/1024/1024,1) "
                    "FROM information_schema.tables WHERE table_schema=DATABASE()"
                )
                row = cur.fetchone()
                out["size"] = f"{row[0]} MB" if row and row[0] else "—"
    except Exception:
        pass
    return out


def _section_ai(*, ai_engine: Any, knowledge_base: Any) -> dict[str, Any]:
    """AI engine training + idle-learning block."""
    try:
        ai_dict = ai_engine.to_dict()
        idle_meta: dict[str, Any] = {}
        try:
            if hasattr(knowledge_base, "idle_learning_status"):
                idle_meta = knowledge_base.idle_learning_status()
        except Exception:
            idle_meta = {}
        return {
            "is_trained": ai_dict.get("is_trained", False),
            "training_ver": ai_dict.get("training_version", 0),
            "status_msg": ai_dict.get("status_msg", ""),
            "progress_pct": ai_dict.get("progress_pct", 0),
            "wf_accuracy": ai_dict.get("wf_accuracy", 0),
            "bull_accuracy": ai_dict.get("bull_accuracy", 0),
            "bear_accuracy": ai_dict.get("bear_accuracy", 0),
            "samples": ai_dict.get("samples", 0),
            "bull_samples": ai_dict.get("bull_samples", 0),
            "bear_samples": ai_dict.get("bear_samples", 0),
            "allowed_count": ai_dict.get("allowed_count", 0),
            "blocked_count": ai_dict.get("blocked_count", 0),
            "weights": ai_dict.get("weights", []),
            "ai_log": ai_dict.get("ai_log", []),
            "trained": ai_dict.get("is_trained", False),
            "accuracy": f"{ai_dict.get('accuracy', 0) * 100:.1f}%",
            "cv_accuracy": f"{ai_dict.get('cv_accuracy', 0) * 100:.1f}%",
            "predictions": ai_dict.get("predictions_made", 0),
            "correct": ai_dict.get("predictions_correct", 0),
            "version": ai_dict.get("training_version", 0),
            "assistant_name": ai_dict.get("assistant_name", "AI"),
            "assistant_version": ai_dict.get("assistant_version", "0.0.0"),
            "assistant_examples": ai_dict.get("assistant_examples", {}),
            "assistant_agents": ai_dict.get("assistant_agents", {}),
            "assistant_review": ai_dict.get("assistant_review", {}),
            "assistant_primary_control": ai_dict.get("assistant_primary_control", False),
            "assistant_autonomy_weight": ai_dict.get("assistant_autonomy_weight", 0.7),
            "last_trained": ai_dict.get("last_trained", "—"),
            "trades_since_retrain": ai_dict.get("trades_since_retrain", 0),
            "idle_learning_runs": idle_meta.get("runs", 0),
            "idle_learning_last_at": idle_meta.get("last_run_at"),
            "idle_learning_summary": idle_meta.get("last_summary", ""),
            "idle_learning_error": idle_meta.get("last_error", ""),
            "llm_providers_used": idle_meta.get("providers_used", 0),
            "llm_responses_used": idle_meta.get("responses_used", 0),
            "llm_collaboration_active": bool(
                idle_meta.get("providers_used", 0) or idle_meta.get("responses_used", 0)
            ),
        }
    except Exception:
        return {}


def _section_risk(*, risk: Any) -> dict[str, Any]:
    try:
        cb = risk.circuit_status()
        return {
            "circuit_active": cb.get("active", False),
            "circuit_losses": cb.get("losses", 0),
            "circuit_limit": cb.get("limit", 0),
            "max_drawdown": f"{risk.max_drawdown:.1f}%",
        }
    except Exception:
        return {}


def _section_revenue(*, revenue_tracker: Any) -> dict[str, Any]:
    try:
        rev = revenue_tracker.snapshot()
        return {
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
        return {}


def _section_attribution(*, perf_attribution: Any) -> dict[str, Any]:
    try:
        pa_stats = perf_attribution.stats()
        return {
            "total_trades": pa_stats.get("total_trades", 0),
            "profit_factor": round(pa_stats.get("profit_factor", 0), 2),
            "expectancy": round(pa_stats.get("expectancy", 0), 2),
            "sharpe": round(pa_stats.get("sharpe_ratio", 0), 2),
        }
    except Exception:
        return {}


def _section_strategies(*, adaptive_weights: Any) -> dict[str, Any]:
    try:
        aw = adaptive_weights.to_dict()
        perf_list = aw.get("performance", [])
        top_strats = sorted(perf_list, key=lambda x: x.get("weight", 0), reverse=True)[:5]
        return {
            "total": aw.get("strategies_total", 0),
            "adapted": aw.get("strategies_adapted", 0),
            "total_votes": aw.get("total_votes", 0),
            "top": [
                {
                    "name": s.get("strategy", "?"),
                    "weight": round(s.get("weight", 0), 2),
                    "win_rate": f"{s.get('win_rate', 0):.0f}%",
                    "trades": s.get("trades", 0),
                }
                for s in top_strats
            ],
        }
    except Exception:
        return {}


def _section_healing(*, healer: Any) -> dict[str, Any]:
    try:
        return healer.health_snapshot()
    except Exception:
        return {}


def _section_cache() -> dict[str, Any]:
    try:
        from services.indicator_cache import cache_stats

        return cache_stats()
    except Exception:
        return {}


def build_system_analytics(
    *,
    config: dict[str, Any],
    state: Any,
    db: Any,
    ai_engine: Any,
    knowledge_base: Any,
    risk: Any,
    revenue_tracker: Any,
    perf_attribution: Any,
    adaptive_weights: Any,
    healer: Any,
    log: Any,
    create_exchange,
) -> dict[str, Any]:
    """Aggregate the full system-analytics payload for the dashboard.

    Each section is built by a private helper that never raises – the
    surrounding dashboard tab tolerates partial data.
    """
    return {
        "system": _section_system(),
        "api": _section_api(config=config, state=state, create_exchange=create_exchange),
        "llm": _section_llm(config=config, knowledge_base=knowledge_base, log=log),
        "db": _section_db(db=db),
        "ai": _section_ai(ai_engine=ai_engine, knowledge_base=knowledge_base),
        "risk": _section_risk(risk=risk),
        "revenue": _section_revenue(revenue_tracker=revenue_tracker),
        "attribution": _section_attribution(perf_attribution=perf_attribution),
        "strategies": _section_strategies(adaptive_weights=adaptive_weights),
        "healing": _section_healing(healer=healer),
        "cache": _section_cache(),
    }
