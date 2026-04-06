from app.core.admin_user_validation import validate_admin_user_payload


def test_validate_admin_user_payload_success():
    ok, payload, key, msg = validate_admin_user_payload(
        {"username": "alice_admin", "password": "StrongPass123", "role": "admin", "balance": 123.45}
    )
    assert ok is True
    assert key == ""
    assert msg == ""
    assert payload["username"] == "alice_admin"
    assert payload["role"] == "admin"


def test_validate_admin_user_payload_rejects_weak_password():
    ok, payload, key, msg = validate_admin_user_payload(
        {"username": "alice", "password": "weakpass", "role": "user"}
    )
    assert ok is False
    assert payload == {}
    assert key == "err_password_length"
    assert "Passwort" in msg


def test_validate_admin_user_payload_rejects_invalid_role():
    ok, payload, key, _ = validate_admin_user_payload(
        {"username": "alice", "password": "StrongPass123", "role": "superadmin"}
    )
    assert ok is False
    assert payload == {}
    assert key == "err_invalid_role"
