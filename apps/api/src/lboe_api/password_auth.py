"""Password hashing helpers for first-party operator accounts."""

from __future__ import annotations

import base64
import hashlib
import hmac
import re
import secrets

SCRYPT_N = 2**14
SCRYPT_R = 8
SCRYPT_P = 1
SCRYPT_DKLEN = 32
_USERNAME_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{2,63}$")


def normalize_username(value: str) -> str:
    return value.strip().casefold()


def valid_username(value: str) -> bool:
    return _USERNAME_RE.fullmatch(normalize_username(value)) is not None


def hash_password(password: str, *, salt: bytes | None = None) -> str:
    """Return a versioned, salted scrypt password hash."""
    if len(password) < 12:
        raise ValueError("password must contain at least 12 characters")
    actual_salt = salt or secrets.token_bytes(16)
    digest = hashlib.scrypt(
        password.encode("utf-8"), salt=actual_salt, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P, dklen=SCRYPT_DKLEN
    )
    return "$".join(
        (
            "scrypt",
            str(SCRYPT_N),
            str(SCRYPT_R),
            str(SCRYPT_P),
            base64.urlsafe_b64encode(actual_salt).decode("ascii"),
            base64.urlsafe_b64encode(digest).decode("ascii"),
        )
    )


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, n, r, p, salt_text, digest_text = encoded.split("$", 5)
        if algorithm != "scrypt":
            return False
        salt = base64.urlsafe_b64decode(salt_text.encode("ascii"))
        expected = base64.urlsafe_b64decode(digest_text.encode("ascii"))
        actual = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=int(n), r=int(r), p=int(p), dklen=len(expected))
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(actual, expected)


# Keep unknown-user checks computationally comparable to known-user checks.
DUMMY_PASSWORD_HASH = hash_password("not-a-real-operator-password", salt=b"lboe-dummy-salt!")
