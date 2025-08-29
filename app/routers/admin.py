from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from ..config import settings
from ..services.jira import JiraClient
from ..effective import load_effective_settings, debug_token_status
from ..db import SessionLocal
from ..utils.crypto import encrypt

router = APIRouter(prefix="/admin", tags=["admin"])

class UpdateConfig(BaseModel):
    jira_base_url: str | None = None
    jira_email: str | None = None
    jira_api_token: str | None = None
    default_window_days: int | None = None
    timezone: str | None = None
    business_hours_start: str | None = None
    business_hours_end: str | None = None
    business_days: str | None = None

@router.get("/config")
async def get_config():
    eff = load_effective_settings()
    return {
        "jira_base_url": eff["jira_base_url"],
        "jira_email": eff["jira_email"],
        "has_token": bool(eff["jira_api_token"]),
        "default_window_days": eff["default_window_days"],
        "timezone": eff["timezone"]
    }

@router.get("/debug")
async def get_debug():
    # No secrets returned
    status = debug_token_status()
    return {
        "env_token_present": status["env_present"],
        "db_token_present": status["db_present"],
        "token_source": status["source"]
    }

@router.put("/config")
async def put_config(body: UpdateConfig):
    sets = []
    params = {}
    if body.jira_base_url is not None:
        sets.append("jira_base_url=:base")
        params["base"] = body.jira_base_url
    if body.jira_email is not None:
        sets.append("jira_email=:email")
        params["email"] = body.jira_email
    if body.jira_api_token is not None:
        cipher = encrypt(settings.app_secret, body.jira_api_token) if body.jira_api_token else ""
        sets.append("jira_api_token_cipher=:cipher")
        params["cipher"] = cipher
    if body.default_window_days is not None:
        sets.append("default_window_days=:days")
        params["days"] = body.default_window_days
    if body.timezone is not None:
        sets.append("timezone=:tz")
        params["tz"] = body.timezone
    if body.business_hours_start is not None:
        sets.append("business_hours_start=:bhs")
        params["bhs"] = body.business_hours_start
    if body.business_hours_end is not None:
        sets.append("business_hours_end=:bhe")
        params["bhe"] = body.business_hours_end
    if body.business_days is not None:
        sets.append("business_days=:bd")
        params["bd"] = body.business_days

    if not sets:
        eff = load_effective_settings()
        return {"ok": True, "updated": 0, "has_token": bool(eff["jira_api_token"])}

    with SessionLocal() as db:
        params["id"] = 1
        sql = text(f"UPDATE settings SET {', '.join(sets)} WHERE id=:id")
        db.execute(sql, params)
        db.commit()

    eff = load_effective_settings()
    return {"ok": True, "updated": len(sets), "has_token": bool(eff["jira_api_token"])}

@router.post("/test-connection")
async def test_connection():
    eff = load_effective_settings()
    client = JiraClient(eff["jira_base_url"], eff["jira_email"], eff["jira_api_token"])
    ok = await client.test_connection()
    if not ok:
        raise HTTPException(400, "Failed to connect to Jira. Check credentials.")
    return {"ok": True}
