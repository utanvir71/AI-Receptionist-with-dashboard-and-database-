"""Shared staff password and session-token helpers."""

from __future__ import annotations

import hashlib
import hmac
from secrets import compare_digest, token_hex


HASH_ALGORITHM = "pbkdf2_sha256"
HASH_ITERATIONS = 260_000
STAFF_SESSION_SUBJECT = "staff"


def hash_staff_password(
    password: str,
    *,
    salt: str | None = None,
    iterations: int = HASH_ITERATIONS,
) -> str:
    """Return a PBKDF2 password hash suitable for STAFF_PASSWORD_HASH."""
    password_salt = salt or token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        password_salt.encode("utf-8"),
        iterations,
    ).hex()
    return f"{HASH_ALGORITHM}${iterations}${password_salt}${digest}"


def verify_staff_password(password: str, password_hash: str) -> bool:
    """Return true when a staff password matches the configured hash."""
    try:
        algorithm, raw_iterations, salt, expected_digest = password_hash.split("$", 3)
        iterations = int(raw_iterations)
    except ValueError:
        return False

    if algorithm != HASH_ALGORITHM:
        return False

    candidate = hash_staff_password(password, salt=salt, iterations=iterations)
    return compare_digest(candidate, password_hash)


def create_staff_session_token(secret_key: str) -> str:
    """Create a signed shared-staff session token."""
    signature = hmac.new(
        secret_key.encode("utf-8"),
        STAFF_SESSION_SUBJECT.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"{STAFF_SESSION_SUBJECT}.{signature}"


def verify_staff_session_token(token: str, secret_key: str) -> bool:
    """Return true when a token was signed with the staff session secret."""
    subject, separator, signature = token.partition(".")
    if subject != STAFF_SESSION_SUBJECT or separator != "." or not signature:
        return False

    expected = create_staff_session_token(secret_key)
    return compare_digest(f"{subject}.{signature}", expected)
