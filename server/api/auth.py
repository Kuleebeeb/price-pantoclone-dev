"""Accounts and sessions, on the standard library alone.

NO NEW DEPENDENCY, deliberately. Passwords go through hashlib.scrypt, which has
been in Python since 3.6 and is a memory-hard KDF - the property that makes a
stolen table expensive to crack. Tokens are signed with hmac.new(sha256) and
compared with compare_digest, which is constant-time.

The alternative was bcrypt plus PyJWT: two more packages to keep patched inside
an image that ships to a factory, for a login screen used by a handful of
people. tech-stack.md asks the same question of every library - "what problem
that has ALREADY HAPPENED does it solve?" - and here there is none.

WHAT THIS IS NOT. It is not a session store. A token carries who and until when,
signed; the server keeps no list of live tokens. So signing out is local, and a
stolen token is good until it expires. The lever that does exist is AUTH_SECRET:
change it and every token ever issued stops verifying at once.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from typing import Any

SCRYPT_N = 2**14
SCRYPT_R = 8
SCRYPT_P = 1
SALT_BYTES = 16
TOKEN_TTL_SECONDS = 12 * 60 * 60  # a working day, then sign in again


class AuthError(Exception):
    """Wrong credentials, expired token, tampered token - never says which."""


def secret() -> bytes:
    value = os.environ.get("AUTH_SECRET", "").strip()
    if len(value) < 16:
        raise RuntimeError("AUTH_SECRET chua dat, hoac ngan hon 16 ky tu")
    return value.encode("utf-8")


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


# ------------------------------------------------------------------ passwords


def hash_password(password: str) -> str:
    if len(password) < 8:
        raise ValueError("รหัสผ่านต้องยาวอย่างน้อย 8 ตัวอักษร / password must be at least 8 characters")
    salt = secrets.token_bytes(SALT_BYTES)
    derived = hashlib.scrypt(
        password.encode("utf-8"), salt=salt, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P, dklen=32
    )
    return "scrypt$" + str(SCRYPT_N) + "$" + str(SCRYPT_R) + "$" + str(SCRYPT_P) + "$" + _b64(salt) + "$" + _b64(derived)


def verify_password(password: str, stored: str | None) -> bool:
    # A row mirrored from PacOs has no local password at all.
    if not stored:
        return False
    try:
        scheme, n, r, p, salt_b64, hash_b64 = stored.split("$")
        if scheme != "scrypt":
            return False
        derived = hashlib.scrypt(
            password.encode("utf-8"),
            salt=_unb64(salt_b64),
            n=int(n),
            r=int(r),
            p=int(p),
            dklen=len(_unb64(hash_b64)),
        )
    except (ValueError, TypeError):
        return False
    # Constant time: a comparison that returns early leaks how much of the hash
    # was right, one byte at a time.
    return hmac.compare_digest(derived, _unb64(hash_b64))


# --------------------------------------------------------------------- tokens


def issue_token(user_id: int, email: str, ttl_seconds: int = TOKEN_TTL_SECONDS) -> dict[str, Any]:
    expires_at = int(time.time()) + ttl_seconds
    body = _b64(
        json.dumps(
            {"sub": user_id, "email": email, "exp": expires_at},
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    )
    signature = _b64(hmac.new(secret(), body.encode("ascii"), hashlib.sha256).digest())
    return {"token": body + "." + signature, "expires_at": expires_at}


def read_token(token: str) -> dict[str, Any]:
    try:
        body, signature = token.split(".", 1)
    except ValueError as exc:
        raise AuthError("token khong hop le") from exc

    expected = _b64(hmac.new(secret(), body.encode("ascii"), hashlib.sha256).digest())
    # Checked BEFORE the body is read: an unsigned body is not data, it is input
    # from whoever sent it.
    if not hmac.compare_digest(expected, signature):
        raise AuthError("token khong hop le")

    try:
        claims = json.loads(_unb64(body))
    except (ValueError, TypeError) as exc:
        raise AuthError("token khong hop le") from exc

    if int(claims.get("exp", 0)) < time.time():
        raise AuthError("token het han")
    return claims
