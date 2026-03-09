#!/usr/bin/env python3
"""
TREVLIX – Umgebungsvariablen-Validierung
==========================================
[Verbesserung #10] Prüft Pflicht-Umgebungsvariablen auf Inhalt und Qualität
vor dem Start des Bots.

Verwendung:
    python validate_env.py          # Warnt bei Problemen, Exit 0 wenn OK
    python validate_env.py --strict # Exit 1 bei kritischen Fehlern

Docker ENTRYPOINT:
    CMD ["sh", "-c", "python validate_env.py && python server.py"]
"""

import base64
import os
import re
import sys
from typing import NamedTuple

load_dotenv_available = False
try:
    from dotenv import load_dotenv

    load_dotenv()
    load_dotenv_available = True
except ImportError:
    pass

# ── ANSI-Farben für Ausgabe ──────────────────────────────────────────────────
_RED = "\033[91m"
_YEL = "\033[93m"
_GRN = "\033[92m"
_RST = "\033[0m"
_NO_COLOR = not sys.stdout.isatty()


def _c(color: str, text: str) -> str:
    if _NO_COLOR:
        return text
    return f"{color}{text}{_RST}"


# ── Validierungsregeln ───────────────────────────────────────────────────────


class Issue(NamedTuple):
    severity: str  # "critical" | "warning"
    var: str
    msg: str


def _check_min_length(var: str, min_len: int, label: str) -> Issue | None:
    val = os.getenv(var, "")
    if not val:
        return Issue("critical", var, f"{label} ist nicht gesetzt")
    if len(val) < min_len:
        return Issue("critical", var, f"{label} ist zu kurz ({len(val)} Zeichen, min. {min_len})")
    return None


def _check_hex(var: str, min_len: int, label: str) -> Issue | None:
    val = os.getenv(var, "")
    if not val:
        return Issue("critical", var, f"{label} ist nicht gesetzt")
    if len(val) < min_len:
        return Issue("critical", var, f"{label} zu kurz ({len(val)} Zeichen, min. {min_len})")
    if not re.fullmatch(r"[0-9a-fA-F]+", val):
        return Issue("warning", var, f"{label} enthält Nicht-Hex-Zeichen – ist es wirklich Hex?")
    return None


def _check_fernet_key(var: str) -> Issue | None:
    val = os.getenv(var, "")
    if not val:
        return Issue("critical", var, "ENCRYPTION_KEY ist nicht gesetzt")
    try:
        decoded = base64.urlsafe_b64decode(val.encode())
        if len(decoded) != 32:
            return Issue("critical", var, f"ENCRYPTION_KEY muss 32 Bytes sein (hat {len(decoded)})")
    except Exception:
        return Issue(
            "critical", var, "ENCRYPTION_KEY ist kein gültiger Fernet-Key (base64url, 44 Zeichen)"
        )
    return None


def _check_password_policy(var: str, label: str) -> Issue | None:
    val = os.getenv(var, "")
    if not val:
        return Issue("critical", var, f"{label} ist nicht gesetzt")
    issues = []
    if len(val) < 12:
        issues.append(f"min. 12 Zeichen (hat {len(val)})")
    if not re.search(r"[A-Z]", val):
        issues.append("min. 1 Großbuchstabe")
    if not re.search(r"[0-9]", val):
        issues.append("min. 1 Ziffer")
    if not re.search(r"[^A-Za-z0-9]", val):
        issues.append("min. 1 Sonderzeichen")
    if issues:
        return Issue("warning", var, f"{label} schwach: {', '.join(issues)}")
    return None


def _check_set(var: str, allowed: set[str], label: str, default: str | None = None) -> Issue | None:
    val = os.getenv(var, default or "")
    if val not in allowed:
        return Issue("warning", var, f"{label} '{val}' ungültig – erlaubt: {sorted(allowed)}")
    return None


