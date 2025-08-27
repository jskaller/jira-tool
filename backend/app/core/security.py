from itsdangerous import URLSafeSerializer, BadSignature
from passlib.context import CryptContext
from typing import Optional
from .config import get_settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(password: str, hashed: str) -> bool:
    return pwd_context.verify(password, hashed)

def get_serializer() -> URLSafeSerializer:
    s = URLSafeSerializer(get_settings().app_secret, salt="session")
    return s

def sign_session(data: dict) -> str:
    s = get_serializer()
    return s.dumps(data)

def verify_session(token: str) -> Optional[dict]:
    s = get_serializer()
    try:
        return s.loads(token)
    except BadSignature:
        return None
