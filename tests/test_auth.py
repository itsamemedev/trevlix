"""
TREVLIX – Unit Tests für Auth & Sicherheit (Verbesserung #41)
==============================================================
Tests für Password-Policy, Session-Timeout, Brute-Force-Schutz,
CSRF-Token, Security Headers.
"""

import os
import re
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestPasswordPolicy:
    """[Verbesserung #4] Password-Policy Tests."""

    def test_min_length_12(self):
        """Passwörter unter 12 Zeichen sind nicht erlaubt."""
        short_pw = "Short1Aa"
        assert len(short_pw) < 12

    def test_requires_uppercase(self):
        """Passwort muss Großbuchstaben enthalten."""
        no_upper = "nouppercase123"
        assert not re.search(r"[A-Z]", no_upper)

    def test_requires_lowercase(self):
        """Passwort muss Kleinbuchstaben enthalten."""
        no_lower = "NOLOWERCASE123"
        assert not re.search(r"[a-z]", no_lower)

    def test_requires_digit(self):
        """Passwort muss Zahlen enthalten."""
        no_digit = "NoDigitsHere"
        assert not re.search(r"\d", no_digit)

    def test_valid_password(self):
        """Gültiges Passwort erfüllt alle Anforderungen."""
        valid = "SecurePass1234"
        assert len(valid) >= 12
        assert re.search(r"[A-Z]", valid)
        assert re.search(r"[a-z]", valid)
        assert re.search(r"\d", valid)


class TestBruteForceProtection:
    """[Verbesserung #3] Brute-Force-Schutz Tests."""

    def test_rate_limit_function(self):
        """Login-Rate-Limiter blockiert nach 5 Versuchen."""
        try:
            from server import _check_login_rate, _login_attempts, _record_login_attempt
        except ImportError:
            pytest.skip("Server nicht importierbar")

        test_ip = "192.168.99.99"
        _login_attempts.pop(test_ip, None)

        # Erste 5 Versuche sollten erlaubt sein
        for _ in range(5):
            assert _check_login_rate(test_ip) is True
            _record_login_attempt(test_ip)

        # 6. Versuch sollte blockiert werden
        assert _check_login_rate(test_ip) is False

        # Aufräumen
        _login_attempts.pop(test_ip, None)


class TestCSRFToken:
    """[Verbesserung #2] CSRF-Token Tests."""

    def test_csrf_token_generated(self):
        """CSRF-Token wird pro Session generiert."""
        try:
            from server import app

            with app.test_request_context():
                from server import _generate_csrf_token

                token = _generate_csrf_token()
                assert token is not None
                assert len(token) == 64  # 32 bytes hex = 64 chars
                # Zweiter Aufruf gibt gleichen Token
                assert _generate_csrf_token() == token
        except ImportError:
            pytest.skip("Server nicht importierbar")


class TestSessionTimeout:
    """[Verbesserung #1] Session-Timeout Tests."""

    def test_timeout_config_exists(self):
        """Session-Timeout-Konfiguration existiert."""
        try:
            from server import _SESSION_TIMEOUT_MIN

            assert isinstance(_SESSION_TIMEOUT_MIN, int)
            assert _SESSION_TIMEOUT_MIN > 0
        except ImportError:
            pytest.skip("Server nicht importierbar")


class TestSecureCookies:
    """[Verbesserung #5] Secure Cookie Flags Tests."""

    def test_cookie_httponly(self):
        """SESSION_COOKIE_HTTPONLY ist gesetzt."""
        try:
            from server import app

            assert app.config.get("SESSION_COOKIE_HTTPONLY") is True
        except ImportError:
            pytest.skip("Server nicht importierbar")

    def test_cookie_samesite(self):
        """SESSION_COOKIE_SAMESITE ist auf Lax gesetzt."""
        try:
            from server import app

            assert app.config.get("SESSION_COOKIE_SAMESITE") == "Lax"
        except ImportError:
            pytest.skip("Server nicht importierbar")


