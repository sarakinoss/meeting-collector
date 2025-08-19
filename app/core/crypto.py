from __future__ import annotations
import base64, hashlib
from cryptography.fernet import Fernet, InvalidToken
from app.core.config import CRYPTO_SECRET

def _fernet() -> Fernet:
    key = hashlib.sha256(CRYPTO_SECRET.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(key))

def encrypt(plain: str | None) -> str | None:
    if not plain:
        return None
    return _fernet().encrypt(plain.encode("utf-8")).decode("utf-8")

def decrypt(token: str | None) -> str | None:
    if not token:
        return None
    try:
        return _fernet().decrypt(token.encode("utf-8")).decode("utf-8")
    except InvalidToken:
        return None