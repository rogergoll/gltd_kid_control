"""Verificação de senha do admin (PBKDF2) no client."""
from __future__ import annotations

import hashlib
import secrets


def verify_password(password: str, stored: str) -> bool:
    if not stored or "$" not in stored:
        return False
    try:
        salt_hex, hash_hex = stored.split("$", 1)
        dk = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), bytes.fromhex(salt_hex), 200_000,
        )
        return secrets.compare_digest(dk.hex(), hash_hex)
    except Exception:  # noqa: BLE001
        return False
