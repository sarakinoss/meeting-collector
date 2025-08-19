from __future__ import annotations
import os
import hashlib
import hmac
import base64

# Minimal password hashing (PBKDF2-HMAC-SHA256). For production consider passlib.
_ITER = 210_000
_SALT_BYTES = 16

def _pbkdf2(pw: str, salt: bytes) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", pw.encode("utf-8"), salt, _ITER)

def hash_password(password: str) -> str:
    salt = os.urandom(_SALT_BYTES)
    dk = _pbkdf2(password, salt)
    return f"pbkdf2$sha256${_ITER}${base64.b64encode(salt).decode()}${base64.b64encode(dk).decode()}"

def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, alg, iters, salt_b64, dk_b64 = stored.split("$")
        if scheme != "pbkdf2" or alg != "sha256":
            return False
        it = int(iters)
        salt = base64.b64decode(salt_b64)
        dk_stored = base64.b64decode(dk_b64)
        dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, it)
        return hmac.compare_digest(dk, dk_stored)
    except Exception:
        return False