-- ============================================================
--  TREVLIX v1.5.0 – MySQL Initialization
--  Automatically executed on first container start.
--  The application also creates these tables on startup,
--  but this file ensures the schema is ready immediately.
-- ============================================================

CREATE DATABASE IF NOT EXISTS trevlix
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE trevlix;

-- ── Trades ──────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS trades (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    user_id         INT DEFAULT 1,
    symbol          VARCHAR(20),
    entry           DOUBLE,
    exit_price      DOUBLE,
    qty             DOUBLE,
    pnl             DOUBLE,
    pnl_pct         DOUBLE,
    reason          VARCHAR(80),
    confidence      DOUBLE,
    ai_score        DOUBLE,
    win_prob        DOUBLE,
    invested        DOUBLE,
    opened          DATETIME,
    closed          DATETIME,
    exchange        VARCHAR(20),
    regime          VARCHAR(10),
    trade_type      VARCHAR(10) DEFAULT 'long',
    partial_sold    TINYINT DEFAULT 0,
    dca_level       INT DEFAULT 0,
    news_score      DOUBLE DEFAULT 0,
    onchain_score   DOUBLE DEFAULT 0,
    INDEX idx_closed (closed),
    INDEX idx_symbol (symbol),
    INDEX idx_user   (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ── Users ────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    username        VARCHAR(50) UNIQUE,
    password_hash   VARCHAR(256),
    role            VARCHAR(20) DEFAULT 'user',
    balance         DOUBLE DEFAULT 10000.0,
    initial_balance DOUBLE DEFAULT 10000.0,
    api_key         VARCHAR(200),
    api_secret      VARCHAR(200),
    exchange        VARCHAR(20) DEFAULT 'cryptocom',
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_login      DATETIME,
    settings_json   MEDIUMTEXT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ── AI Training Samples ──────────────────────────────────────────
CREATE TABLE IF NOT EXISTS ai_training (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    features    TEXT,
    label       TINYINT,
    regime      VARCHAR(10) DEFAULT 'bull',
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_regime (regime)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ── Audit Log ────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS audit_log (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    user_id     INT DEFAULT 0,
    action      VARCHAR(80) NOT NULL,
    detail      VARCHAR(500),
    ip          VARCHAR(45),
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_user   (user_id),
    INDEX idx_action (action),
    INDEX idx_time   (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ── Backtest Results ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS backtest_results (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    symbol          VARCHAR(20),
    timeframe       VARCHAR(10),
    candles         INT,
    total_trades    INT,
    win_rate        DOUBLE,
    total_pnl       DOUBLE,
    profit_factor   DOUBLE,
    max_drawdown    DOUBLE,
    result_json     MEDIUMTEXT,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ── Price Alerts ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS price_alerts (
    id           INT AUTO_INCREMENT PRIMARY KEY,
    user_id      INT DEFAULT 1,
    symbol       VARCHAR(20),
    target_price DOUBLE,
    direction    VARCHAR(10),
    triggered    TINYINT DEFAULT 0,
    created_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
    triggered_at DATETIME
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ── Daily Reports ────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS daily_reports (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    report_date DATE,
    report_json MEDIUMTEXT,
    sent_at     DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_date (report_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ── Sentiment Cache ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS sentiment_cache (
    symbol     VARCHAR(20) PRIMARY KEY,
    score      DOUBLE,
    source     VARCHAR(20),
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ── News Cache ───────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS news_cache (
    symbol        VARCHAR(20) PRIMARY KEY,
    score         DOUBLE,
    headline      VARCHAR(500),
    article_count INT DEFAULT 0,
    updated_at    DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ── On-Chain Cache ───────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS onchain_cache (
    symbol      VARCHAR(20) PRIMARY KEY,
    whale_score DOUBLE,
    flow_score  DOUBLE,
    net_score   DOUBLE,
    detail      VARCHAR(500),
    updated_at  DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ── Genetic Algorithm Results ────────────────────────────────────
CREATE TABLE IF NOT EXISTS genetic_results (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    generation  INT,
    fitness     DOUBLE,
    genome_json TEXT,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ── Arbitrage Opportunities ──────────────────────────────────────
CREATE TABLE IF NOT EXISTS arb_opportunities (
    id             INT AUTO_INCREMENT PRIMARY KEY,
    symbol         VARCHAR(20),
    exchange_buy   VARCHAR(20),
    price_buy      DOUBLE,
    exchange_sell  VARCHAR(20),
    price_sell     DOUBLE,
    spread_pct     DOUBLE,
    executed       TINYINT DEFAULT 0,
    profit         DOUBLE DEFAULT 0,
    found_at       DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ── RL Episodes ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS rl_episodes (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    episode     INT,
    reward      DOUBLE,
    state_json  TEXT,
    action      INT,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ── API Tokens ───────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS api_tokens (
    id         INT AUTO_INCREMENT PRIMARY KEY,
    user_id    INT,
    token      VARCHAR(500),
    label      VARCHAR(100),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_used  DATETIME,
    expires_at DATETIME,
    active     TINYINT DEFAULT 1
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ── User Exchanges (Multi-Exchange pro User) ────────────────────
CREATE TABLE IF NOT EXISTS user_exchanges (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    user_id     INT NOT NULL,
    exchange    VARCHAR(20) NOT NULL,
    api_key     VARCHAR(500),
    api_secret  VARCHAR(500),
    enabled     TINYINT DEFAULT 0,
    is_primary  TINYINT DEFAULT 0,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_user_exchange(user_id, exchange),
    INDEX idx_user(user_id),
    INDEX idx_enabled(user_id, enabled)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ── Trade DNA Fingerprints ──────────────────────────────────────
CREATE TABLE IF NOT EXISTS trade_dna (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    symbol          VARCHAR(20),
    dna_hash        VARCHAR(16),
    fingerprint     VARCHAR(500),
    dimensions_json TEXT,
    raw_values_json TEXT,
    won             TINYINT,
    pnl             DOUBLE DEFAULT 0,
    dna_boost       DOUBLE DEFAULT 1.0,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_hash   (dna_hash),
    INDEX idx_symbol (symbol),
    INDEX idx_time   (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ── Shared Knowledge (KI-Gemeinschaftswissen) ───────────────────
CREATE TABLE IF NOT EXISTS shared_knowledge (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    category    VARCHAR(50) NOT NULL,
    key_name    VARCHAR(100) NOT NULL,
    value_json  MEDIUMTEXT,
    confidence  DOUBLE DEFAULT 0.5,
    source      VARCHAR(50) DEFAULT 'ai',
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at  DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_cat_key(category, key_name),
    INDEX idx_category(category)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ── Revenue Trades (Revenue Tracking Agent v1.5) ──────────────────
CREATE TABLE IF NOT EXISTS revenue_trades (
    id           INT AUTO_INCREMENT PRIMARY KEY,
    symbol       VARCHAR(20),
    side         VARCHAR(10),
    amount       DOUBLE,
    price        DOUBLE,
    fee          DOUBLE DEFAULT 0,
    slippage_est DOUBLE DEFAULT 0,
    funding_fee  DOUBLE DEFAULT 0,
    strategy     VARCHAR(80),
    gross_pnl    DOUBLE DEFAULT 0,
    net_pnl      DOUBLE DEFAULT 0,
    recorded_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_time     (recorded_at),
    INDEX idx_strategy (strategy),
    INDEX idx_symbol   (symbol)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ── Healing Incidents (Auto-Healing Agent v1.5) ───────────────────
CREATE TABLE IF NOT EXISTS healing_incidents (
    id         INT AUTO_INCREMENT PRIMARY KEY,
    service    VARCHAR(30) NOT NULL,
    severity   VARCHAR(20) NOT NULL,
    message    VARCHAR(500),
    recovered  TINYINT DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_service (service),
    INDEX idx_time    (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ── Cluster Nodes (Multi-Server Control Agent v1.5) ───────────────
CREATE TABLE IF NOT EXISTS cluster_nodes (
    id         INT AUTO_INCREMENT PRIMARY KEY,
    name       VARCHAR(50) UNIQUE NOT NULL,
    host       VARCHAR(255) NOT NULL,
    port       INT DEFAULT 5000,
    api_token  VARCHAR(500),
    status     VARCHAR(20) DEFAULT 'offline',
    last_check DATETIME,
    last_error VARCHAR(500),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ── Alert Escalations (Alert Escalation Manager v1.5) ─────────────
CREATE TABLE IF NOT EXISTS alert_escalations (
    alert_id         VARCHAR(100) PRIMARY KEY,
    message          VARCHAR(500),
    source           VARCHAR(50) DEFAULT 'system',
    level            INT DEFAULT 1,
    occurrence_count INT DEFAULT 1,
    created_at       DATETIME DEFAULT CURRENT_TIMESTAMP,
    escalated_at     DATETIME,
    acknowledged     TINYINT DEFAULT 0,
    resolved_at      DATETIME,
    INDEX idx_level  (level),
    INDEX idx_source (source)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
