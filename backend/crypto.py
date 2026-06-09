"""
Encryption utilities for device passwords.
Uses Fernet (AES-128-CBC + HMAC) from the cryptography library.
Encrypted values are prefixed with ENC$ to distinguish from plaintext.
"""
import os
import sys
from pathlib import Path

from cryptography.fernet import Fernet

ENC_PREFIX = "ENC$"

# Key file stored next to the database
KEY_FILE = Path(__file__).resolve().parent.parent / ".encryption_key"

_fernet = None


def _get_fernet() -> Fernet:
    """Lazy-load the Fernet instance. Reads key from env var or key file."""
    global _fernet
    if _fernet is not None:
        return _fernet

    key_b64 = os.environ.get("INSPECT_SECRET_KEY", "").strip()
    if key_b64:
        _fernet = Fernet(key_b64.encode())
        return _fernet

    # Fallback: read or generate key file
    if KEY_FILE.exists():
        key_b64 = KEY_FILE.read_text().strip()
    else:
        key_b64 = Fernet.generate_key().decode()
        KEY_FILE.write_text(key_b64)
        # Restrict permissions on the key file
        try:
            if sys.platform != "win32":
                os.chmod(KEY_FILE, 0o600)
            else:
                # Windows: set read-only for owner via subprocess
                import subprocess as _sp
                _sp.run(["icacls", str(KEY_FILE), "/inheritance:r", "/grant:r", "%USERNAME%:R"],
                        capture_output=True, timeout=5)
        except Exception:
            pass
        print("=" * 60)
        print("[crypto] WARNING: New encryption key generated!")
        print(f"[crypto] Key file: {KEY_FILE}")
        print("[crypto] BACKUP THIS FILE — loss means all device passwords become unrecoverable!")
        print("=" * 60)

    _fernet = Fernet(key_b64.encode())
    return _fernet


def is_encrypted(value: str) -> bool:
    """Check if a password value is already encrypted."""
    return value.startswith(ENC_PREFIX) if value else False


def encrypt_password(plaintext: str) -> str:
    """Encrypt a plaintext password. Returns ENC$<token>."""
    if not plaintext:
        print("[crypto] WARNING: encrypt_password called with empty password!")
        return plaintext
    if is_encrypted(plaintext):
        return plaintext  # Already encrypted
    f = _get_fernet()
    token = f.encrypt(plaintext.encode()).decode()
    return ENC_PREFIX + token


def decrypt_password(encoded: str) -> str:
    """Decrypt a password. Falls back to returning plaintext if not encrypted."""
    if not encoded:
        return encoded
    if not is_encrypted(encoded):
        return encoded  # Plaintext (legacy, not yet migrated)
    f = _get_fernet()
    token = encoded[len(ENC_PREFIX):]
    try:
        return f.decrypt(token.encode()).decode()
    except Exception:
        # If decryption fails, return as-is (corrupted or wrong key)
        return encoded


def migrate_plaintext_passwords(db_session_factory):
    """Encrypt any plaintext device passwords in the database.
    Call this at startup. Returns count of migrated passwords.
    """
    from .models import Device
    db = db_session_factory()
    try:
        devices = db.query(Device).all()
        migrated = 0
        for dev in devices:
            if dev.password and not is_encrypted(dev.password):
                dev.password = encrypt_password(dev.password)
                migrated += 1
        if migrated > 0:
            db.commit()
            print(f"[crypto] Migrated {migrated} device passwords to encrypted storage")
        return migrated
    except Exception as e:
        db.rollback()
        print(f"[crypto] Migration error: {e}")
        return 0
    finally:
        db.close()
