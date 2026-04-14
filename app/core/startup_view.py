"""Startup banner rendering helper.

Bildet beim Serverstart eine ausführliche Übersicht aller relevanten
Subsysteme und Integrationen ab. Ziel: schon am Konsolen-Output erkennen
können, ob Datenbank, Exchange, LLM, Notifications und Trading-Modus
korrekt konfiguriert sind – ohne das Dashboard öffnen zu müssen.
"""

from __future__ import annotations

import os
import platform
import socket
import sys
from typing import Any

# ── ANSI Farben ─────────────────────────────────────────────────────────────
_RESET = "\033[0m"
_BOLD = "\033[1m"
_DIM = "\033[2m"
_JADE = "\033[38;5;47m"
_GREEN = "\033[38;5;46m"
_RED = "\033[38;5;196m"
_YELLOW = "\033[38;5;214m"
_CYAN = "\033[38;5;51m"
_BLUE = "\033[38;5;33m"
_MAGENTA = "\033[38;5;201m"

_WIDTH = 78  # Innere Breite der Box


def _color_enabled() -> bool:
    if os.getenv("NO_COLOR"):
        return False
    if os.getenv("COLOR_LOGS", "true").lower() in ("false", "0", "no"):
        return False
    return sys.stdout.isatty() or os.getenv("FORCE_COLOR") == "1"


def _c(text: str, color: str) -> str:
    """Umbricht Text mit ANSI-Farbe, wenn Farben aktiv sind."""
    return f"{color}{text}{_RESET}" if _color_enabled() else text


def _strip_ansi(text: str) -> str:
    """Entfernt ANSI-Sequenzen für Längenberechnung."""
    import re

    return re.sub(r"\033\[[0-9;]*m", "", text)


def _line(content: str) -> str:
    """Formatiert eine Box-Zeile mit rechtsbündigem Rand."""
    visible = _strip_ansi(content)
    pad = max(0, _WIDTH - len(visible))
    bar = _c("║", _JADE)
    return f"{bar} {content}{' ' * pad}{bar}"


def _separator(char: str = "═") -> str:
    return _c(f"╠{char * (_WIDTH + 2)}╣", _JADE)


def _top() -> str:
    return _c(f"╔{'═' * (_WIDTH + 2)}╗", _JADE)


def _bottom() -> str:
    return _c(f"╚{'═' * (_WIDTH + 2)}╝", _JADE)


def _status(enabled: bool, label_ok: str = "aktiv", label_off: str = "inaktiv") -> str:
    if enabled:
        return _c(f"● {label_ok}", _GREEN)
    return _c(f"○ {label_off}", _DIM)


