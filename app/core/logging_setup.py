"""Logging setup helpers for TREVLIX."""

from __future__ import annotations

import json
import logging
import os
from typing import Any


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
    """JSON-Formatter für strukturierte Logs."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(
    base_dir: str,
    log_level: int,
    use_json_logs: bool,
    use_color_logs: bool,
    logger_name: str = "TREVLIX",
) -> logging.Logger:
    """Konfiguriert Datei- + Konsolenlogging und liefert den Hauptlogger."""
    log_dir = os.path.join(base_dir, "logs")
    os.makedirs(log_dir, exist_ok=True)

    file_handler = logging.FileHandler(os.path.join(log_dir, "trevlix.log"), encoding="utf-8")
    console_handler = logging.StreamHandler()

    if use_color_logs and not use_json_logs:
        console_handler.setFormatter(ColorFormatter())

    handlers: list[logging.Handler] = [file_handler, console_handler]

    if use_json_logs:
        json_formatter = JSONFormatter()
        for handler in handlers:
            handler.setFormatter(json_formatter)

    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=handlers,
    )
    return logging.getLogger(logger_name)
