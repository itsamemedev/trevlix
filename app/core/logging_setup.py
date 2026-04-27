"""Logging setup helpers for TREVLIX."""

from __future__ import annotations

import json
import logging
import logging.handlers
import os
import traceback
from typing import Any

# Max size per log file before rotation (10 MB)
_LOG_MAX_BYTES = 10 * 1024 * 1024
# Number of rotated backup files to keep
_LOG_BACKUP_COUNT = 5
# Max size for errors.log (5 MB – smaller, high-signal only)
_ERR_MAX_BYTES = 5 * 1024 * 1024


class ColorFormatter(logging.Formatter):
    """ANSI-farbiger Log-Formatter für die Konsole."""

    COLORS = {
        "DEBUG": "\033[36m",
        "INFO": "\033[32m",
        "WARNING": "\033[33m",
        "ERROR": "\033[31m",
        "CRITICAL": "\033[41m",
    }
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelname, "")
        ts = self.formatTime(record, datefmt="%H:%M:%S")
        level = f"{color}{self.BOLD}{record.levelname:<8}{self.RESET}"
        msg = record.getMessage()
        return f"{self.DIM}{ts}{self.RESET} {level} {msg}"


class JSONFormatter(logging.Formatter):
    """JSON-Formatter für strukturierte Logs.

    Gibt jede Log-Zeile als einzelnes JSON-Objekt aus. Bei ERROR/CRITICAL
    werden Modul, Funktion, Zeilennummer und der vollständige Traceback
    (falls vorhanden) automatisch mitgeliefert.
    """

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        # Detaillierter Kontext für Fehler-Levels
        # Absolute Pfade (record.pathname) werden bewusst weggelassen, um
        # Server-Topologie nicht in Log-Aggregatoren preiszugeben.
        if record.levelno >= logging.ERROR:
            payload["module"] = record.module
            payload["func"] = record.funcName
            payload["line"] = record.lineno
        if record.exc_info:
            payload["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "value": str(record.exc_info[1]),
                "traceback": traceback.format_exception(*record.exc_info),
            }
        if record.stack_info:
            payload["stack"] = self.formatStack(record.stack_info)
        return json.dumps(payload, ensure_ascii=False)


class _ErrorLevelFilter(logging.Filter):
    """Lässt nur ERROR- und CRITICAL-Records durch."""

    def filter(self, record: logging.LogRecord) -> bool:
        return record.levelno >= logging.ERROR


def configure_logging(
    base_dir: str,
    log_level: int,
    use_json_logs: bool,
    use_color_logs: bool,
    logger_name: str = "TREVLIX",
) -> logging.Logger:
    """Konfiguriert Datei- + Konsolenlogging und liefert den Hauptlogger.

    Richtet drei Handler ein:
    - Konsole: farbig (optional) oder Plaintext
    - trevlix.log: alle Log-Level (rotierend, max 10 MB × 5 Backups)
    - errors.log: nur ERROR/CRITICAL (rotierend, max 5 MB × 5 Backups),
      immer im JSON-Format mit vollständigem Traceback und Kontext
    """
    log_dir = os.path.join(base_dir, "logs")
    os.makedirs(log_dir, exist_ok=True)

    main_log = os.path.join(log_dir, "trevlix.log")
    error_log = os.path.join(log_dir, "errors.log")

    # Haupt-Log: rotierende Datei, alle Levels
    main_handler = logging.handlers.RotatingFileHandler(
        main_log,
        maxBytes=_LOG_MAX_BYTES,
        backupCount=_LOG_BACKUP_COUNT,
        encoding="utf-8",
    )

    # Fehler-Log: rotierende Datei, nur ERROR+, immer JSON mit Traceback
    error_handler = logging.handlers.RotatingFileHandler(
        error_log,
        maxBytes=_ERR_MAX_BYTES,
        backupCount=_LOG_BACKUP_COUNT,
        encoding="utf-8",
    )

    # Restriktive Permissions (0o600): Logs können Tracebacks und API-Antworten
    # enthalten, daher nur für den Bot-Owner lesbar machen.
    for path in (main_log, error_log):
        try:
            if os.path.exists(path):
                os.chmod(path, 0o600)
        except OSError:
            pass
    error_handler.addFilter(_ErrorLevelFilter())
    error_handler.setFormatter(JSONFormatter())

    console_handler = logging.StreamHandler()
    if use_color_logs and not use_json_logs:
        console_handler.setFormatter(ColorFormatter())

    handlers: list[logging.Handler] = [main_handler, error_handler, console_handler]

    if use_json_logs:
        json_formatter = JSONFormatter()
        main_handler.setFormatter(json_formatter)
        console_handler.setFormatter(json_formatter)

    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=handlers,
    )
    return logging.getLogger(logger_name)
