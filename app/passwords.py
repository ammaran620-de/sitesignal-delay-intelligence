from __future__ import annotations

import hashlib
import hmac
import secrets

_ITERATIONS = 240_000


def hash_password(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _ITERATIONS)
    return f"{salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        salt_hex, expected_hex = stored.split("$", 1)
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), _ITERATIONS)
        return hmac.compare_digest(actual.hex(), expected_hex)
    except (ValueError, TypeError):
        return False
