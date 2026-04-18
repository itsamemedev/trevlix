"""Dependency-Container für alle API-Blueprints.

Alle geteilten Objekte (State, DB, Config, Services) werden einmalig in
``server.py`` gebündelt und an Blueprint-Fabriken weitergegeben – kein
impliziter Zugriff auf globale Variablen in server.py.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass
class AppDeps:
    """Gebündelter Dependency-Container für Blueprint-Fabriken."""

    # ── Kern ─────────────────────────────────────────────────────────────────
    config: dict
    state: Any
    db: Any
    log: Any

    # ── Auth-Dekoratoren ──────────────────────────────────────────────────────
    api_auth_required: Callable
    admin_required: Callable

    # ── Request-Helfer ────────────────────────────────────────────────────────
    get_json_body: Callable
    safe_int: Callable
    safe_float: Callable
    safe_bool: Callable

    # ── Trading-Funktionen ────────────────────────────────────────────────────
    create_exchange: Callable
    close_position: Callable
    open_position: Callable
    fetch_markets: Callable
    scan_symbol: Callable
    get_exchange_fee_rate: Callable
    get_heatmap_data: Callable
    fetch_aggregated_balance: Callable
    safety_scan: Callable

    # ── Trading-Ops-Modul (für Modul-Globals wie trade_execution) ────────────
    trading_ops_mod: Any = None

    # ── Metadaten ─────────────────────────────────────────────────────────────
    bot_version: str = ""
    bot_name: str = ""
    bot_full: str = ""

    # ── Services ──────────────────────────────────────────────────────────────
    ai_engine: Any = None
    backtest: Any = None
    tax_report: Any = None
    trade_mode: Any = None
    virginie: Any = None
    knowledge: Any = None
    mcp_tools: Any = None
    risk_mgr: Any = None
    adv_risk: Any = None
    revenue: Any = None
    cluster_ctrl: Any = None
    alert_escalation: Any = None
    healer: Any = None
    perf_attribution: Any = None
    trade_dna: Any = None
    trading_algos: Any = None
    smart_exits: Any = None
    grid_engine: Any = None
    arb_scanner: Any = None
    short_engine: Any = None
    dominance: Any = None
    anomaly: Any = None
    genetic: Any = None
    rl_agent: Any = None
    news_fetcher: Any = None
    onchain: Any = None
    fg_idx: Any = None
    sentiment_f: Any = None
    funding_tracker: Any = None
    adaptive_weights: Any = None
    symbol_cooldown: Any = None
    liq: Any = None
    ob: Any = None
    discord: Any = None
    telegram: Any = None
    price_alerts: Any = None
    emit_event: Callable | None = None
    limiter: Any = None
    exchange_default_fees: dict = field(default_factory=dict)
    exchange_map: dict = field(default_factory=dict)

    # ── Virginie-Forecast-Funktionen ──────────────────────────────────────────
    get_virginie_forecast_feed: Callable | None = None
    get_virginie_forecast_quality: Callable | None = None
    get_virginie_forecast_stats: Callable | None = None

    # ── Sonstige Hilfsfunktionen ──────────────────────────────────────────────
    audit_fn: Callable | None = None
    db_audit_fn: Callable | None = None
    build_prometheus_lines: Callable | None = None
    build_ws_state_snapshot: Callable | None = None
    trades_to_json: Callable | None = None
    tax_rows_to_csv: Callable | None = None
    verify_latest_backup: Callable | None = None
    apply_update: Callable | None = None
    get_update_status: Callable | None = None
    rollback_update: Callable | None = None
    reveal_and_decrypt: Callable | None = None
    is_single_exchange_mode: Callable | None = None
    get_admin_exchange_by_name: Callable | None = None
    get_admin_primary_exchange: Callable | None = None
    get_exchange_key_states: Callable | None = None
    pin_user_exchange: Callable | None = None
    normalize_exchange_name: Callable | None = None
    validate_admin_user_payload: Callable | None = None
    is_admin_password_weak: Callable | None = None
    get_llm_header_status_fn: Callable | None = None
    maybe_auto_start_bot_fn: Callable | None = None
    set_env_var_fn: Callable | None = None
    bot_loop_fn: Callable | None = None
