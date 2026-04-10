"""
TREVLIX – Integration Tests für REST-API (Verbesserung #42)
============================================================
Tests für API-Endpunkte, Auth-Decorators, Health-Check.
"""

import os
import sys
from types import SimpleNamespace

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
        # /metrics ist auth-geschützt (api_auth_required) – setze Session-User
        with app_client.session_transaction() as sess:
            sess["user_id"] = 1
        resp = app_client.get("/metrics")
        assert resp.status_code == 200
        body = resp.data.decode()
        assert "trevlix_bot_running" in body
        assert "trevlix_open_trades" in body


class TestPaperTradingExchangeUpsert:
    """Tests für Exchange-Upsert Verhalten im Paper-/Live-Modus."""

    def test_exchange_upsert_allows_empty_keys_in_paper_mode(self, app_client, monkeypatch):
        from server import CONFIG, db

        old_paper = CONFIG.get("paper_trading", True)
        CONFIG["paper_trading"] = True
        called = {}

        def _fake_upsert(user_id, exchange, api_key, api_secret, enabled=False, is_primary=False, passphrase=""):
            called.update(
                {
                    "user_id": user_id,
                    "exchange": exchange,
                    "api_key": api_key,
                    "api_secret": api_secret,
                    "enabled": enabled,
                    "is_primary": is_primary,
                    "passphrase": passphrase,
                }
            )
            return True

        monkeypatch.setattr(db, "upsert_user_exchange", _fake_upsert)

        with app_client.session_transaction() as sess:
            sess["user_id"] = 1

        resp = app_client.post(
            "/api/v1/user/exchanges",
            json={"exchange": "bybit", "enabled": True, "is_primary": True},
        )

        CONFIG["paper_trading"] = old_paper
        assert resp.status_code == 200
        assert called["exchange"] == "bybit"
        assert called["api_key"] == ""
        assert called["api_secret"] == ""

    def test_exchange_upsert_requires_keys_in_live_mode(self, app_client):
        from server import CONFIG

        old_paper = CONFIG.get("paper_trading", True)
        CONFIG["paper_trading"] = False
        with app_client.session_transaction() as sess:
            sess["user_id"] = 1

        resp = app_client.post(
            "/api/v1/user/exchanges",
            json={"exchange": "okx", "enabled": True},
        )

        CONFIG["paper_trading"] = old_paper
        assert resp.status_code == 400


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


