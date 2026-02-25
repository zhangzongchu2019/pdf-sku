"""Fernet symmetric encryption for API key storage."""
from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet


def _derive_key(secret: str) -> bytes:
    """Derive a Fernet-compatible 32-byte key from JWT_SECRET_KEY."""
    raw = hashlib.sha256(secret.encode()).digest()
    return base64.urlsafe_b64encode(raw)


def encrypt_value(plaintext: str, secret: str) -> str:
    """Return Fernet-encrypted base64 string."""
    f = Fernet(_derive_key(secret))
    return f.encrypt(plaintext.encode()).decode()


def decrypt_value(ciphertext: str, secret: str) -> str:
    """Decrypt a Fernet-encrypted string."""
    f = Fernet(_derive_key(secret))
    return f.decrypt(ciphertext.encode()).decode()
