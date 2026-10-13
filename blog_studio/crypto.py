"""Encryption for secrets stored on behalf of a workspace, such as its Anthropic API key.

Keys are encrypted with Fernet (AES-128-CBC plus HMAC) under MASTHEAD_SECRET_KEY, which never
leaves the server's environment. The database alone is not enough to read a customer's key.
"""

from __future__ import annotations

import base64
import hashlib
import os

from cryptography.fernet import Fernet, InvalidToken


class SecretError(Exception):
    pass


def _fernet() -> Fernet:
    secret = os.environ.get("MASTHEAD_SECRET_KEY", "")
    if len(secret) < 32:
        raise SecretError("MASTHEAD_SECRET_KEY must be set to at least 32 random characters to store API keys.")
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(secret.encode()).digest()))


def encrypt(value: str) -> str:
    return _fernet().encrypt(value.encode()).decode()


def decrypt(token: str) -> str:
    try:
        return _fernet().decrypt(token.encode()).decode()
    except InvalidToken as e:
        raise SecretError("A stored key can't be decrypted. Was MASTHEAD_SECRET_KEY changed?") from e


def last4(value: str) -> str:
    return value[-4:] if len(value) >= 8 else "••••"
