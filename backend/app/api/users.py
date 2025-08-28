from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from ..db.database import get_sessionmaker
from ..db.models import User
from .deps import current_user, current_admin
from ..core.security import verify_password, hash_password
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List

router = APIRouter(prefix="/users", tags=["users"])

# ------ Schemas (inline to keep patch minimal) ------
class ChangePasswordIn(BaseModel):
    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=8)

class UserItem(BaseModel):
    id: int
    email: EmailStr
    name: Optional[str] = None
    role: str
    class Config:
        from_attributes = True

class AdminCreateUserIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    name: Optional[str] = None
    role: str = "user"

# ------ Endpoints ------
@router.post("/me/password")
async def change_my_password(payload: ChangePasswordIn, me=Depends(current_user)):
    Session = get_sessionmaker()
    async with Session() as session:
        # fetch fresh
        res = await session.execute(select(User).where(User.id == me.id))
        user = res.scalar_one()
        if not verify_password(payload.current_password, user.password_hash):
            raise HTTPException(status_code=400, detail="Current password is incorrect")
        user.password_hash = hash_password(payload.new_password)
        await session.commit()
        return {"ok": True}

@router.get("/admin", response_model=List[UserItem])
async def list_users(_: User = Depends(current_admin)):
    Session = get_sessionmaker()
    async with Session() as session:
        res = await session.execute(select(User).order_by(User.id.asc()))
        rows = res.scalars().all()
        return rows

@router.post("/admin", response_model=UserItem)
async def create_user(payload: AdminCreateUserIn, _: User = Depends(current_admin)):
    Session = get_sessionmaker()
    async with Session() as session:
        u = User(email=str(payload.email).lower(), name=payload.name or "", role=payload.role, password_hash=hash_password(payload.password))
        session.add(u)
        try:
            await session.commit()
        except IntegrityError:
            await session.rollback()
            raise HTTPException(status_code=400, detail="Email already exists")
        await session.refresh(u)
        return u
