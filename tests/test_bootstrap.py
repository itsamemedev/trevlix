from app.core.bootstrap import resolve_socketio_async_mode


def test_resolve_socketio_async_mode_from_env(monkeypatch):
    monkeypatch.setenv("SOCKETIO_ASYNC_MODE", "threading")
    assert resolve_socketio_async_mode() == "threading"


def test_resolve_socketio_async_mode_default_is_valid(monkeypatch):
    monkeypatch.delenv("SOCKETIO_ASYNC_MODE", raising=False)
    mode = resolve_socketio_async_mode()
    assert mode in {"eventlet", "gevent", "threading"}
