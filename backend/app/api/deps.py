from fastapi import Depends, HTTPException, Request
from ..core.security import verify_session
from ..db.database import get_sessionmaker
from sqlalchemy import select
from ..db.models import User
from starlette import status

async def current_user(request: Request):
    token = request.cookies.get("session")
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    data = verify_session(token)
    if not data or 'uid' not in data:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session")
    uid = data['uid']
    # Optional existence check
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
