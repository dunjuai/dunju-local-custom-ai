"""
Dunju AI — Backup Encryption (v2.13.0)
Password-based AES encryption for database backups. Fully local/offline.

Format: MAGIC (9 bytes) + salt (16 bytes) + Fernet token.
Key = PBKDF2-HMAC-SHA256(password, salt, 200k iterations) -> Fernet key.

Only backup FILES are encrypted; the live database is never touched, so a
forgotten password can never lock you out of your working data.
"""

import os
import base64

MAGIC = b"DUNJUENC1"
_ITERATIONS = 200_000
_SALT_LEN = 16


def _derive_key(password: str, salt: bytes) -> bytes:
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=_ITERATIONS)
    return base64.urlsafe_b64encode(kdf.derive(password.encode("utf-8")))


def encrypt_bytes(data: bytes, password: str) -> bytes:
    from cryptography.fernet import Fernet
    salt = os.urandom(_SALT_LEN)
    token = Fernet(_derive_key(password, salt)).encrypt(data)
    return MAGIC + salt + token


def decrypt_bytes(blob: bytes, password: str) -> bytes:
    """Raises ValueError on bad format; cryptography.fernet.InvalidToken on wrong password."""
    from cryptography.fernet import Fernet
    if not blob.startswith(MAGIC):
        raise ValueError("Not a Dunju encrypted backup")
    off = len(MAGIC)
    salt = blob[off:off + _SALT_LEN]
    token = blob[off + _SALT_LEN:]
    return Fernet(_derive_key(password, salt)).decrypt(token)
