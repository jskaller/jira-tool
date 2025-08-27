from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from ..schemas import LoginIn, UserOut
from ..db.database import get_sessionmaker
from ..db.models import User
from ..core.security import verify_password, hash_password, sign_session
from ..core.config import get_settings

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/login", response_model=UserOut)
async def login(payload: LoginIn, response: Response):
    Session = get_sessionmaker()
    async with Session() as session:
        res = await session.execute(select(User).where(User.email == payload.email))
        user = res.scalar_one_or_none()
        if not user or not verify_password(payload.password, user.password_hash):
            raise HTTPException(status_code=401, detail="Invalid credentials")
        token = sign_session({"uid": user.id})
        response.set_cookie("session", token, httponly=True, samesite="lax")
        return UserOut(id=user.id, email=user.email, name=user.name, role=user.role)

@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie("session")
    return {"ok": True}
