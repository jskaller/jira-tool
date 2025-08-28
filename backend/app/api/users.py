from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from ..db.database import get_sessionmaker
from ..db.models import User
from .deps import current_user, current_admin
from ..core.security import verify_password, hash_password
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List

router = APIRouter(prefix="/users", tags=["users"])

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

class AdminUpdateUserIn(BaseModel):
    email: Optional[EmailStr] = None
    name: Optional[str] = None
    role: Optional[str] = None
    password: Optional[str] = Field(default=None, min_length=8)

@router.post("/me/password")
async def change_my_password(payload: ChangePasswordIn, me=Depends(current_user)):
    Session = get_sessionmaker()
    async with Session() as session:
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

@router.patch("/admin/{user_id}", response_model=UserItem)
async def update_user(user_id: int, payload: AdminUpdateUserIn, admin=Depends(current_admin)):
    Session = get_sessionmaker()
    async with Session() as session:
        res = await session.execute(select(User).where(User.id == user_id))
        u = res.scalar_one_or_none()
        if not u:
            raise HTTPException(status_code=404, detail="User not found")

        if payload.role and u.role == "admin" and payload.role != "admin":
            res2 = await session.execute(select(func.count()).select_from(User).where(User.role=="admin"))
            admin_count = res2.scalar_one() or 0
            if admin_count <= 1:
                raise HTTPException(status_code=400, detail="Cannot demote the last admin")

        if payload.email is not None:
            u.email = str(payload.email).lower()
        if payload.name is not None:
            u.name = payload.name
        if payload.role is not None:
            u.role = payload.role
        if payload.password:
            u.password_hash = hash_password(payload.password)

        try:
            await session.commit()
        except IntegrityError:
            await session.rollback()
            raise HTTPException(status_code=400, detail="Email already exists")

        await session.refresh(u)
        return u

@router.delete("/admin/{user_id}")
async def delete_user(user_id: int, admin=Depends(current_admin)):
    if admin.id == user_id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")
    Session = get_sessionmaker()
    async with Session() as session:
        res = await session.execute(select(User).where(User.id == user_id))
        u = res.scalar_one_or_none()
        if not u:
            return {"ok": True}
        if u.role == "admin":
            res2 = await session.execute(select(func.count()).select_from(User).where(User.role=="admin"))
            admin_count = res2.scalar_one() or 0
            if admin_count <= 1:
                raise HTTPException(status_code=400, detail="Cannot delete the last admin")
        await session.delete(u)
        await session.commit()
        return {"ok": True}
