from pathlib import Path

from flask import Flask, redirect, session

from routes.dashboard import create_dashboard_blueprint


def _require_auth(func):
    def _wrapped(*args, **kwargs):
        if not session.get("user_id"):
            return redirect("/login")
        return func(*args, **kwargs)

    _wrapped.__name__ = func.__name__
    return _wrapped


def test_dashboard_route_requires_auth(tmp_path: Path):
    (tmp_path / "dashboard.html").write_text("dashboard")

    app = Flask(__name__)
    app.secret_key = "test"
    app.register_blueprint(create_dashboard_blueprint(str(tmp_path), _require_auth))

    client = app.test_client()

    resp = client.get("/dashboard")
    assert resp.status_code == 302
    assert "/login" in resp.location

    with client.session_transaction() as sess:
        sess["user_id"] = 1

    ok_resp = client.get("/dashboard")
    assert ok_resp.status_code == 200
    assert b"dashboard" in ok_resp.data


def test_public_dashboard_blueprint_pages(tmp_path: Path):
    (tmp_path / "about.html").write_text("about")

    app = Flask(__name__)
    app.secret_key = "test"
    app.register_blueprint(create_dashboard_blueprint(str(tmp_path), _require_auth))

    client = app.test_client()
    resp = client.get("/about")
    assert resp.status_code == 200
    assert b"about" in resp.data
