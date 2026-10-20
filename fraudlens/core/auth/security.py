"""Password hashing and JWT issuance for analyst authentication.

Password hashing uses stdlib PBKDF2-HMAC-SHA256 (hashlib) — no bcrypt/
passlib dependency, since those need C extensions that aren't guaranteed to
build cleanly on every teammate's machine this close to a deadline.
PBKDF2 with a per-password random salt and 200k iterations is a real,
defensible choice, not a toy hash.
"""

from __future__ import annotations

import hashlib
import os
import secrets
import time
from pathlib import Path
from typing import Optional

import jwt

_PBKDF2_ITERATIONS = 200_000
_JWT_ALGORITHM = "HS256"
_JWT_TTL_SECONDS = 24 * 60 * 60  # 24h session — a hackathon demo, not a bank


def load_session_secret(path, *, configured=None, mode="demo"):
    """No shared signing fallback; local sessions survive a backend restart."""
    if configured:
        if len(configured) < 32:
            raise ValueError("FRAUDLENS_JWT_SECRET must be at least 32 characters")
        return configured
    if mode != "demo":
        raise ValueError("An explicit strong FRAUDLENS_JWT_SECRET is required outside demo mode")
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        value = path.read_text().strip()
        if len(value) < 32:
            raise ValueError("Stored session secret is invalid")
        return value
    value = secrets.token_urlsafe(48)
    with os.fdopen(descriptor, "w") as file:
        file.write(value)
    return value


_JWT_SECRET = load_session_secret(
    os.environ.get("FRAUDLENS_SESSION_SECRET_PATH", "var/session.key"),
    configured=os.environ.get("FRAUDLENS_JWT_SECRET"),
    mode=os.environ.get("FRAUDLENS_MODE", "demo"),
)


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), _PBKDF2_ITERATIONS)
    return f"{salt}${digest.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        salt, expected_hex = stored_hash.split("$", 1)
    except ValueError:
        return False
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), _PBKDF2_ITERATIONS)
    return secrets.compare_digest(digest.hex(), expected_hex)


def create_access_token(username: str) -> str:
    now = int(time.time())
    payload = {"sub": username, "iat": now, "exp": now + _JWT_TTL_SECONDS}
    return jwt.encode(payload, _JWT_SECRET, algorithm=_JWT_ALGORITHM)


def decode_access_token(token: str) -> Optional[str]:
    """Returns the username the token was issued for, or None if the token
    is missing, malformed, expired, or signed with a different secret."""
    try:
        payload = jwt.decode(token, _JWT_SECRET, algorithms=[_JWT_ALGORITHM])
    except jwt.PyJWTError:
        return None
    return payload.get("sub")
