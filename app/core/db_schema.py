"""Database schema initialisation extracted from db_manager.

The original ``MySQLManager._init_db_once`` packed ~390 lines of
``CREATE TABLE`` / ``ALTER TABLE`` / seed-user / env-key-migration
into a single method on the manager. The DDL itself has no real
dependency on ``MySQLManager`` state – it just needs a cursor, a
config dict, a logger, and (for admin-password hashing + env-key
migration) bcrypt + the encryption helper.

``apply_schema(cursor, ...)`` is now a free function, so it is
testable against a mock cursor and the manager keeps an obvious
delegation wrapper.
"""

from __future__ import annotations

import hashlib
import os
from typing import Any

from services.encryption import encrypt_value


def apply_schema(
    cursor,
    *,
    config: dict[str, Any],
    log,
    bcrypt_module=None,
    bcrypt_available: bool = False,
) -> None:
    """Run all CREATE / ALTER / seed statements on ``cursor``.

    The cursor is assumed to be inside an open transaction managed by
    the caller. ``apply_schema`` does not commit and does not close
    anything – ``MySQLManager._init_db_once`` still controls the
    connection lifecycle.
    """
    c = cursor

    # ── Trades ──────────────────────────────────────────────────────────────
    c.execute("""CREATE TABLE IF NOT EXISTS trades (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id INT DEFAULT 1,
        symbol VARCHAR(20), entry DOUBLE, exit_price DOUBLE,
        qty DOUBLE, pnl DOUBLE, pnl_pct DOUBLE,
        reason VARCHAR(80), confidence DOUBLE,
        ai_score DOUBLE, win_prob DOUBLE, invested DOUBLE,
        opened DATETIME, closed DATETIME,
        exchange VARCHAR(20), regime VARCHAR(10),
        trade_type VARCHAR(10) DEFAULT 'long',
        partial_sold TINYINT DEFAULT 0,
        dca_level INT DEFAULT 0,
        news_score DOUBLE DEFAULT 0,
        onchain_score DOUBLE DEFAULT 0,
        INDEX idx_closed(closed), INDEX idx_symbol(symbol), INDEX idx_user(user_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""")
    for stmt in (
        "ALTER TABLE trades ADD COLUMN trade_mode VARCHAR(10) DEFAULT 'paper'",
        "ALTER TABLE trades ADD COLUMN fees DOUBLE DEFAULT 0",
        "ALTER TABLE trades ADD COLUMN order_ref VARCHAR(120) DEFAULT ''",
    ):
        try:
            c.execute(stmt)
        except Exception:
            pass

    # ── Orders / Decisions / Positions ──────────────────────────────────────
    c.execute("""CREATE TABLE IF NOT EXISTS trade_orders (
        id BIGINT AUTO_INCREMENT PRIMARY KEY,
        user_id INT DEFAULT 1,
        symbol VARCHAR(20) NOT NULL,
        side VARCHAR(8) NOT NULL,
        order_type VARCHAR(20) DEFAULT 'market',
        status VARCHAR(20) DEFAULT 'filled',
        price DOUBLE DEFAULT 0,
        qty DOUBLE DEFAULT 0,
        cost DOUBLE DEFAULT 0,
        fees DOUBLE DEFAULT 0,
        trade_mode VARCHAR(10) DEFAULT 'paper',
        exchange VARCHAR(20) DEFAULT '',
        exchange_order_id VARCHAR(120) DEFAULT '',
        reason VARCHAR(200) DEFAULT '',
        meta_json MEDIUMTEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_orders_user_time(user_id, created_at),
        INDEX idx_orders_symbol(symbol),
        INDEX idx_orders_mode(trade_mode)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""")

    c.execute("""CREATE TABLE IF NOT EXISTS trade_decisions (
        id BIGINT AUTO_INCREMENT PRIMARY KEY,
        user_id INT DEFAULT 1,
        symbol VARCHAR(20) NOT NULL,
        decision VARCHAR(20) NOT NULL,
        reason VARCHAR(255) DEFAULT '',
        confidence DOUBLE DEFAULT 0,
        ai_score DOUBLE DEFAULT 0,
        win_prob DOUBLE DEFAULT 0,
        trade_mode VARCHAR(10) DEFAULT 'paper',
        exchange VARCHAR(20) DEFAULT '',
        payload_json MEDIUMTEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_dec_user_time(user_id, created_at),
        INDEX idx_dec_symbol(symbol),
        INDEX idx_dec_mode(trade_mode)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""")

    c.execute("""CREATE TABLE IF NOT EXISTS trade_positions (
        id BIGINT AUTO_INCREMENT PRIMARY KEY,
        user_id INT DEFAULT 1,
        symbol VARCHAR(20) NOT NULL,
        side VARCHAR(10) DEFAULT 'long',
        qty DOUBLE DEFAULT 0,
        entry_price DOUBLE DEFAULT 0,
        invested DOUBLE DEFAULT 0,
        stop_loss DOUBLE DEFAULT 0,
        take_profit DOUBLE DEFAULT 0,
        trade_mode VARCHAR(10) DEFAULT 'paper',
        exchange VARCHAR(20) DEFAULT '',
        status VARCHAR(20) DEFAULT 'open',
        opened_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        closed_at DATETIME NULL,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        meta_json MEDIUMTEXT,
        UNIQUE KEY uq_open_pos (user_id, symbol, trade_mode, status),
        INDEX idx_pos_user_status(user_id, status),
        INDEX idx_pos_exchange(exchange)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""")

    # ── Users + AI training ─────────────────────────────────────────────────
    c.execute("""CREATE TABLE IF NOT EXISTS users (
        id INT AUTO_INCREMENT PRIMARY KEY,
        username VARCHAR(50) UNIQUE,
        password_hash VARCHAR(256),
        role VARCHAR(20) DEFAULT 'user',
        balance DOUBLE DEFAULT 10000.0,
        initial_balance DOUBLE DEFAULT 10000.0,
        api_key VARCHAR(200),
        api_secret VARCHAR(200),
        exchange VARCHAR(20) DEFAULT 'cryptocom',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        last_login DATETIME,
        settings_json MEDIUMTEXT
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""")

    c.execute("""CREATE TABLE IF NOT EXISTS ai_training (
        id INT AUTO_INCREMENT PRIMARY KEY,
        features TEXT, label TINYINT,
        regime VARCHAR(10) DEFAULT 'bull',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_regime(regime)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""")

    # ── Audit log ───────────────────────────────────────────────────────────
    c.execute("""CREATE TABLE IF NOT EXISTS audit_log (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id INT DEFAULT 0,
        action VARCHAR(80) NOT NULL,
        detail VARCHAR(500),
        ip VARCHAR(45),
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_user(user_id),
        INDEX idx_action(action),
        INDEX idx_time(created_at),
        INDEX idx_user_time(user_id, created_at)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""")
    try:
        c.execute("ALTER TABLE audit_log ADD INDEX idx_user_time(user_id, created_at)")
    except Exception:
        pass

    # ── Backtest / alerts / reports / market intel ──────────────────────────
    c.execute("""CREATE TABLE IF NOT EXISTS backtest_results (
        id INT AUTO_INCREMENT PRIMARY KEY,
        symbol VARCHAR(20), timeframe VARCHAR(10),
        candles INT, total_trades INT,
        win_rate DOUBLE, total_pnl DOUBLE,
        profit_factor DOUBLE, max_drawdown DOUBLE,
        result_json MEDIUMTEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""")

    c.execute("""CREATE TABLE IF NOT EXISTS price_alerts (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id INT DEFAULT 1,
        symbol VARCHAR(20), target_price DOUBLE,
        direction VARCHAR(10), triggered TINYINT DEFAULT 0,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        triggered_at DATETIME
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""")

    c.execute("""CREATE TABLE IF NOT EXISTS daily_reports (
        id INT AUTO_INCREMENT PRIMARY KEY,
        report_date DATE, report_json MEDIUMTEXT,
        sent_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        UNIQUE KEY uq_date(report_date)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""")

    c.execute("""CREATE TABLE IF NOT EXISTS sentiment_cache (
        symbol VARCHAR(20) PRIMARY KEY,
        score DOUBLE, source VARCHAR(20),
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""")

    c.execute("""CREATE TABLE IF NOT EXISTS news_cache (
        symbol VARCHAR(20) PRIMARY KEY,
        score DOUBLE, headline VARCHAR(500),
        article_count INT DEFAULT 0,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""")

    c.execute("""CREATE TABLE IF NOT EXISTS onchain_cache (
        symbol VARCHAR(20) PRIMARY KEY,
        whale_score DOUBLE, flow_score DOUBLE,
        net_score DOUBLE, detail VARCHAR(500),
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""")

    c.execute("""CREATE TABLE IF NOT EXISTS genetic_results (
        id INT AUTO_INCREMENT PRIMARY KEY,
        generation INT, fitness DOUBLE,
        genome_json TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""")

    c.execute("""CREATE TABLE IF NOT EXISTS arb_opportunities (
        id INT AUTO_INCREMENT PRIMARY KEY,
        symbol VARCHAR(20),
        exchange_buy VARCHAR(20), price_buy DOUBLE,
        exchange_sell VARCHAR(20), price_sell DOUBLE,
        spread_pct DOUBLE, executed TINYINT DEFAULT 0,
        profit DOUBLE DEFAULT 0,
        found_at DATETIME DEFAULT CURRENT_TIMESTAMP
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""")

    c.execute("""CREATE TABLE IF NOT EXISTS rl_episodes (
        id INT AUTO_INCREMENT PRIMARY KEY,
        episode INT, reward DOUBLE,
        state_json TEXT, action INT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""")

    c.execute("""CREATE TABLE IF NOT EXISTS api_tokens (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id INT, token VARCHAR(500), label VARCHAR(100),
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        last_used DATETIME, expires_at DATETIME,
        active TINYINT DEFAULT 1
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""")

    # ── User exchanges + passphrase migration ───────────────────────────────
    c.execute("""CREATE TABLE IF NOT EXISTS user_exchanges (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id INT NOT NULL,
        exchange VARCHAR(20) NOT NULL,
        api_key VARCHAR(500),
        api_secret VARCHAR(500),
        passphrase VARCHAR(500),
        enabled TINYINT DEFAULT 0,
        is_primary TINYINT DEFAULT 0,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        UNIQUE KEY uq_user_exchange(user_id, exchange),
        INDEX idx_user(user_id),
        INDEX idx_enabled(user_id, enabled)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""")
    c.execute(
        "SELECT COUNT(*) AS n FROM information_schema.columns "
        "WHERE table_schema=%s AND table_name='user_exchanges' "
        "AND column_name='passphrase'",
        (config["mysql_db"],),
    )
    row = c.fetchone() or {}
    if int(row.get("n", 0) or 0) == 0:
        try:
            c.execute(
                "ALTER TABLE user_exchanges ADD COLUMN passphrase VARCHAR(500) AFTER api_secret"
            )
        except Exception as e:
            log.debug("user_exchanges passphrase migration: %s", e)

    # ── Knowledge / DNA / revenue / healing / cluster / alerts ──────────────
    c.execute("""CREATE TABLE IF NOT EXISTS shared_knowledge (
        id INT AUTO_INCREMENT PRIMARY KEY,
        category VARCHAR(50) NOT NULL,
        key_name VARCHAR(100) NOT NULL,
        value_json MEDIUMTEXT,
        confidence DOUBLE DEFAULT 0.5,
        source VARCHAR(50) DEFAULT 'ai',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        UNIQUE KEY uq_cat_key(category, key_name),
        INDEX idx_category(category)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""")

    c.execute("""CREATE TABLE IF NOT EXISTS trade_dna (
        id INT AUTO_INCREMENT PRIMARY KEY,
        symbol VARCHAR(20),
        dna_hash VARCHAR(16),
        fingerprint VARCHAR(500),
        dimensions_json TEXT,
        raw_values_json TEXT,
        won TINYINT,
        pnl DOUBLE DEFAULT 0,
        dna_boost DOUBLE DEFAULT 1.0,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_hash(dna_hash),
        INDEX idx_symbol(symbol),
        INDEX idx_time(created_at)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""")

    c.execute("""CREATE TABLE IF NOT EXISTS revenue_trades (
        id INT AUTO_INCREMENT PRIMARY KEY,
        symbol VARCHAR(20),
        side VARCHAR(10),
        amount DOUBLE,
        price DOUBLE,
        fee DOUBLE DEFAULT 0,
        slippage_est DOUBLE DEFAULT 0,
        funding_fee DOUBLE DEFAULT 0,
        strategy VARCHAR(80),
        gross_pnl DOUBLE DEFAULT 0,
        net_pnl DOUBLE DEFAULT 0,
        recorded_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_time(recorded_at),
        INDEX idx_strategy(strategy),
        INDEX idx_symbol(symbol)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""")

    c.execute("""CREATE TABLE IF NOT EXISTS healing_incidents (
        id INT AUTO_INCREMENT PRIMARY KEY,
        service VARCHAR(30) NOT NULL,
        severity VARCHAR(20) NOT NULL,
        message VARCHAR(500),
        recovered TINYINT DEFAULT 0,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_service(service),
        INDEX idx_time(created_at)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""")

    c.execute("""CREATE TABLE IF NOT EXISTS cluster_nodes (
        id INT AUTO_INCREMENT PRIMARY KEY,
        name VARCHAR(50) UNIQUE NOT NULL,
        host VARCHAR(255) NOT NULL,
        port INT DEFAULT 5000,
        api_token VARCHAR(500),
        status VARCHAR(20) DEFAULT 'offline',
        last_check DATETIME,
        last_error VARCHAR(500),
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_status(status)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""")

    c.execute("""CREATE TABLE IF NOT EXISTS alert_escalations (
        alert_id VARCHAR(100) PRIMARY KEY,
        message VARCHAR(500),
        source VARCHAR(50) DEFAULT 'system',
        level INT DEFAULT 1,
        occurrence_count INT DEFAULT 1,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        escalated_at DATETIME,
        acknowledged TINYINT DEFAULT 0,
        resolved_at DATETIME,
        INDEX idx_level(level),
        INDEX idx_source(source)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""")

    # ── Seed admin user + .env-key migration ────────────────────────────────
    _seed_admin_user(
        c,
        config=config,
        log=log,
        bcrypt_module=bcrypt_module,
        bcrypt_available=bcrypt_available,
    )


