from fastapi import Depends, HTTPException, Request
from ..core.security import verify_session
from ..db.database import get_sessionmaker
from sqlalchemy import select
from ..db.models import User
from starlette import status

def _extract_token(request: Request) -> str | None:
    # 1) Cookie
    token = request.cookies.get("session")
    if token:
        return token
    # 2) Authorization: Bearer <token>
    auth = request.headers.get("Authorization")
    if auth and auth.lower().startswith("bearer "):
        return auth.split(None, 1)[1].strip()
    # 3) X-Session header
    hdr = request.headers.get("X-Session")
    if hdr:
        return hdr.strip()
    # 4) Query param (fallback for downloads)
    qs = request.query_params.get("x_session")
    if qs:
        return qs.strip()
    return None

async def current_user(request: Request):
    token = _extract_token(request)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    data = verify_session(token)
    if not data or 'uid' not in data:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session")
    uid = data['uid']
    Session = get_sessionmaker()
    async with Session() as session:
        res = await session.execute(select(User).where(User.id == uid))
        user = res.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
        return user

async def current_admin(user=Depends(current_user)):
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    return user
