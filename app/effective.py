from typing import Dict, Any
from sqlalchemy import text
from .db import SessionLocal
from .config import settings
from .utils.crypto import decrypt, encrypt

def ensure_settings_row() -> None:
    with SessionLocal() as db:
        row = db.execute(text("SELECT id FROM settings WHERE id = 1")).first()
        if not row:
            db.execute(
                text(
                    "INSERT INTO settings "
                    "(id, jira_base_url, jira_email, jira_api_token_cipher, default_window_days, "
                    " business_hours_start, business_hours_end, business_days, timezone) "
                    "VALUES (1, :base, :email, :cipher, :days, :bh_s, :bh_e, :b_days, :tz)"
                ),
                {
                    "base": settings.jira_base_url,
                    "email": settings.jira_email,
                    "cipher": encrypt(settings.app_secret, settings.jira_api_token) if settings.jira_api_token else "",
                    "days": settings.default_window_days,
                    "bh_s": settings.business_hours_start,
                    "bh_e": settings.business_hours_end,
                    "b_days": settings.business_days,
                    "tz": settings.timezone,
                }
            )
            db.commit()

def bootstrap_token_from_env_if_empty() -> None:
    # Store env token into DB only if DB token is empty
    env_token = settings.jira_api_token or ""
    if not env_token:
        return
    with SessionLocal() as db:
        row = db.execute(text("SELECT jira_api_token_cipher FROM settings WHERE id = 1")).first()
        if row:
            cipher = row[0] or ""
            if not cipher:
                enc = encrypt(settings.app_secret, env_token)
                db.execute(text("UPDATE settings SET jira_api_token_cipher=:c WHERE id=1"), {"c": enc})
                db.commit()

def load_effective_settings() -> Dict[str, Any]:
    # DB overrides .env; if DB empty, fall back to .env
    with SessionLocal() as db:
        row = db.execute(
            text("SELECT jira_base_url, jira_email, jira_api_token_cipher, default_window_days, "
                 "business_hours_start, business_hours_end, business_days, timezone "
                 "FROM settings WHERE id = 1")
        ).first()
        if row:
            db_token = decrypt(settings.app_secret, row[2] or "")
            return {
                "jira_base_url": row[0] or settings.jira_base_url,
                "jira_email": row[1] or settings.jira_email,
                "jira_api_token": db_token or settings.jira_api_token,
                "default_window_days": row[3] or settings.default_window_days,
                "business_hours_start": row[4] or settings.business_hours_start,
                "business_hours_end": row[5] or settings.business_hours_end,
                "business_days": row[6] or settings.business_days,
                "timezone": row[7] or settings.timezone,
            }
        return {
            "jira_base_url": settings.jira_base_url,
            "jira_email": settings.jira_email,
            "jira_api_token": settings.jira_api_token,
            "default_window_days": settings.default_window_days,
            "business_hours_start": settings.business_hours_start,
            "business_hours_end": settings.business_hours_end,
            "business_days": settings.business_days,
            "timezone": settings.timezone,
        }

def debug_token_status() -> Dict[str, Any]:
    # Report non-sensitive debug info about token presence in env vs DB
    with SessionLocal() as db:
        row = db.execute(text("SELECT jira_api_token_cipher FROM settings WHERE id = 1")).first()
        db_present = bool(row and (row[0] or "").strip())
    env_present = bool(settings.jira_api_token)
    source = "db" if db_present else ("env" if env_present else "none")
    return {"env_present": env_present, "db_present": db_present, "source": source}