def validate() -> list[Issue]:
    """Prüft alle Umgebungsvariablen auf Korrektheit und Sicherheit.

    Prüft Mindestlängen, Hex-Formate, Fernet-Key-Format, Passwort-Policies
    und bekannte schwache Werte für alle sicherheitsrelevanten Variablen.

    Returns:
        Liste von ``Issue``-Objekten mit Severity 'critical' oder 'warning'.
        Leere Liste bedeutet keine Probleme gefunden.

    Example:
        issues = validate()
        critical = [i for i in issues if i.severity == 'critical']
        if critical:
            sys.exit(1)
    """
    issues: list[Issue] = []

    def add(result: Issue | None):
        if result:
            issues.append(result)

    # ── Datenbank ────────────────────────────────────────────────────────────
    add(_check_min_length("MYSQL_PASS", 16, "MYSQL_PASS"))
    add(_check_min_length("MYSQL_USER", 2, "MYSQL_USER"))
    add(_check_min_length("MYSQL_DB", 2, "MYSQL_DB"))
    # MYSQL_HOST: Warnung wenn nicht gesetzt oder leer
    mysql_host = os.getenv("MYSQL_HOST", "")
    if not mysql_host:
        issues.append(
            Issue("warning", "MYSQL_HOST", "MYSQL_HOST ist nicht gesetzt – verwendet 'localhost'")
        )
    # MYSQL_PORT: Warnung wenn gesetzt aber kein gültiger Port
    mysql_port_raw = os.getenv("MYSQL_PORT", "3306")
    try:
        mysql_port = int(mysql_port_raw)
        if not (1 <= mysql_port <= 65535):
            issues.append(
                Issue("critical", "MYSQL_PORT", f"MYSQL_PORT {mysql_port} liegt außerhalb 1-65535")
            )
    except ValueError:
        issues.append(
            Issue("critical", "MYSQL_PORT", f"MYSQL_PORT '{mysql_port_raw}' ist keine gültige Zahl")
        )

    # ── Security ─────────────────────────────────────────────────────────────
    add(_check_hex("JWT_SECRET", 32, "JWT_SECRET"))
    add(_check_hex("SECRET_KEY", 32, "SECRET_KEY"))
    add(_check_fernet_key("ENCRYPTION_KEY"))
    add(_check_password_policy("ADMIN_PASSWORD", "ADMIN_PASSWORD"))

    # ── Exchange (optional, aber wenn gesetzt – dann vollständig) ─────────────
    api_key = os.getenv("API_KEY", "")
    api_secret = os.getenv("API_SECRET", "")
    if api_key and not api_secret:
        issues.append(Issue("warning", "API_SECRET", "API_KEY gesetzt, aber API_SECRET fehlt"))
    if api_secret and not api_key:
        issues.append(Issue("warning", "API_KEY", "API_SECRET gesetzt, aber API_KEY fehlt"))

    # ── Bekannte schwache Werte ───────────────────────────────────────────────
    weak_values = {"test", "geheim", "pass", "password", "123456", "admin", "nexus", "secret"}
    for var in ["MYSQL_PASS", "JWT_SECRET", "ADMIN_PASSWORD", "SECRET_KEY"]:
        val = os.getenv(var, "").lower()
        if val in weak_values:
            issues.append(Issue("critical", var, f"{var} ist ein bekanntes schwaches Passwort"))

    return issues


def main() -> int:
    strict = "--strict" in sys.argv
    issues = validate()

    if not issues:
        print(_c(_GRN, "✅ Alle Umgebungsvariablen sehen gut aus!"))
        return 0

    criticals = [i for i in issues if i.severity == "critical"]
    warnings = [i for i in issues if i.severity == "warning"]

    print(_c(_YEL, "\n⚠️  TREVLIX Umgebungsvariablen-Validierung"))
    print("=" * 55)

    for issue in warnings:
        print(_c(_YEL, f"  ⚠ {issue.var}: {issue.msg}"))

    for issue in criticals:
        print(_c(_RED, f"  ✖ {issue.var}: {issue.msg}"))

    print("=" * 55)

    if criticals:
        print(_c(_RED, f"\n❌ {len(criticals)} kritische Fehler gefunden!"))
        if strict:
            print(_c(_RED, "   Bitte .env korrigieren und neu starten."))
            return 1
        else:
            print(_c(_YEL, "   Bot startet trotzdem (--strict verhindert das)."))
    elif warnings:
        print(_c(_YEL, f"\n⚠️  {len(warnings)} Warnungen – Empfehlung: Konfiguration verbessern."))

    return 0


if __name__ == "__main__":
    sys.exit(main())