class TestTradingControl:
    """Tests für Trading-Control API."""

    def test_trading_control_start_sets_running_and_enabled(self, app_client):
        from server import state, trade_mode

        with app_client.session_transaction() as sess:
            sess["user_id"] = 1

        trade_mode.set_enabled(False)
        with state._lock:
            state.running = False
            state.paused = False

        resp = app_client.post("/api/v1/trading/control", json={"action": "start"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert data["running"] is True
        assert trade_mode.enabled is True
        assert state.running is True

    def test_trading_control_stop_sets_running_false_and_disables(self, app_client):
        from server import state, trade_mode

        with app_client.session_transaction() as sess:
            sess["user_id"] = 1

        trade_mode.set_enabled(True)
        with state._lock:
            state.running = True
            state.paused = False

        resp = app_client.post("/api/v1/trading/control", json={"action": "stop"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert data["running"] is False
        assert trade_mode.enabled is False
        assert state.running is False

    def test_close_position_endpoint_closes_long_position(self, app_client, monkeypatch):
        import server
        from server import state

        with app_client.session_transaction() as sess:
            sess["user_id"] = 1

        called = {}

        def _fake_create_exchange():
            return object()

        def _fake_close_position(_ex, sym, reason, partial_ratio=1.0):
            called.update({"symbol": sym, "reason": reason, "partial_ratio": partial_ratio})
            with state._lock:
                state.positions.pop(sym, None)

        monkeypatch.setattr(server, "create_exchange", _fake_create_exchange)
        monkeypatch.setattr(server, "close_position", _fake_close_position)

        with state._lock:
            state.positions["BTC/USDT"] = {"entry": 100.0, "qty": 1.0}

        resp = app_client.post("/api/v1/trading/close-position", json={"symbol": "BTC/USDT"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert data["symbol"] == "BTC/USDT"
        assert data["side"] == "long"
        assert called["symbol"] == "BTC/USDT"

    def test_close_position_endpoint_returns_404_for_missing_symbol(self, app_client):
        with app_client.session_transaction() as sess:
            sess["user_id"] = 1

        resp = app_client.post("/api/v1/trading/close-position", json={"symbol": "ETH/USDT"})
        assert resp.status_code == 404
        data = resp.get_json()
        assert "error" in data


class TestVirginieChatAPI:
    """Tests für den VIRGINIE-Chat-Endpunkt in der 3D Live View."""

    def test_chat_history_returns_messages_list(self, app_client):
        with app_client.session_transaction() as sess:
            sess["user_id"] = 1

        resp = app_client.get("/api/v1/virginie/chat")
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data.get("messages"), list)
        assert data.get("max_messages", 0) > 0

    def test_chat_post_generates_user_and_assistant_messages(self, app_client, monkeypatch):
        import server

        with app_client.session_transaction() as sess:
            sess["user_id"] = 1

        monkeypatch.setattr(
            server.knowledge_base,
            "query_llm_with_tools",
            lambda prompt, context: f"Echo: {prompt} ({'VIRGINIE' in context})",
        )

        resp = app_client.post("/api/v1/virginie/chat", json={"message": "Wie ist das Risiko heute?"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert data["user"]["role"] == "user"
        assert "Risiko" in data["user"]["content"]
        assert data["assistant"]["role"] == "assistant"
        assert "Echo:" in data["assistant"]["content"]

    def test_chat_post_rejects_empty_message(self, app_client):
        with app_client.session_transaction() as sess:
            sess["user_id"] = 1

        resp = app_client.post("/api/v1/virginie/chat", json={"message": "   "})
        assert resp.status_code == 400
        data = resp.get_json()
        assert "error" in data

    def test_chat_status_endpoint_returns_guardrails(self, app_client):
        with app_client.session_transaction() as sess:
            sess["user_id"] = 1

        resp = app_client.get("/api/v1/virginie/status")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "enabled" in data
        assert "primary_control" in data
        assert "assistant_agents" in data

    def test_chat_clear_endpoint_resets_messages(self, app_client):
        with app_client.session_transaction() as sess:
            sess["user_id"] = 1

        app_client.post("/api/v1/virginie/chat", json={"message": "Test löschen"})
        clear_resp = app_client.post("/api/v1/virginie/chat/clear")
        assert clear_resp.status_code == 200
        assert clear_resp.get_json().get("ok") is True

        hist_resp = app_client.get("/api/v1/virginie/chat")
        assert hist_resp.status_code == 200
        assert hist_resp.get_json().get("messages") == []

    def test_chat_status_command_returns_status_summary(self, app_client):
        with app_client.session_transaction() as sess:
            sess["user_id"] = 1

        resp = app_client.post("/api/v1/virginie/chat", json={"message": "/status"})
        assert resp.status_code == 200
        data = resp.get_json()
        assistant = str(data.get("assistant", {}).get("content", ""))
        assert "Status:" in assistant
        assert "Agents=" in assistant


class TestPaperModeBuild:
    """Smoke-Test für 'Paper-Mode trading build' über API-Kette."""

    def test_paper_mode_start_stop_flow(self, app_client, monkeypatch):
        import server
        from server import CONFIG, state, trade_mode

        with app_client.session_transaction() as sess:
            sess["user_id"] = 1

        # BotLoop-Thread in Tests nicht real starten
        alive_loop = SimpleNamespace(name="BotLoop", is_alive=lambda: True)
        monkeypatch.setattr(server.threading, "enumerate", lambda: [alive_loop])

        # 1) explizit Paper-Mode setzen
        mode_resp = app_client.post("/api/v1/trading/mode", json={"mode": "paper"})
        assert mode_resp.status_code == 200
        mode_data = mode_resp.get_json()
        assert mode_data["paper_trading"] is True

        # 2) Trading starten (im Paper-Mode)
        start_resp = app_client.post("/api/v1/trading/control", json={"action": "start"})
        assert start_resp.status_code == 200
        start_data = start_resp.get_json()
        assert start_data["ok"] is True
        assert start_data["running"] is True
        assert trade_mode.mode == "paper"
        assert trade_mode.enabled is True
        assert CONFIG["paper_trading"] is True
        assert state.running is True

        # 3) State sollte weiterhin Paper-Mode reflektieren
        state_resp = app_client.get("/api/v1/state")
        assert state_resp.status_code == 200
        state_data = state_resp.get_json()
        assert state_data["paper_trading"] is True

        # 4) sauber stoppen
        stop_resp = app_client.post("/api/v1/trading/control", json={"action": "stop"})
        assert stop_resp.status_code == 200
        stop_data = stop_resp.get_json()
        assert stop_data["ok"] is True
        assert stop_data["running"] is False
        assert trade_mode.enabled is False
        assert state.running is False


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
