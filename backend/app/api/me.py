from fastapi import APIRouter, Depends
from ..schemas import UserOut
from .deps import current_user

router = APIRouter(tags=["me"])

@router.get("/me", response_model=UserOut)
async def me(user=Depends(current_user)):
    return UserOut(id=user.id, email=user.email, name=user.name, role=user.role)
