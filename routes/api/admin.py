"""Admin Blueprint – Verwaltungsrouten (nur für Admins).

Enthält: User-Verwaltung, Config, Exchanges, Audit-Log,
IP-Whitelist, Telegram, Funding-Rates, News-Filter.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from flask import Blueprint, jsonify, request, session

if TYPE_CHECKING:
    from routes.api.deps import AppDeps

_PROTECTED_KEYS = frozenset(
    {
        "api_key",
        "secret",
        "short_api_key",
        "short_secret",
        "mysql_pass",
        "mysql_host",
        "mysql_port",
        "mysql_user",
        "mysql_db",
        "jwt_secret",
        "admin_password",
        "cryptopanic_token",
        "discord_webhook",
        "telegram_token",
        "telegram_chat_id",
        "encryption_key",
    }
)


def create_admin_blueprint(deps: AppDeps) -> Blueprint:
    """Erstellt den Admin-Blueprint."""
    bp = Blueprint("api_admin", __name__)

    cfg = deps.config
    db = deps.db
    log = deps.log
    auth = deps.api_auth_required
    admin = deps.admin_required
    body = deps.get_json_body
    si = deps.safe_int
    sf = deps.safe_float

    def _db_audit(user_id, action, detail=""):
        if deps.db_audit_fn:
            deps.db_audit_fn(user_id, action, detail)

    def _set_env(key, value):
        if deps.set_env_var_fn:
            deps.set_env_var_fn(key, value)

    # ── User-Verwaltung ───────────────────────────────────────────────────────

    @bp.route("/api/v1/admin/users")
    @auth
    @admin
    def api_admin_users():
        return jsonify(db.get_all_users())

    @bp.route("/api/v1/admin/users", methods=["POST"])
    @auth
    @admin
    def api_admin_create_user():
        data = body()
        if deps.validate_admin_user_payload:
            is_valid, payload, error_key, error_message = deps.validate_admin_user_payload(data)
            if not is_valid:
                return jsonify({"ok": False, "error": error_message, "key": error_key}), 400
        else:
            payload = data
        ok = db.create_user(
            payload["username"], payload["password"], payload["role"], payload.get("balance", 0)
        )
        return jsonify({"ok": ok})

    # ── Config ────────────────────────────────────────────────────────────────

    @bp.route("/api/v1/admin/config")
    @auth
    @admin
    def api_admin_config():
        _HIDDEN = {
            "api_key",
            "secret",
            "mysql_pass",
            "admin_password",
            "jwt_secret",
            "short_api_key",
            "short_secret",
            "cryptopanic_token",
            "encryption_key",
            "secret_key",
            "telegram_token",
            "extra_exchanges",
            "funding_rate_cache",
        }
        safe = {k: v for k, v in cfg.items() if k not in _HIDDEN}
        return jsonify(safe)

    @bp.route("/api/v1/admin/config", methods=["POST"])
    @auth
    @admin
    def api_admin_config_update():
        data = body()
        updated = []
        for k, v in data.items():
            if k in _PROTECTED_KEYS:
                continue
            if k in cfg:
                original = cfg[k]
                if isinstance(original, (list, dict)):
                    if not isinstance(v, type(original)):
                        continue
                elif isinstance(original, bool):
                    v = bool(v)
                elif isinstance(original, int):
                    v = si(v, original)
                elif isinstance(original, float):
                    v = sf(v, original)
                cfg[k] = v
                updated.append(k)
        _db_audit(
            request.user_id,
            "config_update",
            f"Geändert: {', '.join(updated) if updated else 'nichts'}",
        )
        return jsonify({"ok": True, "updated": updated})

    # ── Exchanges ─────────────────────────────────────────────────────────────

    @bp.route("/api/v1/admin/exchanges")
    @auth
    @admin
    def api_admin_exchanges():
        try:
            with db._get_conn() as conn:
                with conn.cursor() as c:
                    c.execute(
                        "SELECT ue.*, u.username FROM user_exchanges ue "
                        "JOIN users u ON ue.user_id = u.id ORDER BY u.username, ue.exchange"
                    )
                    rows = c.fetchall()
            result = []
            for r in rows:
                d = dict(r)
                d.pop("api_key", None)
                d.pop("api_secret", None)
                if d.get("created_at") and hasattr(d["created_at"], "isoformat"):
                    d["created_at"] = d["created_at"].isoformat()
                result.append(d)
            return jsonify(result)
        except Exception as e:
            log.error("API error: %s", e)
            return jsonify({"error": "Internal server error"}), 500

    @bp.route("/api/v1/admin/exchanges/<int:exchange_id>/toggle", methods=["POST"])
    @auth
    @admin
    def api_admin_exchange_toggle(exchange_id):
        enabled = body().get("enabled", False)
        try:
            with db._get_conn() as conn:
                with conn.cursor() as c:
                    c.execute(
                        "UPDATE user_exchanges SET enabled=%s WHERE id=%s", (enabled, exchange_id)
                    )
            return jsonify({"ok": True})
        except Exception as e:
            log.error("API error: %s", e)
            return jsonify({"error": "Internal server error"}), 500

    # ── Audit-Log ─────────────────────────────────────────────────────────────

    @bp.route("/api/v1/admin/audit-log")
    @auth
    @admin
    def api_audit_log():
        try:
            action_filter = request.args.get("action")
            limit = min(si(request.args.get("limit", 200), 200), 1000)
            with db._get_conn() as conn:
                with conn.cursor() as c:
                    if action_filter:
                        c.execute(
                            "SELECT * FROM audit_log WHERE action=%s ORDER BY created_at DESC LIMIT %s",
                            (action_filter, limit),
                        )
                    else:
                        c.execute(
                            "SELECT * FROM audit_log ORDER BY created_at DESC LIMIT %s", (limit,)
                        )
                    rows = c.fetchall()
            result = []
            for r in rows:
                d = dict(r)
                if d.get("created_at") and hasattr(d["created_at"], "isoformat"):
                    d["created_at"] = d["created_at"].isoformat()
                result.append(d)
            return jsonify(result)
        except Exception as e:
            log.error("API error: %s", e)
            return jsonify({"error": "Internal server error"}), 500

    # ── IP-Whitelist ──────────────────────────────────────────────────────────

    @bp.route("/api/v1/admin/ip-whitelist", methods=["GET"])
    @auth
    @admin
    def api_ip_whitelist_get():
        return jsonify(
            {"whitelist": cfg.get("ip_whitelist", []), "active": bool(cfg.get("ip_whitelist"))}
        )

    @bp.route("/api/v1/admin/ip-whitelist", methods=["POST"])
    @auth
    @admin
    def api_ip_whitelist_set():
        ips = body().get("ips", [])
        cfg["ip_whitelist"] = [ip.strip() for ip in ips if ip.strip()]
        _set_env("IP_WHITELIST", ",".join(cfg["ip_whitelist"]))
        _db_audit(session.get("user_id", 0), "ip_whitelist_update", str(cfg["ip_whitelist"]))
        return jsonify({"whitelist": cfg["ip_whitelist"]})

    # ── Telegram ─────────────────────────────────────────────────────────────

    @bp.route("/api/v1/telegram/test", methods=["POST"])
    @auth
    @admin
    def api_telegram_test():
        if deps.telegram is None:
            return jsonify({"success": False, "enabled": False})
        ok = deps.telegram.test()
        return jsonify({"success": ok, "enabled": deps.telegram.enabled})

    @bp.route("/api/v1/telegram/configure", methods=["POST"])
    @auth
    @admin
    def api_telegram_configure():
        d = body()
        token = d.get("token", "").strip()
        chat_id = d.get("chat_id", "").strip()
        if not token or not chat_id:
            return jsonify({"error": "token und chat_id erforderlich"}), 400
        cfg["telegram_token"] = token
        cfg["telegram_chat_id"] = chat_id
        _set_env("TELEGRAM_TOKEN", token)
        _set_env("TELEGRAM_CHAT_ID", chat_id)
        _db_audit(session.get("user_id", 0), "telegram_configure", "Telegram konfiguriert")
        ok = deps.telegram.test() if deps.telegram else False
        return jsonify(
            {"success": ok, "enabled": deps.telegram.enabled if deps.telegram else False}
        )

    # ── Funding-Rates ─────────────────────────────────────────────────────────

    @bp.route("/api/v1/funding-rates")
    @auth
    def api_funding_rates():
        n = si(request.args.get("n", 20), 20)
        if deps.funding_tracker is None:
            return jsonify({"top_rates": [], "status": {}})
        return jsonify(
            {
                "top_rates": deps.funding_tracker.top_rates(n),
                "status": deps.funding_tracker.status(),
            }
        )

    @bp.route("/api/v1/funding-rates/config", methods=["POST"])
    @auth
    @admin
    def api_funding_config():
        d = body()
        cfg["funding_rate_filter"] = bool(d.get("enabled", True))
        cfg["funding_rate_max"] = sf(d.get("max_rate", 0.001), 0.001)
        status = deps.funding_tracker.status() if deps.funding_tracker else {}
        return jsonify({"success": True, **status})

    # ── News-Filter ───────────────────────────────────────────────────────────

    @bp.route("/api/v1/config/news-filter", methods=["GET", "POST"])
    @auth
    @admin
    def api_news_filter():
        if request.method == "POST":
            d = body()
            cfg["news_sentiment_min"] = sf(
                d.get("min_score", cfg["news_sentiment_min"]), cfg["news_sentiment_min"]
            )
            cfg["news_require_positive"] = bool(
                d.get("require_positive", cfg["news_require_positive"])
            )
            cfg["news_block_score"] = sf(
                d.get("block_score", cfg["news_block_score"]), cfg["news_block_score"]
            )
            _db_audit(
                session.get("user_id", 0),
                "news_filter_update",
                f"min={cfg['news_sentiment_min']} pos={cfg['news_require_positive']}",
            )
            return jsonify(
                {
                    "success": True,
                    "config": {
                        "news_sentiment_min": cfg["news_sentiment_min"],
                        "news_require_positive": cfg["news_require_positive"],
                        "news_block_score": cfg["news_block_score"],
                    },
                }
            )
        return jsonify(
            {
                "news_sentiment_min": cfg.get("news_sentiment_min", -0.2),
                "news_require_positive": cfg.get("news_require_positive", False),
                "news_block_score": cfg.get("news_block_score", -0.4),
            }
        )

    # ── Strategy Weights ──────────────────────────────────────────────────────

    @bp.route("/api/v1/strategies/weights")
    @auth
    def api_strategy_weights():
        if deps.adaptive_weights is None:
            return jsonify({"weights": {}, "performance": []})
        regime = request.args.get("regime")
        return jsonify(
            {
                "weights": deps.adaptive_weights.get_weights(regime),
                "performance": deps.adaptive_weights.strategy_performance(),
                "regime_performance": deps.adaptive_weights.regime_performance(),
                **deps.adaptive_weights.stats(),
            }
        )

    return bp
