
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from sqlalchemy import text
from ..db.database import get_sessionmaker
from .deps import current_admin

router = APIRouter(prefix="/admin", tags=["admin"])

class SettingsPayload(BaseModel):
    jira_base_url: Optional[str] = None
    jira_email: Optional[str] = None
    jira_api_token: Optional[str] = None  # store in settings.jira_token_encrypted
    default_window_days: Optional[int] = None
    business_hours_start: Optional[str] = None
    business_hours_end: Optional[str] = None
    business_days: Optional[str] = None
    timezone: Optional[str] = None

async def _ensure_settings_table():
    Session = get_sessionmaker()
    async with Session() as session:
        await session.execute(text("""
        CREATE TABLE IF NOT EXISTS settings (
          id INTEGER PRIMARY KEY CHECK (id = 1),
          jira_base_url TEXT,
          jira_email TEXT,
          jira_token_encrypted TEXT,
          default_window_days INTEGER,
          business_hours_start TEXT,
          business_hours_end TEXT,
          business_days TEXT,
          timezone TEXT
        );
        """))
        row = (await session.execute(text("SELECT id FROM settings WHERE id = 1"))).first()
        if not row:
            await session.execute(text("INSERT INTO settings (id, default_window_days, business_hours_start, business_hours_end, business_days, timezone) VALUES (1, 180, '09:00', '17:00', 'Mon,Tue,Wed,Thu,Fri', 'America/New_York')"))
        await session.commit()

@router.get("/settings")
async def get_settings_route(_=Depends(current_admin)):
    await _ensure_settings_table()
    Session = get_sessionmaker()
    async with Session() as session:
        res = await session.execute(text("SELECT jira_base_url, jira_email, COALESCE(jira_token_encrypted,'') AS tok, default_window_days, business_hours_start, business_hours_end, business_days, timezone FROM settings WHERE id=1"))
        row = res.first()
        if not row:
            raise HTTPException(status_code=500, detail="Settings row missing")
        data = dict(row._mapping)
        tok = data.pop("tok", "")
        data["token_present"] = bool(tok)
        return data

@router.put("/settings")
async def put_settings_route(payload: SettingsPayload, _=Depends(current_admin)):
    await _ensure_settings_table()
    fields = []
    params = {}
    if payload.jira_base_url is not None:
        fields.append("jira_base_url = :jira_base_url"); params["jira_base_url"] = payload.jira_base_url.strip().rstrip("/")
    if payload.jira_email is not None:
        fields.append("jira_email = :jira_email"); params["jira_email"] = payload.jira_email.strip()
    if payload.default_window_days is not None:
        fields.append("default_window_days = :dwd"); params["dwd"] = int(payload.default_window_days)
    if payload.business_hours_start is not None:
        fields.append("business_hours_start = :bhs"); params["bhs"] = payload.business_hours_start
    if payload.business_hours_end is not None:
        fields.append("business_hours_end = :bhe"); params["bhe"] = payload.business_hours_end
    if payload.business_days is not None:
        fields.append("business_days = :bd"); params["bd"] = payload.business_days
    if payload.timezone is not None:
        fields.append("timezone = :tz"); params["tz"] = payload.timezone
    if payload.jira_api_token:
        fields.append("jira_token_encrypted = :tok"); params["tok"] = payload.jira_api_token.strip()

    if not fields:
        return {"ok": True, "updated": False}

    sql = "UPDATE settings SET " + ", ".join(fields) + " WHERE id = 1"
    Session = get_sessionmaker()
    async with Session() as session:
        await session.execute(text(sql), params)
        await session.commit()

    return {"ok": True, "updated": True}
