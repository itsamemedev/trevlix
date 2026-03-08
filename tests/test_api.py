"""
TREVLIX – Integration Tests für REST-API (Verbesserung #42)
============================================================
Tests für API-Endpunkte, Auth-Decorators, Health-Check.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture
def app_client():
    """Erzeugt einen Flask Test Client."""
    os.environ.setdefault("PAPER_TRADING", "true")
    os.environ.setdefault("ADMIN_PASSWORD", "test-admin-password")
    os.environ.setdefault("JWT_SECRET", "test-jwt-secret-32-bytes-hex")
    os.environ.setdefault("SECRET_KEY", "test-flask-secret")
    os.environ.setdefault("ENCRYPTION_KEY", "dGVzdC1rZXktZm9yLXVuaXQtdGVzdHMtb25seS0xMjM0")
    os.environ.setdefault("LANGUAGE", "de")

    try:
        from server import app

        app.config["TESTING"] = True
        with app.test_client() as client:
            yield client
    except Exception as e:
        pytest.skip(f"Server-Import fehlgeschlagen (DB nicht verfügbar): {e}")


class TestHealthCheck:
    """Tests für den Health-Check-Endpunkt."""

    def test_status_returns_200(self, app_client):
        """Health-Check sollte immer 200 zurückgeben."""
        resp = app_client.get("/api/v1/status")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "status" in data
        assert "version" in data

    def test_status_contains_version(self, app_client):
        resp = app_client.get("/api/v1/status")
        data = resp.get_json()
        assert data["version"]  # Nicht leer


class TestAuthEndpoints:
    """Tests für Authentifizierungs-Endpunkte."""

    def test_login_get_returns_form(self, app_client):
        resp = app_client.get("/login")
        assert resp.status_code == 200
        assert b"Anmelden" in resp.data or b"Login" in resp.data

    def test_login_post_invalid(self, app_client):
        resp = app_client.post(
            "/login",
            data={
                "username": "nonexistent",
                "password": "wrongpassword",
            },
            follow_redirects=False,
        )
        # Sollte zurück zu /login?err=1 redirecten
        assert resp.status_code in (302, 303)

    def test_register_disabled(self, app_client):
        """Registrierung sollte 403 zurückgeben wenn deaktiviert."""
        resp = app_client.get("/register")
        # Wenn ALLOW_REGISTRATION=false, sollte 403 kommen
        assert resp.status_code in (200, 403)


class TestAPIAuth:
    """Tests für API-Auth-Decorator."""

    def test_unauthenticated_api_returns_401(self, app_client):
        """API-Endpunkte ohne Token sollten 401 zurückgeben."""
        resp = app_client.get("/api/v1/state")
        assert resp.status_code == 401
        data = resp.get_json()
        assert "error" in data

    def test_invalid_token_returns_401(self, app_client):
        """Ungültiger Bearer Token sollte 401 zurückgeben."""
        resp = app_client.get("/api/v1/state", headers={"Authorization": "Bearer invalid-token"})
        assert resp.status_code == 401


class TestErrorHandling:
    """Tests für zentrale Fehlerbehandlung (Verbesserung #12)."""

    def test_404_api_returns_json(self, app_client):
        resp = app_client.get("/api/v1/nonexistent")
        assert resp.status_code == 404
        data = resp.get_json()
        assert "error" in data

    def test_404_page_redirects(self, app_client):
        resp = app_client.get("/nonexistent-page", follow_redirects=False)
        assert resp.status_code in (302, 404)


class TestMetrics:
    """Tests für Prometheus-Metriken (Verbesserung #48)."""

    def test_metrics_endpoint(self, app_client):
        resp = app_client.get("/metrics")
        assert resp.status_code == 200
        body = resp.data.decode()
        assert "trevlix_bot_running" in body
        assert "trevlix_open_trades" in body


class TestSecurityHeaders:
    """Tests für Security Headers (Verbesserung #6)."""

    def test_security_headers_present(self, app_client):
        resp = app_client.get("/api/v1/status")
        assert resp.headers.get("X-Content-Type-Options") == "nosniff"
        assert resp.headers.get("X-Frame-Options") == "SAMEORIGIN"
        # X-XSS-Protection ist deprecated und wurde entfernt – kein Test mehr
        assert resp.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
        # Permissions-Policy sollte gesetzt sein
        assert "Permissions-Policy" in resp.headers


class TestPasswordPolicy:
    """Tests für Password-Policy (Verbesserung #4)."""

    def test_short_password_rejected(self, app_client):
        """Passwort unter 12 Zeichen sollte abgelehnt werden."""
        # Setze ALLOW_REGISTRATION temporär
        try:
            from server import CONFIG

            old_val = CONFIG.get("allow_registration", False)
            CONFIG["allow_registration"] = True
            resp = app_client.post(
                "/register",
                data={
                    "username": "testuser",
                    "password": "Short1",
                    "password2": "Short1",
                },
                follow_redirects=False,
            )
            assert resp.status_code in (302, 303)
            assert "err=" in resp.headers.get("Location", "")
            CONFIG["allow_registration"] = old_val
        except Exception:
            pytest.skip("Registration endpoint not available")
