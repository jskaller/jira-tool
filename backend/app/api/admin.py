from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from ..schemas import SettingsIn, SettingsOut
from ..db.database import get_sessionmaker
from ..db.models import Settings
from ..util.crypto import encrypt, decrypt
from .deps import current_admin

router = APIRouter(prefix="/admin", tags=["admin"])

@router.get("/settings", response_model=SettingsOut)
async def get_settings_api(user=Depends(current_admin)):
    Session = get_sessionmaker()
    async with Session() as session:
        res = await session.execute(select(Settings).where(Settings.id == 1))
        s = res.scalar_one_or_none()
        if not s:
            return SettingsOut(has_token=False)
        return SettingsOut(
            jira_base_url=s.jira_base_url,
            jira_email=s.jira_email,
            has_token=bool(s.jira_token_encrypted),
            default_window_days=s.default_window_days,
            business_hours_start=s.business_hours_start,
            business_hours_end=s.business_hours_end,
            business_days=s.business_days,
            timezone=s.timezone,
        )

@router.put("/settings", response_model=SettingsOut)
async def put_settings_api(payload: SettingsIn, user=Depends(current_admin)):
    Session = get_sessionmaker()
    async with Session() as session:
        res = await session.execute(select(Settings).where(Settings.id == 1))
        s = res.scalar_one_or_none()
        if not s:
            from ..db.models import Settings as S
            s = S(id=1)
            session.add(s)
        s.jira_base_url = payload.jira_base_url
        s.jira_email = payload.jira_email
        if payload.jira_api_token:
            s.jira_token_encrypted = encrypt(payload.jira_api_token)
        s.default_window_days = payload.default_window_days
        s.business_hours_start = payload.business_hours_start
        s.business_hours_end = payload.business_hours_end
        s.business_days = payload.business_days
        s.timezone = payload.timezone
        await session.commit()
        return SettingsOut(
            jira_base_url=s.jira_base_url,
            jira_email=s.jira_email,
            has_token=bool(s.jira_token_encrypted),
            default_window_days=s.default_window_days,
            business_hours_start=s.business_hours_start,
            business_hours_end=s.business_hours_end,
            business_days=s.business_days,
            timezone=s.timezone,
        )
