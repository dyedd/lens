from __future__ import annotations

from datetime import UTC, datetime, timedelta
import hashlib
import hmac
import secrets
from typing import Any

import jwt

from .config import Settings


PBKDF2_ITERATIONS = 600_000
JWT_ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        PBKDF2_ITERATIONS,
    ).hex()
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt}${digest}"


def verify_password(password: str, hashed_password: str) -> bool:
    try:
        algorithm, iterations_text, salt, digest = hashed_password.split("$", 3)
    except ValueError:
        return False

    if algorithm != "pbkdf2_sha256":
        return False

    candidate = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        int(iterations_text),
    ).hex()
    return hmac.compare_digest(candidate, digest)


def create_access_token(subject: str, settings: Settings) -> tuple[str, int]:
    expires_in = settings.auth_access_token_minutes * 60
    expires_at = datetime.now(UTC) + timedelta(seconds=expires_in)
    token = jwt.encode(
        {
            "sub": subject,
            "exp": expires_at,
        },
        settings.auth_secret_key,
        algorithm=JWT_ALGORITHM,
    )
    return token, expires_in


def decode_access_token(token: str, settings: Settings) -> dict[str, Any]:
    return jwt.decode(token, settings.auth_secret_key, algorithms=[JWT_ALGORITHM])