def _seed_admin_user(
    c,
    *,
    config: dict[str, Any],
    log,
    bcrypt_module,
    bcrypt_available: bool,
) -> None:
    """Create the admin row if missing and migrate .env keys once."""
    c.execute("SELECT id FROM users WHERE username=%s", ("admin",))
    admin_row = c.fetchone()
    if not admin_row:
        pw = config["admin_password"].encode()
        if bcrypt_available and bcrypt_module is not None:
            h = bcrypt_module.hashpw(pw, bcrypt_module.gensalt()).decode()
        else:
            h = hashlib.sha256(pw).hexdigest()
        c.execute(
            "INSERT INTO users (username,password_hash,role,balance,initial_balance) "
            "VALUES('admin',%s,'admin',10000,10000)",
            (h,),
        )
        admin_id = c.lastrowid
    else:
        admin_id = admin_row["id"]

    env_key_plain = os.getenv("API_KEY", "").strip()
    env_secret_plain = os.getenv("API_SECRET", "").strip()
    env_exchange = (os.getenv("EXCHANGE", "") or "").strip().lower()
    env_passphrase = os.getenv("API_PASSPHRASE", "").strip()
    if admin_id and env_exchange and env_key_plain and env_secret_plain:
        c.execute(
            "SELECT COUNT(*) AS n FROM user_exchanges WHERE user_id=%s",
            (admin_id,),
        )
        has_any = int((c.fetchone() or {}).get("n", 0) or 0) > 0
        if not has_any:
            try:
                enc_key = encrypt_value(env_key_plain)
                enc_sec = encrypt_value(env_secret_plain)
                enc_pass = encrypt_value(env_passphrase) if env_passphrase else ""
                c.execute(
                    "INSERT INTO user_exchanges "
                    "(user_id, exchange, api_key, api_secret, passphrase, enabled, is_primary) "
                    "VALUES(%s,%s,%s,%s,%s,1,1)",
                    (
                        admin_id,
                        env_exchange,
                        enc_key,
                        enc_sec,
                        enc_pass,
                    ),
                )
                log.info("🔑 Admin-Exchange aus .env migriert: %s", env_exchange)
            except Exception as e:
                log.debug("admin exchange seed: %s", e)
