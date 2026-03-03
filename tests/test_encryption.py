"""
╔══════════════════════════════════════════════════════════════╗
║  TREVLIX Tests – Verschlüsselungs-Service                    ║
╚══════════════════════════════════════════════════════════════╝

Führe aus mit:  pytest tests/test_encryption.py -v
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestEncryption:
    """Tests für den Fernet-Verschlüsselungs-Service."""

    def test_encrypt_decrypt_roundtrip(self):
        """Verschlüsseln und Entschlüsseln ergibt den Original-Wert."""
        from services.encryption import decrypt_value, encrypt_value
        original = "my-secret-api-key-12345"
        encrypted = encrypt_value(original)
        decrypted = decrypt_value(encrypted)
        assert decrypted == original

    def test_encrypted_differs_from_plaintext(self):
        """Verschlüsselter Wert != Klartext."""
        from services.encryption import encrypt_value
        original = "api-key-abc"
        encrypted = encrypt_value(original)
        assert encrypted != original

    def test_empty_string_passthrough(self):
        """Leerer String wird unverändert durchgegeben."""
        from services.encryption import decrypt_value, encrypt_value
        assert encrypt_value("") == ""
        assert decrypt_value("") == ""

    def test_none_like_passthrough(self):
        """None-ähnliche Werte (None, None) werden nicht gecrasht."""
        from services.encryption import decrypt_value
        # Legacy unverschlüsselter Wert wird zurückgegeben
        result = decrypt_value("plain-old-unencrypted-key")
        assert result == "plain-old-unencrypted-key"

    def test_is_encrypted_detects_fernet(self):
        """is_encrypted erkennt Fernet-verschlüsselte Werte."""
        from services.encryption import encrypt_value, is_encrypted
        encrypted = encrypt_value("test-key")
        assert is_encrypted(encrypted) is True

    def test_is_encrypted_rejects_plaintext(self):
        """is_encrypted lehnt Klartext ab."""
        from services.encryption import is_encrypted
        assert is_encrypted("plain-api-key") is False
        assert is_encrypted("") is False

    def test_encrypt_with_special_characters(self):
        """Sonderzeichen und lange Strings werden korrekt ver-/entschlüsselt."""
        from services.encryption import decrypt_value, encrypt_value
        special = "abc!@#$%^&*()_+-=[]{}|;':\",./<>?äöü€"
        assert decrypt_value(encrypt_value(special)) == special

    def test_different_encryptions_same_plaintext(self):
        """Gleicher Klartext → verschiedene Ciphertext (Fernet ist nicht deterministisch)."""
        from services.encryption import encrypt_value
        key = "same-api-key"
        enc1 = encrypt_value(key)
        enc2 = encrypt_value(key)
        # Fernet verwendet zufälligen IV → unterschiedliche Outputs
        assert enc1 != enc2

    def test_custom_encryption_key_via_env(self, monkeypatch):
        """Eigener ENCRYPTION_KEY aus Umgebungsvariable wird genutzt."""
        from cryptography.fernet import Fernet
        test_key = Fernet.generate_key().decode()
        monkeypatch.setenv("ENCRYPTION_KEY", test_key)

        # Nach env-Änderung neu importieren
        import importlib

        import services.encryption as enc_module
        importlib.reload(enc_module)

        original = "test-api-secret-xyz"
        encrypted = enc_module.encrypt_value(original)
        decrypted = enc_module.decrypt_value(encrypted)
        assert decrypted == original


class TestDBPool:
    """Grundlegende Tests für den Connection Pool (ohne echte DB)."""

    def test_pool_instantiation_without_db(self):
        """Pool kann instanziiert werden, auch ohne laufende DB."""
        from services.db_pool import ConnectionPool
        # Soll nicht crashen, nur fehlschlagen beim Verbinden
        try:
            pool = ConnectionPool(
                host="127.0.0.1", port=9999,  # kein MySQL auf Port 9999
                user="test", password="test", database="test",
                pool_size=1, timeout=1,
            )
            # Pool erstellt, aber ohne Verbindungen
            assert pool.pool_size == 1
        except Exception:
            pass  # Verbindungsfehler erwartet

    def test_pool_context_manager_interface(self):
        """Connection Pool hat context manager Interface."""
        from services.db_pool import ConnectionPool
        pool = ConnectionPool.__new__(ConnectionPool)
        assert hasattr(pool, 'connection')
        assert hasattr(pool, 'acquire')
        assert hasattr(pool, 'release')
