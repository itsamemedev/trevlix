"""
╔══════════════════════════════════════════════════════════════╗
║  TREVLIX – Encryption Service                                ║
║  Fernet-Verschlüsselung für sensible Daten (API-Schlüssel)  ║
╚══════════════════════════════════════════════════════════════╝

Verwendung:
    from services.encryption import encrypt_value, decrypt_value

    encrypted = encrypt_value("mein-api-key")
    original  = decrypt_value(encrypted)

Umgebungsvariable:
    ENCRYPTION_KEY  – 32-Byte URL-safe base64-kodierter Fernet-Key.
                      Fehlt sie, wird ein temporärer Key generiert und
                      beim Start gewarnt (kein Produktionsbetrieb!).

    Neuen Key erzeugen:
        python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
"""

import base64
import logging
import os

log = logging.getLogger("Encryption")

try:
    from cryptography.fernet import Fernet
    _FERNET_AVAILABLE = True
except ImportError:
    _FERNET_AVAILABLE = False
    log.warning("cryptography nicht installiert – API-Keys werden NICHT verschlüsselt!")


def _get_fernet() -> "Fernet | None":
    """Gibt eine Fernet-Instanz zurück, basierend auf ENCRYPTION_KEY aus .env."""
    if not _FERNET_AVAILABLE:
        return None

    key_str = os.getenv("ENCRYPTION_KEY", "")
    if not key_str:
        # Einmalig warnen – ohne Key kein Verschlüsselungsschutz
        log.warning(
            "ENCRYPTION_KEY nicht gesetzt! Generiere temporären Key für diese Sitzung. "
            "Setze ENCRYPTION_KEY in .env für Produktion: "
            "python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        )
        # Temporärer Key (wird bei Neustart gewechselt → alte verschlüsselte Werte lesbar solange Session läuft)
        _get_fernet._temp_key = getattr(_get_fernet, "_temp_key", Fernet.generate_key())
        return Fernet(_get_fernet._temp_key)

    try:
        # Fernet erwartet URL-safe base64, 32 Bytes → 44 Zeichen
        return Fernet(key_str.encode())
    except Exception:
        # Falls der Key kein gültiger Fernet-Key ist, versuche ihn zu hashen
        import hashlib
        derived = base64.urlsafe_b64encode(hashlib.sha256(key_str.encode()).digest())
        return Fernet(derived)


def encrypt_value(plaintext: str) -> str:
    """
    Verschlüsselt einen Klartext-String mit Fernet.
    Gibt den verschlüsselten Wert als String zurück (URL-safe base64).
    Bei fehlender Bibliothek wird der Klartext unverändert zurückgegeben.
    """
    if not plaintext:
        return plaintext
    f = _get_fernet()
    if f is None:
        return plaintext
    try:
        return f.encrypt(plaintext.encode()).decode()
    except Exception as e:
        log.error(f"encrypt_value: {e}")
        return plaintext


def decrypt_value(ciphertext: str) -> str:
    """
    Entschlüsselt einen mit encrypt_value() verschlüsselten String.
    Gibt bei Fehler (falscher Key, beschädigt) den Originalwert zurück,
    damit ältere unverschlüsselte Einträge nicht kaputt gehen.
    """
    if not ciphertext:
        return ciphertext
    f = _get_fernet()
    if f is None:
        return ciphertext
    try:
        return f.decrypt(ciphertext.encode()).decode()
    except Exception:
        # Rückwärtskompatibel: falls Wert noch unverschlüsselt (Legacy)
        return ciphertext


def is_encrypted(value: str) -> bool:
    """Prüft, ob ein Wert mit Fernet verschlüsselt aussieht (beginnt mit 'gAAAAA')."""
    return bool(value and value.startswith("gAAAAA"))