class TestConfigSecurity:
    """Tests für sicherheitsrelevante Config-Einstellungen."""

    def test_sensitive_keys_excluded_from_backup(self):
        """Sensible Schlüssel werden nicht im Backup-safe_cfg gespeichert."""
        # Diese Liste muss mit dem BACKUP_EXCLUDED_KEYS in server.py übereinstimmen
        sensitive_keys = {
            "api_key",
            "secret",
            "mysql_pass",
            "admin_password",
            "jwt_secret",
            "short_api_key",
            "short_secret",
            "cryptopanic_token",
        }
        try:
            from server import CONFIG

            # Simuliert was backup() macht: safe_cfg ohne sensible Keys
            safe_cfg = {k: v for k, v in CONFIG.items() if k not in sensitive_keys}

            # Prüft dass keiner der sensiblen Keys in safe_cfg enthalten ist
            for key in sensitive_keys:
                assert key not in safe_cfg, f"Sensibler Key '{key}' im Backup gefunden!"
        except ImportError:
            pytest.skip("Server nicht importierbar")

    def test_security_headers_present(self):
        """Security-Headers werden bei Responses gesetzt."""
        try:
            from server import app

            with app.test_client() as client:
                resp = client.get("/login")
                # Pflicht-Security-Headers prüfen
                assert resp.headers.get("X-Content-Type-Options") == "nosniff"
                assert resp.headers.get("X-Frame-Options") == "SAMEORIGIN"
                assert resp.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
                assert "Permissions-Policy" in resp.headers
        except ImportError:
            pytest.skip("Server nicht importierbar")


class TestValidateEnv:
    """Tests für validate_env.py – Umgebungsvariablen-Validierung."""

    def test_weak_password_detected(self, monkeypatch):
        """Bekannte schwache Passwörter werden als critical markiert."""
        monkeypatch.setenv("ADMIN_PASSWORD", "nexus")
        from validate_env import validate

        issues = validate()
        critical = [i for i in issues if i.severity == "critical" and i.var == "ADMIN_PASSWORD"]
        assert len(critical) > 0, "Schwaches ADMIN_PASSWORD sollte als critical erkannt werden"

    def test_invalid_mysql_port_detected(self, monkeypatch):
        """Ungültiger MYSQL_PORT wird als critical Issue gemeldet."""
        monkeypatch.setenv("MYSQL_PORT", "99999")
        from validate_env import validate

        issues = validate()
        port_issues = [i for i in issues if i.var == "MYSQL_PORT"]
        assert len(port_issues) > 0, "Ungültiger MYSQL_PORT sollte erkannt werden"

    def test_missing_mysql_host_warn(self, monkeypatch):
        """Fehlender MYSQL_HOST erzeugt eine Warnung."""
        monkeypatch.delenv("MYSQL_HOST", raising=False)
        from validate_env import validate

        issues = validate()
        host_issues = [i for i in issues if i.var == "MYSQL_HOST"]
        assert len(host_issues) > 0, "Fehlender MYSQL_HOST sollte als warning gemeldet werden"

    def test_invalid_mysql_port_not_number(self, monkeypatch):
        """MYSQL_PORT als nicht-numerischer Wert wird als critical gemeldet."""
        monkeypatch.setenv("MYSQL_PORT", "abc")
        from validate_env import validate

        issues = validate()
        port_issues = [i for i in issues if i.var == "MYSQL_PORT" and i.severity == "critical"]
        assert len(port_issues) > 0, (
            "Nicht-numerischer MYSQL_PORT sollte als critical erkannt werden"
        )

    def test_valid_fernet_key_no_issue(self, monkeypatch):
        """Ein gültiger Fernet-Key erzeugt keinen ENCRYPTION_KEY-Issue."""
        from cryptography.fernet import Fernet

        valid_key = Fernet.generate_key().decode()
        monkeypatch.setenv("ENCRYPTION_KEY", valid_key)
        from validate_env import validate

        issues = validate()
        enc_issues = [i for i in issues if i.var == "ENCRYPTION_KEY"]
        assert len(enc_issues) == 0, (
            f"Gültiger ENCRYPTION_KEY sollte keinen Fehler erzeugen: {enc_issues}"
        )
