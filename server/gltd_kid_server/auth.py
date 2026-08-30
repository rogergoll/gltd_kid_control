"""Autenticação do admin: hash de senha + sessões por token."""
from __future__ import annotations

import hashlib
import os
import secrets
import time


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 200_000)
    return salt.hex() + "$" + dk.hex()


def verify_password(password: str, stored: str) -> bool:
    try:
        salt_hex, hash_hex = stored.split("$", 1)
        dk = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), bytes.fromhex(salt_hex), 200_000,
        )
        return secrets.compare_digest(dk.hex(), hash_hex)
    except Exception:  # noqa: BLE001
        return False


class SessionManager:
    """Sessões em memória (token -> (usuário, expiração))."""

    def __init__(self, ttl_seconds: int = 86400) -> None:
        self._sessions: dict[str, tuple[str, float]] = {}
        self.ttl = ttl_seconds

    def create(self, username: str) -> str:
        token = secrets.token_hex(32)
        self._sessions[token] = (username, time.time() + self.ttl)
        return token

    def validate(self, token: str | None) -> str | None:
        if not token:
            return None
        item = self._sessions.get(token)
        if not item:
            return None
        username, expires = item
        if time.time() > expires:
            self._sessions.pop(token, None)
            return None
        return username

    def revoke(self, token: str | None) -> None:
        if token:
            self._sessions.pop(token, None)
