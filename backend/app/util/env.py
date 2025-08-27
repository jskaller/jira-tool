import base64, hashlib, os
from ..core.config import get_settings

class AppEnv:
    @staticmethod
    def fernet_key() -> bytes:
        # Derive a 32-byte key from APP_SECRET using SHA256, then urlsafe_b64encode
        secret = get_settings().app_secret.encode()
        digest = hashlib.sha256(secret).digest()
        return base64.urlsafe_b64encode(digest)
