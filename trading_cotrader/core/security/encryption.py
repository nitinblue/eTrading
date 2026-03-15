"""
Credential Encryption — AES-256 for broker tokens at rest.

Uses Fernet (AES-128-CBC with HMAC) from the cryptography library.
Per-user encryption key derived from SECRET_KEY + user_id.

Usage:
    from trading_cotrader.core.security.encryption import encrypt_token, decrypt_token

    # Store
    encrypted = encrypt_token(session_token, user_id)
    broker_conn.encrypted_token = encrypted

    # Retrieve
    token = decrypt_token(broker_conn.encrypted_token, user_id)
"""

import os
import hashlib
import base64
import logging
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)

# Master secret — from env var in production
_SECRET_KEY = os.environ.get('SECRET_KEY', 'cotrader-dev-secret-change-in-production')


def _derive_key(user_id: str) -> bytes:
    """Derive a per-user Fernet key from SECRET_KEY + user_id.

    Uses SHA-256 hash, base64-encoded to 32 bytes (Fernet requires url-safe base64).
    Each user gets a unique encryption key — compromising one doesn't expose others.
    """
    raw = f"{_SECRET_KEY}:{user_id}".encode('utf-8')
    digest = hashlib.sha256(raw).digest()
    return base64.urlsafe_b64encode(digest)


def encrypt_token(plaintext: str, user_id: str) -> str:
    """Encrypt a broker token for storage.

    Args:
        plaintext: The broker session token / API key
        user_id: User's ID (for per-user key derivation)

    Returns:
        Encrypted string (base64, safe for DB storage)
    """
    key = _derive_key(user_id)
    f = Fernet(key)
    encrypted = f.encrypt(plaintext.encode('utf-8'))
    return encrypted.decode('utf-8')


def decrypt_token(encrypted: str, user_id: str) -> Optional[str]:
    """Decrypt a broker token from storage.

    Args:
        encrypted: The encrypted token from DB
        user_id: User's ID (for per-user key derivation)

    Returns:
        Decrypted plaintext token, or None if decryption fails
    """
    if not encrypted:
        return None
    try:
        key = _derive_key(user_id)
        f = Fernet(key)
        decrypted = f.decrypt(encrypted.encode('utf-8'))
        return decrypted.decode('utf-8')
    except InvalidToken:
        logger.error("Failed to decrypt token — key may have changed or data corrupted")
        return None
    except Exception as e:
        logger.error(f"Decryption error: {e}")
        return None
