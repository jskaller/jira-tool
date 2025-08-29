import base64, hashlib
from cryptography.fernet import Fernet, InvalidToken

def _derive_key(secret: str) -> bytes:
    # Deterministic key from APP_SECRET
    digest = hashlib.sha256(secret.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)

def encrypt(secret: str, plaintext: str) -> str:
    if not plaintext:
        return ""
    f = Fernet(_derive_key(secret))
    return f.encrypt(plaintext.encode("utf-8")).decode("utf-8")

def decrypt(secret: str, token: str) -> str:
    if not token:
        return ""
    f = Fernet(_derive_key(secret))
    try:
        return f.decrypt(token.encode("utf-8")).decode("utf-8")
    except InvalidToken:
        return ""