def _check_configured(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    return bool(str(value).strip())


def _hostname() -> str:
    try:
        return socket.gethostname()
    except Exception:  # noqa: BLE001
        return "?"


def _kv(label: str, value: str, label_width: int = 14) -> str:
    return f"{_c(label.ljust(label_width), _BOLD)} {value}"


# ── Öffentliche API ──────────────────────────────────────────────────────────


def render_startup_banner(*, bot_version: str, config: dict) -> str:
    """Render the extended startup banner with system, DB, integration and
    trading information.
    """
    paper = bool(config.get("paper_trading", True))
    exchange = str(config.get("exchange", "—")).upper()
    mysql_host = config.get("mysql_host", "—")
    mysql_db = config.get("mysql_db", "—")
    mysql_port = config.get("mysql_port", 3306)

    # Integrationen
    has_cryptopanic = _check_configured(
        config.get("cryptopanic_token") or os.getenv("CRYPTOPANIC_TOKEN")
    )
    has_discord = _check_configured(config.get("discord_webhook") or os.getenv("DISCORD_WEBHOOK"))
    has_telegram = _check_configured(config.get("telegram_token") or os.getenv("TELEGRAM_TOKEN"))
    llm_endpoint = config.get("llm_endpoint") or os.getenv("LLM_ENDPOINT") or ""
    ollama_host = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")
    ollama_model = os.getenv("OLLAMA_MODEL") or config.get("llm_model") or ""
    llm_active = _check_configured(llm_endpoint)

    auto_start = os.getenv("AUTO_START", "true").lower() in ("true", "1", "yes")
    allow_reg = str(config.get("allow_registration", False)).lower() in ("true", "1", "yes")
    port = os.getenv("PORT", "5000")
    lang = str(config.get("language", os.getenv("LANGUAGE", "de"))).upper()

    # Sicherheits-Indikatoren (nur "vorhanden", nie den Wert drucken!)
    has_jwt = _check_configured(os.getenv("JWT_SECRET"))
    has_enc = _check_configured(os.getenv("ENCRYPTION_KEY"))
    has_flask_secret = _check_configured(os.getenv("SECRET_KEY"))

    mode_badge = _c("📝 PAPER-TRADING", _CYAN) if paper else _c("💰 LIVE-TRADING", _RED)

    # ASCII-Logo (unverändert lassen, damit Terminal-Alignment stimmt)
    logo = [
        " ████████╗██████╗ ███████╗██╗   ██╗██╗     ██╗██╗  ██╗",
        " ╚══██╔══╝██╔══██╗██╔════╝██║   ██║██║     ██║╚██╗██╔╝",
        "    ██║   ██████╔╝█████╗  ██║   ██║██║     ██║ ╚███╔╝ ",
        "    ██║   ██╔══██╗██╔══╝  ╚██╗ ██╔╝██║     ██║ ██╔██╗ ",
        "    ██║   ██║  ██║███████╗ ╚████╔╝ ███████╗██║██╔╝ ██╗",
        "    ╚═╝   ╚═╝  ╚═╝╚══════╝  ╚═══╝  ╚══════╝╚═╝╚═╝  ╚═╝",
    ]

    py_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    platform_str = f"{platform.system()} {platform.release()} · {platform.machine()}"

    lines: list[str] = []
    lines.append("")
    lines.append(_top())
    for row in logo:
        lines.append(_line(_c(row, _JADE)))
    subtitle = _c(
        f"Algorithmic Crypto Trading  ·  v{bot_version}  ·  trevlix.dev",
        _DIM,
    )
    lines.append(_line(f"  {subtitle}"))
    lines.append(_separator())

    # ── System ───────────────────────────────────────────────────────────
    lines.append(_line(_c("SYSTEM", _BOLD + _BLUE)))
    lines.append(_line(_kv("Host:", f"{_hostname()}  {_c(f'(PID {os.getpid()})', _DIM)}")))
    lines.append(_line(_kv("Platform:", platform_str)))
    lines.append(_line(_kv("Python:", py_version)))
    lines.append(_line(_kv("Sprache:", lang)))
    lines.append(_separator("─"))

    # ── Datenbank ────────────────────────────────────────────────────────
    lines.append(_line(_c("DATENBANK", _BOLD + _BLUE)))
    lines.append(_line(_kv("MariaDB:", f"{mysql_host}:{mysql_port}/{mysql_db}")))
    db_user = os.getenv("MYSQL_USER", "trevlix")
    pool_size = config.get("db_pool_size", os.getenv("DB_POOL_SIZE", "10"))
    lines.append(_line(_kv("User / Pool:", f"{db_user}  ·  pool_size={pool_size}")))
    lines.append(_separator("─"))

    # ── Security ─────────────────────────────────────────────────────────
    lines.append(_line(_c("SICHERHEIT", _BOLD + _BLUE)))
    lines.append(
        _line(
            _kv(
                "Secrets:",
                f"JWT {_status(has_jwt, 'gesetzt', 'FEHLT')}   "
                f"ENC {_status(has_enc, 'gesetzt', 'FEHLT')}   "
                f"FLASK {_status(has_flask_secret, 'gesetzt', 'FEHLT')}",
            )
        )
    )
    session_min = config.get("session_timeout_min", os.getenv("SESSION_TIMEOUT_MIN", "30"))
    origins = os.getenv("ALLOWED_ORIGINS", "—")
    if len(origins) > _WIDTH - 18:
        origins = origins[: _WIDTH - 21] + "…"
    lines.append(_line(_kv("Session:", f"{session_min} min")))
    lines.append(_line(_kv("Origins:", _c(origins, _DIM))))
    lines.append(_line(_kv("Registration:", _status(allow_reg, "offen", "geschlossen"))))
    lines.append(_separator("─"))

    # ── Trading ──────────────────────────────────────────────────────────
    lines.append(_line(_c("TRADING", _BOLD + _BLUE)))
    lines.append(_line(_kv("Modus:", mode_badge)))
    lines.append(_line(_kv("Exchange:", _c(exchange, _MAGENTA))))
    if paper:
        cap = config.get("paper_balance", "—")
        lines.append(_line(_kv("Paper-Kapital:", f"{cap} USDT")))
    lines.append(
        _line(
            _kv(
                "Auto-Start:",
                _status(auto_start, "bei Exchange ready", "deaktiviert"),
            )
        )
    )
    tf = config.get("timeframe", os.getenv("TIMEFRAME", "1h"))
    max_pos = config.get("max_positions", os.getenv("MAX_POSITIONS", "—"))
    risk_per = config.get("risk_per_trade", os.getenv("RISK_PER_TRADE", "—"))
    lines.append(_line(_kv("Timeframe:", f"{tf}")))
    lines.append(_line(_kv("Risk/Trade:", f"{risk_per}  ·  max_positions={max_pos}")))
    lines.append(_separator("─"))

    # ── Integrationen ────────────────────────────────────────────────────
    lines.append(_line(_c("INTEGRATIONEN", _BOLD + _BLUE)))
    lines.append(_line(_kv("CryptoPanic:", _status(has_cryptopanic))))
    lines.append(_line(_kv("Discord:", _status(has_discord))))
    lines.append(_line(_kv("Telegram:", _status(has_telegram))))
    if llm_active:
        llm_short = llm_endpoint
        if len(llm_short) > 40:
            llm_short = llm_short[:37] + "…"
        model_info = f" · {ollama_model}" if ollama_model else ""
        lines.append(_line(_kv("LLM:", f"{_status(True)}  {_c(llm_short + model_info, _DIM)}")))
    elif ollama_model:
        lines.append(
            _line(
                _kv(
                    "LLM:",
                    f"{_c('○ Ollama verfügbar', _YELLOW)}  "
                    f"{_c(f'{ollama_host} · {ollama_model}', _DIM)}",
                )
            )
        )
    else:
        lines.append(_line(_kv("LLM:", _status(False))))
    lines.append(_separator("─"))

    # ── Server ───────────────────────────────────────────────────────────
    lines.append(_line(_c("SERVER", _BOLD + _BLUE)))
    lines.append(_line(_kv("Dashboard:", _c(f"http://0.0.0.0:{port}", _CYAN))))
    lines.append(_line(_kv("REST-API:", _c(f"http://0.0.0.0:{port}/api/v1/", _CYAN))))
    lines.append(_line(_kv("API-Docs:", _c(f"http://0.0.0.0:{port}/api/v1/docs", _CYAN))))
    lines.append(_bottom())
    lines.append("")

    return "\n".join(lines)


def render_ready_summary(
    *,
    bot_version: str,
    config: dict,
    thread_count: int,
    db_ok: bool,
    ollama_ok: bool | None = None,
    auto_started: bool = False,
    exchange_ready: bool = False,
) -> str:
    """Kompakte Ready-Summary, die nach dem Hochfahren geprinted wird.

    Gibt einen schnellen Überblick, welche Subsysteme tatsächlich laufen –
    ergänzend zum statischen Banner am Anfang.
    """
    lines: list[str] = []
    lines.append(_top())
    lines.append(_line(_c(f"  ✓ TREVLIX {bot_version} · Bereit", _BOLD + _GREEN)))
    lines.append(_separator("─"))
    lines.append(
        _line(
            _kv(
                "Threads:",
                f"{thread_count} aktiv  "
                f"{_c('(Reports · Backup · FG · Dominance · Safety · Healer)', _DIM)}",
            )
        )
    )
    lines.append(_line(_kv("DB-Ping:", _status(db_ok, "OK", "fehlgeschlagen"))))
    if ollama_ok is not None:
        lines.append(_line(_kv("Ollama:", _status(ollama_ok, "erreichbar", "nicht erreichbar"))))
    if auto_started:
        exch = str(config.get("exchange", "—")).upper()
        lines.append(_line(_kv("Bot-Loop:", _c(f"● gestartet ({exch})", _GREEN))))
    elif not exchange_ready:
        lines.append(
            _line(
                _kv(
                    "Bot-Loop:",
                    _c("○ wartet auf Exchange-Konfiguration", _YELLOW),
                )
            )
        )
    else:
        lines.append(_line(_kv("Bot-Loop:", _c("○ manueller Start erforderlich", _YELLOW))))
    lines.append(_bottom())
    return "\n".join(lines)
