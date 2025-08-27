from cryptography.fernet import Fernet, InvalidToken
from .env import AppEnv

def get_fernet() -> Fernet:
    key = AppEnv.fernet_key()
    return Fernet(key)

def encrypt(text: str) -> str:
    return get_fernet().encrypt(text.encode()).decode()

def decrypt(token: str) -> str:
    return get_fernet().decrypt(token.encode()).decode()
