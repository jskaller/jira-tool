from fastapi import APIRouter, HTTPException, Response, Request
from pydantic import BaseModel
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from passlib.hash import bcrypt
from datetime import timedelta
from sqlalchemy import select
from ..db import SessionLocal
from ..models import User
from ..config import settings

router = APIRouter(prefix="/auth", tags=["auth"])

COOKIE_NAME = "session"
serializer = URLSafeTimedSerializer(settings.app_secret)

class LoginIn(BaseModel):
    email: str
    password: str

@router.get("/bootstrap")
async def bootstrap_info():
    """Non-sensitive info to help UI show the right bootstrap email."""
    with SessionLocal() as db:
        has_users = db.query(User).count() > 0
    return {
        "has_users": has_users,
        "bootstrap_email": settings.bootstrap_admin_email or "admin@example.com"
    }

@router.post("/bootstrap-sync")
async def bootstrap_sync():
    """Ensure a bootstrap admin exists matching .env (email+password). Useful if DB got out of sync."""
    if not settings.bootstrap_admin_email or not settings.bootstrap_admin_password:
        raise HTTPException(400, "Bootstrap email/password not set in .env")
    with SessionLocal() as db:
        user = db.execute(select(User).where(User.email == settings.bootstrap_admin_email)).scalars().first()
        if user:
            user.password_hash = bcrypt.hash(settings.bootstrap_admin_password)
            user.is_admin = True
        else:
            user = User(email=settings.bootstrap_admin_email, password_hash=bcrypt.hash(settings.bootstrap_admin_password), is_admin=True)
            db.add(user)
        db.commit()
    return {"ok": True, "email": settings.bootstrap_admin_email}

@router.post("/login")
async def login(body: LoginIn, response: Response):
    with SessionLocal() as db:
        user = db.execute(select(User).where(User.email == body.email)).scalars().first()
        if not user:
            # allow bootstrap creds exactly as in .env when user not found
            if (
                settings.bootstrap_admin_email
                and settings.bootstrap_admin_password
                and body.email == settings.bootstrap_admin_email
                and body.password == settings.bootstrap_admin_password
            ):
                user = User(email=body.email, password_hash=bcrypt.hash(body.password), is_admin=True)
                db.add(user)
                db.commit()
                db.refresh(user)
            else:
                raise HTTPException(401, "Invalid email or password")
        else:
            if not bcrypt.verify(body.password, user.password_hash):
                raise HTTPException(401, "Invalid email or password")

        token = serializer.dumps({"uid": user.id, "email": user.email})
        response.set_cookie(COOKIE_NAME, token, httponly=True, samesite="lax", max_age=int(timedelta(days=7).total_seconds()))
        return {"ok": True, "email": user.email, "is_admin": user.is_admin}

@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie(COOKIE_NAME)
    return {"ok": True}

@router.get("/me")
async def me(request: Request):
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return {"authenticated": False}
    try:
        data = serializer.loads(token, max_age=int(timedelta(days=7).total_seconds()))
    except (BadSignature, SignatureExpired):
        return {"authenticated": False}
    with SessionLocal() as db:
        user = db.get(User, data.get("uid"))
        if not user:
            return {"authenticated": False}
        return {"authenticated": True, "email": user.email, "is_admin": user.is_admin}
