from datetime import UTC, datetime, timedelta
import hashlib
import hmac
import secrets
from typing import Any

import jwt

PBKDF2_ITERATIONS = 600_000
JWT_ALGORITHM = "HS256"
_MIN_AUTH_SECRET_BYTES = 32
MIN_ADMIN_PASSWORD_LENGTH = 12


def validate_auth_secret_key(secret_key: str) -> None:
    """Require enough key material for HS256 signing."""
    if not secret_key.strip():
        raise RuntimeError("LENS_AUTH_SECRET_KEY is required")
    if len(secret_key.encode("utf-8")) < _MIN_AUTH_SECRET_BYTES:
        raise RuntimeError("LENS_AUTH_SECRET_KEY must be at least 32 bytes")


def validate_admin_password(password: str) -> str:
    """Validate a newly supplied administrator password."""
    if len(password) < MIN_ADMIN_PASSWORD_LENGTH:
        raise ValueError(
            f"Administrator passwords must be at least {MIN_ADMIN_PASSWORD_LENGTH} characters"
        )
    if not password.strip():
        raise ValueError("Administrator password cannot contain only whitespace")
    return password


def hash_password(password: str) -> str:
    """Hash a password using the configured PBKDF2 format."""
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        PBKDF2_ITERATIONS,
    ).hex()
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt}${digest}"


def verify_password(password: str, hashed_password: str) -> bool:
    """Return whether a password matches a stored PBKDF2 hash."""
    parts = hashed_password.split("$", 3)
    if len(parts) != 4:
        return False
    algorithm, iterations_text, salt, digest = parts

    if algorithm != "pbkdf2_sha256":
        return False

    candidate = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        int(iterations_text),
    ).hex()
    return hmac.compare_digest(candidate, digest)


def create_access_token(
    subject: str,
    secret_key: str,
    access_token_minutes: int,
    token_version: int,
) -> tuple[str, int]:
    """Create a signed access token and return it with its lifetime."""
    validate_auth_secret_key(secret_key)
    expires_in = access_token_minutes * 60
    expires_at = datetime.now(UTC) + timedelta(seconds=expires_in)
    token = jwt.encode(
        {
            "sub": subject,
            "ver": token_version,
            "exp": expires_at,
        },
        secret_key,
        algorithm=JWT_ALGORITHM,
    )
    return token, expires_in


def decode_access_token(token: str, secret_key: str) -> dict[str, Any]:
    """Decode and validate a signed access token."""
    validate_auth_secret_key(secret_key)
    return jwt.decode(token, secret_key, algorithms=[JWT_ALGORITHM])
